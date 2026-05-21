"""
Import NCP English Grade 1 curriculum data into Dars staging.

One-shot ETL: reads from live `fde_staging` schema (taleemabad-core SLO + book
tables) and Schema (LLM-backed sub-SLO breakdown + topic mapping) and Claude
(sub-SLO `lp_type` classifier), and writes directly to Dars staging via SQL
upserts in a single transaction.

Per docs/features/ncp-english-g1-seed/01-decision-log.md:
  D-15: book id defaults to 1171 ("English G1 Taleemabad" by Taleemabad).
  D-17: fde_staging access uses CORE_STAGING_DB_* env vars.
  D-18: writes directly to Dars staging (no JSON intermediate, no v2_seed integration).
  D-19: Dars staging access uses DARS_STAGING_DATABASE_URL env var.

Usage:
    cd dars/server
    uv run python ../scripts/import_ncp_english_g1.py [--book-id 1171] [--dry-run] [--verbose]

    # First, ensure dars/.env has:
    #   CORE_STAGING_DB_HOST / PORT / NAME / USER / PASSWORD
    #   DARS_STAGING_DATABASE_URL  (postgres://... for Dars staging via Railway public TCP proxy)
    #   ANTHROPIC_API_KEY

Side effects on success (without --dry-run):
  * Upserts 'NCP' row into Dars `curriculums`
  * Upserts NCP English G1 SLOs into Dars `slos`
  * Upserts sub-NCP-SLOs (with Claude-classified lp_type) into Dars `sub_slos`
  * Upserts book 1171 + 12 chapters into Dars `books` / `book_chapters`
  * Upserts topics + topic↔sub-SLO mappings into Dars `topics` / `topic_sub_slos`
  * Derived: `book_chapter_slos` (chapter↔SLO via topics)
  * All wrapped in one Dars transaction — rolls back on any error.

The Aisha demo tenancy is untouched. Existing Dars curriculum SLOs/books are
untouched. v2_seed.py is unchanged.
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import uuid
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

log = logging.getLogger("import_ncp_english_g1")


# Deterministic UUID namespace for derived seed IDs (see seeds/lookups.py).
SEED_NAMESPACE = uuid.UUID("00000000-0000-5da7-5000-000000000001")


def seed_uuid(key: str) -> uuid.UUID:
    """Deterministic UUID v5 derived from SEED_NAMESPACE + key."""
    return uuid.uuid5(SEED_NAMESPACE, key)


# ── Env / connection setup ───────────────────────────────────────────────────


def _load_env() -> None:
    """Load dars/.env so CORE_STAGING_DB_* and DARS_STAGING_DATABASE_URL are present."""
    repo_root = Path(__file__).resolve().parent.parent
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        log.error("Missing required env var: %s (add it to dars/.env)", name)
        sys.exit(1)
    return val


def _fde_dsn() -> str:
    host = _require_env("CORE_STAGING_DB_HOST")
    port = _require_env("CORE_STAGING_DB_PORT")
    name = _require_env("CORE_STAGING_DB_NAME")
    user = _require_env("CORE_STAGING_DB_USER")
    password = _require_env("CORE_STAGING_DB_PASSWORD")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def _dars_dsn() -> str:
    return _require_env("DARS_STAGING_DATABASE_URL")


async def _open_fde_connection() -> asyncpg.Connection:
    """
    Open a read-only connection to fde_staging.

    - search_path is set to `fde_staging, public` so queries can use unqualified
      table names AND we avoid the silent-falls-back-to-public footgun seen in
      planning.
    - Wrap in `BEGIN READ ONLY` so even an accidental INSERT raises.
    """
    conn = await asyncpg.connect(_fde_dsn())
    await conn.execute("SET search_path TO fde_staging, public")
    await conn.execute("BEGIN READ ONLY")
    log.info("Connected to fde_staging (READ ONLY, search_path=fde_staging,public)")
    # Smoke check: must see the NCP SLO table.
    n = await conn.fetchval("SELECT COUNT(*) FROM fde_staging.slo_ncpslo")
    log.info("fde_staging.slo_ncpslo row count: %s", n)
    return conn


async def _open_dars_connection() -> asyncpg.Connection:
    """Open a read-write connection to Dars staging. Caller wraps in a tx."""
    conn = await asyncpg.connect(_dars_dsn())
    log.info("Connected to Dars staging")
    # Smoke check: schema must have the v2 tables.
    n = await conn.fetchval("SELECT COUNT(*) FROM curriculums")
    log.info("Dars staging curriculums row count: %s", n)
    return conn


# ── F1.5: NCP curriculum + SLOs ──────────────────────────────────────────────


async def _resolve_grade_subject_ids(dars_conn: asyncpg.Connection) -> tuple[uuid.UUID, uuid.UUID]:
    """Look up the Dars grade_id for G1 and subject_id for Eng. Both must exist
    (seeded by lookups.py during normal v2_seed boot)."""
    grade_id = await dars_conn.fetchval(
        "SELECT id FROM grades WHERE code = $1", 1
    )
    if grade_id is None:
        raise RuntimeError("Dars `grades` is missing code=1 (Grade 1) — seed lookups first")
    subject_id = await dars_conn.fetchval(
        "SELECT id FROM subjects WHERE code = $1", "Eng"
    )
    if subject_id is None:
        raise RuntimeError("Dars `subjects` is missing code 'Eng' — seed lookups first")
    return grade_id, subject_id


async def upsert_ncp_curriculum_row(dars_conn: asyncpg.Connection) -> uuid.UUID:
    """Upsert the NCP curriculum row (D-8). Returns its UUID."""
    ncp_uuid = seed_uuid("curriculum:NCP")
    await dars_conn.execute(
        """
        INSERT INTO curriculums (id, code, name, description, is_active)
        VALUES ($1, 'NCP', 'National Curriculum of Pakistan',
                'National Curriculum of Pakistan — top-level SLOs sourced from fde_staging.slo_ncpslo.',
                TRUE)
        ON CONFLICT (code) DO NOTHING
        """,
        ncp_uuid,
    )
    # If a row already existed under that code with a different id, prefer the
    # existing id over our deterministic one. Re-query to be safe.
    row_id = await dars_conn.fetchval("SELECT id FROM curriculums WHERE code = 'NCP'")
    log.info("curriculums NCP row id=%s", row_id)
    return row_id


async def import_ncp_slos(
    *,
    fde_conn: asyncpg.Connection,
    dars_conn: asyncpg.Connection,
    curriculum_id: uuid.UUID,
    grade_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> dict[str, tuple[uuid.UUID, str]]:
    """
    Read NCP English G1 SLOs from fde_staging, upsert into Dars `slos`.

    Returns mapping {ncp_slo_id (code): (dars_slo_uuid, statement)} for
    downstream sub-SLO upserts (which need both the parent UUID for FK and
    the parent statement as context for the lp_type classifier).

    Per D-11, we do NOT populate `slos.recommended_lp_type` for NCP — that
    column stays NULL; lp_type lives on the sub-SLO rows.
    """
    rows = await fde_conn.fetch(
        """
        SELECT n.ncp_slo_id, n.slo_statement, n.category
        FROM fde_staging.slo_ncpslo n
        JOIN fde_staging.slo_gradesubject gs ON n.grade_subject_id = gs.id
        JOIN fde_staging.slo_grade g ON gs.grade_id = g.id
        JOIN fde_staging.slo_subject s ON gs.subject_id = s.id
        WHERE g.short_code = 'G1'
          AND s.short_code = 'Eng'
          AND n.is_active = TRUE
        ORDER BY n.ncp_slo_id
        """
    )
    log.info("fde_staging: read %d NCP English G1 SLOs", len(rows))

    code_to_info: dict[str, tuple[uuid.UUID, str]] = {}
    for position, row in enumerate(rows, start=1):
        code = row["ncp_slo_id"]
        statement = row["slo_statement"]
        slo_uuid = seed_uuid(f"slo:NCP:G1:Eng:{code}")
        await dars_conn.execute(
            """
            INSERT INTO slos
                (id, curriculum_id, grade_id, subject_id, code, statement, position)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (curriculum_id, grade_id, subject_id, code) DO UPDATE
              SET statement = EXCLUDED.statement,
                  position  = EXCLUDED.position,
                  updated_at = now()
            """,
            slo_uuid, curriculum_id, grade_id, subject_id,
            code, statement, position,
        )
        # Re-fetch in case the row pre-existed with a different (non-deterministic) UUID.
        actual_id = await dars_conn.fetchval(
            """
            SELECT id FROM slos
            WHERE curriculum_id = $1 AND grade_id = $2 AND subject_id = $3 AND code = $4
            """,
            curriculum_id, grade_id, subject_id, code,
        )
        code_to_info[code] = (actual_id, statement)

    log.info("slos: upserted %d NCP English G1 SLOs", len(code_to_info))
    return code_to_info


# ── F1.6: Sub-SLO breakdown via Schema prompt + Claude lp_type ───────────────

# We replicate Schema's breakdown pipeline directly inside the dars script
# rather than importing Schema as a Python module — Schema brings in openai
# as a dep, and the dars venv has no reason to install it for a one-shot
# script. We reuse Schema's authoritative prompt verbatim (read from disk)
# and call Anthropic ourselves (the SDK is already in dars deps).

SCHEMA_REPO_ROOT = Path("/home/hataf/taleemabad/Schema")
SCHEMA_ENGLISH_PROMPT = SCHEMA_REPO_ROOT / "prompts" / "english_prompt.txt"

# Use Claude Opus for the breakdown (Schema uses opus). One call, large output.
BREAKDOWN_MODEL = "claude-opus-4-6"
BREAKDOWN_MAX_TOKENS = 32000


def _format_slos_for_prompt(slo_code_to_info: dict[str, tuple[uuid.UUID, str]]) -> str:
    """Render the SLO list in the shape Schema's prompt expects."""
    lines = []
    for code in sorted(slo_code_to_info.keys()):
        _uuid, statement = slo_code_to_info[code]
        lines.append(f"{code}: {statement}")
    return "\n".join(lines)


