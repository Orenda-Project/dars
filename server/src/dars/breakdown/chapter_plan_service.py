"""
Chapter Plan — pure slot-sequence planners.

Salvaged from the now-deleted `auto_build_service.py` (D-12). These pure
functions distribute a chapter's day budget into a sequence of lesson /
formative-assessment / summative-assessment / revision slots and assign
lp_type per topic. No DB, no I/O.

Used by the teacher-app "break it down" flow (Phase 3): the slot count is
computed from the teacher's real timetable (D-9) and these planners turn that
count into a concrete slot sequence for one chapter.

The number of returned slots equals the `chapter_days` the allocation was built
for (1 slot = 1 teaching day, D-74).
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

import asyncpg

from dars.breakdown.holidays import get_effective_holidays, resolve_cst_context
from dars.breakdown.lp_type_heuristics import pick_lp_type
from dars.breakdown.projector import compute_teaching_days

log = logging.getLogger("breakdown.chapter_plan")


def compute_chapter_day_budget(
    topic_counts_in_order: list[int],
    total_teaching_days: int,
) -> list[int]:
    """
    Split `total_teaching_days` across chapters proportional to topic count.
    Returns one budget per chapter. Every chapter gets at least 1 day.
    Sum is guaranteed to equal total_teaching_days.
    """
    total_topics = sum(topic_counts_in_order)
    if total_topics <= 0:
        return [1 for _ in topic_counts_in_order]
    raw = [
        (count / total_topics) * total_teaching_days for count in topic_counts_in_order
    ]
    rounded = [max(1, round(x)) for x in raw]
    drift = total_teaching_days - sum(rounded)
    if drift != 0 and rounded:
        idx = rounded.index(max(rounded))
        rounded[idx] = max(1, rounded[idx] + drift)
    return rounded


@dataclass(frozen=True)
class ChapterDayAllocation:
    """How a chapter's day budget is split into slot kinds."""

    lesson_days: int           # number of lesson slots
    fa_count: int              # number of FA slots
    sa_count: int              # number of SA slots
    revision_count: int        # 0 or 1
    days_per_topic: list[int]  # length == topic_count; sum == lesson_days


def allocate_chapter_days(
    chapter_days: int,
    topic_count: int,
    fa_cadence: int,
    sa_per_chapter: int,
) -> ChapterDayAllocation:
    """
    Decide how the chapter's day budget splits into lesson/FA/SA/revision
    slots, and how lesson days distribute across topics.

    Invariant: lesson_days + fa_count + sa_count + revision_count == chapter_days.

    Priority when the chapter is small:
        1. SA(s) and revision are reserved first (1 day each).
        2. Remaining days are split into lesson_days + fa_count, with
           fa_count = floor(lesson_days / fa_cadence).
        3. If even that's impossible (chapter_days too small), drop
           revision then SAs until everything fits.

    Lesson days distribute uniformly across topics: each topic gets
    floor(lesson_days / topic_count) days; the first `remainder` topics
    get one extra. If topic_count == 0, days_per_topic is empty and
    lesson_days is 0.
    """
    if chapter_days < 1:
        raise ValueError(f"chapter_days must be >= 1, got {chapter_days}")
    if fa_cadence < 1:
        raise ValueError(f"fa_cadence must be >= 1, got {fa_cadence}")
    if sa_per_chapter < 0:
        raise ValueError(f"sa_per_chapter must be >= 0, got {sa_per_chapter}")
    if topic_count < 0:
        raise ValueError(f"topic_count must be >= 0, got {topic_count}")

    sa_count = sa_per_chapter
    revision_count = 1
    remaining = chapter_days - sa_count - revision_count

    if remaining < 0:
        revision_count = 0
        remaining = chapter_days - sa_count
        while remaining < 0 and sa_count > 0:
            sa_count -= 1
            remaining += 1
        # remaining is now >= 0.

    if topic_count == 0:
        # No topics → no lessons, no FAs. Dump leftover into extra SAs to
        # preserve the count == chapter_days invariant.
        return ChapterDayAllocation(
            lesson_days=0,
            fa_count=0,
            sa_count=sa_count + remaining,
            revision_count=revision_count,
            days_per_topic=[],
        )

    # Solve lesson_days + fa_count == remaining with fa_count == lesson_days // fa_cadence.
    # Closed form: lesson_days = remaining - remaining // (fa_cadence + 1) ... but iterating
    # is easier to read and converges in <= 2 steps.
    lesson_days = remaining
    fa_count = 0
    for _ in range(64):
        new_lessons = remaining - fa_count
        new_fa = new_lessons // fa_cadence
        if new_fa == fa_count and new_lessons == lesson_days:
            break
        lesson_days = new_lessons
        fa_count = new_fa

    # Sanity: enforce the invariant.
    if lesson_days + fa_count != remaining:
        # Off by one due to recurrence corner — eat the diff into fa_count.
        fa_count = remaining - lesson_days

    base = lesson_days // topic_count
    rem = lesson_days % topic_count
    days_per_topic = [base + (1 if i < rem else 0) for i in range(topic_count)]

    return ChapterDayAllocation(
        lesson_days=lesson_days,
        fa_count=fa_count,
        sa_count=sa_count,
        revision_count=revision_count,
        days_per_topic=days_per_topic,
    )


