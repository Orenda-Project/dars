import json
import logging
import re
from datetime import date, timedelta

import anthropic

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.config import settings
from dars.curriculum.models import BookChapter, CurriculumChapterSchedule, Topic
from dars.clients.models import Client
from dars.generated_exams.models import GeneratedExam
from dars.generated_exams.schemas import GeneratedExamCreate
from dars.generated_exams.service import create_generated_exam
from dars.generated_lps.models import GeneratedLP
from dars.generated_lps.schemas import GeneratedLPCreate
from dars.generated_lps.service import create_generated_lp
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
    academic_year_id: int,
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
    cst_id: int,
    db: AsyncSession,
) -> list[date]:
    """
    Return sorted list of teaching dates for a ClassSubjectTeacher.

    Logic:
    1. Load CST → SchoolClass → AcademicYear
    2. Get timetable rows (day_of_week); fall back to Mon–Sat (0–5) if empty
    3. Walk every date in [start_date, end_date], keep only timetable days
    4. Remove holidays for the academic year

    By default a CST is auto-created with Mon–Sat timetable rows, so this
    effectively returns all weekday academic days unless the teacher has
    manually customised their timetable.
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

    # Timetable days (auto-populated Mon–Sat on CST creation; falls back if empty)
    tt_result = await db.execute(
        select(Timetable).where(Timetable.class_subject_teacher_id == cst_id)
    )
    tt_rows = list(tt_result.scalars().all())
    active_days = {row.day_of_week for row in tt_rows} if tt_rows else {0, 1, 2, 3, 4, 5}

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
    cst_id: int,
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
    cst_id: int,
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
    cst_id: int,
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
    curriculum_id = client.curriculum_id if client else None

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
    schedule_map: dict[int, CurriculumChapterSchedule] = {}
    if curriculum_id:
        chapter_ids = [c.id for c in chapters]
        sched_result = await db.execute(
            select(CurriculumChapterSchedule).where(
                CurriculumChapterSchedule.curriculum_id == curriculum_id,
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


# ---------------------------------------------------------------------------
# AI lesson breakdown helpers
# ---------------------------------------------------------------------------

# LP types by subject for Claude prompt
_LP_TYPES_BY_SUBJECT = {
    "english": "Reading, Vocabulary, Comprehension (Word Meanings), Comprehension (Q&A), Grammar, Creative Writing, Revision",
    "maths": "Concept Introduction, Concrete Practice, Pictorial & Abstract, Word Problems, Revision",
    "mathematics": "Concept Introduction, Concrete Practice, Pictorial & Abstract, Word Problems, Revision",
    "urdu": "Qiraat, Lughat, Grammar, Tehrir, Islah, Dohrai",
}
_DEFAULT_LP_TYPES = "Introduction, Practice, Review, Revision"

_BREAKDOWN_SYSTEM_PROMPT = """You are an expert Pakistani school curriculum planner. Given a chapter's details,
design an optimal lesson sequence using the available LP types for the subject.

LP types by subject:
- English: Reading, Vocabulary, Comprehension (Word Meanings), Comprehension (Q&A),
           Grammar, Creative Writing, Revision
- Maths / Mathematics: Concept Introduction, Concrete Practice, Pictorial & Abstract,
         Word Problems, Revision
- Urdu: Qiraat, Lughat, Grammar, Tehrir, Islah, Dohrai
- Default: Introduction, Practice, Review, Revision

Rules:
1. The LAST slot of a chapter is ALWAYS "Revision" (type: lesson)
2. Insert one Formative Assessment (type: assessment, assessment_type: "formative") after every 3-4 teaching lesson days
3. Never place a Formative Assessment on the first or last day
4. Distribute LP types to cover chapter topics evenly
5. Return ONLY valid JSON — no markdown, no explanation

