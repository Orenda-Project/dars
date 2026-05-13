import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.curriculum.models import BookChapter, CurriculumChapterSchedule
from dars.clients.models import Client
from dars.school.models import (
    AcademicYear,
    AssessmentSlot,
    ChapterPlan,
    ClassLessonSlot,
    ClassSubjectTeacher,
    Holiday,
    SchoolClass,
    Timetable,
)

logger = logging.getLogger(__name__)

# Subject → cycling LP types (last slot always overridden to "Revision")
_LP_CYCLES: dict[str, list[str]] = {
    "english": ["Reading", "Grammar", "Writing", "Comprehension", "Revision-cycle"],
    "math": ["Concept", "Practice", "Problem Solving", "Revision-cycle"],
    "mathematics": ["Concept", "Practice", "Problem Solving", "Revision-cycle"],
}
_DEFAULT_CYCLE = ["Introduction", "Practice", "Review", "Revision-cycle"]


async def compute_teaching_days_for_year(
    academic_year_id: uuid.UUID,
    db: AsyncSession,
) -> int:
    """
    Count teaching days in an academic year: all Mon–Fri dates excluding holidays.
    Used for the summary count shown in the dashboard (no timetable needed).
    """
    logger.info("compute_teaching_days_for_year: academic_year_id=%s", academic_year_id)

    year_result = await db.execute(select(AcademicYear).where(AcademicYear.id == academic_year_id))
    academic_year = year_result.scalar_one_or_none()
    if academic_year is None:
        logger.error("compute_teaching_days_for_year: academic_year_id=%s not found", academic_year_id)
        return 0

    hol_result = await db.execute(
        select(Holiday).where(Holiday.academic_year_id == academic_year_id)
    )
    holiday_dates = {h.date for h in hol_result.scalars().all()}

    start = academic_year.start_date
    end = academic_year.end_date
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in holiday_dates:
            count += 1
        current += timedelta(days=1)

    logger.info(
        "compute_teaching_days_for_year: academic_year_id=%s count=%d", academic_year_id, count
    )
    return count


async def compute_teaching_days(
    cst_id: uuid.UUID,
    db: AsyncSession,
) -> list[date]:
    """
    Return sorted list of teaching dates for a ClassSubjectTeacher.

    Logic:
    1. Load CST → SchoolClass → AcademicYear
    2. Get timetable rows (day_of_week); fall back to Mon-Fri if empty
    3. Walk every date in [start_date, end_date], keep only timetable days
    4. Remove holidays for the academic year
    """
    logger.info("compute_teaching_days: cst_id=%s", cst_id)

    cst_result = await db.execute(select(ClassSubjectTeacher).where(ClassSubjectTeacher.id == cst_id))
    cst = cst_result.scalar_one_or_none()
    if cst is None:
        logger.error("compute_teaching_days: cst_id=%s not found", cst_id)
        return []

    class_result = await db.execute(
        select(SchoolClass).where(SchoolClass.id == cst.class_id)
    )
    school_class = class_result.scalar_one_or_none()
    if school_class is None:
        logger.error("compute_teaching_days: school_class not found for cst_id=%s", cst_id)
        return []

    year_result = await db.execute(
        select(AcademicYear).where(AcademicYear.id == school_class.academic_year_id)
    )
    academic_year = year_result.scalar_one_or_none()
    if academic_year is None:
        logger.error("compute_teaching_days: academic_year not found for cst_id=%s", cst_id)
        return []

    # Timetable days
    tt_result = await db.execute(
        select(Timetable).where(Timetable.class_subject_teacher_id == cst_id)
    )
    tt_rows = list(tt_result.scalars().all())
    if tt_rows:
        active_days = {row.day_of_week for row in tt_rows}
    else:
        active_days = {0, 1, 2, 3, 4}  # Mon-Fri fallback

    # Holidays
    hol_result = await db.execute(
        select(Holiday).where(Holiday.academic_year_id == school_class.academic_year_id)
    )
    holiday_dates = {h.date for h in hol_result.scalars().all()}

    # Walk dates
    start = academic_year.start_date
    end = academic_year.end_date
    teaching: list[date] = []
    current = start
    while current <= end:
        if current.weekday() in active_days and current not in holiday_dates:
            teaching.append(current)
        current += timedelta(days=1)

    logger.info(
        "compute_teaching_days: cst_id=%s total_teaching_days=%d", cst_id, len(teaching)
    )
    return teaching