# ---------------------------------------------------------------------------
# Slot sequence planner (pure)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlannedSlot:
    slot_type: str           # 'lesson' | 'formative_assessment' | 'summative_assessment' | 'revision'
    topic_id: UUID | None    # for lessons
    lp_type: str | None      # for lessons; 'revision' for revision; None for FA/SA
    covered_topic_ids: tuple[UUID, ...]  # for FA/SA: the topics this assessment covers


def plan_chapter_slots(
    topic_ids: list[UUID],
    topic_lp_types: list[str],
    allocation: ChapterDayAllocation,
    fa_cadence: int,
) -> list[PlannedSlot]:
    """
    Materialise the day-by-day sequence for one chapter.

    Order: lessons (with FAs interleaved every `fa_cadence` lessons) →
    SA(s) → revision. Returns exactly chapter_days slots.

    For each topic, emit `allocation.days_per_topic[i]` consecutive
    lesson slots with the same lp_type. After every `fa_cadence` lesson
    days, slot an FA whose `covered_topic_ids` lists the topics touched
    since the previous FA.
    """
    slots: list[PlannedSlot] = []
    if len(topic_ids) != len(topic_lp_types):
        raise ValueError("topic_ids and topic_lp_types length mismatch")
    if len(topic_ids) != len(allocation.days_per_topic):
        raise ValueError("topic count mismatch with allocation.days_per_topic")

    # Walk lessons one day at a time, interleaving FAs.
    fas_left = allocation.fa_count
    lessons_since_last_fa = 0
    recent_topic_ids: list[UUID] = []

    for i, t_id in enumerate(topic_ids):
        n = allocation.days_per_topic[i]
        if n <= 0:
            continue
        lp_type = topic_lp_types[i]
        for _ in range(n):
            slots.append(
                PlannedSlot(
                    slot_type="lesson",
                    topic_id=t_id,
                    lp_type=lp_type,
                    covered_topic_ids=(),
                )
            )
            lessons_since_last_fa += 1
            if t_id not in recent_topic_ids:
                recent_topic_ids.append(t_id)
            if lessons_since_last_fa >= fa_cadence and fas_left > 0:
                slots.append(
                    PlannedSlot(
                        slot_type="formative_assessment",
                        topic_id=None,
                        lp_type=None,
                        covered_topic_ids=tuple(recent_topic_ids),
                    )
                )
                fas_left -= 1
                lessons_since_last_fa = 0
                recent_topic_ids = []

    # If there are still FAs to emit (lesson_days % fa_cadence > 0 path,
    # or no FAs were placed due to a small chapter), tack remaining FAs
    # onto the end of the lesson sequence to preserve count parity.
    while fas_left > 0:
        slots.append(
            PlannedSlot(
                slot_type="formative_assessment",
                topic_id=None,
                lp_type=None,
                covered_topic_ids=tuple(recent_topic_ids) if recent_topic_ids else tuple(topic_ids),
            )
        )
        fas_left -= 1
        recent_topic_ids = []

    # SA(s) at chapter end — cover all chapter topics.
    for _ in range(allocation.sa_count):
        slots.append(
            PlannedSlot(
                slot_type="summative_assessment",
                topic_id=None,
                lp_type=None,
                covered_topic_ids=tuple(topic_ids),
            )
        )

    # Revision.
    for _ in range(allocation.revision_count):
        slots.append(
            PlannedSlot(
                slot_type="revision",
                topic_id=None,
                lp_type="revision",
                covered_topic_ids=(),
            )
        )

    return slots


# ---------------------------------------------------------------------------
# Teacher Chapter Plan — DB-facing (Phase 3, D-9/D-14/D-16)
# ---------------------------------------------------------------------------


@dataclass
class CstSyllabusContext:
    """Resolved (curriculum, grade, subject, book) for a CST + its syllabus."""
    cst_id: UUID
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    book_id: UUID | None
    subject_code: str
    syllabus_breakdown_id: UUID | None  # None if no published global syllabus