Return JSON array only:
[
  {"day": 1, "type": "lesson", "lp_type": "Reading", "title": "Title of lesson"},
  {"day": 3, "type": "assessment", "assessment_type": "formative", "title": "Chapter FA 1"},
  ...
]"""


def _extract_json_array_from_response(response: str) -> list:
    """Extract JSON array from LLM response using two fallback strategies."""
    if not response or not isinstance(response, str):
        return []

    # Strategy 1: ```json ... ``` code block
    code_block = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n?\s*```", response)
    if code_block:
        try:
            result = json.loads(code_block.group(1).strip())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError as exc:
            logger.debug("code-block JSON parse failed — %s", exc)

    # Strategy 2: greedy bracket match — find outermost [ ... ]
    greedy = re.search(r"\[[\s\S]*\]", response)
    if greedy:
        try:
            result = json.loads(greedy.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError as exc:
            logger.debug("greedy JSON parse failed — %s", exc)

    return []


async def ai_breakdown_chapter(
    chapter_plan_id: int,
    db: AsyncSession,
    global_day_offset: int = 0,
) -> dict:
    """
    Use Claude to generate a pedagogically sound lesson sequence for a chapter plan.
    Creates ClassLessonSlot rows (lessons) and AssessmentSlot rows (formative only).
    Falls back to generate_lesson_sequence() if Claude fails.

    global_day_offset: the running day count before this chapter (so day_number is
    globally unique across all chapters for the CST, not per-chapter).

    Returns {"lesson_slots": [...], "assessment_slots": [], "days_used": N}.
    """
    logger.info("ai_breakdown_chapter: chapter_plan_id=%s", chapter_plan_id)

    # 1. Load ChapterPlan
    plan_result = await db.execute(select(ChapterPlan).where(ChapterPlan.id == chapter_plan_id))
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        logger.error("ai_breakdown_chapter: chapter_plan_id=%s not found", chapter_plan_id)
        return {"lesson_slots": [], "assessment_slots": []}

    # 2. Load ClassSubjectTeacher
    cst_result = await db.execute(
        select(ClassSubjectTeacher).where(ClassSubjectTeacher.id == plan.class_subject_teacher_id)
    )
    cst = cst_result.scalar_one_or_none()
    if cst is None:
        logger.error("ai_breakdown_chapter: CST not found for chapter_plan_id=%s", chapter_plan_id)
        return {"lesson_slots": [], "assessment_slots": []}

    # 3. Load BookChapter
    chapter_result = await db.execute(
        select(BookChapter).where(BookChapter.id == plan.chapter_id)
    )
    book_chapter = chapter_result.scalar_one_or_none()
    chapter_title = book_chapter.title if book_chapter else "Unknown Chapter"
    chapter_number = book_chapter.chapter_number if book_chapter else 1

    # 4. Load SchoolClass
    class_result = await db.execute(
        select(SchoolClass).where(SchoolClass.id == cst.class_id)
    )
    school_class = class_result.scalar_one_or_none()

    # 5. Load Topics
    topics_result = await db.execute(
        select(Topic)
        .where(Topic.chapter_id == plan.chapter_id)
        .order_by(Topic.topic_number)
    )
    topics = list(topics_result.scalars().all())
    topic_list = ", ".join(t.title for t in topics) if topics else "General chapter content"

    from dars.lookup.service import get_grade_code as _ggc_bd, get_subject_code
    grade = (await _ggc_bd(db, school_class.grade_id) if school_class and school_class.grade_id else None) or "?"
    subject_code = await get_subject_code(db, cst.subject_id) if cst.subject_id else "General"
    subject = subject_code or "General"
    teaching_days = plan.teaching_days
    lp_types_hint = _LP_TYPES_BY_SUBJECT.get(subject.lower(), _DEFAULT_LP_TYPES)

    user_prompt = (
        f"Chapter: {chapter_title} (Chapter {chapter_number})\n"
        f"Subject: {subject}, Grade: {grade}\n"
        f"Teaching days: {teaching_days}\n"
        f"Topics: {topic_list}\n"
        f"Available LP types: {lp_types_hint}"
    )

    try:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured")

        logger.info(
            "ai_breakdown_chapter: calling Claude — chapter=%r subject=%r days=%d",
            chapter_title, subject, teaching_days,
        )

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=_BREAKDOWN_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = message.content[0].text
        logger.info(
            "ai_breakdown_chapter: Claude response received — chars=%d chapter=%r",
            len(raw), chapter_title,
        )

        items = _extract_json_array_from_response(raw)
        if not items:
            raise ValueError(f"Empty or unparseable Claude response for chapter {chapter_plan_id}")

        # 9. Delete existing ClassLessonSlot rows
        await db.execute(
            delete(ClassLessonSlot).where(ClassLessonSlot.chapter_plan_id == chapter_plan_id)
        )

        # 10. Delete existing formative AssessmentSlot rows (preserve summative)
        await db.execute(
            delete(AssessmentSlot).where(
                AssessmentSlot.chapter_plan_id == chapter_plan_id,
                AssessmentSlot.assessment_type.in_(["FA", "formative"]),
            )
        )

        # 11+12. Insert new slots — day numbers are global (offset + local day)
        lesson_slots: list[ClassLessonSlot] = []
        assessment_slots: list[AssessmentSlot] = []
        fa_counter = 1
        max_local_day = 0

        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type", "lesson")
            local_day = item.get("day", 1)
            global_day = global_day_offset + local_day
            max_local_day = max(max_local_day, local_day)

            if item_type == "lesson":
                lp_type = item.get("lp_type", "Introduction")
                title = item.get("title", f"Day {global_day}: {lp_type}")
                slot = ClassLessonSlot(
                    client_id=cst.client_id,
                    class_subject_teacher_id=cst.id,
                    chapter_plan_id=chapter_plan_id,
                    day_number=global_day,
                    lp_type=lp_type,
                    title=title,
                    status="planned",
                )
                db.add(slot)
                lesson_slots.append(slot)

            elif item_type == "assessment":
                assessment_type = item.get("assessment_type", "formative")
                title = item.get("title", f"Formative Assessment {fa_counter}")
                fa_counter += 1
                aslot = AssessmentSlot(
                    client_id=cst.client_id,
                    class_subject_teacher_id=cst.id,
                    chapter_plan_id=chapter_plan_id,
                    assessment_type=assessment_type,
                    day_number=global_day,
                    scheduled_date=None,
                    title=title,
                    status="scheduled",
                )
                db.add(aslot)
                assessment_slots.append(aslot)

        await db.flush()
        for s in lesson_slots:
            await db.refresh(s)
        for s in assessment_slots:
            await db.refresh(s)

        await db.commit()
        days_used = max_local_day
        logger.info(
            "ai_breakdown_chapter: done chapter_plan_id=%s lesson_slots=%d assessment_slots=%d days_used=%d",
            chapter_plan_id, len(lesson_slots), len(assessment_slots), days_used,
        )
        return {"lesson_slots": lesson_slots, "assessment_slots": assessment_slots, "days_used": days_used}

    except Exception:
        logger.error(
            "ai_breakdown_chapter: Claude failed for chapter_plan_id=%s — falling back to generate_lesson_sequence",
            chapter_plan_id,
            exc_info=True,
        )
        fallback_slots = await generate_lesson_sequence(chapter_plan_id, db, global_day_offset=global_day_offset)
        days_used = max((s.day_number - global_day_offset for s in fallback_slots), default=0)
        return {"lesson_slots": fallback_slots, "assessment_slots": [], "days_used": days_used}


async def ai_breakdown_all(
    cst_id: int,
    db: AsyncSession,
) -> dict:
    """
    Run AI lesson breakdown for all chapter plans of a CST, ordered by position.
    Returns summary counts.
    """
    logger.info("ai_breakdown_all: cst_id=%s", cst_id)

    plans_result = await db.execute(
        select(ChapterPlan)
        .where(ChapterPlan.class_subject_teacher_id == cst_id)
        .order_by(ChapterPlan.position)
    )
    plans = list(plans_result.scalars().all())

    total_lesson_slots = 0
    total_assessment_slots = 0
    global_offset = 0

    for plan in plans:
        result = await ai_breakdown_chapter(plan.id, db, global_day_offset=global_offset)
        total_lesson_slots += len(result["lesson_slots"])
        total_assessment_slots += len(result["assessment_slots"])
        global_offset += result.get("days_used", plan.teaching_days)

    logger.info(
        "ai_breakdown_all: cst_id=%s chapters=%d lesson_slots=%d assessment_slots=%d",
        cst_id, len(plans), total_lesson_slots, total_assessment_slots,
    )
    return {
        "chapters_planned": len(plans),
        "total_lesson_slots": total_lesson_slots,
        "total_assessment_slots": total_assessment_slots,
    }


# ---------------------------------------------------------------------------
# LP & Exam generation from slots
# ---------------------------------------------------------------------------


async def generate_lp_for_slot(
    db: AsyncSession,
    slot_id: int,
    client_id: int,
    curriculum: str,
) -> GeneratedLP:
    """
    Create a GeneratedLP from a ClassLessonSlot and link it back to the slot.
    Returns the GeneratedLP (status=PENDING). Background task runs separately.
    Raises 404 if slot not found or doesn't belong to client.
    Raises 409 if slot already has a lesson_plan_id.
    """
    logger.info("generate_lp_for_slot: slot_id=%s client_id=%s", slot_id, client_id)

    slot_result = await db.execute(
        select(ClassLessonSlot).where(
            ClassLessonSlot.id == slot_id,
            ClassLessonSlot.client_id == client_id,
        )
    )
    slot = slot_result.scalar_one_or_none()
    if slot is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Lesson slot not found")

    if slot.lesson_plan_id is not None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Lesson slot already has a lesson plan",
        )

    # Load chapter plan → CST → SchoolClass for grade and subject
    plan_result = await db.execute(select(ChapterPlan).where(ChapterPlan.id == slot.chapter_plan_id))
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Chapter plan not found")

    cst_result = await db.execute(
        select(ClassSubjectTeacher).where(ClassSubjectTeacher.id == slot.class_subject_teacher_id)
    )
    cst = cst_result.scalar_one_or_none()
    if cst is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Class subject teacher not found")

    class_result = await db.execute(select(SchoolClass).where(SchoolClass.id == cst.class_id))
    school_class = class_result.scalar_one_or_none()

    from dars.lookup.service import get_grade_code as _ggc_lp, get_subject_code as _gsc
    grade = (await _ggc_lp(db, school_class.grade_id) if school_class and school_class.grade_id else None) or 5
    subject_code = (await _gsc(db, cst.subject_id) if cst.subject_id else None) or "General"

    lp_data = GeneratedLPCreate(
        grade=grade,
        subject=subject_code,
        topic=slot.title,
        lp_type=slot.lp_type,
        external_id=str(slot_id),
    )
    lp = await create_generated_lp(db, client_id, lp_data, curriculum)

    slot.lesson_plan_id = lp.id
    await db.commit()
    await db.refresh(slot)

    logger.info(
        "generate_lp_for_slot: slot_id=%s lp_id=%s status=%s", slot_id, lp.id, lp.status
    )
    return lp


async def generate_all_lps_for_chapter(
    db: AsyncSession,
    chapter_plan_id: int,
    client_id: int,
    curriculum: str,
) -> tuple[list[tuple[int, GeneratedLPCreate]], int]:
    """
    Queue LP generation for all 'planned' slots in a chapter_plan that don't have a lesson_plan_id yet.
    Returns (list_of_(lp_id, request_data), skipped_count).
    Skipped = slots that already have a lesson_plan_id.
    """
    logger.info(
        "generate_all_lps_for_chapter: chapter_plan_id=%s client_id=%s", chapter_plan_id, client_id
    )

    plan_result = await db.execute(
        select(ChapterPlan).where(
            ChapterPlan.id == chapter_plan_id,
            ChapterPlan.client_id == client_id,
        )
    )
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Chapter plan not found")

    cst_result = await db.execute(
        select(ClassSubjectTeacher).where(ClassSubjectTeacher.id == plan.class_subject_teacher_id)
    )
    cst = cst_result.scalar_one_or_none()
    from dars.lookup.service import get_subject_code as _gsc2
    subject = (await _gsc2(db, cst.subject_id) if cst and cst.subject_id else None) or "General"

    grade = 5
    if cst is not None:
        class_result2 = await db.execute(select(SchoolClass).where(SchoolClass.id == cst.class_id))
        school_class2 = class_result2.scalar_one_or_none()
        if school_class2 and school_class2.grade_id:
            from dars.lookup.service import get_grade_code as _ggc2
            grade = (await _ggc2(db, school_class2.grade_id)) or 5

    slots_result = await db.execute(
        select(ClassLessonSlot).where(
            ClassLessonSlot.chapter_plan_id == chapter_plan_id,
            ClassLessonSlot.client_id == client_id,
        ).order_by(ClassLessonSlot.day_number)
    )
    all_slots = list(slots_result.scalars().all())

    queued_pairs: list[tuple[int, GeneratedLPCreate]] = []
    skipped = 0

    for slot in all_slots:
        if slot.lesson_plan_id is not None:
            skipped += 1
            continue

        lp_data = GeneratedLPCreate(
            grade=grade,
            subject=subject,
            topic=slot.title,
            lp_type=slot.lp_type,
            external_id=str(slot.id),
        )
        lp = await create_generated_lp(db, client_id, lp_data, curriculum)
        slot.lesson_plan_id = lp.id
        await db.flush()
        queued_pairs.append((lp.id, lp_data))

    await db.commit()
    logger.info(
        "generate_all_lps_for_chapter: chapter_plan_id=%s queued=%d skipped=%d",
        chapter_plan_id, len(queued_pairs), skipped,
    )
    return queued_pairs, skipped


async def generate_exam_for_slot(
    db: AsyncSession,
    slot_id: int,
    client_id: int,
    curriculum: str,
) -> GeneratedExam:
    """
    Create a GeneratedExam from an AssessmentSlot and link it back to the slot.
    Returns the GeneratedExam (status=PENDING). Background task runs separately.
    Raises 404 if slot not found or doesn't belong to client.
    Raises 409 if slot already has an exam_id.
    """
    logger.info("generate_exam_for_slot: slot_id=%s client_id=%s", slot_id, client_id)

    slot_result = await db.execute(
        select(AssessmentSlot).where(
            AssessmentSlot.id == slot_id,
            AssessmentSlot.client_id == client_id,
        )
    )
    slot = slot_result.scalar_one_or_none()
    if slot is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Assessment slot not found")

    if slot.exam_id is not None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Assessment slot already has an exam",
        )

    cst_result = await db.execute(
        select(ClassSubjectTeacher).where(ClassSubjectTeacher.id == slot.class_subject_teacher_id)
    )
    cst = cst_result.scalar_one_or_none()
    if cst is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Class subject teacher not found")

    class_result = await db.execute(select(SchoolClass).where(SchoolClass.id == cst.class_id))
    school_class = class_result.scalar_one_or_none()

    from dars.lookup.service import get_grade_code as _ggc_ex, get_subject_code as _gsc3
    grade = (await _ggc_ex(db, school_class.grade_id) if school_class and school_class.grade_id else None) or 5
    subject_code3 = (await _gsc3(db, cst.subject_id) if cst.subject_id else None) or "General"

    exam_data = GeneratedExamCreate(
        grade=grade,
        subject=subject_code3,
        page_ranges="1-50",
        generation_type=slot.assessment_type if slot.assessment_type in ("exam", "formative", "summative") else "exam",
        external_id=str(slot_id),
    )
    exam = await create_generated_exam(db, client_id, exam_data, curriculum)

    slot.exam_id = exam.id
    await db.commit()
    await db.refresh(slot)

    logger.info(
        "generate_exam_for_slot: slot_id=%s exam_id=%s status=%s", slot_id, exam.id, exam.status
    )
    return exam


async def generate_lesson_sequence(
    chapter_plan_id: int,
    db: AsyncSession,
    global_day_offset: int = 0,
) -> list[ClassLessonSlot]:
    """
    Generate ClassLessonSlot rows for a chapter plan using subject-aware LP type cycling.
    Deletes any existing rows for this chapter plan, then inserts fresh ones.
    Last slot is always "Revision".

    global_day_offset: added to each local day_number so slots are globally unique.
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

    from dars.lookup.service import get_subject_code as _gsc4
    subject_str = (await _gsc4(db, cst.subject_id) if cst.subject_id else None) or "General"
    subject_key = subject_str.lower()
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
    for local_day, lp_type in enumerate(lp_types, start=1):
        global_day = global_day_offset + local_day
        slot = ClassLessonSlot(
            client_id=cst.client_id,
            class_subject_teacher_id=cst.id,
            chapter_plan_id=chapter_plan_id,
            day_number=global_day,
            lp_type=lp_type,
            title=f"Day {global_day}: {lp_type}",
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


# ---------------------------------------------------------------------------
# Calendar week computation
# ---------------------------------------------------------------------------


async def get_calendar_week(
    client_id: int,
    teacher_id: int,
    week_start: date,
    db: AsyncSession,
) -> dict:
    """
    Return one period per (class, academic day in week).
    Day numbers from the breakdown sequence map 1:1 to academic days (Mon–Sat, no holidays).
    Assessment slots take priority over lesson slots on the same day.
    """
    week_end = week_start + timedelta(days=6)
    logger.info(
        "get_calendar_week: client_id=%s teacher_id=%s week=%s..%s",
        client_id, teacher_id, week_start, week_end,
    )

    from dars.lookup.models import Subject

    # All CSTs for this teacher
    cst_result = await db.execute(
        select(ClassSubjectTeacher).where(
            ClassSubjectTeacher.client_id == client_id,
            ClassSubjectTeacher.teacher_id == teacher_id,
        )
    )
    csts = list(cst_result.scalars().all())

    # day_map: date → list[period dicts]
    day_map: dict[date, list] = {}
    for i in range(7):
        day_map[week_start + timedelta(days=i)] = []

    for cst in csts:
        sc = await db.get(SchoolClass, cst.class_id)
        if sc is None:
            continue

        subject_obj = await db.get(Subject, cst.subject_id)
        subject_display = subject_obj.display_name if subject_obj else str(cst.subject_id)

        # Build global day_number → date index from academic teaching days
        teaching_days = await compute_teaching_days(cst.id, db)
        if not teaching_days:
            continue
        day_num_to_date: dict[int, date] = {
            i + 1: d for i, d in enumerate(teaching_days)
        }
        # Reverse: date → day_number (for the week range)
        week_dates = {week_start + timedelta(days=i) for i in range(7)}
        date_to_day_num: dict[date, int] = {
            d: n for n, d in day_num_to_date.items() if d in week_dates
        }

        if not date_to_day_num:
            continue  # no academic days in this week for this CST

        week_day_nums = set(date_to_day_num.values())

        # Lesson slots whose day_number falls in this week
        lesson_slots_result = await db.execute(
            select(ClassLessonSlot).where(
                ClassLessonSlot.class_subject_teacher_id == cst.id,
                ClassLessonSlot.client_id == client_id,
                ClassLessonSlot.day_number.in_(week_day_nums),
            )
        )
        lessons_by_day: dict[int, ClassLessonSlot] = {}
        for slot in lesson_slots_result.scalars().all():
            lessons_by_day[slot.day_number] = slot

        # Assessment slots whose day_number falls in this week
        assessments_result = await db.execute(
            select(AssessmentSlot).where(
                AssessmentSlot.class_subject_teacher_id == cst.id,
                AssessmentSlot.client_id == client_id,
                AssessmentSlot.day_number.in_(week_day_nums),
            )
        )
        assessments_by_day: dict[int, list] = {}
        for aslot in assessments_result.scalars().all():
            if aslot.day_number is not None:
                assessments_by_day.setdefault(aslot.day_number, []).append(aslot)

        # Also include assessment slots with explicit scheduled_date in this week
        # (legacy / manual entries that predate the day_number migration)
        legacy_assessments_result = await db.execute(
            select(AssessmentSlot).where(
                AssessmentSlot.class_subject_teacher_id == cst.id,
                AssessmentSlot.client_id == client_id,
                AssessmentSlot.day_number.is_(None),
                AssessmentSlot.scheduled_date >= week_start,
                AssessmentSlot.scheduled_date <= week_end,
            )
        )
        legacy_by_date: dict[date, list] = {}
        for aslot in legacy_assessments_result.scalars().all():
            if aslot.scheduled_date is not None:
                legacy_by_date.setdefault(aslot.scheduled_date, []).append(aslot)

        # Emit one period per academic day in this week
        for d, day_num in sorted(date_to_day_num.items()):
            base = {
                "date": d,
                "cst_id": cst.id,
                "class_id": sc.id,
                "class_name": sc.name,
                "subject": subject_display,
            }

            if day_num in assessments_by_day:
                for aslot in assessments_by_day[day_num]:
                    day_map[d].append({
                        **base,
                        "period_type": "assessment",
                        "assessment_slot_id": aslot.id,
                        "assessment_type": aslot.assessment_type,
                        "assessment_title": aslot.title,
                        "assessment_status": aslot.status,
                        "exam_id": aslot.exam_id,
                    })
            elif d in legacy_by_date:
                for aslot in legacy_by_date[d]:
                    day_map[d].append({
                        **base,
                        "period_type": "assessment",
                        "assessment_slot_id": aslot.id,
                        "assessment_type": aslot.assessment_type,
                        "assessment_title": aslot.title,
                        "assessment_status": aslot.status,
                        "exam_id": aslot.exam_id,
                    })
            elif day_num in lessons_by_day:
                slot = lessons_by_day[day_num]
                day_map[d].append({
                    **base,
                    "period_type": "lesson",
                    "slot_id": slot.id,
                    "day_number": slot.day_number,
                    "lp_type": slot.lp_type,
                    "title": slot.title,
                    "lesson_status": slot.status,
                    "lesson_plan_id": slot.lesson_plan_id,
                })
            else:
                day_map[d].append({
                    **base,
                    "period_type": "no_breakdown",
                })

    total_periods = sum(len(v) for v in day_map.values())
    logger.info("get_calendar_week: week=%s total_periods=%d", week_start, total_periods)
    items = [{"date": week_start + timedelta(days=i), "periods": day_map[week_start + timedelta(days=i)]} for i in range(7)]
    return {"items": items, "week_start": week_start, "week_end": week_end}
