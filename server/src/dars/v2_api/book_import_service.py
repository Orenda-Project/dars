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
Topics are produced by the Schema topic-breakdown prompt: each chapter is split
into MULTIPLE focused topics (one per explicit topic heading), each with its own
short topic_text sliced from the chapter prose by line range. If the breakdown
yields no topics, a single fallback topic (whole-chapter prose) is written and a
warning is recorded. The Schema breakdown + topic-breakdown prompts are both
vendored in this package (D-4).

This module makes LLM + DB calls; it is exercised by unit tests with mocks
(no live calls in CI). Real runs need core-DB env vars + ANTHROPIC_API_KEY on
the server.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import uuid
from importlib import resources

import anthropic
import asyncpg

from dars.v2_api.lp_type_classifier import (
    SYSTEM_PROMPT as LP_TYPE_SYSTEM_PROMPT,
    VALID_LP_TYPES,
    classify_lp_type,
)

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

# Schema identifier guard (mirror of the router's; defends the search_path
# interpolation in the background task).
_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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


def _load_topic_breakdown_prompt() -> str:
    """Read the vendored Schema topic-breakdown prompt from package data (D-4).

    Identical to Schema's `topic_breakdown_prompt.txt`. Loaded verbatim and used
    as the system prompt — splits a chapter into topic sections by line number.
    Vendored in this package (`dars.v2_api.prompts`) so the import service does
    not depend on the `dars.breakdown` package (which has no resource __init__).
    """
    return (
        resources.files("dars.v2_api.prompts")
        .joinpath("topic_breakdown_prompt.txt")
        .read_text(encoding="utf-8")
    )


# Cap on a single topic's stored text (matches the column / write loop).
_TOPIC_TEXT_CAP = 50000


# ---------------------------------------------------------------------------
# Pure helpers (ported)
# ---------------------------------------------------------------------------


def _add_line_numbers(text: str) -> str:
    """Prefix each line with ``Line: N - `` (1-indexed). Ported from Schema."""
    lines = text.split("\n")
    return "\n".join(f"Line: {i + 1} - {line}" for i, line in enumerate(lines))


def _clean_topic_title(title: str) -> str:
    """Strip a leading ``Topic 1:`` style prefix — keep text after first colon."""
    if not title or ":" not in title:
        return (title or "").strip()
    return title.split(":", 1)[1].strip()


def _extract_topic_text(chapter_text: str, start_line: int, end_line: int) -> str:
    """Slice 1-indexed lines [start_line, end_line) from chapter_text."""
    lines = chapter_text.split("\n")
    start_idx = max(0, start_line - 1)
    end_idx = min(len(lines), end_line)
    return "\n".join(lines[start_idx:end_idx]).strip()


def _split_chapter_into_topics(parsed_json: dict, chapter_prose: str) -> list[dict]:
    """Slice a chapter's prose into topics from the breakdown JSON line numbers.

    Given parsed ``{topic_sections: [{section_title, starting_line_number}],
    exercise: {starting_line_number}}``, each topic runs from its start line to
    the NEXT topic's start (or, for the last topic, to the exercise start or the
    chapter end). Returns dicts with title / topic_text / start_line / end_line.
    Ported from Schema's `format_topic_for_extraction` (no page-number math).
    """
    if not isinstance(parsed_json, dict) or "topic_sections" not in parsed_json:
        return []

    topic_sections = parsed_json.get("topic_sections") or []
    final_exercise = parsed_json.get("exercise") or {}
    total_lines = len(chapter_prose.split("\n"))

    def _as_int(value, default):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    exercise_start = None
    if final_exercise and final_exercise.get("starting_line_number") is not None:
        exercise_start = _as_int(final_exercise.get("starting_line_number"), None)

    topics: list[dict] = []
    for idx, section in enumerate(topic_sections):
        title = _clean_topic_title(section.get("section_title", "") or "Topic")
        start_line = _as_int(section.get("starting_line_number", 1), 1)
        if idx + 1 < len(topic_sections):
            end_line = _as_int(
                topic_sections[idx + 1].get("starting_line_number", total_lines),
                total_lines,
            )
        else:
            end_line = exercise_start if exercise_start else total_lines
        topic_text = _extract_topic_text(chapter_prose, start_line, end_line)
        topics.append({
            "title": title or "Topic",
            "topic_text": topic_text,
            "start_line": start_line,
            "end_line": end_line,
        })
    return topics