async def resolve_cst_syllabus_context(
    conn: asyncpg.Connection, cst_id: UUID
) -> CstSyllabusContext:
    """
    Resolve a CST to its (curriculum via org, grade via class, subject direct)
    and the published global Syllabus Breakdown for that triple.
    Raises ValueError if the CST isn't found.
    """
    row = await conn.fetchrow(
        """
        SELECT cst.subject_id, cst.book_id,
               sc.grade_id,
               o.curriculum_id,
               s.code AS subject_code
        FROM class_subject_teachers cst
        JOIN school_classes sc ON sc.id = cst.school_class_id
        JOIN organizations o   ON o.id = cst.org_id
        JOIN subjects s        ON s.id = cst.subject_id
        WHERE cst.id = $1
        """,
        cst_id,
    )
    if row is None:
        raise ValueError(f"cst {cst_id} not found")

    syllabus_id = await conn.fetchval(
        """
        SELECT id FROM syllabus_breakdowns
        WHERE status = 'published'
          AND curriculum_id = $1 AND grade_id = $2 AND subject_id = $3
        ORDER BY created_at DESC
        LIMIT 1
        """,
        row["curriculum_id"], row["grade_id"], row["subject_id"],
    )
    return CstSyllabusContext(
        cst_id=cst_id,
        curriculum_id=row["curriculum_id"],
        grade_id=row["grade_id"],
        subject_id=row["subject_id"],
        book_id=row["book_id"],
        subject_code=row["subject_code"],
        syllabus_breakdown_id=syllabus_id,
    )


async def _cst_weekday_set(conn: asyncpg.Connection, cst_id: UUID) -> set[int]:
    """The CST's timetable weekdays (0=Mon..6=Sun). Default Mon-Fri if none set."""
    rows = await conn.fetch(
        "SELECT day_of_week FROM timetables WHERE cst_id = $1", cst_id
    )
    days = {r["day_of_week"] for r in rows}
    return days or {0, 1, 2, 3, 4}


async def chapter_slot_count(
    conn: asyncpg.Connection,
    cst_id: UUID,
    start_date: date | None,
    end_date: date | None,
) -> int:
    """
    D-9/D-14: slot count = number of real teaching periods in the chapter's
    date range = teaching days on the CST's timetable weekdays, minus holidays.
    Returns 0 if the chapter has no date range (admin hasn't set dates yet).
    """
    if start_date is None or end_date is None:
        return 0
    weekday_set = await _cst_weekday_set(conn, cst_id)
    holidays = await get_effective_holidays(conn, cst_id)
    return len(compute_teaching_days(start_date, end_date, weekday_set, holidays))


@dataclass
class GeneratePlanResult:
    cst_id: UUID
    book_chapter_id: UUID
    slot_count: int
    lesson_slot_count: int = 0
    assessment_slot_count: int = 0
    warnings: list[str] = field(default_factory=list)


