"""
Slot-mutation primitives — Dynamic Chapter Planner, Phase 1 (F-1.2, F-1.3).

The live plan is the per-CST realized slot sequence across BOTH
`class_lesson_slots` and `class_assessment_slots`, which share ONE position
number space (`UNIQUE (cst_id, position)` on each; the projector merges them by
position — D-8). To insert or remove a slot we open/close a one-position gap by
renumbering EVERY downstream row in BOTH tables, in a single transaction.

Renumber strategy (D-12): two-step large-offset. A naive
`UPDATE ... SET position = position + 1 WHERE position > N` can transiently
violate `UNIQUE (cst_id, position)` mid-statement on engines that check the
constraint per-row (sqlite does; asyncpg/Postgres checks at statement end but
we keep ONE portable path). So we first shift the affected rows out of the live
range by a large offset (`_RENUMBER_OFFSET`), then settle them to their final
positions. No transient collision on either engine.

All mutation SQL is raw and portable (asyncpg `$N` placeholders; no
PG-only functions), so the same code runs against sqlite in tests (D-11).

Structured logging per CLAUDE.md rule 11: entry/exit at INFO with cst_id +
counts; errors at ERROR with exc_info=True.
"""
import logging
from uuid import UUID, uuid4

log = logging.getLogger(__name__)

# Large enough to clear any realistic per-CST position range (one slot = one
# teaching day; a year is < ~250). Keeps the two-step renumber collision-free.
_RENUMBER_OFFSET = 1_000_000


# ---------------------------------------------------------------------------
# Taught-lock invariant (F-1.3, D-7)
# ---------------------------------------------------------------------------


async def _last_taught_position(conn, cst_id: UUID) -> int:
    """
    The CST's highest position carrying a settled status — `taught` lessons or
    `completed` assessments — across BOTH slot tables. 0 when nothing is settled
    yet (the whole plan is mutable).
    """
    val = await conn.fetchval(
        """
        SELECT max(p) FROM (
            SELECT position AS p FROM class_lesson_slots
              WHERE cst_id = $1 AND status = 'taught'
            UNION ALL
            SELECT position AS p FROM class_assessment_slots
              WHERE cst_id = $1 AND status = 'completed'
        ) settled
        """,
        cst_id,
    )
    return val or 0


async def _assert_mutable(conn, cst_id: UUID, after_position: int) -> None:
    """
    Reject any mutation at or before the CST's last taught/completed position
    (D-7). Only future `planned`/`scheduled` slots may move; the past is frozen.

    `after_position` is the position the mutation operates at or just after
    (insert opens a gap at `after_position + 1`; remove deletes `after_position`;
    consume-flex repurposes a slot strictly after `after_position`). We require
    `after_position >= last_taught` so the touched/shifted rows are all > the
    frozen boundary.

    Raises ValueError (route layer maps to 422).
    """
    last_taught = await _last_taught_position(conn, cst_id)
    if after_position < last_taught:
        raise ValueError(
            f"cannot mutate at/before the last taught position "
            f"(last_taught={last_taught}, requested after_position={after_position})"
        )


# ---------------------------------------------------------------------------
# Renumber helpers (D-8, D-12) — portable two-step large-offset
# ---------------------------------------------------------------------------


async def _shift_positions(conn, cst_id: UUID, gt_position: int, delta: int) -> None:
    """
    Move every lesson AND assessment row with `position > gt_position` by
    `delta`, collision-free, in two steps:
      1. park: position += _RENUMBER_OFFSET   (vacates the live range)
      2. settle: position += (delta - _RENUMBER_OFFSET)

    Both tables are touched so the shared position sequence stays gap-correct.
    Must run inside the caller's transaction.
    """
    for table in ("class_lesson_slots", "class_assessment_slots"):
        # Step 1 — park out of the live range.
        await conn.execute(
            f"""
            UPDATE {table}
               SET position = position + {_RENUMBER_OFFSET}
             WHERE cst_id = $1 AND position > $2
            """,
            cst_id, gt_position,
        )
        # Step 2 — settle to final position.
        await conn.execute(
            f"""
            UPDATE {table}
               SET position = position + ($3)
             WHERE cst_id = $1 AND position > $2
            """,
            cst_id, gt_position + _RENUMBER_OFFSET, delta - _RENUMBER_OFFSET,
        )