async def compute_chapter_date_ranges(
    cst_id: uuid.UUID,
    db: AsyncSession,
) -> list[dict]:
    """
    For each chapter plan (ordered by position), compute start/end date by slicing
    the available teaching days sequentially.

    Returns list of {chapter_plan_id, start_date, end_date} (dates are None if
    there are not enough teaching days).
    """
    logger.info("compute_chapter_date_ranges: cst_id=%s", cst_id)

    plans_result = await db.execute(
        select(ChapterPlan)
        .where(ChapterPlan.class_subject_teacher_id == cst_id)
        .order_by(ChapterPlan.position)
    )
    plans = list(plans_result.scalars().all())

    if not plans:
        logger.info("compute_chapter_date_ranges: cst_id=%s no chapter plans", cst_id)
        return []

    teaching_days = await compute_teaching_days(cst_id, db)
    ranges: list[dict] = []
    offset = 0

    for plan in plans:
        needed = plan.teaching_days
        if offset >= len(teaching_days):
            ranges.append(
                {"chapter_plan_id": plan.id, "start_date": None, "end_date": None}
            )
        else:
            slice_days = teaching_days[offset : offset + needed]
            start_date = slice_days[0] if slice_days else None
            end_date = slice_days[-1] if slice_days else None
            ranges.append(
                {"chapter_plan_id": plan.id, "start_date": start_date, "end_date": end_date}
            )
        offset += needed

    logger.info(
        "compute_chapter_date_ranges: cst_id=%s plans=%d", cst_id, len(ranges)
    )
    return ranges