def _parse_breakdown_markdown(md: str) -> list[dict[str, str]]:
    """Parse Schema's expected markdown table format into rows. Same logic as
    Schema.services.slo_breakdown.markdown_to_rows but inlined."""
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


def _run_breakdown_llm(slos_text: str) -> str:
    """Call Anthropic with Schema's English breakdown prompt + the SLOs.
    Returns the raw markdown response."""
    import anthropic
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set; cannot run breakdown")

    system_prompt = SCHEMA_ENGLISH_PROMPT.read_text(encoding="utf-8")
    user_message = (
        f"Subject: English\n"
        f"Grade: Grade One\n\n"
        f"Here are the main SLOs:\n\n{slos_text}"
    )
    log.info(
        "Calling Anthropic for breakdown — model=%s slos_count=%d system_chars=%d",
        BREAKDOWN_MODEL, len(slos_text.splitlines()), len(system_prompt),
    )
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=BREAKDOWN_MODEL,
        max_tokens=BREAKDOWN_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    log.info(
        "Breakdown response received — usage in=%d out=%d",
        response.usage.input_tokens, response.usage.output_tokens,
    )
    return "".join(b.text for b in response.content if b.type == "text")


async def import_sub_slos(
    *,
    dars_conn: asyncpg.Connection,
    slo_code_to_info: dict[str, tuple[uuid.UUID, str]],
) -> dict[str, uuid.UUID]:
    """
    Generate sub-NCP-SLOs from the top-level NCP SLOs using Schema's
    breakdown prompt + Anthropic (per D-5), classify each sub-SLO's lp_type
    via Claude (per D-11/D-14), and upsert into Dars `sub_slos` with
    `recommended_lp_type` (per D-12).

    Returns mapping {sub_slo_code: dars_sub_slo_uuid} for downstream topic
    mapping.
    """
    # Local import for classifier (lives next to this script).
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from lp_type_classifier import classify_lp_type  # type: ignore

    slos_text = _format_slos_for_prompt(slo_code_to_info)
    log.info("Running sub-SLO breakdown for English G1 (one Anthropic call)...")
    raw_markdown = await asyncio.to_thread(_run_breakdown_llm, slos_text)

    # Save raw markdown for audit (per D-5 — not committed; for the developer).
    audit_path = Path("/tmp") / f"ncp_english_g1_breakdown_{os.getpid()}.md"
    audit_path.write_text(raw_markdown, encoding="utf-8")
    log.info("Saved breakdown markdown for audit: %s", audit_path)

    rows = _parse_breakdown_markdown(raw_markdown)
    log.info("Parsed %d sub-SLO rows from breakdown markdown", len(rows))

    # Parse rows: {Sub SLO Code, Sub SLOs} -> {code, statement, parent_slo_code}
    parsed: list[dict[str, str]] = []
    skipped_orphans = 0
    for row in rows:
        code = (row.get("Sub SLO Code") or "").strip()
        statement = (row.get("Sub SLOs") or "").strip()
        if not code or not statement:
            continue
        # Parent code is everything up to the final "-<letter>" suffix.
        # E.g. "A1-02-a" -> "A1-02"; codes without that pattern are skipped
        # (Schema occasionally emits header-row or summary lines).
        m = _SUB_SLO_CODE_RE.match(code)
        if not m:
            log.warning("Skipping malformed sub-SLO code %r", code)
            continue
        parent_code = m.group(1)
        if parent_code not in slo_code_to_info:
            log.warning(
                "Sub-SLO %r references unknown parent SLO %r — skipping",
                code, parent_code,
            )
            skipped_orphans += 1
            continue
        parsed.append({"code": code, "statement": statement, "parent_slo_code": parent_code})

    if skipped_orphans:
        log.warning("Skipped %d sub-SLOs with no parent SLO in Dars", skipped_orphans)
    log.info("Parsed %d sub-SLOs ready for classification", len(parsed))

    # Classify lp_type per sub-SLO (sequential — cache reuse pays off).
    log.info("Classifying lp_type for %d sub-SLOs via Claude (haiku)...", len(parsed))
    for i, rec in enumerate(parsed):
        parent_uuid, parent_stmt = slo_code_to_info[rec["parent_slo_code"]]
        rec["lp_type"] = await asyncio.to_thread(
            classify_lp_type,
            parent_slo_statement=parent_stmt,
            sub_slo_statement=rec["statement"],
        )
        if i == 0 or (i + 1) % 25 == 0:
            log.info("  classified %d/%d (last: %s -> %s)",
                     i + 1, len(parsed), rec["code"], rec["lp_type"])

    # Upsert into Dars sub_slos, ordering by code within parent.
    # Group by parent so we can assign position within each parent.
    sub_code_to_uuid: dict[str, uuid.UUID] = {}
    by_parent: dict[str, list[dict[str, str]]] = {}
    for rec in parsed:
        by_parent.setdefault(rec["parent_slo_code"], []).append(rec)

    inserted = 0
    for parent_code, subs in by_parent.items():
        parent_uuid, _ = slo_code_to_info[parent_code]
        subs.sort(key=lambda r: r["code"])
        for position, rec in enumerate(subs, start=1):
            sub_uuid = seed_uuid(f"sub_slo:NCP:G1:Eng:{rec['code']}")
            await dars_conn.execute(
                """
                INSERT INTO sub_slos
                    (id, slo_id, code, statement, position, source, recommended_lp_type)
                VALUES ($1, $2, $3, $4, $5, 'schema_breakdown', $6)
                ON CONFLICT (slo_id, code) DO UPDATE
                  SET statement = EXCLUDED.statement,
                      position  = EXCLUDED.position,
                      source    = EXCLUDED.source,
                      recommended_lp_type = EXCLUDED.recommended_lp_type,
                      updated_at = now()
                """,
                sub_uuid, parent_uuid, rec["code"], rec["statement"],
                position, rec["lp_type"],
            )
            actual_id = await dars_conn.fetchval(
                "SELECT id FROM sub_slos WHERE slo_id = $1 AND code = $2",
                parent_uuid, rec["code"],
            )
            sub_code_to_uuid[rec["code"]] = actual_id
            inserted += 1

    log.info("sub_slos: upserted %d rows", inserted)
    return sub_code_to_uuid


