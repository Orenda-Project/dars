"""
F2.5 — Auto-build a draft Breakdown from a book + curriculum.

Endpoint shape (caller in router_breakdown.py):
    POST /api/v2/breakdowns/auto-build
    body: AutoBuildRequest

Model: **1 slot = 1 teaching day** (D-74). The number of breakdown_slots
rows for a breakdown equals breakdowns.total_teaching_days exactly.

Algorithm:
    1. Per chapter, allocate a day budget proportional to topic count
       (compute_chapter_day_budget — sums to total_teaching_days).
    2. Within each chapter, decide the per-day sequence:
         a. Reserve `sa_per_chapter` days for SA + 1 day for revision.
         b. Of the remaining lesson_days, every `fa_cadence`-th day is
            a formative_assessment. fa_count is computed so that
            lesson_days + fa_count + sa_count + revision_count == chapter_days.
         c. Distribute lesson_days uniformly across topics.
         d. Walk the lessons one day at a time; after every `fa_cadence`
            lessons, slot an FA covering the recent topics. Then SA(s)
            at the chapter end (covering all chapter topics) and one
            revision slot.

Properties:
    - count(breakdown_slots WHERE breakdown_id = X) == total_teaching_days
    - Consecutive same-topic lesson slots share lp_type (Identical, D-74).
    - lp_type per topic comes from lp_type_heuristics.pick_lp_type().
"""
import logging
from dataclasses import dataclass, field
from uuid import UUID

import asyncpg

from dars.breakdown.lp_type_heuristics import pick_lp_type
from dars.v2_api.lp_types import is_valid_lp_type

log = logging.getLogger("breakdown.auto_build")


# ---------------------------------------------------------------------------
# Request / result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AutoBuildRequest:
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    book_id: UUID
    total_teaching_days: int = 180
    fa_cadence: int = 5
    sa_per_chapter: int = 1
    scope: str = "global"
    scope_ref_id: UUID | None = None


@dataclass
class AutoBuildResult:
    breakdown_id: UUID
    chapter_count: int = 0
    lesson_slot_count: int = 0
    fa_slot_count: int = 0
    sa_slot_count: int = 0
    revision_slot_count: int = 0
    total_slot_count: int = 0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


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
# Service
# ---------------------------------------------------------------------------


