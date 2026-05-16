"""
F2.13 — Mid-year onboarding (D-12).

A teacher onboarding mid-year declares (chapter_position, chapter_day).
We resolve that to a global sequence `position` via the CST's
published class breakdown, then write cst_state.

Slots before joined_at_position remain `planned` with no slot_progress
event. The sub-SLO coverage report (F2.12 GET endpoint) distinguishes
"unknown" (no event, position < joined_at) from "not_taught" (no event,
position >= joined_at).
"""
import logging
from dataclasses import dataclass
from uuid import UUID

import asyncpg

log = logging.getLogger("breakdown.onboarding")


@dataclass
class OnboardResult:
    cst_id: UUID
    breakdown_id: UUID
    resolved_position: int
    joined_at_position: int


async def find_class_breakdown_for_cst(
    conn: asyncpg.Connection, cst_id: UUID
) -> asyncpg.Record | None:
    """Return the most recently published class breakdown for the CST."""
    return await conn.fetchrow(
        """
        SELECT id, scope, scope_ref_id, status, created_at
        FROM breakdowns
        WHERE scope = 'class' AND scope_ref_id = $1 AND status = 'published'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        cst_id,
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

    bd = await find_class_breakdown_for_cst(conn, cst_id)
    if bd is None:
        raise ValueError(
            f"cst {cst_id} has no published class-scope breakdown; cannot onboard"
        )

    chapter = await conn.fetchrow(
        """
        SELECT id, position
        FROM breakdown_chapters
        WHERE breakdown_id = $1 AND position = $2
        """,
        bd["id"], chapter_position,
    )
    if chapter is None:
        raise ValueError(
            f"breakdown {bd['id']} has no chapter at position {chapter_position}"
        )

    slot = await conn.fetchrow(
        """
        SELECT id, position
        FROM breakdown_slots
        WHERE breakdown_chapter_id = $1 AND chapter_position = $2
        """,
        chapter["id"], chapter_day,
    )
    if slot is None:
        raise ValueError(
            f"chapter {chapter_position} has no slot at chapter_position {chapter_day}"
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
        "onboard_cst: cst=%s breakdown=%s chapter=%d day=%d → position=%d",
        cst_id, bd["id"], chapter_position, chapter_day, resolved_position,
    )
    return OnboardResult(
        cst_id=cst_id,
        breakdown_id=bd["id"],
        resolved_position=resolved_position,
        joined_at_position=resolved_position,
    )
