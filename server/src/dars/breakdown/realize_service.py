"""
F2.9 — Class realization: instantiate a published class-scope breakdown
into per-CST slot tables.

`realize_class_breakdown(conn, class_breakdown_id)` walks
`breakdown_slots` and creates `class_lesson_slots` + `class_assessment_slots`
(+ `class_assessment_slot_topics`) for the breakdown's CST.

Idempotent on `(cst_id, position)` UNIQUE — re-realize is safe; existing
rows are updated instead of inserted. Returns counts of inserts vs updates.

Realization is allowed on `class`-scope breakdowns only. The breakdown
may be `draft` or `published` (publish flow calls realize; the endpoint
also allows re-realize on a draft for previewing).
"""
import logging
from dataclasses import dataclass
from uuid import UUID

import asyncpg

log = logging.getLogger("breakdown.realize")


_LESSON_TYPES = {"lesson", "revision"}
_ASSESSMENT_TYPES = {"formative_assessment", "summative_assessment"}


@dataclass
class RealizationResult:
    breakdown_id: UUID
    cst_id: UUID
    lesson_slots_upserted: int = 0
    assessment_slots_upserted: int = 0
    assessment_topics_inserted: int = 0
    skipped: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.skipped is None:
            self.skipped = []


async def realize_class_breakdown(
    conn: asyncpg.Connection,
    class_breakdown_id: UUID,
) -> RealizationResult:
    bd = await conn.fetchrow(
        """
        SELECT id, scope, scope_ref_id, status
        FROM breakdowns
        WHERE id = $1
        """,
        class_breakdown_id,
    )
    if bd is None:
        raise ValueError(f"breakdown {class_breakdown_id} not found")
    if bd["scope"] != "class":
        raise ValueError(
            f"realize requires scope='class'; got {bd['scope']!r}"
        )
    cst_id = bd["scope_ref_id"]
    if cst_id is None:
        raise ValueError(f"class breakdown {class_breakdown_id} has no scope_ref_id")

    # Resolve org_id for the CST (FK column on class_*_slots).
    org_id = await conn.fetchval(
        "SELECT org_id FROM class_subject_teachers WHERE id = $1",
        cst_id,
    )
    if org_id is None:
        raise ValueError(f"cst {cst_id} not found")

    log.info(
        "realize_class_breakdown: breakdown=%s cst=%s status=%s",
        class_breakdown_id, cst_id, bd["status"],
    )

    slots = await conn.fetch(
        """
        SELECT id, position, chapter_position, slot_type, lp_type, topic_id, anchor_date
        FROM breakdown_slots
        WHERE breakdown_id = $1
        ORDER BY position
        """,
        class_breakdown_id,
    )

    result = RealizationResult(breakdown_id=class_breakdown_id, cst_id=cst_id)

    async with conn.transaction():
        for s in slots:
            if s["slot_type"] in _LESSON_TYPES:
                # Upsert into class_lesson_slots.
                await conn.execute(
                    """
                    INSERT INTO class_lesson_slots
                      (org_id, cst_id, breakdown_slot_id, position, slot_type,
                       lp_type, topic_id, anchor_date)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (cst_id, position) DO UPDATE
                    SET breakdown_slot_id = EXCLUDED.breakdown_slot_id,
                        slot_type = EXCLUDED.slot_type,
                        lp_type = EXCLUDED.lp_type,
                        topic_id = EXCLUDED.topic_id,
                        anchor_date = EXCLUDED.anchor_date,
                        updated_at = now()
                    """,
                    org_id, cst_id, s["id"], s["position"], s["slot_type"],
                    s["lp_type"], s["topic_id"], s["anchor_date"],
                )
                result.lesson_slots_upserted += 1
            elif s["slot_type"] in _ASSESSMENT_TYPES:
                assessment_type = (
                    "formative" if s["slot_type"] == "formative_assessment"
                    else "summative"
                )
                # Upsert into class_assessment_slots.
                slot_id = await conn.fetchval(
                    """
                    INSERT INTO class_assessment_slots
                      (org_id, cst_id, breakdown_slot_id, position, assessment_type, anchor_date)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (cst_id, position) DO UPDATE
                    SET breakdown_slot_id = EXCLUDED.breakdown_slot_id,
                        assessment_type = EXCLUDED.assessment_type,
                        anchor_date = EXCLUDED.anchor_date,
                        updated_at = now()
                    RETURNING id
                    """,
                    org_id, cst_id, s["id"], s["position"], assessment_type, s["anchor_date"],
                )
                # Rebuild assessment_slot_topics for this slot.
                await conn.execute(
                    "DELETE FROM class_assessment_slot_topics WHERE class_assessment_slot_id = $1",
                    slot_id,
                )
                extras = await conn.fetch(
                    """
                    SELECT topic_id, position
                    FROM breakdown_slot_topics
                    WHERE breakdown_slot_id = $1
                    ORDER BY position
                    """,
                    s["id"],
                )
                for er in extras:
                    await conn.execute(
                        """
                        INSERT INTO class_assessment_slot_topics
                          (class_assessment_slot_id, topic_id, position)
                        VALUES ($1, $2, $3)
                        """,
                        slot_id, er["topic_id"], er["position"],
                    )
                    result.assessment_topics_inserted += 1
                # If the breakdown slot has its own topic_id, include it too.
                if s["topic_id"] is not None:
                    await conn.execute(
                        """
                        INSERT INTO class_assessment_slot_topics
                          (class_assessment_slot_id, topic_id, position)
                        VALUES ($1, $2, $3)
                        ON CONFLICT DO NOTHING
                        """,
                        slot_id, s["topic_id"], 0,
                    )
                result.assessment_slots_upserted += 1
            else:
                result.skipped.append(
                    f"slot {s['id']} has unknown slot_type={s['slot_type']!r}"
                )

    log.info(
        "realize_class_breakdown: exit breakdown=%s cst=%s lessons=%d assessments=%d skipped=%d",
        class_breakdown_id, cst_id,
        result.lesson_slots_upserted, result.assessment_slots_upserted,
        len(result.skipped),
    )
    return result