async def auto_build_breakdown(
    conn: asyncpg.Connection,
    request: AutoBuildRequest,
) -> AutoBuildResult:
    """
    Build and persist a draft breakdown. Raises ValueError on bad input.
    """
    log.info(
        "auto_build_breakdown: entry book=%s grade=%s subject=%s days=%d fa=%d sa=%d",
        request.book_id, request.grade_id, request.subject_id,
        request.total_teaching_days, request.fa_cadence, request.sa_per_chapter,
    )
    if request.fa_cadence < 1:
        raise ValueError("fa_cadence must be >= 1")
    if request.sa_per_chapter < 0:
        raise ValueError("sa_per_chapter must be >= 0")
    if request.total_teaching_days < 1:
        raise ValueError("total_teaching_days must be >= 1")

    subject_code = await conn.fetchval(
        "SELECT code FROM subjects WHERE id = $1", request.subject_id
    )
    if subject_code is None:
        raise ValueError(f"subject_id {request.subject_id} not found")

    book = await conn.fetchrow(
        """
        SELECT id, curriculum_id, grade_id, subject_id
        FROM books
        WHERE id = $1
        """,
        request.book_id,
    )
    if book is None:
        raise ValueError(f"book_id {request.book_id} not found")
    if (
        book["curriculum_id"] != request.curriculum_id
        or book["grade_id"] != request.grade_id
        or book["subject_id"] != request.subject_id
    ):
        raise ValueError("book does not match (curriculum_id, grade_id, subject_id)")

    chapters = await conn.fetch(
        """
        SELECT id, chapter_number, title
        FROM book_chapters
        WHERE book_id = $1
        ORDER BY chapter_number
        """,
        request.book_id,
    )
    if not chapters:
        raise ValueError("book has no chapters")
    chapter_ids = [c["id"] for c in chapters]

    topic_rows = await conn.fetch(
        """
        SELECT t.id, t.book_chapter_id, t.topic_number, t.title, t.topic_text
        FROM topics t
        WHERE t.book_chapter_id = ANY($1::uuid[])
        ORDER BY t.book_chapter_id, t.topic_number
        """,
        chapter_ids,
    )
    topics_by_chapter: dict[UUID, list[asyncpg.Record]] = {}
    for tr in topic_rows:
        topics_by_chapter.setdefault(tr["book_chapter_id"], []).append(tr)

    # Per topic, we resolve two preferences (D-13):
    #   * The first non-null sub-SLO `recommended_lp_type` (highest precedence).
    #   * The first non-null parent-SLO `recommended_lp_type` (fallback).
    # `pick_lp_type` resolves the precedence; we just collect both and pass.
    topic_sub_slo_lp: dict[UUID, str | None] = {}
    topic_recommended_lp: dict[UUID, str | None] = {}
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
                topic_recommended_lp.setdefault(r["topic_id"], r["slo_lp_type"])

    topic_counts = [len(topics_by_chapter.get(c["id"], [])) for c in chapters]
    chapter_days = compute_chapter_day_budget(topic_counts, request.total_teaching_days)

    result = AutoBuildResult(breakdown_id=UUID(int=0))

    async with conn.transaction():
        breakdown_id = await conn.fetchval(
            """
            INSERT INTO breakdowns
              (scope, scope_ref_id, curriculum_id, grade_id, subject_id,
               book_id, total_teaching_days, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'draft')
            RETURNING id
            """,
            request.scope, request.scope_ref_id, request.curriculum_id,
            request.grade_id, request.subject_id, request.book_id,
            request.total_teaching_days,
        )
        result.breakdown_id = breakdown_id

        global_position = 0

        for idx, chapter in enumerate(chapters):
            chapter_topics = topics_by_chapter.get(chapter["id"], [])
            if not chapter_topics:
                # No topics — still emit a placeholder chapter row + fill
                # its days with SAs/revision so total count parity holds.
                result.warnings.append(
                    f"chapter {chapter['chapter_number']} has no topics"
                )

            bd_chapter_id = await conn.fetchval(
                """
                INSERT INTO breakdown_chapters
                  (breakdown_id, book_chapter_id, position, teaching_days)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                breakdown_id, chapter["id"], idx + 1, chapter_days[idx],
            )
            result.chapter_count += 1

            allocation = allocate_chapter_days(
                chapter_days=chapter_days[idx],
                topic_count=len(chapter_topics),
                fa_cadence=request.fa_cadence,
                sa_per_chapter=request.sa_per_chapter,
            )

            if chapter_topics and allocation.lesson_days == 0:
                result.warnings.append(
                    f"chapter {chapter['chapter_number']} budget too small for any lesson slots"
                )

            # Resolve lp_type per topic up front.
            topic_lp_types: list[str] = []
            for topic in chapter_topics:
                lp_type = pick_lp_type(
                    subject_code=subject_code,
                    topic_title=topic["title"],
                    topic_text=topic["topic_text"],
                    recommended_lp_type=topic_recommended_lp.get(topic["id"]),
                    sub_slo_recommended_lp_type=topic_sub_slo_lp.get(topic["id"]),
                )
                if not is_valid_lp_type(subject_code, lp_type):
                    result.warnings.append(
                        f"topic {topic['id']} got invalid lp_type {lp_type!r}; defaulting"
                    )
                    lp_type = "revision"
                topic_lp_types.append(lp_type)

            planned = plan_chapter_slots(
                topic_ids=[t["id"] for t in chapter_topics],
                topic_lp_types=topic_lp_types,
                allocation=allocation,
                fa_cadence=request.fa_cadence,
            )

            # Sanity invariant: planned slots match chapter_days.
            if len(planned) != chapter_days[idx]:
                result.warnings.append(
                    f"chapter {chapter['chapter_number']}: planner produced "
                    f"{len(planned)} slots for {chapter_days[idx]} days"
                )

            chapter_position = 0
            for plan in planned:
                chapter_position += 1
                global_position += 1
                slot_id = await conn.fetchval(
                    """
                    INSERT INTO breakdown_slots
                      (breakdown_id, breakdown_chapter_id, position, chapter_position,
                       slot_type, lp_type, topic_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                    """,
                    breakdown_id, bd_chapter_id, global_position, chapter_position,
                    plan.slot_type, plan.lp_type, plan.topic_id,
                )
                if plan.slot_type == "lesson":
                    result.lesson_slot_count += 1
                elif plan.slot_type == "formative_assessment":
                    result.fa_slot_count += 1
                elif plan.slot_type == "summative_assessment":
                    result.sa_slot_count += 1
                elif plan.slot_type == "revision":
                    result.revision_slot_count += 1

                if plan.covered_topic_ids:
                    for i, t_id in enumerate(plan.covered_topic_ids, start=1):
                        await conn.execute(
                            """
                            INSERT INTO breakdown_slot_topics (breakdown_slot_id, topic_id, position)
                            VALUES ($1, $2, $3)
                            """,
                            slot_id, t_id, i,
                        )

        result.total_slot_count = (
            result.lesson_slot_count
            + result.fa_slot_count
            + result.sa_slot_count
            + result.revision_slot_count
        )

    log.info(
        "auto_build_breakdown: exit breakdown_id=%s chapters=%d lessons=%d fa=%d sa=%d rev=%d total=%d warnings=%d",
        result.breakdown_id, result.chapter_count, result.lesson_slot_count,
        result.fa_slot_count, result.sa_slot_count, result.revision_slot_count,
        result.total_slot_count, len(result.warnings),
    )
    return result
