"""
Mid-year onboarding.

A teacher onboarding mid-year declares (chapter_position, chapter_day):
the Nth chapter of their syllabus and the Nth teaching day within that
chapter's generated Chapter Plan. We resolve that to the class slot's global
`position` and write cst_state.

Post the syllabus re-architecture, this resolves against the CST's own
generated class slots (class_lesson_slots / class_assessment_slots stamped
with book_chapter_id, D-16) — there is no class-scope breakdown anymore.
`chapter_position` is the 1-based index into the CST's syllabus chapters
(ordered by book chapter_number); `chapter_day` is the 1-based ordinal of the
slot within that chapter's slots (ordered by global position).

Slots before joined_at_position remain `planned` with no slot_progress event.
"""
import logging
from dataclasses import dataclass
from uuid import UUID

import asyncpg

from dars.breakdown.chapter_plan_service import resolve_cst_syllabus_context

log = logging.getLogger("breakdown.onboarding")


@dataclass
class OnboardResult:
    cst_id: UUID
    resolved_position: int
    joined_at_position: int


async def _chapter_at_position(
    conn: asyncpg.Connection, syllabus_breakdown_id: UUID, chapter_position: int
) -> asyncpg.Record | None:
    """The book chapter at the 1-based syllabus position (by book chapter_number)."""
    return await conn.fetchrow(
        """
        SELECT sch.book_chapter_id, bc.chapter_number
        FROM syllabus_chapters sch
        JOIN book_chapters bc ON bc.id = sch.book_chapter_id
        WHERE sch.syllabus_breakdown_id = $1
        ORDER BY bc.chapter_number
        OFFSET $2 LIMIT 1
        """,
        syllabus_breakdown_id, chapter_position - 1,
    )


async def onboard_cst(
    conn: asyncpg.Connection,
    *,
    cst_id: UUID,
    chapter_position: int,
    chapter_day: int,
) -> OnboardResult:
    if chapter_position < 1 or chapter_day < 1:
        raise ValueError("chapter_position and chapter_day must be >= 1")

    ctx = await resolve_cst_syllabus_context(conn, cst_id)
    if ctx.syllabus_breakdown_id is None:
        raise ValueError(
            f"cst {cst_id} has no published syllabus breakdown; cannot onboard"
        )

    chapter = await _chapter_at_position(
        conn, ctx.syllabus_breakdown_id, chapter_position
    )
    if chapter is None:
        raise ValueError(
            f"syllabus has no chapter at position {chapter_position}"
        )
    book_chapter_id = chapter["book_chapter_id"]

    # The Nth generated class slot (lesson or assessment) within that chapter,
    # ordered by the global position sequence.
    slot = await conn.fetchrow(
        """
        SELECT position FROM (
            SELECT position FROM class_lesson_slots
              WHERE cst_id = $1 AND book_chapter_id = $2
            UNION ALL
            SELECT position FROM class_assessment_slots
              WHERE cst_id = $1 AND book_chapter_id = $2
        ) s
        ORDER BY position
        OFFSET $3 LIMIT 1
        """,
        cst_id, book_chapter_id, chapter_day - 1,
    )
    if slot is None:
        raise ValueError(
            f"chapter {chapter_position} has no generated slot at day {chapter_day} "
            "(break the chapter down first)"
        )

    resolved_position = slot["position"]
    await conn.execute(
        """
        INSERT INTO cst_state (cst_id, current_sequence_position, joined_at_position, updated_at)
        VALUES ($1, $2, $2, now())
        ON CONFLICT (cst_id) DO UPDATE
        SET current_sequence_position = EXCLUDED.current_sequence_position,
            joined_at_position = EXCLUDED.joined_at_position,
            updated_at = now()
        """,
        cst_id, resolved_position,
    )
    log.info(
        "onboard_cst: cst=%s chapter=%d day=%d → position=%d",
        cst_id, chapter_position, chapter_day, resolved_position,
    )
    return OnboardResult(
        cst_id=cst_id,
        resolved_position=resolved_position,
        joined_at_position=resolved_position,
    )
