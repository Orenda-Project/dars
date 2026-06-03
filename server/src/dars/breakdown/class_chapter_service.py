"""
Class chapter path — the class's own teaching path (D-2).

Picking a chapter records a `class_chapters` row (which chapter, in what order,
with teacher-set dates); breaking it down is a separate flow (D-5, see
`chapter_plan_service.generate_chapter_plan`). The global Syllabus Breakdown is
advisory and only supplies a *recommendation* for the next chapter (D-3).

Chapter status is derived from the CST's generated class slots, never stored
(D-4). Reorder/remove lock started chapters in place (D-6): the past is
immutable, the future is freely reorderable.

This module is the path service named in 03-phase-1-class-chapters.md (F1.2–F1.5).
"""
import logging
from datetime import date
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


def validate_reorder(
    current_order: list[UUID],
    current_statuses: dict[UUID, str],
    submitted_order: list[UUID],
) -> None:
    """
    Validate a reorder against the D-6 lock rule. Raises ValueError if invalid.

    Rules:
      1. The submitted set must exactly equal the current path's set
         (every id present, no extras, no duplicates).
      2. Started chapters (status != yet_to_start) are locked to the front,
         in their current relative order. A submitted order is rejected if it
         moves any non-yet_to_start chapter out of its current leading
         position — i.e. the leading prefix of started chapters must appear
         first in `submitted_order`, in the same relative order they hold now.

    `current_order` is the path ordered by position (ascending).
    `current_statuses` maps each book_chapter_id to its derived status.
    """
    current_set = set(current_order)
    submitted_set = set(submitted_order)
    if len(submitted_order) != len(submitted_set):
        raise ValueError("reorder contains duplicate chapters")
    if submitted_set != current_set:
        raise ValueError(
            "reorder must include exactly the chapters currently in the path"
        )

    # The locked prefix = the contiguous run of started chapters at the front
    # of the *current* order. Per D-6 a partially-taught chapter is in_progress
    # and stays put; started chapters keep their current relative order at the
    # front. We require that same prefix to lead the submitted order unchanged.
    locked_prefix: list[UUID] = []
    for bc_id in current_order:
        if current_statuses.get(bc_id, STATUS_YET_TO_START) != STATUS_YET_TO_START:
            locked_prefix.append(bc_id)
        else:
            break

    if submitted_order[: len(locked_prefix)] != locked_prefix:
        raise ValueError(
            "started chapters are locked and must stay at the front "
            "in their current order"
        )


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
                "slot_count": await chapter_slot_count(
                    conn, cst_id, r["start_date"], r["end_date"]
                ),
                "status": derive_chapter_status(
                    status_map.get(r["book_chapter_id"], [])
                ),
            }
        )
    log.info("list_class_path: exit cst=%s chapters=%d", cst_id, len(path))
    return path


async def pick_chapter(
    conn: asyncpg.Connection,
    cst_id: UUID,
    org_id: UUID,
    book_chapter_id: UUID,
) -> dict:
    """
    Record a chapter choice (Action 1, D-2): insert a `class_chapters` row at
    the end of the path (max(position)+1, or 1 if empty). Undated (D-7).

    Raises ValueError (→ 422) if the chapter is already in the path, or if the
    book_chapter_id doesn't belong to the CST's book.
    """
    log.info(
        "pick_chapter: entry cst=%s chapter=%s org=%s",
        cst_id, book_chapter_id, org_id,
    )

    # Validate the chapter belongs to the CST's book. Resolve the CST's book_id
    # via the shared resolver; fall back to syllabus context if the CST has no
    # book_id set directly.
    ctx = await resolve_cst_syllabus_context(conn, cst_id)
    chapter_book_id = await conn.fetchval(
        "SELECT book_id FROM book_chapters WHERE id = $1", book_chapter_id
    )
    if chapter_book_id is None:
        raise ValueError("chapter not found")
    if ctx.book_id is not None and chapter_book_id != ctx.book_id:
        raise ValueError("chapter does not belong to this class's book")

    # Already in path? (also enforced by the unique constraint, but we want a
    # clean 422 not a DB integrity error).
    exists = await conn.fetchval(
        "SELECT 1 FROM class_chapters WHERE cst_id = $1 AND book_chapter_id = $2",
        cst_id, book_chapter_id,
    )
    if exists:
        raise ValueError("chapter already in the class path")

    async with conn.transaction():
        next_pos = await conn.fetchval(
            "SELECT coalesce(max(position), 0) + 1 FROM class_chapters WHERE cst_id = $1",
            cst_id,
        )
        row = await conn.fetchrow(
            """
            INSERT INTO class_chapters (org_id, cst_id, book_chapter_id, position)
            VALUES ($1, $2, $3, $4)
            RETURNING book_chapter_id, position, start_date, end_date
            """,
            org_id, cst_id, book_chapter_id, next_pos,
        )
    log.info(
        "pick_chapter: exit cst=%s chapter=%s position=%d",
        cst_id, book_chapter_id, row["position"],
    )
    return dict(row)


async def set_chapter_dates(
    conn: asyncpg.Connection,
    cst_id: UUID,
    book_chapter_id: UUID,
    start_date: date | None,
    end_date: date | None,
) -> dict:
    """
    Set a path chapter's date range (D-7). Raises ValueError (→ 422) if the
    chapter isn't in the path.

    Only the dates that are provided (non-None) are updated; a None leaves the
    existing value untouched (COALESCE). This is the fix for the bug where
    saving just the end date wiped the start date (and vice versa) — the UI
    sends one field at a time. Clearing a date via this endpoint is therefore
    unsupported (acceptable for the prototype).
    """
    log.info(
        "set_chapter_dates: entry cst=%s chapter=%s start=%s end=%s",
        cst_id, book_chapter_id, start_date, end_date,
    )
    row = await conn.fetchrow(
        """
        UPDATE class_chapters
           SET start_date = COALESCE($3, start_date),
               end_date   = COALESCE($4, end_date),
               updated_at = now()
         WHERE cst_id = $1 AND book_chapter_id = $2
        RETURNING book_chapter_id, position, start_date, end_date
        """,
        cst_id, book_chapter_id, start_date, end_date,
    )
    if row is None:
        raise ValueError("chapter not in the class path")
    log.info(
        "set_chapter_dates: exit cst=%s chapter=%s", cst_id, book_chapter_id,
    )
    return dict(row)


