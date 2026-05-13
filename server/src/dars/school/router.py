import logging
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_current_client
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
from dars.school.schemas import (
    AcademicYearCreate,
    AcademicYearListResponse,
    AcademicYearRead,
    AssessmentSlotCreate,
    AssessmentSlotListResponse,
    AssessmentSlotRead,
    AssessmentSlotUpdate,
    BreakdownYearResponse,
    ChapterPlanBulkUpsertRequest,
    ChapterPlanListResponse,
    ChapterPlanRead,
    ChapterPlanUpdate,
    ChapterPlanWithDates,
    ClassLessonSlotListResponse,
    ClassLessonSlotRead,
    ClassLessonSlotUpdate,
    CSTCreate,
    CSTRead,
    CSTUpdate,
    GenerateAllLPsResponse,
    GenerateExamResponse,
    GenerateLPResponse,
    HolidayCreate,
    HolidayListResponse,
    HolidayRead,
    SchoolClassCreate,
    SchoolClassListResponse,
    SchoolClassRead,
    SchoolClassWithSubjects,
    TeachingDaysResponse,
    TimetableResponse,
    TimetableSetRequest,
    TimetableSlotRead,
    TodaySlotEntry,
)
from dars.curriculum.schemas import PrefillChapterPlan, PrefillResponse
from dars.generated_exams.service import generate_exam_task
from dars.generated_lps.service import generate_lp_task
from dars.school.service import (
    ai_breakdown_all,
    ai_breakdown_chapter,
    auto_schedule_formative_assessments,
    compute_chapter_date_ranges,
    compute_teaching_days_for_year,
    generate_all_lps_for_chapter,
    generate_exam_for_slot,
    generate_lp_for_slot,
    generate_lesson_sequence,
    get_prefill_chapter_plans,
)
from dars.teachers.models import Teacher

logger = logging.getLogger(__name__)

router = APIRouter(tags=["school"])