# Matches "A1-02-a", "B-01-c", etc. — capture the parent prefix before the final -<letter>.
_SUB_SLO_CODE_RE = re.compile(r"^([A-Z]\d*-\d+)-[a-z]$")


# ── F1.7: Book + chapters upsert ─────────────────────────────────────────────


async def import_book_and_chapters(
    *,
    fde_conn: asyncpg.Connection,
    dars_conn: asyncpg.Connection,
    book_id: int,
    curriculum_id: uuid.UUID,
    grade_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> tuple[uuid.UUID, list[dict]]:
    """
    Pull book metadata + book.book_text + all chapter rows from fde_staging,
    slice book_text by pdf_page_no per chapter (D-16), and upsert into Dars
    `books` + `book_chapters`.

    Returns (dars_book_uuid, chapters_list) where chapters_list is each
    chapter as {id, chapter_number, title, start_page, end_page} for downstream
    topic/mapping steps.
    """
    # 1. Pull the book row.
    book_row = await fde_conn.fetchrow(
        """
        SELECT b.id, b.title, b.publisher, b.edition, b.published_year,
               b.total_chapters, b.pdf_url, b.book_text, b.status, b.is_active,
               g.short_code AS grade, s.short_code AS subject
        FROM fde_staging.book_library_book b
        LEFT JOIN fde_staging.slo_gradesubject gs ON b.grade_subject_id = gs.id
        LEFT JOIN fde_staging.slo_grade g ON gs.grade_id = g.id
        LEFT JOIN fde_staging.slo_subject s ON gs.subject_id = s.id
        WHERE b.id = $1
        """,
        book_id,
    )
    if book_row is None:
        raise RuntimeError(f"fde_staging.book_library_book id={book_id} not found")

    # Sanity assert per D-15.
    if book_row["status"] != "OnProd":
        raise RuntimeError(
            f"book {book_id} status={book_row['status']!r}; expected 'OnProd' (D-15)"
        )
    if not book_row["is_active"]:
        raise RuntimeError(f"book {book_id} is_active=False; expected True")
    if book_row["grade"] != "G1" or book_row["subject"] != "Eng":
        raise RuntimeError(
            f"book {book_id} is grade={book_row['grade']!r} subject={book_row['subject']!r}; "
            f"expected G1/Eng (D-15)"
        )
    log.info(
        "Book %d: title=%r publisher=%r book_text_chars=%s",
        book_id, book_row["title"], book_row["publisher"],
        len(book_row["book_text"]) if book_row["book_text"] else 0,
    )

    book_text = book_row["book_text"]
    # asyncpg returns jsonb as str by default; parse to a Python list of dicts.
    if isinstance(book_text, str):
        book_text_parsed = json.loads(book_text) if book_text else []
    elif isinstance(book_text, (list, dict)):
        book_text_parsed = book_text
    elif book_text is None:
        book_text_parsed = []
    else:
        book_text_parsed = []

    # 2. Upsert book row into Dars.
    book_uuid = seed_uuid(f"book:NCP:G1:Eng:{book_id}")
    # book_text in Dars is JSONB — pass as a JSON string + cast.
    await dars_conn.execute(
        """
        INSERT INTO books
            (id, curriculum_id, grade_id, subject_id, title, publisher, edition,
             published_year, total_chapters, pdf_url, book_text)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
        ON CONFLICT (id) DO UPDATE
          SET title = EXCLUDED.title,
              publisher = EXCLUDED.publisher,
              edition = EXCLUDED.edition,
              published_year = EXCLUDED.published_year,
              total_chapters = EXCLUDED.total_chapters,
              pdf_url = EXCLUDED.pdf_url,
              book_text = EXCLUDED.book_text,
              updated_at = now()
        """,
        book_uuid, curriculum_id, grade_id, subject_id,
        book_row["title"], book_row["publisher"], book_row["edition"],
        book_row["published_year"], book_row["total_chapters"], book_row["pdf_url"],
        json.dumps(book_text_parsed),
    )
    log.info("books: upserted book id=%s", book_uuid)

    # 3. Pull chapter index from fde_staging (no is_active filter per D-16).
    chapter_rows = await fde_conn.fetch(
        """
        SELECT bc.chapter_number, bc.title, bc.start_page, bc.end_page,
               bc.status, bc.is_active
        FROM fde_staging.book_library_bookchapter bc
        WHERE bc.book_id = $1
          AND bc.deleted_at IS NULL
        ORDER BY bc.chapter_number
        """,
        book_id,
    )
    log.info("fde_staging: %d chapter rows for book %d", len(chapter_rows), book_id)

    # 4. For each chapter, slice book.book_text by pdf_page_no in [start_page, end_page].
    chapters_out: list[dict] = []
    for ch in chapter_rows:
        start_page = ch["start_page"]
        end_page = ch["end_page"]
        if start_page is None or end_page is None:
            log.warning(
                "Chapter %d (%r): start_page=%s end_page=%s — no page range, skipping prose slice",
                ch["chapter_number"], ch["title"], start_page, end_page,
            )
            chapter_text_slice: list[dict] = []
        else:
            chapter_text_slice = [
                p for p in book_text_parsed
                if isinstance(p, dict) and isinstance(p.get("pdf_page_no"), int)
                and start_page <= p["pdf_page_no"] <= end_page
            ]
            log.debug(
                "Chapter %d (%r): pages %d-%d -> %d page objects",
                ch["chapter_number"], ch["title"], start_page, end_page,
                len(chapter_text_slice),
            )

        status = "published" if (ch["status"] == "OnProd" and ch["is_active"]) else "draft"
        chapter_uuid = seed_uuid(f"book_chapter:NCP:G1:Eng:{book_id}:{ch['chapter_number']}")
        await dars_conn.execute(
            """
            INSERT INTO book_chapters
                (id, book_id, chapter_number, title, start_page, end_page,
                 chapter_text, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
            ON CONFLICT (book_id, chapter_number) DO UPDATE
              SET title = EXCLUDED.title,
                  start_page = EXCLUDED.start_page,
                  end_page = EXCLUDED.end_page,
                  chapter_text = EXCLUDED.chapter_text,
                  status = EXCLUDED.status,
                  updated_at = now()
            """,
            chapter_uuid, book_uuid, ch["chapter_number"], ch["title"],
            start_page, end_page,
            json.dumps(chapter_text_slice), status,
        )
        actual_id = await dars_conn.fetchval(
            "SELECT id FROM book_chapters WHERE book_id = $1 AND chapter_number = $2",
            book_uuid, ch["chapter_number"],
        )
        chapters_out.append({
            "id": actual_id,
            "chapter_number": ch["chapter_number"],
            "title": ch["title"],
            "start_page": start_page,
            "end_page": end_page,
            "status": status,
        })

    log.info("book_chapters: upserted %d rows", len(chapters_out))
    return book_uuid, chapters_out


# ── F1.8: Topics + topic↔sub-SLO mapping + book_chapter_slos ─────────────────


TOPIC_MAPPER_MODEL = "claude-opus-4-6"


def _build_sub_slo_index(sub_slos_with_statements: list[dict]) -> str:
    """Render the sub-SLO list as a single text block for the mapper's system prompt."""
    lines = [f"- {s['code']}: {s['statement']}" for s in sub_slos_with_statements]
    return "\n".join(lines)


def _flatten_chapter_prose(chapter_text_slice: list[dict]) -> str:
    """Concatenate `text` fields from book_text page objects into a single string."""
    if not chapter_text_slice:
        return ""
    parts = []
    for p in chapter_text_slice:
        if isinstance(p, dict):
            t = p.get("text") or ""
            if t:
                parts.append(t)
    return "\n\n".join(parts)


def _map_chapter_to_sub_slos(
    *,
    chapter_title: str,
    chapter_prose: str,
    sub_slo_index_text: str,
    valid_codes: set[str],
) -> list[str]:
    """One Anthropic call: given a chapter's prose + the full sub-SLO list,
    return which sub-SLO codes apply. Uses prompt caching on the index so 12
    chapter calls share the prefix."""
    import anthropic
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set; cannot map topics")

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
    # Cap prose to keep the request from running away; ~12K chars is plenty for an LLM
    # to judge a chapter's themes.
    truncated_prose = chapter_prose[:12000]
    user_message = (
        f"Chapter title: {chapter_title}\n\n"
        f"Chapter prose:\n{truncated_prose}\n\n"
        f"Return the matching sub-SLO codes, one per line."
    )
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=TOPIC_MAPPER_MODEL,
        max_tokens=2000,
        system=[
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{"role": "user", "content": user_message}],
    )
    log.debug(
        "Topic-mapper response for %r: in=%d out=%d cache_read=%d",
        chapter_title, response.usage.input_tokens, response.usage.output_tokens,
        response.usage.cache_read_input_tokens,
    )
    raw_text = "".join(b.text for b in response.content if b.type == "text").strip()
    codes_out: list[str] = []
    for line in raw_text.splitlines():
        candidate = line.strip().lstrip("-").strip()
        if candidate and candidate in valid_codes:
            codes_out.append(candidate)
    return codes_out


