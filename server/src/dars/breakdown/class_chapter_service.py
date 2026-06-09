"""
Class chapter path — the class's own teaching path (D-2).

The teacher path (`class_chapters`) is now a read-only mirror of the org's
published Syllabus Breakdown (`syllabus_chapters`): `seed_class_chapters_from_
breakdown` copies every chapter (book_chapter_id, position, dates) on first
read of the syllabus GET (teacher-readonly-syllabus Phase 1, D-2). The teacher
no longer picks/reorders/dates/removes chapters — those mutation paths were
removed. Breaking a chapter down is a separate flow (see
`chapter_plan_service.generate_chapter_plan`).

Chapter status is derived from the CST's generated class slots, never stored
(D-4).
"""
import logging
from uuid import UUID

import asyncpg

from dars.breakdown.chapter_plan_service import (
    chapter_slot_count,
    resolve_cst_syllabus_context,
)

log = logging.getLogger("breakdown.class_chapter")

# Slots in any of these statuses count as "real teaching has happened" (D-4).
# Covers both class_lesson_slots (taught/skipped) and class_assessment_slots
# (completed/skipped). A 'skipped' slot still represents a decision made about
# the chapter, so it's terminal for status purposes.
TERMINAL_SLOT_STATUSES: frozenset[str] = frozenset({"taught", "completed", "skipped"})

# Chapter status values (D-4).
STATUS_YET_TO_START = "yet_to_start"
STATUS_IN_PROGRESS = "in_progress"
STATUS_DONE = "done"


# ---------------------------------------------------------------------------
# Pure helpers (no DB) — extracted so the lock + status logic is unit-testable.
# ---------------------------------------------------------------------------


def derive_chapter_status(slot_statuses: list[str]) -> str:
    """
    Derive a chapter's status from its CST slots' statuses (D-4).

    - no slots, or no terminal slot  -> 'yet_to_start'
    - some terminal, not all         -> 'in_progress'
    - all terminal (and >= 1 slot)   -> 'done'

    A picked-but-not-yet-broken-down chapter has no slots → 'yet_to_start'.
    """
    if not slot_statuses:
        return STATUS_YET_TO_START
    terminal = sum(1 for s in slot_statuses if s in TERMINAL_SLOT_STATUSES)
    if terminal == 0:
        return STATUS_YET_TO_START
    if terminal == len(slot_statuses):
        return STATUS_DONE
    return STATUS_IN_PROGRESS


# ---------------------------------------------------------------------------
# DB-facing path operations
# ---------------------------------------------------------------------------


async def _chapter_terminal_map(
    conn: asyncpg.Connection, cst_id: UUID
) -> dict[UUID, list[str]]:
    """
    Map each book_chapter_id in the CST's slots to the list of its slot
    statuses (lessons ∪ assessments). Drives status derivation in one query
    each table, avoiding an N+1 over chapters.
    """
    rows = await conn.fetch(
        """
        SELECT book_chapter_id, status
          FROM class_lesson_slots
         WHERE cst_id = $1 AND book_chapter_id IS NOT NULL
        UNION ALL
        SELECT book_chapter_id, status
          FROM class_assessment_slots
         WHERE cst_id = $1 AND book_chapter_id IS NOT NULL
        """,
        cst_id,
    )
    out: dict[UUID, list[str]] = {}
    for r in rows:
        out.setdefault(r["book_chapter_id"], []).append(r["status"])
    return out