def _extract_json_from_response(response: str) -> dict:
    """Robust JSON extraction from an LLM response (ported from Schema).

    Tries, in order: a ```json``` code block, a non-greedy brace match, then a
    greedy brace match. Returns {} if nothing parses.
    """
    if not response or not isinstance(response, str):
        return {}
    code_block = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", response)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            log.debug("topic-breakdown JSON: code-block parse failed")
    non_greedy = re.search(r"\{(?:[^{}]|(?:\{[^{}]*\}))*?\}", response)
    if non_greedy:
        try:
            return json.loads(non_greedy.group())
        except json.JSONDecodeError:
            log.debug("topic-breakdown JSON: non-greedy parse failed")
    greedy = re.search(r"\{[\s\S]*\}", response)
    if greedy:
        try:
            return json.loads(greedy.group())
        except json.JSONDecodeError:
            log.debug("topic-breakdown JSON: greedy parse failed")
    return {}


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


def _llm_backend() -> str:
    """Which LLM backend to use: 'agent_sdk' (local dev, Claude Code OAuth, no
    API key) or 'anthropic' (default — the Anthropic API client).

    Set DARS_LLM_BACKEND=agent_sdk for local development. See
    docs/features/core-book-import/01-decision-log.md D-15.
    """
    return os.environ.get("DARS_LLM_BACKEND", "anthropic").strip().lower()


async def _complete(system: str, user: str, *, label: str, client=None) -> str:
    """One text completion (system, user) -> text, backend-agnostic.

    - agent_sdk: claude-agent-sdk over the dev's Claude Code session (no key).
    - anthropic: the Anthropic API client (prod), run off the event loop.
    Logs entry + exit + errors uniformly (rule 11). `client` is an injectable
    Anthropic client for tests (ignored by the agent_sdk path).
    """
    backend = _llm_backend()
    log.info(
        "LLM %s start: backend=%s system_chars=%d user_chars=%d",
        label, backend, len(system), len(user),
    )
    try:
        if backend == "agent_sdk":
            out = await _complete_agent_sdk(system, user)
        else:
            out = await asyncio.to_thread(_complete_anthropic, system, user, client)
    except Exception:
        log.error("LLM %s FAILED: backend=%s", label, backend, exc_info=True)
        raise
    log.info("LLM %s done: backend=%s response_chars=%d", label, backend, len(out))
    if not out.strip():
        raise RuntimeError(f"LLM {label} returned an empty response (backend={backend})")
    return out


async def _complete_agent_sdk(system: str, user: str) -> str:
    """Dev backend: claude-agent-sdk over the Claude Code OAuth session (D-15).

    Mirrors chapter-planner-app/planner_llm.py: assistant text lives in
    message.content[].text blocks; options must be a ClaudeAgentOptions object.
    """
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "DARS_LLM_BACKEND=agent_sdk but claude-agent-sdk is not installed "
            "(`uv sync --extra dev`)"
        ) from exc
    chunks: list[str] = []
    async for message in query(prompt=user, options=ClaudeAgentOptions(system_prompt=system)):
        for block in getattr(message, "content", None) or []:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)