async def import_topics_and_mappings(
    *,
    dars_conn: asyncpg.Connection,
    chapters: list[dict],
    sub_slo_code_to_uuid: dict[str, uuid.UUID],
) -> None:
    """
    Create one synthetic topic per chapter (per D-7), call Anthropic to map
    that chapter's prose to applicable sub-SLO codes, and upsert into
    `topics`, `topic_sub_slos`, and `book_chapter_slos`.
    """
    # Build a sub-SLO index for the mapper's cached system prompt.
    # We need statements; re-fetch from Dars.
    sub_slo_rows = await dars_conn.fetch(
        """
        SELECT ss.code, ss.statement
        FROM sub_slos ss
        JOIN slos s ON s.id = ss.slo_id
        JOIN curriculums c ON c.id = s.curriculum_id
        WHERE c.code = 'NCP' AND ss.code = ANY($1::text[])
        ORDER BY ss.code
        """,
        list(sub_slo_code_to_uuid.keys()),
    )
    sub_slos_with_statements = [{"code": r["code"], "statement": r["statement"]} for r in sub_slo_rows]
    sub_slo_index_text = _build_sub_slo_index(sub_slos_with_statements)
    valid_codes = set(sub_slo_code_to_uuid.keys())
    log.info(
        "Topic-mapper: %d sub-SLOs in index (~%d chars system prompt)",
        len(sub_slos_with_statements), len(sub_slo_index_text),
    )

    total_topic_sub_slos = 0
    book_chapter_slos_seen: set[tuple[uuid.UUID, uuid.UUID]] = set()

    for chapter in chapters:
        # Reconstruct prose from the chapter_text we wrote in F1.7.
        row = await dars_conn.fetchrow(
            "SELECT chapter_text FROM book_chapters WHERE id = $1",
            chapter["id"],
        )
        chapter_text = row["chapter_text"]
        if isinstance(chapter_text, str):
            try:
                chapter_text_parsed = json.loads(chapter_text) if chapter_text else []
            except json.JSONDecodeError:
                chapter_text_parsed = []
        elif isinstance(chapter_text, (list, dict)):
            chapter_text_parsed = chapter_text
        else:
            chapter_text_parsed = []
        prose = _flatten_chapter_prose(chapter_text_parsed if isinstance(chapter_text_parsed, list) else [])

        # Synthetic topic = "1 topic per chapter" per D-7.
        topic_uuid = seed_uuid(f"topic:NCP:G1:Eng:ch{chapter['chapter_number']}:1")
        await dars_conn.execute(
            """
            INSERT INTO topics
                (id, book_chapter_id, topic_number, title, topic_text, status)
            VALUES ($1, $2, 1, $3, $4, 'published')
            ON CONFLICT (book_chapter_id, topic_number) DO UPDATE
              SET title = EXCLUDED.title,
                  topic_text = EXCLUDED.topic_text,
                  status = EXCLUDED.status,
                  updated_at = now()
            """,
            topic_uuid, chapter["id"], chapter["title"], prose[:50000],
        )
        actual_topic_id = await dars_conn.fetchval(
            "SELECT id FROM topics WHERE book_chapter_id = $1 AND topic_number = 1",
            chapter["id"],
        )
        log.info(
            "Chapter %d (%r): synthetic topic id=%s",
            chapter["chapter_number"], chapter["title"], actual_topic_id,
        )

        # Map this chapter to sub-SLOs via Anthropic — skip if prose is empty.
        if not prose.strip():
            log.warning("Chapter %d has no prose; skipping sub-SLO mapping",
                        chapter["chapter_number"])
            continue

        codes = await asyncio.to_thread(
            _map_chapter_to_sub_slos,
            chapter_title=chapter["title"],
            chapter_prose=prose,
            sub_slo_index_text=sub_slo_index_text,
            valid_codes=valid_codes,
        )
        log.info(
            "Chapter %d (%r) -> %d sub-SLO mappings",
            chapter["chapter_number"], chapter["title"], len(codes),
        )

        # Insert topic_sub_slos rows + derive book_chapter_slos.
        for code in codes:
            sub_slo_uuid = sub_slo_code_to_uuid[code]
            await dars_conn.execute(
                """
                INSERT INTO topic_sub_slos (topic_id, sub_slo_id)
                VALUES ($1, $2)
                ON CONFLICT (topic_id, sub_slo_id) DO NOTHING
                """,
                actual_topic_id, sub_slo_uuid,
            )
            total_topic_sub_slos += 1

            # Derive book_chapter_slos: chapter -> parent SLO of this sub-SLO.
            parent_slo_id = await dars_conn.fetchval(
                "SELECT slo_id FROM sub_slos WHERE id = $1", sub_slo_uuid,
            )
            key = (chapter["id"], parent_slo_id)
            if key not in book_chapter_slos_seen:
                await dars_conn.execute(
                    """
                    INSERT INTO book_chapter_slos (book_chapter_id, slo_id)
                    VALUES ($1, $2)
                    ON CONFLICT (book_chapter_id, slo_id) DO NOTHING
                    """,
                    chapter["id"], parent_slo_id,
                )
                book_chapter_slos_seen.add(key)

    log.info(
        "topics: 1 per chapter (%d total). topic_sub_slos: %d. book_chapter_slos: %d.",
        len(chapters), total_topic_sub_slos, len(book_chapter_slos_seen),
    )


