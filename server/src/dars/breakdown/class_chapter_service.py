"""
Class chapter path — the class's own teaching path (D-2).

The class path is **auto-seeded** from the org's published Syllabus Breakdown
(`syllabus_chapters`) on first read of the syllabus GET (D-10):
`seed_class_chapters_from_breakdown` copies every chapter (book_chapter_id,
position, dates) once, idempotently, clean-install only. The teacher then
**edits on top** — pick / set-dates / reorder / remove — for that class only
(Phase 3 Revival, D-9). The global Syllabus Breakdown stays advisory (D-1) and
also supplies a *recommendation* for the next chapter (D-3). Breaking a chapter
down is a separate flow (D-5, see `chapter_plan_service.generate_chapter_plan`).

Chapter status is derived from the CST's generated class slots, never stored
(D-4). Reorder/remove lock started chapters in place (D-6): the past is
immutable, the future is freely reorderable. `remove_chapter` additionally
rejects any chapter with generated slots so it never orphans a plan (D-11).

This module is the path service named in 03-phase-1-class-chapters.md (F1.2–F1.5)
and revived in 05-phase-3-revival.md (F3.1).
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


def _norm_uuid(value) -> UUID | None:
    """
    Canonicalise a DB-returned UUID to a stdlib ``uuid.UUID``.

    asyncpg returns UUID columns as ``asyncpg.pgproto.pgproto.UUID``. Those
    compare and hash equal to ``uuid.UUID`` today, but the map in
    ``_chapter_terminal_map`` is keyed by one query's rows and looked up against
    another's — so we pin both sides to a single canonical type to keep the
    ``dict`` lookup type-stable regardless of the active asyncpg codec
    (CLAUDE.md: prefer a type-stable comparison over relying on cross-type hash
    equality). ``None`` passes through unchanged.
    """
    if value is None:
        return None
    return UUID(str(value))


async def _chapter_terminal_map(
    conn: asyncpg.Connection, cst_id: UUID
) -> dict[UUID, list[str]]:
    """
    Map each book_chapter_id in the CST's slots to the list of its slot
    statuses (lessons ∪ assessments). Drives status derivation in one query
    each table, avoiding an N+1 over chapters.

    A slot's owning chapter is resolved by COALESCE(slot.book_chapter_id,
    <chapter the slot's topics belong to>). The direct ``book_chapter_id``
    column was added later (migration 20260605, nullable) and back-filled by the
    break-it-down generator; slots created before that — or by any path that
    didn't stamp it — carry a NULL ``book_chapter_id`` yet still link to their
    chapter through topics (lesson slots via ``topic_id`` → ``topics``;
    assessment slots via ``class_assessment_slot_topics``). Relying on the direct
    column alone made those slots invisible here, so a fully-planned chapter read
    back as ``is_generated=false`` / ``yet_to_start`` (the bug this fixes). The
    COALESCE recovers the linkage; a chapter with genuinely no slots still yields
    no rows and stays ungenerated.

    Keys are canonicalised with ``_norm_uuid`` so the map is type-stable for the
    Python lookup in ``list_class_path`` regardless of asyncpg's UUID codec.
    """
    rows = await conn.fetch(
        """
        SELECT COALESCE(cls.book_chapter_id, lt.book_chapter_id) AS book_chapter_id,
               cls.status
          FROM class_lesson_slots cls
          LEFT JOIN topics lt ON lt.id = cls.topic_id
         WHERE cls.cst_id = $1
           AND COALESCE(cls.book_chapter_id, lt.book_chapter_id) IS NOT NULL
        UNION ALL
        SELECT COALESCE(cas.book_chapter_id, at.book_chapter_id) AS book_chapter_id,
               cas.status
          FROM class_assessment_slots cas
          LEFT JOIN LATERAL (
              SELECT t.book_chapter_id
                FROM class_assessment_slot_topics ast_t
                JOIN topics t ON t.id = ast_t.topic_id
               WHERE ast_t.class_assessment_slot_id = cas.id
               ORDER BY ast_t.position
               LIMIT 1
          ) at ON TRUE
         WHERE cas.cst_id = $1
           AND COALESCE(cas.book_chapter_id, at.book_chapter_id) IS NOT NULL
        """,
        cst_id,
    )
    out: dict[UUID, list[str]] = {}
    for r in rows:
        key = _norm_uuid(r["book_chapter_id"])
        if key is None:
            continue
        out.setdefault(key, []).append(r["status"])
    log.info(
        "_chapter_terminal_map: cst=%s chapters_with_slots=%d slot_rows=%d",
        cst_id, len(out), len(rows),
    )
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
        # Look up by the same canonical key type the map is keyed on.
        chapter_statuses = status_map.get(_norm_uuid(r["book_chapter_id"]), [])
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
                "is_generated": bool(chapter_statuses),
                "status": derive_chapter_status(chapter_statuses),
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


# ---------------------------------------------------------------------------
# Path mutations (Phase 3 Revival, D-9): pick / set-dates / reorder / remove.
# Layered ON TOP of the auto-seed (D-10) — they edit the seeded path; they do
# not replace it. The teacher edits their own class's path only (D-1 holds: the
# global syllabus is never touched here).
# ---------------------------------------------------------------------------


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
    Set a path chapter's date range (D-7). Patches only the bounds supplied —
    a NULL `start_date`/`end_date` argument leaves the existing column value
    untouched (COALESCE), so sending one bound doesn't wipe the other.

    Raises ValueError (→ 422) if the chapter isn't in the path.
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

    Rejects with ValueError (→ 422) when:
      - the chapter isn't in the path; or
      - the chapter has started (status != yet_to_start) — the past is locked
        (D-6); or
      - the chapter has ANY generated class slot (lesson or assessment) for
        this CST — not only terminal ones (D-11). Since the dynamic-chapter-
        planner (PR #143) added non-terminal generated slots (fresh break-down,
        reteach/flex inserts), deleting the path row would orphan them. Removal
        stays a yet-to-start, not-yet-broken-down operation; clear the plan
        first. Message surfaced to the teacher:
        "this chapter has a generated plan; clear it before removing."
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
    chapter_slot_statuses = status_map.get(_norm_uuid(book_chapter_id), [])

    # D-11: reject any chapter that has been broken down — even if no slot is
    # terminal yet — so we never orphan dynamic-planner slots.
    if chapter_slot_statuses:
        raise ValueError(
            "this chapter has a generated plan; clear it before removing."
        )

    # Defensive belt-and-braces: a chapter with no slots is yet_to_start, but
    # keep the D-6 lock explicit in case status derivation ever diverges.
    status = derive_chapter_status(chapter_slot_statuses)
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
        bc_id: derive_chapter_status(status_map.get(_norm_uuid(bc_id), []))
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