def _complete_anthropic(system: str, user: str, client) -> str:
    """Prod backend: Anthropic API. Streamed (large max_tokens) for headroom."""
    if client is None:
        client = anthropic.Anthropic()
    with client.messages.stream(
        model=BREAKDOWN_MODEL,
        max_tokens=BREAKDOWN_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        response = stream.get_final_message()
    stop = getattr(response, "stop_reason", None)
    if stop == "max_tokens":
        log.warning("LLM hit max_tokens (%d) — output may be truncated", BREAKDOWN_MAX_TOKENS)
    return "".join(b.text for b in response.content if b.type == "text")


async def _classify_lp_type(
    *, parent_slo_statement: str, sub_slo_statement: str, client=None
) -> str:
    """lp_type for one sub-SLO, backend-aware.

    On the agent_sdk dev backend, route through `_complete` with the classifier's
    system prompt and parse the single enum word; otherwise delegate to the
    Anthropic-based `classify_lp_type` (cached system block + retry) off-thread.
    """
    if _llm_backend() == "agent_sdk":
        user = (
            f"Parent SLO: {parent_slo_statement.strip()}\n"
            f"Sub-SLO: {sub_slo_statement.strip()}\n"
            f"Return only the enum value."
        )
        raw = await _complete(LP_TYPE_SYSTEM_PROMPT, user, label="lp_type")
        candidate = raw.strip().lower().split()[0].strip(".,'\"") if raw.strip() else ""
        if candidate not in VALID_LP_TYPES:
            raise ValueError(f"agent_sdk lp_type out of enum: {candidate!r}")
        return candidate
    return await asyncio.to_thread(
        classify_lp_type,
        parent_slo_statement=parent_slo_statement,
        sub_slo_statement=sub_slo_statement,
        client=client,
    )


async def _run_breakdown_llm(
    slos_text: str,
    *,
    subject_label: str,
    grade_label: str,
    client: anthropic.Anthropic | None = None,
) -> str:
    system_prompt = _load_breakdown_prompt()
    user_message = (
        f"Subject: {subject_label}\n"
        f"Grade: {grade_label}\n\n"
        f"Here are the main SLOs:\n\n{slos_text}"
    )
    return await _complete(system_prompt, user_message, label="breakdown", client=client)


async def _map_chapter_to_sub_slos(
    *,
    chapter_title: str,
    chapter_prose: str,
    sub_slo_index_text: str,
    valid_codes: set[str],
    client: anthropic.Anthropic | None = None,
) -> list[str]:
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
    raw_text = (await _complete(
        system_prompt, user_message, label=f"chapter-map({chapter_title})", client=client,
    )).strip()
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
        "chapter-map %r: matched=%d dropped=%d%s",
        chapter_title, len(codes_out), len(dropped),
        f" (dropped: {dropped[:10]})" if dropped else "",
    )
    return codes_out