# ── Pipeline ─────────────────────────────────────────────────────────────────


async def run(*, book_id: int, dry_run: bool) -> int:
    """Returns process exit code."""
    fde_conn = None
    dars_conn = None
    try:
        fde_conn = await _open_fde_connection()
        dars_conn = await _open_dars_connection()

        if dry_run:
            log.info("DRY RUN: planning only, no writes")
            # In dry-run we still run the read-side queries to validate access
            # + show counts, but we never enter the Dars write transaction.
            await _dry_run_preview(fde_conn, book_id)
            log.info("DRY RUN: complete (no writes performed)")
            return 0

        # Real run: single Dars transaction wrapping every upsert.
        async with dars_conn.transaction():
            log.info("Beginning Dars write transaction")

            grade_id, subject_id = await _resolve_grade_subject_ids(dars_conn)
            log.info("Resolved grade_id=%s subject_id=%s for G1/Eng", grade_id, subject_id)

            curriculum_id = await upsert_ncp_curriculum_row(dars_conn)
            slo_code_to_info = await import_ncp_slos(
                fde_conn=fde_conn,
                dars_conn=dars_conn,
                curriculum_id=curriculum_id,
                grade_id=grade_id,
                subject_id=subject_id,
            )
            log.info("F1.5 complete: %d SLOs upserted", len(slo_code_to_info))

            sub_slo_code_to_uuid = await import_sub_slos(
                dars_conn=dars_conn,
                slo_code_to_info=slo_code_to_info,
            )
            log.info("F1.6 complete: %d sub-SLOs upserted", len(sub_slo_code_to_uuid))

            dars_book_uuid, chapters = await import_book_and_chapters(
                fde_conn=fde_conn,
                dars_conn=dars_conn,
                book_id=book_id,
                curriculum_id=curriculum_id,
                grade_id=grade_id,
                subject_id=subject_id,
            )
            log.info("F1.7 complete: book id=%s, %d chapters",
                     dars_book_uuid, len(chapters))

            await import_topics_and_mappings(
                dars_conn=dars_conn,
                chapters=chapters,
                sub_slo_code_to_uuid=sub_slo_code_to_uuid,
            )
            log.info("F1.8 complete")

        log.info("Done")
        return 0
    except Exception:
        log.exception("Import failed")
        return 1
    finally:
        if fde_conn is not None:
            try:
                await fde_conn.execute("ROLLBACK")
            except Exception:
                pass
            await fde_conn.close()
        if dars_conn is not None:
            await dars_conn.close()


