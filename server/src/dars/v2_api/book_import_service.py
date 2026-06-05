"""
Core Book Import service (core-book-import F-1.4).

Ports the proven ETL from `scripts/import_ncp_english_g1.py` into an in-app,
background-runnable service generalised to any (curriculum, grade, subject)
cell — the script's hard-coded NCP/G1/Eng is replaced by the resolved cell
codes (D-2, D-6). Reads taleemabad-core (`fde_staging`, read-only) and upserts
the whole cell into Dars in a single transaction; reports progress into an
`import_runs` row as it goes (D-1); on any error rolls back the Dars writes and
marks the run failed (the failure write uses a fresh connection so it survives
the rollback — D-5).

Five steps: slos -> sub_slos -> book_chapters -> topics -> mappings.
Topics are 1-per-chapter with topic_text = flattened chapter prose (D-3).
The Schema breakdown prompt is vendored in this package (D-4).

This module makes LLM + DB calls; it is exercised by unit tests with mocks
(no live calls in CI). Real runs need core-DB env vars + ANTHROPIC_API_KEY on
the server.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from importlib import resources

import anthropic
import asyncpg

from dars.v2_api.lp_type_classifier import classify_lp_type

log = logging.getLogger(__name__)

# Deterministic UUID namespace — same value the seed + the original script use,
# so imports are idempotent and align with seeded rows (D-6).
SEED_NAMESPACE = uuid.UUID("00000000-0000-5da7-5000-000000000001")

BREAKDOWN_MODEL = "claude-opus-4-6"
BREAKDOWN_MAX_TOKENS = 32000
TOPIC_MAPPER_MODEL = "claude-opus-4-6"

# Strips a sub-SLO suffix to recover the parent SLO code. The breakdown prompt
# (rule 6) emits dot-notation (`A-01.1`) or, when unsplittable, the bare parent
# code (`A-01`); the original script also produced hyphen-letter codes
# (`A1-02-a`). `_derive_parent_code` handles all three by matching against the
# set of KNOWN parent codes (D-9 fix) — see _derive_parent_code below.
_SUB_SLO_SUFFIX_RE = re.compile(
    r"""^(?P<parent>.+?)        # parent prefix (non-greedy)
        (?:                     # one of the known sub-SLO suffixes:
            \.\d+               #   .1 .2 …            (prompt dot-notation)
          | -[a-z]+             #   -a -b … -aa        (hyphen-letter)
          | \(\d+\)             #   (1) (2) …          (occasional paren)
        )$""",
    re.VERBOSE,
)


def _derive_parent_code(code: str, known_parents: set[str]) -> str | None:
    """Map a sub-SLO code to its parent SLO code, robust to format (D-9).

    Strategy, most-trusted first:
      1. exact match — an unsplittable SLO keeps the parent code (`A-01`).
      2. strip a recognised suffix (`A-01.1`, `A1-02-a`, `A-01(1)`) → parent.
      3. longest known parent that is a prefix of the code (handles odd
         separators we didn't anticipate).
    Returns the parent code if it is a known parent, else None.
    """
    code = code.strip()
    if code in known_parents:
        return code
    m = _SUB_SLO_SUFFIX_RE.match(code)
    if m and m.group("parent") in known_parents:
        return m.group("parent")
    # Fallback: longest known parent code that prefixes this sub-code.
    candidates = [p for p in known_parents if code.startswith(p) and code != p]
    if candidates:
        return max(candidates, key=len)
    return None


def _sub_code_sort_key(code: str) -> tuple:
    """Order sub-SLO codes by their trailing index, numeric-aware.

    `A-01.2` < `A-01.10`; `-b` < `-aa`. Returns a (kind, value) tuple so a
    numeric suffix sorts before/independent of an alpha one; unknown shapes
    sort last but stably.
    """
    code = code.strip()
    m = re.search(r"(?:\.(\d+)|\((\d+)\)|-([a-z]+))$", code)
    if not m:
        return (2, 0, code)
    if m.group(1) is not None:
        return (0, int(m.group(1)), "")
    if m.group(2) is not None:
        return (0, int(m.group(2)), "")
    # alpha suffix: a, b, …, z, aa — base-26-ish, length-then-lex is fine
    suffix = m.group(3)
    return (1, len(suffix), suffix)

STEPS = ("slos", "sub_slos", "book_chapters", "topics", "mappings")


def seed_uuid(key: str) -> uuid.UUID:
    """Deterministic UUID v5 from SEED_NAMESPACE + key."""
    return uuid.uuid5(SEED_NAMESPACE, key)


def _load_breakdown_prompt() -> str:
    """Read the vendored Schema breakdown prompt from package data (D-4).

    English-only for now; non-English cells reuse this prompt (logged warning
    at the call site). Never reads a workstation path.
    """
    return (
        resources.files("dars.v2_api.prompts")
        .joinpath("slo_breakdown_english.txt")
        .read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# Pure helpers (ported)
# ---------------------------------------------------------------------------


def _parse_jsonb(value):
    """asyncpg returns JSONB as str; parse to Python or pass through."""
    if value is None or isinstance(value, (list, dict)):
        return value
    return json.loads(value)


def _format_slos_for_prompt(slo_code_to_info: dict[str, tuple[uuid.UUID, str]]) -> str:
    lines = []
    for code in sorted(slo_code_to_info.keys()):
        _uuid, statement = slo_code_to_info[code]
        lines.append(f"{code}: {statement}")
    return "\n".join(lines)


def _parse_breakdown_markdown(md: str) -> list[dict[str, str]]:
    """Parse the breakdown prompt's markdown table into rows."""
    headers = None
    rows: list[dict[str, str]] = []
    for line in md.strip().splitlines():
        line = line.strip()
        if re.match(r"^\|[\s\-:|]+\|$", line):
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if headers is None:
                headers = cells
            else:
                rows.append(dict(zip(headers, cells)))
    return rows


def _build_sub_slo_index(sub_slos_with_statements: list[dict]) -> str:
    lines = [f"- {s['code']}: {s['statement']}" for s in sub_slos_with_statements]
    return "\n".join(lines)


def _flatten_chapter_prose(chapter_text_slice: list[dict]) -> str:
    """Concatenate `text` fields from book_text page objects into one string."""
    if not chapter_text_slice:
        return ""
    parts = []
    for p in chapter_text_slice:
        if isinstance(p, dict):
            t = p.get("text") or ""
            if t:
                parts.append(t)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# LLM calls (sync; run via asyncio.to_thread). client injectable for tests.
#
# Every call logs uniformly so imports are debuggable from logs alone (rule 11):
#   INFO  before  — purpose, model, input size
#   INFO  after   — in/out tokens, cache reads, response chars
#   ERROR on fail — with exc_info=True
# ---------------------------------------------------------------------------


def _usage_str(response) -> str:
    """Compact token-usage summary for logs; tolerant of a missing usage block."""
    u = getattr(response, "usage", None)
    if u is None:
        return "usage=n/a"
    return (
        f"in={getattr(u, 'input_tokens', '?')} "
        f"out={getattr(u, 'output_tokens', '?')} "
        f"cache_read={getattr(u, 'cache_read_input_tokens', 0)}"
    )


def _run_breakdown_llm(
    slos_text: str,
    *,
    subject_label: str,
    grade_label: str,
    client: anthropic.Anthropic | None = None,
) -> str:
    if client is None:
        client = anthropic.Anthropic()
    system_prompt = _load_breakdown_prompt()
    user_message = (
        f"Subject: {subject_label}\n"
        f"Grade: {grade_label}\n\n"
        f"Here are the main SLOs:\n\n{slos_text}"
    )
    log.info(
        "LLM breakdown start: model=%s subject=%s grade=%s slos=%d system_chars=%d user_chars=%d",
        BREAKDOWN_MODEL, subject_label, grade_label,
        len(slos_text.splitlines()), len(system_prompt), len(user_message),
    )
    try:
        with client.messages.stream(
            model=BREAKDOWN_MODEL,
            max_tokens=BREAKDOWN_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            response = stream.get_final_message()
    except Exception:
        log.error("LLM breakdown FAILED: model=%s", BREAKDOWN_MODEL, exc_info=True)
        raise
    text = "".join(b.text for b in response.content if b.type == "text")
    stop = getattr(response, "stop_reason", None)
    if stop == "max_tokens":
        log.warning("LLM breakdown hit max_tokens (%d) — output may be truncated", BREAKDOWN_MAX_TOKENS)
    log.info("LLM breakdown done: %s stop=%s response_chars=%d", _usage_str(response), stop, len(text))
    return text


def _map_chapter_to_sub_slos(
    *,
    chapter_title: str,
    chapter_prose: str,
    sub_slo_index_text: str,
    valid_codes: set[str],
    client: anthropic.Anthropic | None = None,
) -> list[str]:
    if client is None:
        client = anthropic.Anthropic()
    system_prompt = (
        "You map a chapter's prose to the sub-SLOs (sub learning outcomes) it teaches.\n\n"
        "You will receive:\n"
        "1. A list of all available sub-SLOs (code + statement).\n"
        "2. A chapter title and its prose text.\n\n"
        "Return ONLY the sub-SLO codes that the chapter directly teaches, one per line, "
        "no other text. Be selective — only include codes whose statement clearly matches "
        "skills taught or practised in the chapter. If no sub-SLOs apply, return an empty response.\n\n"
        "Available sub-SLOs:\n\n"
        f"{sub_slo_index_text}"
    )
    truncated_prose = chapter_prose[:12000]
    user_message = (
        f"Chapter title: {chapter_title}\n\n"
        f"Chapter prose:\n{truncated_prose}\n\n"
        f"Return the matching sub-SLO codes, one per line."
    )
    log.info(
        "LLM chapter-map start: model=%s chapter=%r prose_chars=%d candidates=%d",
        TOPIC_MAPPER_MODEL, chapter_title, len(truncated_prose), len(valid_codes),
    )
    try:
        response = client.messages.create(
            model=TOPIC_MAPPER_MODEL,
            max_tokens=2000,
            system=[
                {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception:
        log.error("LLM chapter-map FAILED: chapter=%r", chapter_title, exc_info=True)
        raise
    raw_text = "".join(b.text for b in response.content if b.type == "text").strip()
    codes_out: list[str] = []
    dropped: list[str] = []
    for line in raw_text.splitlines():
        candidate = line.strip().lstrip("-").strip()
        if not candidate:
            continue
        if candidate in valid_codes:
            codes_out.append(candidate)
        else:
            dropped.append(candidate)
    log.info(
        "LLM chapter-map done: chapter=%r %s matched=%d dropped=%d%s",
        chapter_title, _usage_str(response), len(codes_out), len(dropped),
        f" (dropped: {dropped[:10]})" if dropped else "",
    )
    return codes_out


# ---------------------------------------------------------------------------
# Progress helpers — mutate the in-memory run dict and persist it.
# ---------------------------------------------------------------------------


class _Progress:
    """Accumulates step state / counts / warnings and flushes to import_runs."""

    def __init__(self, run_id: uuid.UUID):
        self.run_id = run_id
        self.steps: dict[str, dict] = {s: {"status": "pending"} for s in STEPS}
        self.counts: dict[str, int] = {}
        self.warnings: list[str] = []
        self.current_step: str | None = None
        self.dars_book_id: uuid.UUID | None = None

    async def start_step(self, conn: asyncpg.Connection, step: str) -> None:
        self.current_step = step
        self.steps[step] = {"status": "running"}
        await self._flush(conn, status="running")

    async def finish_step(self, conn: asyncpg.Connection, step: str, count: int) -> None:
        self.steps[step] = {"status": "done", "count": count}
        self.counts[step] = count
        await self._flush(conn, status="running")

    def warn(self, message: str) -> None:
        log.warning("import_run %s: %s", self.run_id, message)
        self.warnings.append(message)

    async def _flush(self, conn: asyncpg.Connection, *, status: str) -> None:
        await conn.execute(
            """
            UPDATE import_runs
               SET status = $2, current_step = $3, steps = $4::jsonb,
                   counts = $5::jsonb, warnings = $6::jsonb,
                   dars_book_id = COALESCE($7, dars_book_id), updated_at = now()
             WHERE id = $1
            """,
            self.run_id, status, self.current_step,
            json.dumps(self.steps), json.dumps(self.counts),
            json.dumps(self.warnings), self.dars_book_id,
        )


# ---------------------------------------------------------------------------
# Cell resolution
# ---------------------------------------------------------------------------


async def resolve_cell(
    dars_conn: asyncpg.Connection,
    fde_conn: asyncpg.Connection,
    *,
    core_book_id: int,
    curriculum_id: uuid.UUID | None,
) -> dict:
    """Resolve the (curriculum, grade, subject) cell + codes for a core book.

    Raises ValueError (→ 422 upstream) if the book is missing/ineligible or the
    core grade/subject don't map to Dars lookup rows. No G1/Eng assert (D-2).
    """
    book_row = await fde_conn.fetchrow(
        """
        SELECT b.id, b.status, b.is_active,
               g.short_code AS grade, s.short_code AS subject
        FROM fde_staging.book_library_book b
        LEFT JOIN fde_staging.slo_gradesubject gs ON b.grade_subject_id = gs.id
        LEFT JOIN fde_staging.slo_grade g ON gs.grade_id = g.id
        LEFT JOIN fde_staging.slo_subject s ON gs.subject_id = s.id
        WHERE b.id = $1
        """,
        core_book_id,
    )
    if book_row is None:
        raise ValueError(f"core book {core_book_id} not found")
    if book_row["status"] != "OnProd":
        raise ValueError(f"core book {core_book_id} status={book_row['status']!r}; expected OnProd")
    if not book_row["is_active"]:
        raise ValueError(f"core book {core_book_id} is_active=False")

    grade_code = book_row["grade"]
    subject_code = book_row["subject"]
    if not grade_code or not subject_code:
        raise ValueError(f"core book {core_book_id} has no grade/subject in core")

    # Resolve Dars grade/subject from the core short_codes.
    grade_id = await dars_conn.fetchval(
        "SELECT id FROM grades WHERE code = $1", _grade_code_to_int(grade_code)
    )
    if grade_id is None:
        raise ValueError(f"no Dars grade for core grade {grade_code!r}")
    subject_id = await dars_conn.fetchval(
        "SELECT id FROM subjects WHERE code = $1", subject_code
    )
    if subject_id is None:
        raise ValueError(f"no Dars subject for core subject {subject_code!r}")

    # Curriculum: requested, else the active Dars curriculum.
    if curriculum_id is None:
        cur_row = await dars_conn.fetchrow(
            "SELECT id, code FROM curriculums WHERE is_active = TRUE ORDER BY code LIMIT 1"
        )
        if cur_row is None:
            raise ValueError("no active Dars curriculum to import into")
        curriculum_id = cur_row["id"]
        curriculum_code = cur_row["code"]
    else:
        curriculum_code = await dars_conn.fetchval(
            "SELECT code FROM curriculums WHERE id = $1", curriculum_id
        )
        if curriculum_code is None:
            raise ValueError(f"curriculum {curriculum_id} not found")

    return {
        "curriculum_id": curriculum_id,
        "curriculum_code": curriculum_code,
        "grade_id": grade_id,
        "grade_code": grade_code,
        "subject_id": subject_id,
        "subject_code": subject_code,
    }


def _grade_code_to_int(short_code: str) -> int:
    """Core grade short_code 'G1' -> Dars grades.code 1."""
    digits = re.sub(r"\D", "", short_code or "")
    if not digits:
        raise ValueError(f"cannot parse grade short_code {short_code!r}")
    return int(digits)


def _cell_key(cell: dict) -> str:
    return f"{cell['curriculum_code']}:{cell['grade_code']}:{cell['subject_code']}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def run_import(
    *,
    run_id: uuid.UUID,
    core_book_id: int,
    curriculum_id: uuid.UUID | None,
    core_dsn: str,
    dars_dsn: str,
    anthropic_client: anthropic.Anthropic | None = None,
) -> None:
    """Run the full import as a background job. Updates the import_runs row.

    Opens its own core (read-only) + Dars (rw) connections (D-5). Dars writes in
    one transaction; on error, roll back then mark failed via a fresh connection.
    """
    log.info("run_import start run_id=%s core_book_id=%s", run_id, core_book_id)
    prog = _Progress(run_id)
    fde_conn: asyncpg.Connection | None = None
    dars_conn: asyncpg.Connection | None = None
    try:
        fde_conn = await asyncpg.connect(core_dsn)
        await fde_conn.execute("SET search_path TO fde_staging, public")
        dars_conn = await asyncpg.connect(dars_dsn)

        cell = await resolve_cell(
            dars_conn, fde_conn, core_book_id=core_book_id, curriculum_id=curriculum_id
        )
        if cell["subject_code"] != "Eng":
            prog.warn(
                f"subject is {cell['subject_code']!r}; breakdown prompt is English-only — "
                "results may be poor (D-4)."
            )

        async with dars_conn.transaction():
            await _import_cell(
                fde_conn=fde_conn,
                dars_conn=dars_conn,
                core_book_id=core_book_id,
                cell=cell,
                prog=prog,
                client=anthropic_client,
            )

        # Success — finalise outside the (now-committed) tx.
        await dars_conn.execute(
            """
            UPDATE import_runs
               SET status = 'succeeded', current_step = NULL, updated_at = now()
             WHERE id = $1
            """,
            run_id,
        )
        log.info("run_import done run_id=%s counts=%s", run_id, prog.counts)
    except Exception as exc:  # noqa: BLE001 — must capture to mark the run failed
        log.error("run_import failed run_id=%s: %s", run_id, exc, exc_info=True)
        await _mark_failed(dars_dsn, run_id, str(exc))
    finally:
        if fde_conn is not None:
            await fde_conn.close()
        if dars_conn is not None:
            await dars_conn.close()


async def _mark_failed(dars_dsn: str, run_id: uuid.UUID, error: str) -> None:
    """Persist failure on a FRESH connection so it survives the rolled-back tx."""
    conn = None
    try:
        conn = await asyncpg.connect(dars_dsn)
        await conn.execute(
            "UPDATE import_runs SET status='failed', error=$2, updated_at=now() WHERE id=$1",
            run_id, error,
        )
    except Exception:  # noqa: BLE001
        log.error("could not persist failure for run_id=%s", run_id, exc_info=True)
    finally:
        if conn is not None:
            await conn.close()


# ---------------------------------------------------------------------------
# The five steps (run inside the Dars transaction)
# ---------------------------------------------------------------------------


async def _import_cell(
    *,
    fde_conn: asyncpg.Connection,
    dars_conn: asyncpg.Connection,
    core_book_id: int,
    cell: dict,
    prog: _Progress,
    client: anthropic.Anthropic | None,
) -> None:
    ck = _cell_key(cell)
    cur_id, grade_id, subj_id = cell["curriculum_id"], cell["grade_id"], cell["subject_id"]

    # Ensure the curriculum row exists (it must, since we resolved its code).
    # --- Step 1: SLOs -------------------------------------------------------
    await prog.start_step(dars_conn, "slos")
    slo_rows = await fde_conn.fetch(
        """
        SELECT n.ncp_slo_id, n.slo_statement
        FROM fde_staging.slo_ncpslo n
        JOIN fde_staging.slo_gradesubject gs ON n.grade_subject_id = gs.id
        JOIN fde_staging.slo_grade g ON gs.grade_id = g.id
        JOIN fde_staging.slo_subject s ON gs.subject_id = s.id
        WHERE g.short_code = $1 AND s.short_code = $2 AND n.is_active = TRUE
        ORDER BY n.ncp_slo_id
        """,
        cell["grade_code"], cell["subject_code"],
    )
    slo_code_to_info: dict[str, tuple[uuid.UUID, str]] = {}
    for position, row in enumerate(slo_rows, start=1):
        code, statement = row["ncp_slo_id"], row["slo_statement"]
        slo_uuid = seed_uuid(f"slo:{ck}:{code}")
        await dars_conn.execute(
            """
            INSERT INTO slos (id, curriculum_id, grade_id, subject_id, code, statement, position)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (curriculum_id, grade_id, subject_id, code) DO UPDATE
              SET statement = EXCLUDED.statement, position = EXCLUDED.position, updated_at = now()
            """,
            slo_uuid, cur_id, grade_id, subj_id, code, statement, position,
        )
        actual_id = await dars_conn.fetchval(
            "SELECT id FROM slos WHERE curriculum_id=$1 AND grade_id=$2 AND subject_id=$3 AND code=$4",
            cur_id, grade_id, subj_id, code,
        )
        slo_code_to_info[code] = (actual_id, statement)
    await prog.finish_step(dars_conn, "slos", len(slo_code_to_info))

    # --- Step 2: sub-SLOs (LLM breakdown + lp_type) -------------------------
    await prog.start_step(dars_conn, "sub_slos")
    sub_code_to_uuid: dict[str, uuid.UUID] = {}
    if slo_code_to_info:
        slos_text = _format_slos_for_prompt(slo_code_to_info)
        raw_md = await asyncio.to_thread(
            _run_breakdown_llm, slos_text,
            subject_label=cell["subject_code"], grade_label=f"Grade {cell['grade_code']}",
            client=client,
        )
        rows = _parse_breakdown_markdown(raw_md)
        log.info("sub_slos: breakdown parsed %d markdown rows", len(rows))
        known_parents = set(slo_code_to_info.keys())
        parsed: list[dict[str, str]] = []
        skipped = 0
        for row in rows:
            code = (row.get("Sub SLO Code") or "").strip()
            statement = (row.get("Sub SLOs") or "").strip()
            if not code or not statement:
                continue
            parent_code = _derive_parent_code(code, known_parents)
            if parent_code is None:
                skipped += 1
                continue
            parsed.append({"code": code, "statement": statement, "parent_slo_code": parent_code})
        if skipped:
            prog.warn(f"{skipped} sub-SLO row(s) had no recognisable parent SLO code — skipped")
        if rows and not parsed:
            prog.warn(
                "breakdown returned rows but none mapped to a known parent SLO — "
                "check the breakdown output format against the SLO codes"
            )
        # Classify lp_type per sub-SLO (per-call logging is DEBUG in the
        # classifier; log a summary + any failure here at INFO/ERROR).
        log.info("sub_slos: classifying lp_type for %d sub-SLOs", len(parsed))
        for i, rec in enumerate(parsed):
            _puuid, parent_stmt = slo_code_to_info[rec["parent_slo_code"]]
            try:
                rec["lp_type"] = await asyncio.to_thread(
                    classify_lp_type,
                    parent_slo_statement=parent_stmt,
                    sub_slo_statement=rec["statement"],
                    client=client,
                )
            except Exception:
                log.error(
                    "lp_type classification FAILED for sub-SLO %s (%d/%d)",
                    rec["code"], i + 1, len(parsed), exc_info=True,
                )
                raise
        if parsed:
            from collections import Counter
            dist = Counter(r["lp_type"] for r in parsed)
            log.info("sub_slos: lp_type distribution %s", dict(dist))
        # Upsert, position within parent. Preserve breakdown order, but break
        # ties by the numeric/alpha suffix so `.2` precedes `.10` (and `-b`
        # precedes `-aa`) regardless of code format (D-9).
        by_parent: dict[str, list[dict]] = {}
        for idx, rec in enumerate(parsed):
            rec["_order"] = idx
            by_parent.setdefault(rec["parent_slo_code"], []).append(rec)
        for parent_code, subs in by_parent.items():
            parent_uuid, _ = slo_code_to_info[parent_code]
            subs.sort(key=lambda r: (_sub_code_sort_key(r["code"]), r["_order"]))
            for position, rec in enumerate(subs, start=1):
                sub_uuid = seed_uuid(f"sub_slo:{ck}:{rec['code']}")
                await dars_conn.execute(
                    """
                    INSERT INTO sub_slos
                        (id, slo_id, code, statement, position, source, recommended_lp_type)
                    VALUES ($1, $2, $3, $4, $5, 'schema_breakdown', $6)
                    ON CONFLICT (slo_id, code) DO UPDATE
                      SET statement = EXCLUDED.statement, position = EXCLUDED.position,
                          source = EXCLUDED.source, recommended_lp_type = EXCLUDED.recommended_lp_type,
                          updated_at = now()
                    """,
                    sub_uuid, parent_uuid, rec["code"], rec["statement"], position, rec["lp_type"],
                )
                actual_id = await dars_conn.fetchval(
                    "SELECT id FROM sub_slos WHERE slo_id=$1 AND code=$2", parent_uuid, rec["code"],
                )
                sub_code_to_uuid[rec["code"]] = actual_id
    await prog.finish_step(dars_conn, "sub_slos", len(sub_code_to_uuid))

    # --- Step 3: book + chapters -------------------------------------------
    await prog.start_step(dars_conn, "book_chapters")
    book_uuid, chapters = await _import_book_and_chapters(
        fde_conn=fde_conn, dars_conn=dars_conn, core_book_id=core_book_id,
        cell=cell, prog=prog,
    )
    prog.dars_book_id = book_uuid
    await prog.finish_step(dars_conn, "book_chapters", len(chapters))

    # --- Step 4 + 5: topics + mappings -------------------------------------
    await prog.start_step(dars_conn, "topics")
    topic_count, mapping_count, bcs_count = await _import_topics_and_mappings(
        dars_conn=dars_conn, chapters=chapters, cell=cell,
        sub_code_to_uuid=sub_code_to_uuid, prog=prog, client=client,
    )
    await prog.finish_step(dars_conn, "topics", topic_count)
    prog.steps["mappings"] = {
        "status": "done", "topic_sub_slos": mapping_count, "book_chapter_slos": bcs_count,
    }
    prog.counts["topic_sub_slos"] = mapping_count
    prog.counts["book_chapter_slos"] = bcs_count
    await prog._flush(dars_conn, status="running")


async def _import_book_and_chapters(
    *,
    fde_conn: asyncpg.Connection,
    dars_conn: asyncpg.Connection,
    core_book_id: int,
    cell: dict,
    prog: _Progress,
) -> tuple[uuid.UUID, list[dict]]:
    ck = _cell_key(cell)
    book_row = await fde_conn.fetchrow(
        """
        SELECT b.id, b.title, b.publisher, b.edition, b.published_year,
               b.total_chapters, b.pdf_url, b.book_text
        FROM fde_staging.book_library_book b
        WHERE b.id = $1
        """,
        core_book_id,
    )
    book_text_parsed = _parse_jsonb(book_row["book_text"]) or []
    book_uuid = seed_uuid(f"book:{ck}:{core_book_id}")
    await dars_conn.execute(
        """
        INSERT INTO books
            (id, curriculum_id, grade_id, subject_id, title, publisher, edition,
             published_year, total_chapters, pdf_url, book_text)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
        ON CONFLICT (id) DO UPDATE
          SET title = EXCLUDED.title, publisher = EXCLUDED.publisher,
              edition = EXCLUDED.edition, published_year = EXCLUDED.published_year,
              total_chapters = EXCLUDED.total_chapters, pdf_url = EXCLUDED.pdf_url,
              book_text = EXCLUDED.book_text, updated_at = now()
        """,
        book_uuid, cell["curriculum_id"], cell["grade_id"], cell["subject_id"],
        book_row["title"], book_row["publisher"], book_row["edition"],
        book_row["published_year"], book_row["total_chapters"], book_row["pdf_url"],
        json.dumps(book_text_parsed),
    )

    chapter_rows = await fde_conn.fetch(
        """
        SELECT bc.chapter_number, bc.title, bc.start_page, bc.end_page,
               bc.status, bc.is_active
        FROM fde_staging.book_library_bookchapter bc
        WHERE bc.book_id = $1 AND bc.deleted_at IS NULL
        ORDER BY bc.chapter_number
        """,
        core_book_id,
    )
    chapters_out: list[dict] = []
    for ch in chapter_rows:
        start_page, end_page = ch["start_page"], ch["end_page"]
        if start_page is None or end_page is None:
            prog.warn(
                f"chapter {ch['chapter_number']} ({ch['title']!r}) has no page range; "
                "prose slice empty"
            )
            chapter_text_slice: list[dict] = []
        else:
            chapter_text_slice = [
                p for p in book_text_parsed
                if isinstance(p, dict) and isinstance(p.get("pdf_page_no"), int)
                and start_page <= p["pdf_page_no"] <= end_page
            ]
        status = "published" if (ch["status"] == "OnProd" and ch["is_active"]) else "draft"
        chapter_uuid = seed_uuid(f"book_chapter:{ck}:{core_book_id}:{ch['chapter_number']}")
        await dars_conn.execute(
            """
            INSERT INTO book_chapters
                (id, book_id, chapter_number, title, start_page, end_page, chapter_text, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
            ON CONFLICT (book_id, chapter_number) DO UPDATE
              SET title = EXCLUDED.title, start_page = EXCLUDED.start_page,
                  end_page = EXCLUDED.end_page, chapter_text = EXCLUDED.chapter_text,
                  status = EXCLUDED.status, updated_at = now()
            """,
            chapter_uuid, book_uuid, ch["chapter_number"], ch["title"],
            start_page, end_page, json.dumps(chapter_text_slice), status,
        )
        actual_id = await dars_conn.fetchval(
            "SELECT id FROM book_chapters WHERE book_id=$1 AND chapter_number=$2",
            book_uuid, ch["chapter_number"],
        )
        chapters_out.append({
            "id": actual_id, "chapter_number": ch["chapter_number"],
            "title": ch["title"], "chapter_text": chapter_text_slice,
        })
    return book_uuid, chapters_out


async def _import_topics_and_mappings(
    *,
    dars_conn: asyncpg.Connection,
    chapters: list[dict],
    cell: dict,
    sub_code_to_uuid: dict[str, uuid.UUID],
    prog: _Progress,
    client: anthropic.Anthropic | None,
) -> tuple[int, int, int]:
    ck = _cell_key(cell)
    # Sub-SLO index for the mapper's cached system prompt.
    sub_slo_rows = await dars_conn.fetch(
        """
        SELECT ss.code, ss.statement
        FROM sub_slos ss JOIN slos s ON s.id = ss.slo_id
        WHERE s.curriculum_id = $1 AND ss.code = ANY($2::text[])
        ORDER BY ss.code
        """,
        cell["curriculum_id"], list(sub_code_to_uuid.keys()),
    )
    sub_slo_index_text = _build_sub_slo_index(
        [{"code": r["code"], "statement": r["statement"]} for r in sub_slo_rows]
    )
    valid_codes = set(sub_code_to_uuid.keys())

    topic_count = 0
    total_topic_sub_slos = 0
    bcs_seen: set[tuple[uuid.UUID, uuid.UUID]] = set()

    for chapter in chapters:
        prose = _flatten_chapter_prose(chapter.get("chapter_text") or [])
        topic_uuid = seed_uuid(f"topic:{ck}:ch{chapter['chapter_number']}:1")
        await dars_conn.execute(
            """
            INSERT INTO topics (id, book_chapter_id, topic_number, title, topic_text, status)
            VALUES ($1, $2, 1, $3, $4, 'published')
            ON CONFLICT (book_chapter_id, topic_number) DO UPDATE
              SET title = EXCLUDED.title, topic_text = EXCLUDED.topic_text,
                  status = EXCLUDED.status, updated_at = now()
            """,
            topic_uuid, chapter["id"], chapter["title"], prose[:50000],
        )
        actual_topic_id = await dars_conn.fetchval(
            "SELECT id FROM topics WHERE book_chapter_id=$1 AND topic_number=1", chapter["id"],
        )
        topic_count += 1

        if not prose.strip() or not valid_codes:
            if not prose.strip():
                prog.warn(f"chapter {chapter['chapter_number']} has no prose; skipped mapping")
            continue

        codes = await asyncio.to_thread(
            _map_chapter_to_sub_slos,
            chapter_title=chapter["title"], chapter_prose=prose,
            sub_slo_index_text=sub_slo_index_text, valid_codes=valid_codes,
            client=client,
        )
        for code in codes:
            sub_slo_uuid = sub_code_to_uuid[code]
            await dars_conn.execute(
                "INSERT INTO topic_sub_slos (topic_id, sub_slo_id) VALUES ($1, $2) "
                "ON CONFLICT (topic_id, sub_slo_id) DO NOTHING",
                actual_topic_id, sub_slo_uuid,
            )
            total_topic_sub_slos += 1
            parent_slo_id = await dars_conn.fetchval(
                "SELECT slo_id FROM sub_slos WHERE id = $1", sub_slo_uuid,
            )
            key = (chapter["id"], parent_slo_id)
            if key not in bcs_seen:
                await dars_conn.execute(
                    "INSERT INTO book_chapter_slos (book_chapter_id, slo_id) VALUES ($1, $2) "
                    "ON CONFLICT (book_chapter_id, slo_id) DO NOTHING",
                    chapter["id"], parent_slo_id,
                )
                bcs_seen.add(key)

    return topic_count, total_topic_sub_slos, len(bcs_seen)