async def _breakdown_chapter_into_topics(
    chapter_title: str,
    chapter_prose: str,
    *,
    start_page: int | None = None,
    client: anthropic.Anthropic | None = None,
) -> list[dict]:
    """Split one chapter's prose into MULTIPLE focused topics via the LLM.

    Line-numbers the prose, calls the vendored Schema topic-breakdown prompt
    (system=prompt, user=title + numbered text), parses the JSON, and slices the
    chapter into topics by line range. Each returned dict has title / topic_text
    / start_line / end_line. If parsing yields zero topics, returns NO topics so
    the caller can apply its single-topic fallback. Logs uniformly (rule 11).
    """
    log.info(
        "topic-breakdown start: chapter=%r prose_chars=%d start_page=%s",
        chapter_title, len(chapter_prose), start_page,
    )
    try:
        numbered = _add_line_numbers(chapter_prose)
        page_hint = f"Start Page: {start_page}\n" if start_page else ""
        user_message = (
            f"Chapter Title: {chapter_title}\n{page_hint}\n"
            f"Chapter Text:\n{numbered}"
        )
        raw = await _complete(
            _load_topic_breakdown_prompt(), user_message,
            label=f"topic-breakdown({chapter_title})", client=client,
        )
        parsed = _extract_json_from_response(raw)
        topics = _split_chapter_into_topics(parsed, chapter_prose)
    except Exception:
        log.error(
            "topic-breakdown FAILED: chapter=%r", chapter_title, exc_info=True,
        )
        raise
    log.info(
        "topic-breakdown done: chapter=%r topics=%d", chapter_title, len(topics),
    )
    return topics


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

    async def mark_running(self, conn: asyncpg.Connection, cell: dict) -> None:
        """Flip the row to 'running' once the cell is resolved, before the long
        Phase A. So the dashboard shows 'running' during the LLM phase even
        though no per-step DB writes happen until Phase B."""
        self.current_step = "sub_slos"
        await conn.execute(
            "UPDATE import_runs SET status='running', current_step=$2, updated_at=now() WHERE id=$1",
            self.run_id, self.current_step,
        )

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
        FROM book_library_book b
        LEFT JOIN slo_gradesubject gs ON b.grade_subject_id = gs.id
        LEFT JOIN slo_grade g ON gs.grade_id = g.id
        LEFT JOIN slo_subject s ON gs.subject_id = s.id
        WHERE b.id = $1
        """,
        core_book_id,
    )
    if book_row is None:
        raise ValueError(f"core book {core_book_id} not found")
    # Importable statuses: a published book or one ready for review. Anything
    # earlier (Draft etc.) is rejected — but a non-OnProd book is allowed so the
    # admin can pull a book that isn't live yet (logged for visibility).
    importable = {"OnProd", "ReadyForReview"}
    if book_row["status"] not in importable:
        raise ValueError(
            f"core book {core_book_id} status={book_row['status']!r}; "
            f"expected one of {sorted(importable)}"
        )
    if book_row["status"] != "OnProd":
        log.warning(
            "core book %s status=%s (not OnProd) — importing anyway",
            core_book_id, book_row["status"],
        )

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
    schema: str = "fde_staging",
    anthropic_client: anthropic.Anthropic | None = None,
) -> None:
    """Run the full import as a background job. Updates the import_runs row.

    Opens its own core (read-only) + Dars (rw) connections (D-5). Dars writes in
    one transaction; on error, roll back then mark failed via a fresh connection.
    `schema` is the source schema in core (validated by the caller); core table
    refs are unqualified and resolved via search_path.
    """
    log.info("run_import start run_id=%s core_book_id=%s schema=%r", run_id, core_book_id, schema)
    if not _SCHEMA_RE.match(schema):
        # Defensive — the router validates, but the bg task must not run with a
        # bad identifier (search_path interpolation).
        await _mark_failed(dars_dsn, run_id, f"invalid schema name {schema!r}")
        return
    prog = _Progress(run_id)
    fde_conn: asyncpg.Connection | None = None
    dars_conn: asyncpg.Connection | None = None
    try:
        # Core connection lives through Phase A (reads happen across the LLM
        # phase). command_timeout bounds any single query.
        fde_conn = await asyncpg.connect(core_dsn, command_timeout=120)
        await fde_conn.execute(f"SET search_path TO {schema}, public")

        # Resolve the cell with a SHORT-LIVED Dars connection — do NOT keep a
        # Dars connection open across Phase A (D-16: a Dars conn idle through the
        # ~14-min LLM phase gets dropped, then Phase B's transaction explodes
        # with "connection was closed"). We reconnect fresh for Phase B.
        async with _dars_conn(dars_dsn) as setup_conn:
            cell = await resolve_cell(
                setup_conn, fde_conn, core_book_id=core_book_id, curriculum_id=curriculum_id
            )
            await prog.mark_running(setup_conn, cell)
        if cell["subject_code"] != "Eng":
            prog.warn(
                f"subject is {cell['subject_code']!r}; breakdown prompt is English-only — "
                "results may be poor (D-4)."
            )

        # Phase A — all core reads + all LLM work, NO Dars connection held. This
        # is where the minutes go (177+ LLM calls).
        plan = await _build_import_plan(
            fde_conn=fde_conn, core_book_id=core_book_id, cell=cell,
            prog=prog, client=anthropic_client,
        )

        # Phase B — open a FRESH Dars connection, write everything in one short
        # transaction, commit, finalise.
        async with _dars_conn(dars_dsn) as dars_conn:
            async with dars_conn.transaction():
                await _write_import_plan(dars_conn=dars_conn, cell=cell, plan=plan, prog=prog)
            await dars_conn.execute(
                "UPDATE import_runs SET status='succeeded', current_step=NULL, updated_at=now() "
                "WHERE id=$1",
                run_id,
            )
        log.info("run_import done run_id=%s counts=%s", run_id, prog.counts)
    except Exception as exc:  # noqa: BLE001 — must capture to mark the run failed
        log.error("run_import failed run_id=%s: %s", run_id, exc, exc_info=True)
        await _mark_failed(dars_dsn, run_id, str(exc))
    finally:
        if fde_conn is not None:
            await fde_conn.close()
        # dars_conn is managed by the `async with _dars_conn(...)` blocks above.


@contextlib.asynccontextmanager
async def _dars_conn(dars_dsn: str):
    """Short-lived Dars connection (command_timeout bounds queries). Always
    closed on exit — never held open across the long LLM phase (D-16)."""
    conn = await asyncpg.connect(dars_dsn, command_timeout=120)
    try:
        yield conn
    finally:
        await conn.close()


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
# Phase A: build the import plan (core reads + all LLM work, NO transaction).
# Phase B: write the plan (one short Dars transaction). Split so the slow LLM
# phase never holds a DB transaction open — that caused the connection to drop
# and the task to hang (D-16). Deterministic UUIDs are the row ids, so no
# post-insert SELECT round-trips are needed.
# ---------------------------------------------------------------------------


async def _build_import_plan(
    *,
    fde_conn: asyncpg.Connection,
    core_book_id: int,
    cell: dict,
    prog: _Progress,
    client: anthropic.Anthropic | None,
) -> dict:
    """All core reads + all LLM calls. Returns a plan of plain dicts to write.

    No Dars writes here — Dars is only touched in _write_import_plan, inside a
    short transaction. Progress is flushed on its own connection (prog has none
    yet; we flush minimally via log only, the row is updated in phase B).
    """
    ck = _cell_key(cell)

    # 1. SLOs from core.
    log.info("plan: reading SLOs from core")
    slo_rows = await fde_conn.fetch(
        """
        SELECT n.ncp_slo_id, n.slo_statement
        FROM slo_ncpslo n
        JOIN slo_gradesubject gs ON n.grade_subject_id = gs.id
        JOIN slo_grade g ON gs.grade_id = g.id
        JOIN slo_subject s ON gs.subject_id = s.id
        WHERE g.short_code = $1 AND s.short_code = $2 AND n.is_active = TRUE
        ORDER BY n.ncp_slo_id
        """,
        cell["grade_code"], cell["subject_code"],
    )
    # slo plan rows + a code->(uuid, statement) map for downstream LLM context.
    slos: list[dict] = []
    slo_code_to_info: dict[str, tuple[uuid.UUID, str]] = {}
    for position, row in enumerate(slo_rows, start=1):
        code, statement = row["ncp_slo_id"], row["slo_statement"]
        sid = seed_uuid(f"slo:{ck}:{code}")
        slos.append({"id": sid, "code": code, "statement": statement, "position": position})
        slo_code_to_info[code] = (sid, statement)

    # 1b. book + chapters from core — read NOW, while the core connection is
    # fresh. All core reads happen before any LLM call so fde_conn is never held
    # idle across the long LLM phase (D-16: an idle core conn gets dropped and
    # the next read TimeoutErrors). After this, the LLM work touches no DB.
    log.info("plan: reading book + chapters from core")
    book, chapters = await _read_book_and_chapters(
        fde_conn=fde_conn, core_book_id=core_book_id, cell=cell, prog=prog,
    )

    # 2. sub-SLOs: LLM breakdown + parse (no DB; lp_type deferred per D-17).
    sub_slos: list[dict] = []
    sub_code_to_uuid: dict[str, uuid.UUID] = {}
    if slo_code_to_info:
        slos_text = _format_slos_for_prompt(slo_code_to_info)
        raw_md = await _run_breakdown_llm(
            slos_text,
            subject_label=cell["subject_code"], grade_label=f"Grade {cell['grade_code']}",
            client=client,
        )
        rows = _parse_breakdown_markdown(raw_md)
        log.info("plan: breakdown parsed %d markdown rows", len(rows))
        known_parents = set(slo_code_to_info.keys())
        parsed: list[dict] = []
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
        # lp_type is NOT classified here (D-17) — left NULL on import and computed
        # lazily at LP-generation time. This removes ~N serial LLM calls (the
        # import's old bottleneck). Assign positions within parent + det. uuids.
        by_parent: dict[str, list[dict]] = {}
        for idx, rec in enumerate(parsed):
            rec["_order"] = idx
            by_parent.setdefault(rec["parent_slo_code"], []).append(rec)
        for parent_code, group in by_parent.items():
            parent_uuid = slo_code_to_info[parent_code][0]
            group.sort(key=lambda r: (_sub_code_sort_key(r["code"]), r["_order"]))
            for position, rec in enumerate(group, start=1):
                ssid = seed_uuid(f"sub_slo:{ck}:{rec['code']}")
                sub_code_to_uuid[rec["code"]] = ssid
                sub_slos.append({
                    "id": ssid, "slo_id": parent_uuid, "code": rec["code"],
                    "statement": rec["statement"], "position": position,
                    "lp_type": None,  # deferred (D-17)
                })

    # 3. topics (N/chapter via the topic-breakdown prompt) + per-topic sub-SLO
    # mapping (LLM per chapter to split, then LLM per topic to map; no DB).
    sub_slo_index_text = _build_sub_slo_index(
        [{"code": s["code"], "statement": s["statement"]} for s in sub_slos]
    )
    valid_codes = set(sub_code_to_uuid.keys())
    topics: list[dict] = []
    for chapter in chapters:
        prose = _flatten_chapter_prose(chapter.get("chapter_text") or [])
        ch_num = chapter["chapter_number"]
        if not prose.strip():
            prog.warn(f"chapter {ch_num} has no prose; skipped topic breakdown + mapping")
            continue

        # Split the chapter into focused topics. Fall back to a single
        # whole-chapter topic if the breakdown yields none.
        chapter_topics = await _breakdown_chapter_into_topics(
            chapter["title"], prose,
            start_page=chapter.get("start_page"), client=client,
        )
        if not chapter_topics:
            prog.warn(
                f"chapter {ch_num} ({chapter['title']!r}) produced no topics from the "
                "breakdown — falling back to a single whole-chapter topic"
            )
            chapter_topics = [{"title": chapter["title"], "topic_text": prose}]

        for topic_number, ct in enumerate(chapter_topics, start=1):
            topic_title = (ct.get("title") or chapter["title"]).strip() or chapter["title"]
            topic_text = ct.get("topic_text") or ""
            topic = {
                "id": seed_uuid(f"topic:{ck}:ch{ch_num}:{topic_number}"),
                "book_chapter_id": chapter["id"],
                "topic_number": topic_number,
                "title": topic_title,
                "topic_text": topic_text[:_TOPIC_TEXT_CAP],
                "sub_slo_codes": [],
            }
            if topic_text.strip() and valid_codes:
                topic["sub_slo_codes"] = await _map_chapter_to_sub_slos(
                    chapter_title=topic_title, chapter_prose=topic_text,
                    sub_slo_index_text=sub_slo_index_text, valid_codes=valid_codes,
                    client=client,
                )
            topics.append(topic)

    return {
        "slos": slos,
        "sub_slos": sub_slos,
        "sub_code_to_uuid": sub_code_to_uuid,
        "book": book,
        "chapters": chapters,
        "topics": topics,
    }


async def _read_book_and_chapters(
    *, fde_conn: asyncpg.Connection, core_book_id: int, cell: dict, prog: _Progress,
) -> tuple[dict, list[dict]]:
    """Core reads only — build book + chapter plan dicts (no Dars writes)."""
    ck = _cell_key(cell)
    book_row = await fde_conn.fetchrow(
        """
        SELECT b.id, b.title, b.publisher, b.edition, b.published_year,
               b.total_chapters, b.pdf_url, b.book_text
        FROM book_library_book b WHERE b.id = $1
        """,
        core_book_id,
    )
    book_text_parsed = _parse_jsonb(book_row["book_text"]) or []
    book = {
        "id": seed_uuid(f"book:{ck}:{core_book_id}"),
        "title": book_row["title"], "publisher": book_row["publisher"],
        "edition": book_row["edition"], "published_year": book_row["published_year"],
        "total_chapters": book_row["total_chapters"], "pdf_url": book_row["pdf_url"],
        "book_text": book_text_parsed,
    }
    chapter_rows = await fde_conn.fetch(
        """
        SELECT bc.chapter_number, bc.title, bc.start_page, bc.end_page, bc.status, bc.is_active
        FROM book_library_bookchapter bc
        WHERE bc.book_id = $1 AND bc.deleted_at IS NULL
        ORDER BY bc.chapter_number
        """,
        core_book_id,
    )
    chapters: list[dict] = []
    for ch in chapter_rows:
        start_page, end_page = ch["start_page"], ch["end_page"]
        if start_page is None or end_page is None:
            prog.warn(
                f"chapter {ch['chapter_number']} ({ch['title']!r}) has no page range; prose slice empty"
            )
            slice_ = []
        else:
            slice_ = [
                p for p in book_text_parsed
                if isinstance(p, dict) and isinstance(p.get("pdf_page_no"), int)
                and start_page <= p["pdf_page_no"] <= end_page
            ]
        chapters.append({
            "id": seed_uuid(f"book_chapter:{ck}:{core_book_id}:{ch['chapter_number']}"),
            "book_id": book["id"], "chapter_number": ch["chapter_number"], "title": ch["title"],
            "start_page": start_page, "end_page": end_page,
            "status": "published" if (ch["status"] == "OnProd" and ch["is_active"]) else "draft",
            "chapter_text": slice_,
        })
    return book, chapters


async def _write_import_plan(
    *, dars_conn: asyncpg.Connection, cell: dict, plan: dict, prog: _Progress,
) -> None:
    """Phase B — write the whole plan in one short transaction (the caller's).

    Deterministic UUIDs are the row ids, so no post-insert SELECTs. Fast burst
    of upserts; the transaction is open for seconds, not the whole import.
    """
    cur_id, grade_id, subj_id = cell["curriculum_id"], cell["grade_id"], cell["subject_id"]

    # SLOs
    await prog.start_step(dars_conn, "slos")
    for s in plan["slos"]:
        await dars_conn.execute(
            """
            INSERT INTO slos (id, curriculum_id, grade_id, subject_id, code, statement, position)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (curriculum_id, grade_id, subject_id, code) DO UPDATE
              SET statement = EXCLUDED.statement, position = EXCLUDED.position, updated_at = now()
            """,
            s["id"], cur_id, grade_id, subj_id, s["code"], s["statement"], s["position"],
        )
    await prog.finish_step(dars_conn, "slos", len(plan["slos"]))

    # sub-SLOs
    await prog.start_step(dars_conn, "sub_slos")
    for ss in plan["sub_slos"]:
        await dars_conn.execute(
            """
            INSERT INTO sub_slos (id, slo_id, code, statement, position, source, recommended_lp_type)
            VALUES ($1, $2, $3, $4, $5, 'schema_breakdown', $6)
            ON CONFLICT (slo_id, code) DO UPDATE
              SET statement = EXCLUDED.statement, position = EXCLUDED.position,
                  source = EXCLUDED.source, recommended_lp_type = EXCLUDED.recommended_lp_type,
                  updated_at = now()
            """,
            ss["id"], ss["slo_id"], ss["code"], ss["statement"], ss["position"], ss["lp_type"],
        )
    await prog.finish_step(dars_conn, "sub_slos", len(plan["sub_slos"]))

    # book + chapters
    await prog.start_step(dars_conn, "book_chapters")
    b = plan["book"]
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
        b["id"], cur_id, grade_id, subj_id, b["title"], b["publisher"], b["edition"],
        b["published_year"], b["total_chapters"], b["pdf_url"], json.dumps(b["book_text"]),
    )
    prog.dars_book_id = b["id"]
    for ch in plan["chapters"]:
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
            ch["id"], ch["book_id"], ch["chapter_number"], ch["title"],
            ch["start_page"], ch["end_page"], json.dumps(ch["chapter_text"]), ch["status"],
        )
    await prog.finish_step(dars_conn, "book_chapters", len(plan["chapters"]))

    # topics + mappings
    await prog.start_step(dars_conn, "topics")
    sub_code_to_uuid = plan["sub_code_to_uuid"]
    # sub_slo_id -> parent slo_id, from the plan (no DB lookup).
    sub_uuid_to_slo = {ss["id"]: ss["slo_id"] for ss in plan["sub_slos"]}
    topic_count = 0
    mapping_count = 0
    bcs_seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for topic in plan["topics"]:
        await dars_conn.execute(
            """
            INSERT INTO topics (id, book_chapter_id, topic_number, title, topic_text, status)
            VALUES ($1, $2, $3, $4, $5, 'published')
            ON CONFLICT (book_chapter_id, topic_number) DO UPDATE
              SET title = EXCLUDED.title, topic_text = EXCLUDED.topic_text,
                  status = EXCLUDED.status, updated_at = now()
            """,
            topic["id"], topic["book_chapter_id"], topic["topic_number"],
            topic["title"], topic["topic_text"],
        )
        topic_count += 1
        for code in topic["sub_slo_codes"]:
            ss_uuid = sub_code_to_uuid[code]
            await dars_conn.execute(
                "INSERT INTO topic_sub_slos (topic_id, sub_slo_id) VALUES ($1, $2) "
                "ON CONFLICT (topic_id, sub_slo_id) DO NOTHING",
                topic["id"], ss_uuid,
            )
            mapping_count += 1
            parent_slo_id = sub_uuid_to_slo.get(ss_uuid)
            key = (topic["book_chapter_id"], parent_slo_id)
            if parent_slo_id is not None and key not in bcs_seen:
                await dars_conn.execute(
                    "INSERT INTO book_chapter_slos (book_chapter_id, slo_id) VALUES ($1, $2) "
                    "ON CONFLICT (book_chapter_id, slo_id) DO NOTHING",
                    topic["book_chapter_id"], parent_slo_id,
                )
                bcs_seen.add(key)
    await prog.finish_step(dars_conn, "topics", topic_count)
    prog.steps["mappings"] = {
        "status": "done", "topic_sub_slos": mapping_count, "book_chapter_slos": len(bcs_seen),
    }
    prog.counts["topic_sub_slos"] = mapping_count
    prog.counts["book_chapter_slos"] = len(bcs_seen)
    await prog._flush(dars_conn, status="running")