async def _dry_run_preview(fde_conn: asyncpg.Connection, book_id: int) -> None:
    """Sanity counts so the developer can eyeball before doing a real run."""
    slo_count = await fde_conn.fetchval(
        """
        SELECT COUNT(*)
        FROM fde_staging.slo_ncpslo n
        JOIN fde_staging.slo_gradesubject gs ON n.grade_subject_id = gs.id
        JOIN fde_staging.slo_grade g ON gs.grade_id = g.id
        JOIN fde_staging.slo_subject s ON gs.subject_id = s.id
        WHERE g.short_code = 'G1' AND s.short_code = 'Eng' AND n.is_active = TRUE
        """
    )
    log.info("DRY RUN: would import %s NCP English G1 SLOs", slo_count)

    book_row = await fde_conn.fetchrow(
        """
        SELECT b.id, b.title, b.publisher, b.status, b.is_active,
               g.short_code AS grade, s.short_code AS subject,
               LENGTH(b.book_text::text) AS book_text_len,
               (SELECT COUNT(*) FROM fde_staging.book_library_bookchapter bc
                 WHERE bc.book_id = b.id AND bc.deleted_at IS NULL) AS chapter_count
        FROM fde_staging.book_library_book b
        LEFT JOIN fde_staging.slo_gradesubject gs ON b.grade_subject_id = gs.id
        LEFT JOIN fde_staging.slo_grade g ON gs.grade_id = g.id
        LEFT JOIN fde_staging.slo_subject s ON gs.subject_id = s.id
        WHERE b.id = $1
        """,
        book_id,
    )
    if book_row is None:
        log.error("DRY RUN: book id %s not found in fde_staging", book_id)
        sys.exit(1)
    log.info(
        "DRY RUN: would import book %s '%s' by %s (status=%s grade=%s subject=%s book_text=%s chars chapters=%s)",
        book_row["id"], book_row["title"], book_row["publisher"], book_row["status"],
        book_row["grade"], book_row["subject"], book_row["book_text_len"], book_row["chapter_count"],
    )

    # Sanity-assert: book must be English G1 OnProd, as required by F1.7.
    if book_row["status"] != "OnProd":
        log.error("DRY RUN: book status is %r, expected 'OnProd' (D-15)", book_row["status"])
        sys.exit(1)
    if book_row["grade"] != "G1" or book_row["subject"] != "Eng":
        log.error(
            "DRY RUN: book is grade=%r subject=%r, expected G1/Eng (D-15)",
            book_row["grade"], book_row["subject"],
        )
        sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--book-id", type=int, default=1171,
                        help="fde_staging.book_library_book.id to import (default: 1171, per D-15)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Read from fde_staging + Dars to validate access; perform no writes")
    parser.add_argument("--verbose", action="store_true", help="Enable DEBUG-level logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    _load_env()

    return asyncio.run(run(book_id=args.book_id, dry_run=args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