async def auto_schedule_formative_assessments(
    cst_id: uuid.UUID,
    db: AsyncSession,
) -> list[AssessmentSlot]:
    """
    For each chapter plan, schedule a formative assessment on the teaching day
    immediately after the chapter's last teaching day. Idempotent: upserts by
    (class_subject_teacher_id, chapter_plan_id, assessment_type='formative').
    """
    logger.info("auto_schedule_formative_assessments: cst_id=%s", cst_id)

    # Need CST for client_id
    cst_result = await db.execute(select(ClassSubjectTeacher).where(ClassSubjectTeacher.id == cst_id))
    cst = cst_result.scalar_one_or_none()
    if cst is None:
        logger.error("auto_schedule_formative_assessments: cst_id=%s not found", cst_id)
        return []

    date_ranges = await compute_chapter_date_ranges(cst_id, db)
    teaching_days = await compute_teaching_days(cst_id, db)
    teaching_day_set = sorted(teaching_days)

    slots: list[AssessmentSlot] = []
    for dr in date_ranges:
        chapter_plan_id = dr["chapter_plan_id"]
        end_date = dr["end_date"]
        if end_date is None:
            continue

        # Find the teaching day immediately after end_date
        fa_date: date | None = None
        for d in teaching_day_set:
            if d > end_date:
                fa_date = d
                break

        if fa_date is None:
            logger.info(
                "auto_schedule_formative_assessments: no teaching day after chapter_plan_id=%s end_date=%s",
                chapter_plan_id,
                end_date,
            )
            continue

        # Upsert
        existing_result = await db.execute(
            select(AssessmentSlot).where(
                AssessmentSlot.class_subject_teacher_id == cst_id,
                AssessmentSlot.chapter_plan_id == chapter_plan_id,
                AssessmentSlot.assessment_type == "formative",
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            existing.scheduled_date = fa_date
            slots.append(existing)
        else:
            slot = AssessmentSlot(
                client_id=cst.client_id,
                class_subject_teacher_id=cst_id,
                chapter_plan_id=chapter_plan_id,
                assessment_type="formative",
                scheduled_date=fa_date,
                status="scheduled",
            )
            db.add(slot)
            await db.flush()
            await db.refresh(slot)
            slots.append(slot)

    await db.commit()
    logger.info(
        "auto_schedule_formative_assessments: cst_id=%s created/updated=%d", cst_id, len(slots)
    )
    return slots


async def get_prefill_chapter_plans(
    cst_id: uuid.UUID,
    db: AsyncSession,
) -> list[dict]:
    """
    Return all chapters for the CST's book, merged with curriculum default schedule
    (suggested_teaching_days, suggested_position, term). If no book or no schedule,
    returns chapters with None values.
    """
    logger.info("get_prefill_chapter_plans: cst_id=%s", cst_id)

    cst_result = await db.execute(select(ClassSubjectTeacher).where(ClassSubjectTeacher.id == cst_id))
    cst = cst_result.scalar_one_or_none()
    if cst is None:
        logger.error("get_prefill_chapter_plans: cst_id=%s not found", cst_id)
        return []

    if cst.book_id is None:
        logger.info("get_prefill_chapter_plans: cst_id=%s has no book_id, returning empty", cst_id)
        return []

    # Walk CST → SchoolClass → AcademicYear → Client to get curriculum
    class_result = await db.execute(select(SchoolClass).where(SchoolClass.id == cst.class_id))
    school_class = class_result.scalar_one_or_none()
    if school_class is None:
        logger.error("get_prefill_chapter_plans: school_class not found for cst_id=%s", cst_id)
        return []

    year_result = await db.execute(select(AcademicYear).where(AcademicYear.id == school_class.academic_year_id))
    academic_year = year_result.scalar_one_or_none()
    if academic_year is None:
        logger.error("get_prefill_chapter_plans: academic_year not found for cst_id=%s", cst_id)
        return []

    client_result = await db.execute(select(Client).where(Client.id == academic_year.client_id))
    client = client_result.scalar_one_or_none()
    curriculum = client.curriculum if client else None

    # Load chapters for the book
    chapters_result = await db.execute(
        select(BookChapter)
        .where(BookChapter.book_id == cst.book_id)
        .order_by(BookChapter.chapter_number)
    )
    chapters = list(chapters_result.scalars().all())

    if not chapters:
        logger.info("get_prefill_chapter_plans: cst_id=%s no chapters found for book_id=%s", cst_id, cst.book_id)
        return []

    # Load curriculum schedule rows for these chapter IDs
    schedule_map: dict[uuid.UUID, CurriculumChapterSchedule] = {}
    if curriculum:
        chapter_ids = [c.id for c in chapters]
        sched_result = await db.execute(
            select(CurriculumChapterSchedule).where(
                CurriculumChapterSchedule.curriculum == curriculum,
                CurriculumChapterSchedule.chapter_id.in_(chapter_ids),
            )
        )
        for row in sched_result.scalars().all():
            schedule_map[row.chapter_id] = row

    # Merge
    result = []
    for chapter in chapters:
        sched = schedule_map.get(chapter.id)
        result.append({
            "chapter_id": chapter.id,
            "title": chapter.title,
            "chapter_number": chapter.chapter_number,
            "suggested_teaching_days": sched.suggested_teaching_days if sched else None,
            "suggested_position": sched.suggested_position if sched else None,
            "term": sched.term if sched else None,
        })

    logger.info("get_prefill_chapter_plans: cst_id=%s returning=%d chapters", cst_id, len(result))
    return result


async def generate_lesson_sequence(
    chapter_plan_id: uuid.UUID,
    db: AsyncSession,
) -> list[ClassLessonSlot]:
    """
    Generate ClassLessonSlot rows for a chapter plan using subject-aware LP type cycling.
    Deletes any existing rows for this chapter plan, then inserts fresh ones.
    Last slot is always "Revision".
    """
    logger.info("generate_lesson_sequence: chapter_plan_id=%s", chapter_plan_id)

    plan_result = await db.execute(
        select(ChapterPlan).where(ChapterPlan.id == chapter_plan_id)
    )
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        logger.error("generate_lesson_sequence: chapter_plan_id=%s not found", chapter_plan_id)
        return []

    cst_result = await db.execute(
        select(ClassSubjectTeacher).where(ClassSubjectTeacher.id == plan.class_subject_teacher_id)
    )
    cst = cst_result.scalar_one_or_none()
    if cst is None:
        logger.error(
            "generate_lesson_sequence: CST not found for chapter_plan_id=%s", chapter_plan_id
        )
        return []

    subject_key = cst.subject.lower()
    cycle = _LP_CYCLES.get(subject_key, _DEFAULT_CYCLE)

    n = plan.teaching_days
    lp_types: list[str] = []
    for i in range(n):
        if i == n - 1:
            lp_types.append("Revision")
        else:
            lp_types.append(cycle[i % len(cycle)])

    # Delete existing slots for this chapter plan
    await db.execute(
        delete(ClassLessonSlot).where(ClassLessonSlot.chapter_plan_id == chapter_plan_id)
    )

    new_slots: list[ClassLessonSlot] = []
    for day_num, lp_type in enumerate(lp_types, start=1):
        slot = ClassLessonSlot(
            client_id=cst.client_id,
            class_subject_teacher_id=cst.id,
            chapter_plan_id=chapter_plan_id,
            day_number=day_num,
            lp_type=lp_type,
            title=f"Day {day_num}: {lp_type}",
            status="planned",
        )
        db.add(slot)
        new_slots.append(slot)

    await db.flush()
    for slot in new_slots:
        await db.refresh(slot)

    await db.commit()
    logger.info(
        "generate_lesson_sequence: chapter_plan_id=%s created=%d slots", chapter_plan_id, len(new_slots)
    )
    return new_slots