# ---------------------------------------------------------------------------
# Public mutation primitives (F-1.2)
# ---------------------------------------------------------------------------


async def insert_lesson_slot(
    conn,
    cst_id: UUID,
    after_position: int,
    *,
    topic_ids: list[UUID],
    lp_type: str | None,
    origin: str = "manual",
    reteach_for_sub_slo_id: UUID | None = None,
    flex: bool = False,
) -> UUID:
    """
    Insert a new `planned` lesson slot at `after_position + 1`, shifting every
    downstream lesson AND assessment row (position > after_position) up by one
    (D-8), then writing the slot + its `class_lesson_slot_topics` rows. Single
    transaction. Returns the new slot id.

    Raises ValueError if the insertion point is at/before the last taught
    position (F-1.3).
    """
    log.info(
        "insert_lesson_slot: entry cst=%s after_position=%s topics=%d "
        "origin=%s flex=%s reteach_for=%s",
        cst_id, after_position, len(topic_ids), origin, flex,
        reteach_for_sub_slo_id,
    )
    try:
        async with conn.transaction():
            await _assert_mutable(conn, cst_id, after_position)

            org_id = await conn.fetchval(
                "SELECT org_id FROM class_subject_teachers WHERE id = $1",
                cst_id,
            )
            if org_id is None:
                raise ValueError(f"cst {cst_id} not found")

            # Open the one-position gap at after_position + 1.
            await _shift_positions(conn, cst_id, after_position, delta=1)

            new_position = after_position + 1
            lead_topic_id = topic_ids[0] if topic_ids else None
            # Generate the id in Python rather than relying on a DB-side
            # gen_random_uuid() default + RETURNING (D-12): portable to sqlite
            # (whose test schema has no UUID default), identical on Postgres
            # (the column accepts an explicit id).
            slot_id = uuid4()
            await conn.execute(
                """
                INSERT INTO class_lesson_slots
                  (id, org_id, cst_id, position, slot_type, lp_type, topic_id,
                   status, origin, reteach_for_sub_slo_id, flex)
                VALUES ($1, $2, $3, $4, 'lesson', $5, $6, 'planned', $7, $8, $9)
                """,
                slot_id, org_id, cst_id, new_position, lp_type, lead_topic_id,
                origin, reteach_for_sub_slo_id, flex,
            )
            for member_pos, t_id in enumerate(topic_ids, start=1):
                await conn.execute(
                    """
                    INSERT INTO class_lesson_slot_topics
                      (class_lesson_slot_id, topic_id, position)
                    VALUES ($1, $2, $3)
                    """,
                    slot_id, t_id, member_pos,
                )

        log.info(
            "insert_lesson_slot: exit cst=%s slot=%s position=%d topics=%d",
            cst_id, slot_id, new_position, len(topic_ids),
        )
        return slot_id
    except Exception:
        log.error(
            "insert_lesson_slot: error cst=%s after_position=%s",
            cst_id, after_position, exc_info=True,
        )
        raise