async def remove_chapter(
    conn: asyncpg.Connection,
    cst_id: UUID,
    book_chapter_id: UUID,
) -> None:
    """
    Remove a chapter from the path (D-2). Does NOT touch generated class slots.

    Raises ValueError (→ 422) if the chapter isn't in the path, or if it has
    started (status != yet_to_start) — the past is locked (D-6).
    """
    log.info(
        "remove_chapter: entry cst=%s chapter=%s", cst_id, book_chapter_id,
    )
    exists = await conn.fetchval(
        "SELECT 1 FROM class_chapters WHERE cst_id = $1 AND book_chapter_id = $2",
        cst_id, book_chapter_id,
    )
    if not exists:
        raise ValueError("chapter not in the class path")

    status_map = await _chapter_terminal_map(conn, cst_id)
    status = derive_chapter_status(status_map.get(book_chapter_id, []))
    if status != STATUS_YET_TO_START:
        raise ValueError(
            "cannot remove a chapter that has already started "
            f"(status: {status})"
        )

    await conn.execute(
        "DELETE FROM class_chapters WHERE cst_id = $1 AND book_chapter_id = $2",
        cst_id, book_chapter_id,
    )
    log.info("remove_chapter: exit cst=%s chapter=%s removed", cst_id, book_chapter_id)


async def reorder_path(
    conn: asyncpg.Connection,
    cst_id: UUID,
    ordered_book_chapter_ids: list[UUID],
) -> list[dict]:
    """
    Rewrite the path positions to 1..N in one transaction (D-6).

    The submitted set must exactly equal the current path's set, and started
    (non-yet_to_start) chapters must stay at the front in their current
    relative order (the past is locked). Raises ValueError (→ 422) otherwise.

    Returns the reordered path (same shape as `list_class_path`).
    """
    log.info(
        "reorder_path: entry cst=%s submitted=%d",
        cst_id, len(ordered_book_chapter_ids),
    )
    rows = await conn.fetch(
        "SELECT book_chapter_id, position FROM class_chapters WHERE cst_id = $1 ORDER BY position",
        cst_id,
    )
    current_order = [r["book_chapter_id"] for r in rows]
    status_map = await _chapter_terminal_map(conn, cst_id)
    current_statuses = {
        bc_id: derive_chapter_status(status_map.get(bc_id, []))
        for bc_id in current_order
    }

    # Pure validation (raises ValueError on any violation).
    validate_reorder(current_order, current_statuses, ordered_book_chapter_ids)

    # Rewrite positions 1..N. The (cst_id, position) unique constraint means we
    # can't pass through a colliding intermediate state, so bump every row out
    # of range first, then set the final positions (all inside one transaction).
    async with conn.transaction():
        await conn.execute(
            "UPDATE class_chapters SET position = position + $2 WHERE cst_id = $1",
            cst_id, len(ordered_book_chapter_ids) + 1,
        )
        for new_pos, bc_id in enumerate(ordered_book_chapter_ids, start=1):
            await conn.execute(
                """
                UPDATE class_chapters
                   SET position = $3, updated_at = now()
                 WHERE cst_id = $1 AND book_chapter_id = $2
                """,
                cst_id, bc_id, new_pos,
            )
    log.info("reorder_path: exit cst=%s reordered=%d", cst_id, len(ordered_book_chapter_ids))
    return await list_class_path(conn, cst_id)


async def recommended_next_chapter(
    conn: asyncpg.Connection, cst_id: UUID
) -> dict | None:
    """
    The global default's next-recommended chapter (D-3): the lowest-`position`
    `syllabus_chapters` chapter whose `book_chapter_id` is NOT already in the
    class path. Empty path → the global's first chapter. None if the path
    already covers every global chapter (or there's no published global).

    Returns {book_chapter_id, chapter_number, title} or None.
    """
    log.info("recommended_next_chapter: entry cst=%s", cst_id)
    ctx = await resolve_cst_syllabus_context(conn, cst_id)
    if ctx.syllabus_breakdown_id is None:
        log.info("recommended_next_chapter: exit cst=%s no global syllabus", cst_id)
        return None

    row = await conn.fetchrow(
        """
        SELECT sch.book_chapter_id, bc.chapter_number, bc.title
          FROM syllabus_chapters sch
          JOIN book_chapters bc ON bc.id = sch.book_chapter_id
         WHERE sch.syllabus_breakdown_id = $1
           AND sch.book_chapter_id NOT IN (
                 SELECT book_chapter_id FROM class_chapters WHERE cst_id = $2
           )
         ORDER BY sch.position
         LIMIT 1
        """,
        ctx.syllabus_breakdown_id, cst_id,
    )
    if row is None:
        log.info("recommended_next_chapter: exit cst=%s path covers global", cst_id)
        return None
    log.info(
        "recommended_next_chapter: exit cst=%s chapter=%s",
        cst_id, row["book_chapter_id"],
    )
    return {
        "book_chapter_id": row["book_chapter_id"],
        "chapter_number": row["chapter_number"],
        "title": row["title"],
    }