async def generate_chapter_plan(
    conn: asyncpg.Connection,
    *,
    cst_id: UUID,
    book_chapter_id: UUID,
    org_id: UUID,
    fa_cadence: int = 5,
    sa_per_chapter: int = 1,
) -> GeneratePlanResult:
    """
    F3.3: "break it down" — generate a chapter's slots into the class slot
    tables for this CST, sized by the teacher's real timetable (D-9).

    - slot_count = teaching periods in the chapter's syllabus date range.
    - planners (allocate_chapter_days + plan_chapter_slots + pick_lp_type)
      distribute lessons/FAs/SAs/revision and pick lp_type per topic.
    - rows are appended after the CST's current max position, stamped with
      book_chapter_id (D-16) and page ranges left null (teacher fills).
    - Refuses (ValueError) if the chapter already has class slots for this CST,
      or if the chapter has no date range yet (slot_count == 0).
    Caller does org/access checks.
    """
    log.info(
        "generate_chapter_plan: entry cst=%s chapter=%s", cst_id, book_chapter_id
    )
    ctx = await resolve_cst_syllabus_context(conn, cst_id)
    if ctx.syllabus_breakdown_id is None:
        raise ValueError("no published syllabus breakdown for this class")

    chapter = await conn.fetchrow(
        """
        SELECT sch.start_date, sch.end_date
        FROM syllabus_chapters sch
        WHERE sch.syllabus_breakdown_id = $1 AND sch.book_chapter_id = $2
        """,
        ctx.syllabus_breakdown_id, book_chapter_id,
    )
    if chapter is None:
        raise ValueError("chapter not in this class's syllabus breakdown")

    slot_count = await chapter_slot_count(
        conn, cst_id, chapter["start_date"], chapter["end_date"]
    )
    if slot_count < 1:
        raise ValueError(
            "chapter has no teaching days in its date range "
            "(set the chapter's dates on the syllabus first)"
        )

    existing = await conn.fetchval(
        """
        SELECT
          (SELECT count(*) FROM class_lesson_slots
             WHERE cst_id = $1 AND book_chapter_id = $2)
        + (SELECT count(*) FROM class_assessment_slots
             WHERE cst_id = $1 AND book_chapter_id = $2)
        """,
        cst_id, book_chapter_id,
    )
    if existing:
        raise ValueError("chapter already broken down; clear it first to regenerate")

    # Topics + lp_type preference per topic (same data access as old auto-build).
    topic_rows = await conn.fetch(
        "SELECT id, title, topic_text FROM topics WHERE book_chapter_id = $1 ORDER BY topic_number",
        book_chapter_id,
    )
    topic_sub_slo_lp: dict[UUID, str | None] = {}
    topic_slo_lp: dict[UUID, str | None] = {}
    if topic_rows:
        rec_rows = await conn.fetch(
            """
            SELECT tss.topic_id,
                   ss.recommended_lp_type AS sub_slo_lp_type,
                   s.recommended_lp_type  AS slo_lp_type
            FROM topic_sub_slos tss
            JOIN sub_slos ss ON ss.id = tss.sub_slo_id
            JOIN slos s ON s.id = ss.slo_id
            WHERE tss.topic_id = ANY($1::uuid[])
            ORDER BY tss.topic_id, ss.position
            """,
            [t["id"] for t in topic_rows],
        )
        for r in rec_rows:
            if r["sub_slo_lp_type"] is not None:
                topic_sub_slo_lp.setdefault(r["topic_id"], r["sub_slo_lp_type"])
            if r["slo_lp_type"] is not None:
                topic_slo_lp.setdefault(r["topic_id"], r["slo_lp_type"])

    result = GeneratePlanResult(
        cst_id=cst_id, book_chapter_id=book_chapter_id, slot_count=slot_count
    )

    allocation = allocate_chapter_days(
        chapter_days=slot_count,
        topic_count=len(topic_rows),
        fa_cadence=fa_cadence,
        sa_per_chapter=sa_per_chapter,
    )
    topic_lp_types: list[str] = []
    for topic in topic_rows:
        lp = pick_lp_type(
            subject_code=ctx.subject_code,
            topic_title=topic["title"],
            topic_text=topic["topic_text"],
            recommended_lp_type=topic_slo_lp.get(topic["id"]),
            sub_slo_recommended_lp_type=topic_sub_slo_lp.get(topic["id"]),
        )
        topic_lp_types.append(lp)

    planned = plan_chapter_slots(
        topic_ids=[t["id"] for t in topic_rows],
        topic_lp_types=topic_lp_types,
        allocation=allocation,
        fa_cadence=fa_cadence,
    )

    async with conn.transaction():
        # Lessons + assessments share ONE global position sequence per CST
        # (the projector merges both tables by position; 1 slot = 1 teaching day).
        pos = await conn.fetchval(
            """
            SELECT greatest(
              (SELECT coalesce(max(position), 0) FROM class_lesson_slots WHERE cst_id = $1),
              (SELECT coalesce(max(position), 0) FROM class_assessment_slots WHERE cst_id = $1)
            )
            """,
            cst_id,
        )
        for plan in planned:
            pos += 1
            if plan.slot_type in ("lesson", "revision"):
                await conn.execute(
                    """
                    INSERT INTO class_lesson_slots
                      (org_id, cst_id, position, slot_type, lp_type, topic_id,
                       book_chapter_id, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'planned')
                    """,
                    org_id, cst_id, pos, plan.slot_type, plan.lp_type,
                    plan.topic_id, book_chapter_id,
                )
                result.lesson_slot_count += 1
            else:  # formative/summative assessment
                slot_id = await conn.fetchval(
                    """
                    INSERT INTO class_assessment_slots
                      (org_id, cst_id, position, assessment_type, book_chapter_id, status)
                    VALUES ($1, $2, $3, $4, $5, 'planned')
                    RETURNING id
                    """,
                    org_id, cst_id, pos, plan.slot_type, book_chapter_id,
                )
                for i, t_id in enumerate(plan.covered_topic_ids, start=1):
                    await conn.execute(
                        """
                        INSERT INTO class_assessment_slot_topics
                          (class_assessment_slot_id, topic_id, position)
                        VALUES ($1, $2, $3)
                        """,
                        slot_id, t_id, i,
                    )
                result.assessment_slot_count += 1

    log.info(
        "generate_chapter_plan: exit cst=%s chapter=%s lessons=%d assessments=%d",
        cst_id, book_chapter_id, result.lesson_slot_count, result.assessment_slot_count,
    )
    return result