async def remove_slot(conn, cst_id: UUID, position: int) -> None:
    """
    Remove the slot at `position` (lesson OR assessment) and close the gap by
    shifting every downstream row in BOTH tables down by one (D-8). Single
    transaction.

    Refuses a settled slot: a `taught` lesson or `completed` assessment raises
    ValueError (also caught by the taught-lock, but checked explicitly for a
    clear message). Raises ValueError if no slot exists at `position`.
    """
    log.info("remove_slot: entry cst=%s position=%s", cst_id, position)
    try:
        async with conn.transaction():
            # The taught-lock forbids touching at/before the last settled
            # position; removing `position` shifts everything after it.
            await _assert_mutable(conn, cst_id, position)

            lesson = await conn.fetchrow(
                "SELECT id, status FROM class_lesson_slots "
                "WHERE cst_id = $1 AND position = $2",
                cst_id, position,
            )
            assessment = await conn.fetchrow(
                "SELECT id, status FROM class_assessment_slots "
                "WHERE cst_id = $1 AND position = $2",
                cst_id, position,
            )
            if lesson is None and assessment is None:
                raise ValueError(
                    f"no slot at position {position} for cst {cst_id}"
                )

            if lesson is not None:
                if lesson["status"] != "planned":
                    raise ValueError(
                        f"cannot remove lesson slot in status "
                        f"'{lesson['status']}' (only 'planned' is removable)"
                    )
                await conn.execute(
                    "DELETE FROM class_lesson_slot_topics "
                    "WHERE class_lesson_slot_id = $1",
                    lesson["id"],
                )
                await conn.execute(
                    "DELETE FROM class_lesson_slots WHERE id = $1", lesson["id"]
                )
            if assessment is not None:
                if assessment["status"] != "scheduled":
                    raise ValueError(
                        f"cannot remove assessment slot in status "
                        f"'{assessment['status']}' (only 'scheduled' is removable)"
                    )
                await conn.execute(
                    "DELETE FROM class_assessment_slot_topics "
                    "WHERE class_assessment_slot_id = $1",
                    assessment["id"],
                )
                await conn.execute(
                    "DELETE FROM class_assessment_slots WHERE id = $1",
                    assessment["id"],
                )

            # Close the gap: shift the tail (> position) down by one.
            await _shift_positions(conn, cst_id, position, delta=-1)

        log.info("remove_slot: exit cst=%s position=%s removed", cst_id, position)
    except Exception:
        log.error(
            "remove_slot: error cst=%s position=%s", cst_id, position,
            exc_info=True,
        )
        raise


async def consume_flex_slot(
    conn,
    cst_id: UUID,
    after_position: int,
    *,
    reteach_for_sub_slo_id: UUID | None,
    lp_type: str | None,
    topic_ids: list[UUID],
) -> UUID | None:
    """
    Repurpose the nearest downstream droppable flex lesson slot for a reteach,
    in place — no position shift (D-5/D-12). Finds the lowest-position
    `flex=true planned` lesson slot at `position > after_position`, flips it to
    `origin='reteach'`, `flex=false`, sets `reteach_for_sub_slo_id`, rewrites its
    topics, and clears `generated_lp_id`. Single transaction.

    Returns the repurposed slot id, or None when there is no downstream flex
    slot (the caller then decides whether to `insert_lesson_slot`).
    """
    log.info(
        "consume_flex_slot: entry cst=%s after_position=%s topics=%d reteach_for=%s",
        cst_id, after_position, len(topic_ids), reteach_for_sub_slo_id,
    )
    try:
        async with conn.transaction():
            await _assert_mutable(conn, cst_id, after_position)

            row = await conn.fetchrow(
                """
                SELECT id FROM class_lesson_slots
                 WHERE cst_id = $1
                   AND position > $2
                   AND flex = $3
                   AND status = 'planned'
                 ORDER BY position
                 LIMIT 1
                """,
                cst_id, after_position, True,
            )
            if row is None:
                log.info(
                    "consume_flex_slot: exit cst=%s after_position=%s — "
                    "no downstream flex slot",
                    cst_id, after_position,
                )
                return None

            slot_id = row["id"]
            lead_topic_id = topic_ids[0] if topic_ids else None
            await conn.execute(
                """
                UPDATE class_lesson_slots
                   SET origin = 'reteach',
                       flex = $2,
                       reteach_for_sub_slo_id = $3,
                       lp_type = $4,
                       topic_id = $5,
                       generated_lp_id = NULL
                 WHERE id = $1
                """,
                slot_id, False, reteach_for_sub_slo_id, lp_type, lead_topic_id,
            )
            await conn.execute(
                "DELETE FROM class_lesson_slot_topics "
                "WHERE class_lesson_slot_id = $1",
                slot_id,
            )
            for member_pos, t_id in enumerate(topic_ids, start=1):
                await conn.execute(
                    """
                    INSERT INTO class_lesson_slot_topics
                      (class_lesson_slot_id, topic_id, position)
                    VALUES ($1, $2, $3)
                    """,
                    slot_id, t_id, member_pos,
                )

        log.info(
            "consume_flex_slot: exit cst=%s slot=%s repurposed topics=%d",
            cst_id, slot_id, len(topic_ids),
        )
        return slot_id
    except Exception:
        log.error(
            "consume_flex_slot: error cst=%s after_position=%s",
            cst_id, after_position, exc_info=True,
        )
        raise