async def list_class_path(conn: asyncpg.Connection, cst_id: UUID) -> list[dict]:
    """
    The CST's teaching path: `class_chapters` rows ordered by `position`, each
    enriched with chapter_number/title, `slot_count` (real teaching periods in
    the row's date range, via `chapter_slot_count`), and derived `status` (D-4).

    Returns a list of dicts with keys:
      book_chapter_id, position, start_date, end_date,
      chapter_number, title, slot_count, status.
    """
    log.info("list_class_path: entry cst=%s", cst_id)
    rows = await conn.fetch(
        """
        SELECT cc.book_chapter_id, cc.position, cc.start_date, cc.end_date,
               bc.chapter_number, bc.title
          FROM class_chapters cc
          JOIN book_chapters bc ON bc.id = cc.book_chapter_id
         WHERE cc.cst_id = $1
         ORDER BY cc.position
        """,
        cst_id,
    )
    status_map = await _chapter_terminal_map(conn, cst_id)

    path: list[dict] = []
    for r in rows:
        path.append(
            {
                "book_chapter_id": r["book_chapter_id"],
                "position": r["position"],
                "start_date": r["start_date"],
                "end_date": r["end_date"],
                "chapter_number": r["chapter_number"],
                "title": r["title"],
                # slot_count = projected teaching periods in the date range
                # (capacity), NOT generated slots. Used for the "{N} periods"
                # label + sizing the plan.
                "slot_count": await chapter_slot_count(
                    conn, cst_id, r["start_date"], r["end_date"]
                ),
                # is_generated = the chapter actually has generated class slots
                # (it's been broken down). Distinct from slot_count, which is
                # non-zero the moment dates are set. Drives the "Broken down ✓"
                # state + whether the Generate button shows.
                "is_generated": bool(status_map.get(r["book_chapter_id"])),
                "status": derive_chapter_status(
                    status_map.get(r["book_chapter_id"], [])
                ),
            }
        )
    log.info("list_class_path: exit cst=%s chapters=%d", cst_id, len(path))
    return path


async def seed_class_chapters_from_breakdown(
    conn: asyncpg.Connection, cst_id: UUID
) -> int:
    """
    Auto-seed the class teaching path from the CST's published org breakdown
    (D-2). The teacher path mirrors the org `syllabus_chapters` — chapters,
    positions and dates are copied verbatim; the teacher no longer edits it.

    Resolves the published `syllabus_breakdowns` for the CST's
    (curriculum, grade, subject) via `resolve_cst_syllabus_context`. If none is
    published → no-op (D-7 empty state).

    **Clean-install rule (position-collision safety, see 02-data-model Note):**
    seed ONLY when the CST has zero `class_chapters` rows. A CST with any
    pre-existing path (e.g. a legacy partial teacher-built path with arbitrary
    positions) is left untouched and logged at WARNING — copying into it could
    collide on the `(cst_id, position)` unique constraint. This makes the helper
    idempotent: a second call finds rows already present and inserts nothing.

    All inserted rows stamp `org_id` + `cst_id` (tenancy, rule 3). Dates are the
    org-decided ranges (non-null on every chapter of a published breakdown).

    Returns the number of `class_chapters` rows inserted.
    """
    log.info("seed_class_chapters_from_breakdown: entry cst=%s", cst_id)

    existing = await conn.fetchval(
        "SELECT count(*) FROM class_chapters WHERE cst_id = $1", cst_id
    )
    if existing:
        log.warning(
            "seed_class_chapters_from_breakdown: cst=%s already has %d "
            "class_chapters rows — leaving path untouched (clean-install rule)",
            cst_id, existing,
        )
        return 0

    ctx = await resolve_cst_syllabus_context(conn, cst_id)
    if ctx.syllabus_breakdown_id is None:
        log.info(
            "seed_class_chapters_from_breakdown: exit cst=%s no published "
            "breakdown — seeded 0", cst_id,
        )
        return 0

    # Resolve org_id from the CST (tenancy stamp on every inserted row).
    org_id = await conn.fetchval(
        "SELECT org_id FROM class_subject_teachers WHERE id = $1", cst_id
    )
    if org_id is None:
        raise ValueError(f"cst {cst_id} not found")

    src_rows = await conn.fetch(
        """
        SELECT book_chapter_id, position, start_date, end_date
          FROM syllabus_chapters
         WHERE syllabus_breakdown_id = $1
         ORDER BY position
        """,
        ctx.syllabus_breakdown_id,
    )

    inserted = 0
    async with conn.transaction():
        for r in src_rows:
            # ON CONFLICT guards both unique constraints; with the clean-install
            # rule the table is empty here, so every row inserts.
            status = await conn.execute(
                """
                INSERT INTO class_chapters
                    (org_id, cst_id, book_chapter_id, position, start_date, end_date)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT DO NOTHING
                """,
                org_id, cst_id, r["book_chapter_id"], r["position"],
                r["start_date"], r["end_date"],
            )
            # asyncpg returns e.g. "INSERT 0 1"; count the affected row.
            if status.endswith(" 1"):
                inserted += 1

    log.info(
        "seed_class_chapters_from_breakdown: exit cst=%s breakdown=%s inserted=%d",
        cst_id, ctx.syllabus_breakdown_id, inserted,
    )
    return inserted
