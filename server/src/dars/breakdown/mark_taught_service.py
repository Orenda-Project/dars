"""
F2.12 — Mark-taught flow for class lesson + assessment slots.

Per the phase doc + D-5, D-11, D-67, D-70: each action runs in one DB
transaction and:
    1. Inserts a slot_progress row (append-only event log)
    2. Updates the slot's materialized `status` column
    3. For lesson 'taught' actions, upserts cst_sub_slo_coverage to
       'taught' for every sub-SLO linked to the slot's topic (D-5).
    4. Recomputes cst_state.current_sequence_position =
       max(position of any slot with terminal action) + 1.

Out-of-order completion is allowed; positions are recomputed from the
event log so a late "mark Day 2" doesn't undo an earlier "mark Day 3".
"""
import logging
from dataclasses import dataclass
from datetime import date
from uuid import UUID

import asyncpg

log = logging.getLogger("breakdown.mark_taught")


_LESSON_TERMINAL_ACTIONS = {"taught", "skipped"}
_ASSESSMENT_TERMINAL_ACTIONS = {"completed", "skipped"}


@dataclass
class MarkTaughtResult:
    cst_id: UUID
    slot_id: UUID
    slot_kind: str
    action: str
    occurred_on: date
    new_sequence_position: int
    sub_slo_coverage_updates: int = 0


async def _recompute_sequence_position(
    conn: asyncpg.Connection, cst_id: UUID
) -> int:
    """
    Position = max(position of any slot with terminal slot_progress) + 1.
    Joins both lesson + assessment slots since both contribute to the
    sequence.
    """
    row = await conn.fetchrow(
        """
        WITH lesson AS (
            SELECT COALESCE(MAX(s.position), 0) AS p
            FROM slot_progress sp
            JOIN class_lesson_slots s ON s.id = sp.slot_id
            WHERE sp.cst_id = $1 AND sp.slot_kind = 'lesson'
        ),
        assess AS (
            SELECT COALESCE(MAX(s.position), 0) AS p
            FROM slot_progress sp
            JOIN class_assessment_slots s ON s.id = sp.slot_id
            WHERE sp.cst_id = $1 AND sp.slot_kind = 'assessment'
        )
        SELECT GREATEST((SELECT p FROM lesson), (SELECT p FROM assess)) AS max_pos
        """,
        cst_id,
    )
    max_pos = row["max_pos"] if row else 0
    new_pos = max_pos + 1
    await conn.execute(
        """
        INSERT INTO cst_state (cst_id, current_sequence_position, joined_at_position, last_marked_at)
        VALUES ($1, $2, 1, now())
        ON CONFLICT (cst_id) DO UPDATE
        SET current_sequence_position = EXCLUDED.current_sequence_position,
            last_marked_at = now(),
            updated_at = now()
        """,
        cst_id, new_pos,
    )
    return new_pos


async def _update_sub_slo_coverage(
    conn: asyncpg.Connection, cst_id: UUID, topic_id: UUID | None
) -> int:
    if topic_id is None:
        return 0
    sub_slos = await conn.fetch(
        "SELECT sub_slo_id FROM topic_sub_slos WHERE topic_id = $1",
        topic_id,
    )
    if not sub_slos:
        return 0
    for r in sub_slos:
        await conn.execute(
            """
            INSERT INTO cst_sub_slo_coverage (cst_id, sub_slo_id, status, marked_at)
            VALUES ($1, $2, 'taught', now())
            ON CONFLICT (cst_id, sub_slo_id) DO UPDATE
            SET status = 'taught', marked_at = now()
            """,
            cst_id, r["sub_slo_id"],
        )
    return len(sub_slos)


async def mark_lesson_slot(
    conn: asyncpg.Connection,
    *,
    slot_id: UUID,
    action: str,
    occurred_on: date | None = None,
    notes: str | None = None,
) -> MarkTaughtResult:
    if action not in _LESSON_TERMINAL_ACTIONS:
        raise ValueError(
            f"action must be one of {sorted(_LESSON_TERMINAL_ACTIONS)} for a lesson slot"
        )
    slot = await conn.fetchrow(
        """
        SELECT id, cst_id, topic_id, position, org_id
        FROM class_lesson_slots
        WHERE id = $1
        """,
        slot_id,
    )
    if slot is None:
        raise ValueError(f"class_lesson_slot {slot_id} not found")

    cst_id = slot["cst_id"]
    occurred = occurred_on or date.today()
    new_status = "taught" if action == "taught" else "skipped"

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO slot_progress (cst_id, slot_kind, slot_id, action, occurred_on, notes)
            VALUES ($1, 'lesson', $2, $3, $4, $5)
            """,
            cst_id, slot_id, action, occurred, notes,
        )
        await conn.execute(
            """
            UPDATE class_lesson_slots
            SET status = $1, updated_at = now()
            WHERE id = $2
            """,
            new_status, slot_id,
        )
        coverage_updates = 0
        if action == "taught":
            coverage_updates = await _update_sub_slo_coverage(
                conn, cst_id, slot["topic_id"]
            )
        new_pos = await _recompute_sequence_position(conn, cst_id)

    log.info(
        "mark_lesson_slot: cst=%s slot=%s action=%s pos=%d coverage_updates=%d",
        cst_id, slot_id, action, new_pos, coverage_updates,
    )
    return MarkTaughtResult(
        cst_id=cst_id,
        slot_id=slot_id,
        slot_kind="lesson",
        action=action,
        occurred_on=occurred,
        new_sequence_position=new_pos,
        sub_slo_coverage_updates=coverage_updates,
    )


async def mark_assessment_slot(
    conn: asyncpg.Connection,
    *,
    slot_id: UUID,
    action: str,
    occurred_on: date | None = None,
    notes: str | None = None,
) -> MarkTaughtResult:
    if action not in _ASSESSMENT_TERMINAL_ACTIONS:
        raise ValueError(
            f"action must be one of {sorted(_ASSESSMENT_TERMINAL_ACTIONS)} for an assessment slot"
        )
    slot = await conn.fetchrow(
        """
        SELECT id, cst_id, position
        FROM class_assessment_slots
        WHERE id = $1
        """,
        slot_id,
    )
    if slot is None:
        raise ValueError(f"class_assessment_slot {slot_id} not found")

    cst_id = slot["cst_id"]
    occurred = occurred_on or date.today()
    new_status = "completed" if action == "completed" else "skipped"

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO slot_progress (cst_id, slot_kind, slot_id, action, occurred_on, notes)
            VALUES ($1, 'assessment', $2, $3, $4, $5)
            """,
            cst_id, slot_id, action, occurred, notes,
        )
        await conn.execute(
            """
            UPDATE class_assessment_slots
            SET status = $1, updated_at = now()
            WHERE id = $2
            """,
            new_status, slot_id,
        )
        # Assessments don't drive sub-SLO coverage in this hop; mastery
        # rollups are computed separately (Phase 2 doesn't ship them).
        new_pos = await _recompute_sequence_position(conn, cst_id)

    log.info(
        "mark_assessment_slot: cst=%s slot=%s action=%s pos=%d",
        cst_id, slot_id, action, new_pos,
    )
    return MarkTaughtResult(
        cst_id=cst_id,
        slot_id=slot_id,
        slot_kind="assessment",
        action=action,
        occurred_on=occurred,
        new_sequence_position=new_pos,
    )