# ---------------------------------------------------------------------------
# Academic Years
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/academic-years",
    response_model=AcademicYearRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_academic_year(
    body: AcademicYearCreate,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> AcademicYearRead:
    logger.info(
        "create_academic_year: client_id=%s name=%r", current_client.id, body.name
    )
    obj = AcademicYear(
        client_id=current_client.id,
        name=body.name,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    logger.info("create_academic_year: done id=%s", obj.id)
    return AcademicYearRead.model_validate(obj)


@router.get("/api/v1/academic-years", response_model=AcademicYearListResponse)
async def list_academic_years(
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> AcademicYearListResponse:
    logger.info("list_academic_years: client_id=%s", current_client.id)
    result = await db.execute(
        select(AcademicYear).where(AcademicYear.client_id == current_client.id)
    )
    items = list(result.scalars().all())
    logger.info("list_academic_years: client_id=%s count=%d", current_client.id, len(items))
    return AcademicYearListResponse(
        items=[AcademicYearRead.model_validate(y) for y in items],
        total=len(items),
    )


@router.get(
    "/api/v1/academic-years/{year_id}/teaching-days",
    response_model=TeachingDaysResponse,
)
async def get_teaching_days(
    year_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> TeachingDaysResponse:
    logger.info("get_teaching_days: client_id=%s year_id=%s", current_client.id, year_id)
    year = await db.get(AcademicYear, year_id)
    if year is None or year.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")
    count = await compute_teaching_days_for_year(year_id, db)
    logger.info("get_teaching_days: year_id=%s count=%d", year_id, count)
    return TeachingDaysResponse(academic_year_id=year_id, teaching_days=count)


# ---------------------------------------------------------------------------
# Holidays
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/academic-years/{year_id}/holidays",
    response_model=HolidayRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_holiday(
    year_id: uuid.UUID,
    body: HolidayCreate,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> HolidayRead:
    logger.info("add_holiday: client_id=%s year_id=%s date=%s", current_client.id, year_id, body.date)
    year = await db.get(AcademicYear, year_id)
    if year is None or year.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")
    obj = Holiday(
        client_id=current_client.id,
        academic_year_id=year_id,
        date=body.date,
        name=body.name,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    logger.info("add_holiday: done id=%s", obj.id)
    return HolidayRead.model_validate(obj)


@router.get("/api/v1/academic-years/{year_id}/holidays", response_model=HolidayListResponse)
async def list_holidays(
    year_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> HolidayListResponse:
    logger.info("list_holidays: client_id=%s year_id=%s", current_client.id, year_id)
    year = await db.get(AcademicYear, year_id)
    if year is None or year.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")
    result = await db.execute(
        select(Holiday).where(
            Holiday.academic_year_id == year_id,
            Holiday.client_id == current_client.id,
        )
    )
    items = list(result.scalars().all())
    logger.info("list_holidays: count=%d", len(items))
    return HolidayListResponse(
        items=[HolidayRead.model_validate(h) for h in items],
        total=len(items),
    )


@router.delete(
    "/api/v1/academic-years/{year_id}/holidays/{holiday_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_holiday(
    year_id: uuid.UUID,
    holiday_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> None:
    logger.info("delete_holiday: holiday_id=%s", holiday_id)
    obj = await db.get(Holiday, holiday_id)
    if (
        obj is None
        or obj.client_id != current_client.id
        or obj.academic_year_id != year_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")
    await db.delete(obj)
    await db.commit()
    logger.info("delete_holiday: done holiday_id=%s", holiday_id)


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/classes",
    response_model=SchoolClassRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_class(
    body: SchoolClassCreate,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> SchoolClassRead:
    logger.info(
        "create_class: client_id=%s grade=%s section=%r", current_client.id, body.grade, body.section
    )
    year = await db.get(AcademicYear, body.academic_year_id)
    if year is None or year.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")
    obj = SchoolClass(
        client_id=current_client.id,
        academic_year_id=body.academic_year_id,
        grade=body.grade,
        section=body.section,
        name=body.name,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    logger.info("create_class: done id=%s", obj.id)
    return SchoolClassRead.model_validate(obj)


@router.get("/api/v1/classes", response_model=SchoolClassListResponse)
async def list_classes(
    academic_year_id: uuid.UUID | None = Query(default=None),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> SchoolClassListResponse:
    logger.info("list_classes: client_id=%s academic_year_id=%s", current_client.id, academic_year_id)
    q = select(SchoolClass).where(SchoolClass.client_id == current_client.id)
    if academic_year_id:
        q = q.where(SchoolClass.academic_year_id == academic_year_id)
    result = await db.execute(q)
    items = list(result.scalars().all())
    logger.info("list_classes: count=%d", len(items))
    return SchoolClassListResponse(
        items=[SchoolClassRead.model_validate(c) for c in items],
        total=len(items),
    )


@router.get("/api/v1/classes/{class_id}", response_model=SchoolClassWithSubjects)
async def get_class(
    class_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> SchoolClassWithSubjects:
    logger.info("get_class: class_id=%s", class_id)
    obj = await db.get(SchoolClass, class_id)
    if obj is None or obj.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    cst_result = await db.execute(
        select(ClassSubjectTeacher).where(
            ClassSubjectTeacher.class_id == class_id,
            ClassSubjectTeacher.client_id == current_client.id,
        )
    )
    subjects = list(cst_result.scalars().all())
    data = SchoolClassWithSubjects.model_validate(obj)
    data.subjects = [CSTRead.model_validate(s) for s in subjects]
    logger.info("get_class: class_id=%s subjects=%d", class_id, len(subjects))
    return data


@router.post(
    "/api/v1/classes/{class_id}/subjects",
    response_model=CSTRead,
    status_code=status.HTTP_201_CREATED,
)
async def assign_subject(
    class_id: uuid.UUID,
    body: CSTCreate,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> CSTRead:
    logger.info(
        "assign_subject: class_id=%s subject=%r client_id=%s", class_id, body.subject, current_client.id
    )
    sc = await db.get(SchoolClass, class_id)
    if sc is None or sc.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    obj = ClassSubjectTeacher(
        client_id=current_client.id,
        class_id=class_id,
        subject=body.subject,
        teacher_id=body.teacher_id,
        book_id=body.book_id,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    logger.info("assign_subject: done cst_id=%s", obj.id)
    return CSTRead.model_validate(obj)


@router.patch(
    "/api/v1/classes/{class_id}/subjects/{cst_id}",
    response_model=CSTRead,
)
async def update_subject(
    class_id: uuid.UUID,
    cst_id: uuid.UUID,
    body: CSTUpdate,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> CSTRead:
    logger.info("update_subject: cst_id=%s", cst_id)
    obj = await db.get(ClassSubjectTeacher, cst_id)
    if obj is None or obj.client_id != current_client.id or obj.class_id != class_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject assignment not found")
    if body.teacher_id is not None:
        obj.teacher_id = body.teacher_id
    if body.book_id is not None:
        obj.book_id = body.book_id
    await db.commit()
    await db.refresh(obj)
    logger.info("update_subject: done cst_id=%s", cst_id)
    return CSTRead.model_validate(obj)


# ---------------------------------------------------------------------------
# Timetable
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/classes/{class_id}/subjects/{cst_id}/timetable",
    response_model=TimetableResponse,
)
async def set_timetable(
    class_id: uuid.UUID,
    cst_id: uuid.UUID,
    body: TimetableSetRequest,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> TimetableResponse:
    logger.info("set_timetable: cst_id=%s slots=%d", cst_id, len(body.slots))
    obj = await db.get(ClassSubjectTeacher, cst_id)
    if obj is None or obj.client_id != current_client.id or obj.class_id != class_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject assignment not found")
    # Delete existing
    await db.execute(
        delete(Timetable).where(Timetable.class_subject_teacher_id == cst_id)
    )
    new_rows: list[Timetable] = []
    for s in body.slots:
        row = Timetable(
            client_id=current_client.id,
            class_subject_teacher_id=cst_id,
            day_of_week=s.day_of_week,
            start_time=s.start_time,
            end_time=s.end_time,
        )
        db.add(row)
        new_rows.append(row)
    await db.flush()
    for row in new_rows:
        await db.refresh(row)
    await db.commit()
    logger.info("set_timetable: done cst_id=%s inserted=%d", cst_id, len(new_rows))
    return TimetableResponse(items=[TimetableSlotRead.model_validate(r) for r in new_rows])


@router.get(
    "/api/v1/classes/{class_id}/subjects/{cst_id}/timetable",
    response_model=TimetableResponse,
)
async def get_timetable(
    class_id: uuid.UUID,
    cst_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> TimetableResponse:
    logger.info("get_timetable: cst_id=%s", cst_id)
    obj = await db.get(ClassSubjectTeacher, cst_id)
    if obj is None or obj.client_id != current_client.id or obj.class_id != class_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject assignment not found")
    result = await db.execute(
        select(Timetable).where(Timetable.class_subject_teacher_id == cst_id)
    )
    rows = list(result.scalars().all())
    logger.info("get_timetable: cst_id=%s rows=%d", cst_id, len(rows))
    return TimetableResponse(items=[TimetableSlotRead.model_validate(r) for r in rows])


# ---------------------------------------------------------------------------
# Chapter Plans
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/classes/{class_id}/subjects/{cst_id}/chapter-plans",
    response_model=ChapterPlanListResponse,
)
async def bulk_upsert_chapter_plans(
    class_id: uuid.UUID,
    cst_id: uuid.UUID,
    body: ChapterPlanBulkUpsertRequest,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ChapterPlanListResponse:
    logger.info(
        "bulk_upsert_chapter_plans: cst_id=%s plans=%d", cst_id, len(body.plans)
    )
    obj = await db.get(ClassSubjectTeacher, cst_id)
    if obj is None or obj.client_id != current_client.id or obj.class_id != class_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject assignment not found")

    results: list[ChapterPlan] = []
    for item in body.plans:
        # Try to find existing
        existing_result = await db.execute(
            select(ChapterPlan).where(
                ChapterPlan.class_subject_teacher_id == cst_id,
                ChapterPlan.chapter_id == item.chapter_id,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            existing.position = item.position
            existing.teaching_days = item.teaching_days
            await db.flush()
            await db.refresh(existing)
            results.append(existing)
        else:
            plan = ChapterPlan(
                client_id=current_client.id,
                class_subject_teacher_id=cst_id,
                chapter_id=item.chapter_id,
                position=item.position,
                teaching_days=item.teaching_days,
            )
            db.add(plan)
            await db.flush()
            await db.refresh(plan)
            results.append(plan)

    await db.commit()

    # Attach computed date ranges and curriculum defaults
    date_ranges_list = await compute_chapter_date_ranges(cst_id, db)
    dr_map = {dr["chapter_plan_id"]: dr for dr in date_ranges_list}

    prefill_items = await get_prefill_chapter_plans(cst_id, db)
    prefill_map = {str(p["chapter_id"]): p for p in prefill_items}

    items: list[ChapterPlanWithDates] = []
    for plan in sorted(results, key=lambda p: p.position):
        dr = dr_map.get(plan.id, {})
        r = ChapterPlanWithDates.model_validate(plan)
        r.start_date = dr.get("start_date")
        r.end_date = dr.get("end_date")
        pf = prefill_map.get(str(plan.chapter_id), {})
        r.suggested_teaching_days = pf.get("suggested_teaching_days")
        r.suggested_position = pf.get("suggested_position")
        items.append(r)

    logger.info("bulk_upsert_chapter_plans: done cst_id=%s count=%d", cst_id, len(items))
    return ChapterPlanListResponse(items=items)


@router.get(
    "/api/v1/classes/{class_id}/subjects/{cst_id}/chapter-plans",
    response_model=ChapterPlanListResponse,
)
async def list_chapter_plans(
    class_id: uuid.UUID,
    cst_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ChapterPlanListResponse:
    logger.info("list_chapter_plans: cst_id=%s", cst_id)
    obj = await db.get(ClassSubjectTeacher, cst_id)
    if obj is None or obj.client_id != current_client.id or obj.class_id != class_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject assignment not found")

    plans_result = await db.execute(
        select(ChapterPlan)
        .where(ChapterPlan.class_subject_teacher_id == cst_id)
        .order_by(ChapterPlan.position)
    )
    plans = list(plans_result.scalars().all())

    date_ranges_list = await compute_chapter_date_ranges(cst_id, db)
    dr_map = {dr["chapter_plan_id"]: dr for dr in date_ranges_list}

    # Fetch curriculum defaults keyed by chapter_id
    prefill_items = await get_prefill_chapter_plans(cst_id, db)
    prefill_map = {str(p["chapter_id"]): p for p in prefill_items}

    items: list[ChapterPlanWithDates] = []
    for plan in plans:
        dr = dr_map.get(plan.id, {})
        r = ChapterPlanWithDates.model_validate(plan)
        r.start_date = dr.get("start_date")
        r.end_date = dr.get("end_date")
        pf = prefill_map.get(str(plan.chapter_id), {})
        r.suggested_teaching_days = pf.get("suggested_teaching_days")
        r.suggested_position = pf.get("suggested_position")
        items.append(r)

    logger.info("list_chapter_plans: cst_id=%s count=%d", cst_id, len(items))
    return ChapterPlanListResponse(items=items)


@router.get(
    "/api/v1/classes/{class_id}/subjects/{cst_id}/chapter-plans/prefill",
    response_model=PrefillResponse,
)
async def prefill_chapter_plans(
    class_id: uuid.UUID,
    cst_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> PrefillResponse:
    logger.info("prefill_chapter_plans: cst_id=%s", cst_id)
    obj = await db.get(ClassSubjectTeacher, cst_id)
    if obj is None or obj.client_id != current_client.id or obj.class_id != class_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject assignment not found")
    items = await get_prefill_chapter_plans(cst_id, db)
    logger.info("prefill_chapter_plans: cst_id=%s returned=%d", cst_id, len(items))
    return PrefillResponse(items=[PrefillChapterPlan(**item) for item in items])


@router.patch("/api/v1/chapter-plans/{plan_id}", response_model=ChapterPlanRead)
async def update_chapter_plan(
    plan_id: uuid.UUID,
    body: ChapterPlanUpdate,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ChapterPlanRead:
    logger.info("update_chapter_plan: plan_id=%s", plan_id)
    plan = await db.get(ChapterPlan, plan_id)
    if plan is None or plan.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter plan not found")
    if body.teaching_days is not None:
        plan.teaching_days = body.teaching_days
    if body.position is not None:
        plan.position = body.position
    await db.commit()
    await db.refresh(plan)
    logger.info("update_chapter_plan: done plan_id=%s", plan_id)
    return ChapterPlanRead.model_validate(plan)


# ---------------------------------------------------------------------------
# Lesson Slots
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/chapter-plans/{plan_id}/lesson-slots/generate",
    response_model=ClassLessonSlotListResponse,
)
async def generate_lesson_slots(
    plan_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ClassLessonSlotListResponse:
    logger.info("generate_lesson_slots: plan_id=%s", plan_id)
    plan = await db.get(ChapterPlan, plan_id)
    if plan is None or plan.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter plan not found")
    result = await ai_breakdown_chapter(plan_id, db)
    slots = result["lesson_slots"]
    logger.info("generate_lesson_slots: plan_id=%s slots=%d", plan_id, len(slots))
    return ClassLessonSlotListResponse(
        items=[ClassLessonSlotRead.model_validate(s) for s in slots]
    )


@router.post(
    "/api/v1/chapter-plans/{plan_id}/lesson-slots/regenerate",
    response_model=ClassLessonSlotListResponse,
)
async def regenerate_lesson_slots(
    plan_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ClassLessonSlotListResponse:
    logger.info("regenerate_lesson_slots: plan_id=%s", plan_id)
    plan = await db.get(ChapterPlan, plan_id)
    if plan is None or plan.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter plan not found")
    result = await ai_breakdown_chapter(plan_id, db)
    slots = result["lesson_slots"]
    logger.info("regenerate_lesson_slots: plan_id=%s slots=%d", plan_id, len(slots))
    return ClassLessonSlotListResponse(
        items=[ClassLessonSlotRead.model_validate(s) for s in slots]
    )


@router.get(
    "/api/v1/chapter-plans/{plan_id}/lesson-slots",
    response_model=ClassLessonSlotListResponse,
)
async def list_lesson_slots(
    plan_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ClassLessonSlotListResponse:
    logger.info("list_lesson_slots: plan_id=%s", plan_id)
    plan = await db.get(ChapterPlan, plan_id)
    if plan is None or plan.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter plan not found")
    result = await db.execute(
        select(ClassLessonSlot)
        .where(ClassLessonSlot.chapter_plan_id == plan_id)
        .order_by(ClassLessonSlot.day_number)
    )
    slots = list(result.scalars().all())
    logger.info("list_lesson_slots: plan_id=%s count=%d", plan_id, len(slots))
    return ClassLessonSlotListResponse(
        items=[ClassLessonSlotRead.model_validate(s) for s in slots]
    )


@router.patch(
    "/api/v1/class-lesson-slots/{slot_id}/mark-taught",
    response_model=ClassLessonSlotRead,
)
async def mark_slot_taught(
    slot_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ClassLessonSlotRead:
    logger.info("mark_slot_taught: slot_id=%s", slot_id)
    slot = await db.get(ClassLessonSlot, slot_id)
    if slot is None or slot.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson slot not found")
    slot.status = "taught"
    slot.taught_date = datetime.now(timezone.utc).date()
    await db.commit()
    await db.refresh(slot)
    logger.info("mark_slot_taught: done slot_id=%s taught_date=%s", slot_id, slot.taught_date)
    return ClassLessonSlotRead.model_validate(slot)


@router.patch(
    "/api/v1/class-lesson-slots/{slot_id}",
    response_model=ClassLessonSlotRead,
)
async def update_lesson_slot(
    slot_id: uuid.UUID,
    body: ClassLessonSlotUpdate,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ClassLessonSlotRead:
    logger.info("update_lesson_slot: slot_id=%s", slot_id)
    slot = await db.get(ClassLessonSlot, slot_id)
    if slot is None or slot.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson slot not found")
    if body.lp_type is not None:
        slot.lp_type = body.lp_type
    if body.title is not None:
        slot.title = body.title
    if body.lesson_plan_id is not None:
        slot.lesson_plan_id = body.lesson_plan_id
    await db.commit()
    await db.refresh(slot)
    logger.info("update_lesson_slot: done slot_id=%s", slot_id)
    return ClassLessonSlotRead.model_validate(slot)


# ---------------------------------------------------------------------------
# Assessment Slots
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/classes/{class_id}/subjects/{cst_id}/breakdown-year",
    response_model=BreakdownYearResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def breakdown_year(
    class_id: uuid.UUID,
    cst_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> BreakdownYearResponse:
    logger.info("breakdown_year: cst_id=%s", cst_id)
    obj = await db.get(ClassSubjectTeacher, cst_id)
    if obj is None or obj.client_id != current_client.id or obj.class_id != class_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject assignment not found")

    # Count chapter plans before handing off to background task
    plans_result = await db.execute(
        select(ChapterPlan).where(ChapterPlan.class_subject_teacher_id == cst_id)
    )
    chapter_count = len(list(plans_result.scalars().all()))

    background_tasks.add_task(ai_breakdown_all, cst_id, db)
    logger.info("breakdown_year: queued cst_id=%s chapters=%d", cst_id, chapter_count)
    return BreakdownYearResponse(status="queued", chapters=chapter_count)


@router.post(
    "/api/v1/classes/{class_id}/subjects/{cst_id}/assessment-slots/auto-schedule",
    response_model=AssessmentSlotListResponse,
)
async def auto_schedule_assessments(
    class_id: uuid.UUID,
    cst_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> AssessmentSlotListResponse:
    logger.info("auto_schedule_assessments: cst_id=%s", cst_id)
    obj = await db.get(ClassSubjectTeacher, cst_id)
    if obj is None or obj.client_id != current_client.id or obj.class_id != class_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject assignment not found")
    slots = await auto_schedule_formative_assessments(cst_id, db)
    logger.info("auto_schedule_assessments: cst_id=%s slots=%d", cst_id, len(slots))
    return AssessmentSlotListResponse(
        items=[AssessmentSlotRead.model_validate(s) for s in slots]
    )


@router.post(
    "/api/v1/classes/{class_id}/subjects/{cst_id}/assessment-slots",
    response_model=AssessmentSlotRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_assessment_slot(
    class_id: uuid.UUID,
    cst_id: uuid.UUID,
    body: AssessmentSlotCreate,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> AssessmentSlotRead:
    logger.info(
        "add_assessment_slot: cst_id=%s type=%s date=%s", cst_id, body.assessment_type, body.scheduled_date
    )
    obj = await db.get(ClassSubjectTeacher, cst_id)
    if obj is None or obj.client_id != current_client.id or obj.class_id != class_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject assignment not found")
    slot = AssessmentSlot(
        client_id=current_client.id,
        class_subject_teacher_id=cst_id,
        chapter_plan_id=body.chapter_plan_id,
        assessment_type=body.assessment_type,
        scheduled_date=body.scheduled_date,
        title=body.title,
        status="scheduled",
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    logger.info("add_assessment_slot: done id=%s", slot.id)
    return AssessmentSlotRead.model_validate(slot)


@router.get(
    "/api/v1/classes/{class_id}/subjects/{cst_id}/assessment-slots",
    response_model=AssessmentSlotListResponse,
)
async def list_assessment_slots(
    class_id: uuid.UUID,
    cst_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> AssessmentSlotListResponse:
    logger.info("list_assessment_slots: cst_id=%s", cst_id)
    obj = await db.get(ClassSubjectTeacher, cst_id)
    if obj is None or obj.client_id != current_client.id or obj.class_id != class_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject assignment not found")
    result = await db.execute(
        select(AssessmentSlot).where(
            AssessmentSlot.class_subject_teacher_id == cst_id,
            AssessmentSlot.client_id == current_client.id,
        )
    )
    items = list(result.scalars().all())
    logger.info("list_assessment_slots: cst_id=%s count=%d", cst_id, len(items))
    return AssessmentSlotListResponse(
        items=[AssessmentSlotRead.model_validate(s) for s in items]
    )


@router.patch("/api/v1/assessment-slots/{slot_id}", response_model=AssessmentSlotRead)
async def update_assessment_slot(
    slot_id: uuid.UUID,
    body: AssessmentSlotUpdate,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> AssessmentSlotRead:
    logger.info("update_assessment_slot: slot_id=%s", slot_id)
    slot = await db.get(AssessmentSlot, slot_id)
    if slot is None or slot.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment slot not found")
    if body.scheduled_date is not None:
        slot.scheduled_date = body.scheduled_date
    if body.status is not None:
        slot.status = body.status
    if body.title is not None:
        slot.title = body.title
    await db.commit()
    await db.refresh(slot)
    logger.info("update_assessment_slot: done slot_id=%s", slot_id)
    return AssessmentSlotRead.model_validate(slot)


@router.delete("/api/v1/assessment-slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment_slot(
    slot_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> None:
    logger.info("delete_assessment_slot: slot_id=%s", slot_id)
    slot = await db.get(AssessmentSlot, slot_id)
    if slot is None or slot.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment slot not found")
    await db.delete(slot)
    await db.commit()
    logger.info("delete_assessment_slot: done slot_id=%s", slot_id)


# ---------------------------------------------------------------------------
# LP & Exam generation from slots
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/class-lesson-slots/{slot_id}/generate-lp",
    response_model=GenerateLPResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_lp_for_lesson_slot(
    slot_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GenerateLPResponse:
    logger.info(
        "generate_lp_for_lesson_slot: slot_id=%s client_id=%s", slot_id, current_client.id
    )
    if not current_client.curriculum:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client curriculum is not set",
        )
    lp = await generate_lp_for_slot(
        db, slot_id, current_client.id, current_client.curriculum
    )
    # Build request object for background task (re-use lp fields)
    from dars.generated_lps.schemas import GeneratedLPCreate as _LPCreate
    lp_req = _LPCreate(
        grade=int(lp.grade),
        subject=lp.subject,
        topic=lp.topic,
        lp_type=lp.lp_type,
        external_id=lp.external_id,
    )
    background_tasks.add_task(
        generate_lp_task, lp.id, current_client.id, current_client.curriculum, lp_req
    )
    logger.info(
        "generate_lp_for_lesson_slot: queued lp_id=%s slot_id=%s", lp.id, slot_id
    )
    return GenerateLPResponse(lesson_plan_id=lp.id, status=lp.status)


@router.post(
    "/api/v1/chapter-plans/{plan_id}/generate-all-lps",
    response_model=GenerateAllLPsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_all_lps_for_chapter_plan(
    plan_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GenerateAllLPsResponse:
    logger.info(
        "generate_all_lps_for_chapter_plan: plan_id=%s client_id=%s", plan_id, current_client.id
    )
    if not current_client.curriculum:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client curriculum is not set",
        )
    queued_pairs, skipped = await generate_all_lps_for_chapter(
        db, plan_id, current_client.id, current_client.curriculum
    )
    from dars.generated_lps.schemas import GeneratedLPCreate as _LPCreate
    for lp_id, lp_req in queued_pairs:
        background_tasks.add_task(
            generate_lp_task, lp_id, current_client.id, current_client.curriculum, lp_req
        )
    logger.info(
        "generate_all_lps_for_chapter_plan: plan_id=%s queued=%d skipped=%d",
        plan_id, len(queued_pairs), skipped,
    )
    return GenerateAllLPsResponse(queued=len(queued_pairs), skipped=skipped)


@router.post(
    "/api/v1/assessment-slots/{slot_id}/generate-exam",
    response_model=GenerateExamResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_exam_for_assessment_slot(
    slot_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GenerateExamResponse:
    logger.info(
        "generate_exam_for_assessment_slot: slot_id=%s client_id=%s", slot_id, current_client.id
    )
    if not current_client.curriculum:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client curriculum is not set",
        )
    exam = await generate_exam_for_slot(
        db, slot_id, current_client.id, current_client.curriculum
    )
    from dars.generated_exams.schemas import GeneratedExamCreate as _ExamCreate
    exam_req = _ExamCreate(
        grade=exam.grade,
        subject=exam.subject,
        page_ranges=exam.page_ranges,
        generation_type=exam.generation_type,
        external_id=exam.external_id,
    )
    background_tasks.add_task(
        generate_exam_task, exam.id, current_client.id, current_client.curriculum, exam_req
    )
    logger.info(
        "generate_exam_for_assessment_slot: queued exam_id=%s slot_id=%s", exam.id, slot_id
    )
    return GenerateExamResponse(exam_id=exam.id, status=exam.status)


# ---------------------------------------------------------------------------
# Today endpoint
# ---------------------------------------------------------------------------


@router.get("/api/v1/today")
async def get_today_schedule(
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> list[TodaySlotEntry]:
    today = date.today()
    today_weekday = today.weekday()
    logger.info(
        "get_today_schedule: client_id=%s today=%s weekday=%d", current_client.id, today, today_weekday
    )

    # Get all timetable rows for today's weekday for this client
    tt_result = await db.execute(
        select(Timetable).where(
            Timetable.client_id == current_client.id,
            Timetable.day_of_week == today_weekday,
        )
    )
    tt_rows = list(tt_result.scalars().all())
    logger.info("get_today_schedule: timetable rows for today=%d", len(tt_rows))

    entries: list[TodaySlotEntry] = []
    for tt in tt_rows:
        cst_id = tt.class_subject_teacher_id

        # Load CST
        cst_result = await db.execute(
            select(ClassSubjectTeacher).where(
                ClassSubjectTeacher.id == cst_id,
                ClassSubjectTeacher.client_id == current_client.id,
            )
        )
        cst = cst_result.scalar_one_or_none()
        if cst is None:
            continue

        # Load class
        sc = await db.get(SchoolClass, cst.class_id)
        if sc is None:
            continue

        # Load teacher name if available
        teacher_name: str | None = None
        if cst.teacher_id:
            teacher = await db.get(Teacher, cst.teacher_id)
            if teacher:
                teacher_name = teacher.name

        # Next planned slot
        next_planned_result = await db.execute(
            select(ClassLessonSlot)
            .where(
                ClassLessonSlot.class_subject_teacher_id == cst_id,
                ClassLessonSlot.client_id == current_client.id,
                ClassLessonSlot.status == "planned",
            )
            .order_by(ClassLessonSlot.day_number)
            .limit(1)
        )
        next_planned = next_planned_result.scalar_one_or_none()

        # Previous taught slot
        prev_taught_result = await db.execute(
            select(ClassLessonSlot)
            .where(
                ClassLessonSlot.class_subject_teacher_id == cst_id,
                ClassLessonSlot.client_id == current_client.id,
                ClassLessonSlot.status == "taught",
            )
            .order_by(ClassLessonSlot.day_number.desc())
            .limit(1)
        )
        prev_taught = prev_taught_result.scalar_one_or_none()

        entries.append(
            TodaySlotEntry(
                class_id=cst.class_id,
                class_name=sc.name,
                subject=cst.subject,
                cst_id=cst_id,
                teacher_id=cst.teacher_id,
                teacher_name=teacher_name,
                next_planned_slot=(
                    ClassLessonSlotRead.model_validate(next_planned) if next_planned else None
                ),
                previous_taught_slot=(
                    ClassLessonSlotRead.model_validate(prev_taught) if prev_taught else None
                ),
            )
        )

    logger.info("get_today_schedule: entries=%d", len(entries))
    return entries
