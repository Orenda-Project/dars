import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_current_client
from dars.lookup.models import Grade, Subject
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
    CalendarPeriod,
    CalendarResponse,
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
    MyClassEntry,
    MyClassListResponse,
    SchoolClassCreate,
    SchoolClassListResponse,
    SchoolClassRead,
    SchoolClassWithSubjects,
    TeacherClassCreate,
    TeacherClassCreated,
    TeachingDaysResponse,
    TimetableResponse,
    TimetableSetRequest,
    TimetableSlotRead,
    TodaySlotEntry,
)
from dars.curriculum.models import Book
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
    get_calendar_week,
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
    year_id: int,
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
    year_id: int,
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
    year_id: int,
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
    year_id: int,
    holiday_id: int,
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
        "create_class: client_id=%s grade_id=%s section=%r", current_client.id, body.grade_id, body.section
    )
    year = await db.get(AcademicYear, body.academic_year_id)
    if year is None or year.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")
    obj = SchoolClass(
        client_id=current_client.id,
        academic_year_id=body.academic_year_id,
        grade_id=body.grade_id,
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
    academic_year_id: int | None = Query(default=None),
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
    class_id: int,
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
    class_id: int,
    body: CSTCreate,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> CSTRead:
    logger.info(
        "assign_subject: class_id=%s subject_id=%s client_id=%s", class_id, body.subject_id, current_client.id
    )
    sc = await db.get(SchoolClass, class_id)
    if sc is None or sc.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    obj = ClassSubjectTeacher(
        client_id=current_client.id,
        class_id=class_id,
        subject_id=body.subject_id,
        teacher_id=body.teacher_id,
        book_id=body.book_id,
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    await _auto_create_timetable(obj, db)
    await db.commit()
    await db.refresh(obj)
    logger.info("assign_subject: done cst_id=%s", obj.id)
    return CSTRead.model_validate(obj)


@router.patch(
    "/api/v1/classes/{class_id}/subjects/{cst_id}",
    response_model=CSTRead,
)
async def update_subject(
    class_id: int,
    cst_id: int,
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


async def _auto_create_timetable(cst: ClassSubjectTeacher, db: AsyncSession) -> None:
    """Create Mon–Sat timetable rows for a new CST. Idempotent — skips if rows exist."""
    existing = await db.execute(
        select(Timetable).where(Timetable.class_subject_teacher_id == cst.id).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return
    for day in range(6):  # 0=Mon … 5=Sat
        db.add(Timetable(
            client_id=cst.client_id,
            class_subject_teacher_id=cst.id,
            day_of_week=day,
        ))
    await db.flush()


@router.post(
    "/api/v1/classes/{class_id}/subjects/{cst_id}/timetable",
    response_model=TimetableResponse,
)
async def set_timetable(
    class_id: int,
    cst_id: int,
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
    class_id: int,
    cst_id: int,
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


@router.get("/api/v1/cst/{cst_id}", response_model=CSTRead)
async def get_cst(
    cst_id: int,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> CSTRead:
    """Return a single ClassSubjectTeacher record by ID."""
    logger.info("get_cst: cst_id=%s client_id=%s", cst_id, current_client.id)
    cst = await db.get(ClassSubjectTeacher, cst_id)
    if cst is None or cst.client_id != current_client.id:
        raise HTTPException(status_code=404, detail="CST not found")
    return CSTRead.model_validate(cst)


# ---------------------------------------------------------------------------
# Chapter Plans
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/classes/{class_id}/subjects/{cst_id}/chapter-plans",
    response_model=ChapterPlanListResponse,
)
async def bulk_upsert_chapter_plans(
    class_id: int,
    cst_id: int,
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
    class_id: int,
    cst_id: int,
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
    class_id: int,
    cst_id: int,
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
    plan_id: int,
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
    plan_id: int,
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
    plan_id: int,
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
    plan_id: int,
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
    slot_id: int,
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
    slot_id: int,
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
    class_id: int,
    cst_id: int,
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
    class_id: int,
    cst_id: int,
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
    class_id: int,
    cst_id: int,
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
    class_id: int,
    cst_id: int,
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
    slot_id: int,
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
    slot_id: int,
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
    slot_id: int,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GenerateLPResponse:
    logger.info(
        "generate_lp_for_lesson_slot: slot_id=%s client_id=%s", slot_id, current_client.id
    )
    if not current_client.curriculum_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client curriculum is not set",
        )
    from dars.lookup.service import get_curriculum_code as _gcc, get_grade_code as _rgc, get_subject_code as _rsc
    curriculum_code = await _gcc(db, current_client.curriculum_id)
    lp = await generate_lp_for_slot(
        db, slot_id, current_client.id, curriculum_code
    )
    # Build request object for background task (re-use lp fields)
    from dars.generated_lps.schemas import GeneratedLPCreate as _LPCreate
    grade_code = await _rgc(db, lp.grade_id)
    subject_code = await _rsc(db, lp.subject_id)
    lp_req = _LPCreate(
        grade=grade_code,
        subject=subject_code,
        topic=lp.topic,
        lp_type=lp.lp_type,
        external_id=lp.external_id,
    )
    background_tasks.add_task(
        generate_lp_task, lp.id, current_client.id, curriculum_code, lp_req
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
    plan_id: int,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GenerateAllLPsResponse:
    logger.info(
        "generate_all_lps_for_chapter_plan: plan_id=%s client_id=%s", plan_id, current_client.id
    )
    if not current_client.curriculum_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client curriculum is not set",
        )
    from dars.lookup.service import get_curriculum_code as _gcc2
    curriculum_code2 = await _gcc2(db, current_client.curriculum_id)
    queued_pairs, skipped = await generate_all_lps_for_chapter(
        db, plan_id, current_client.id, curriculum_code2
    )
    from dars.generated_lps.schemas import GeneratedLPCreate as _LPCreate
    for lp_id, lp_req in queued_pairs:
        background_tasks.add_task(
            generate_lp_task, lp_id, current_client.id, curriculum_code2, lp_req
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
    slot_id: int,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GenerateExamResponse:
    logger.info(
        "generate_exam_for_assessment_slot: slot_id=%s client_id=%s", slot_id, current_client.id
    )
    if not current_client.curriculum_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client curriculum is not set",
        )
    from dars.lookup.service import get_curriculum_code as _gcc2, get_grade_code as _rgc2, get_subject_code as _rsc2
    curriculum_code2 = await _gcc2(db, current_client.curriculum_id) or "NCP"
    exam = await generate_exam_for_slot(
        db, slot_id, current_client.id, curriculum_code2
    )
    from dars.generated_exams.schemas import GeneratedExamCreate as _ExamCreate
    grade_code2 = await _rgc2(db, exam.grade_id)
    subject_code2 = await _rsc2(db, exam.subject_id)
    exam_req = _ExamCreate(
        grade=grade_code2,
        subject=subject_code2 or "General",
        page_ranges=exam.page_ranges,
        generation_type=exam.generation_type,
        external_id=exam.external_id,
    )
    background_tasks.add_task(
        generate_exam_task, exam.id, current_client.id, curriculum_code2, exam_req
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
                subject_id=cst.subject_id,
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


# ---------------------------------------------------------------------------
# Teacher App — My Classes
# ---------------------------------------------------------------------------


@router.get("/api/v1/me/classes", response_model=MyClassListResponse)
async def get_my_classes(
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> MyClassListResponse:
    """
    Return all ClassSubjectTeacher rows assigned to the client's default_teacher_id.
    If default_teacher_id is None, returns an empty list.
    """
    logger.info(
        "get_my_classes: client_id=%s default_teacher_id=%s",
        current_client.id,
        current_client.default_teacher_id,
    )

    if current_client.default_teacher_id is None:
        logger.info("get_my_classes: no default_teacher_id, returning empty list")
        return MyClassListResponse(items=[])

    # Fetch all CSTs for the default teacher
    cst_result = await db.execute(
        select(ClassSubjectTeacher).where(
            ClassSubjectTeacher.client_id == current_client.id,
            ClassSubjectTeacher.teacher_id == current_client.default_teacher_id,
        )
    )
    csts = list(cst_result.scalars().all())
    logger.info("get_my_classes: found %d CSTs", len(csts))

    items: list[MyClassEntry] = []
    for cst in csts:
        # Load the school class
        sc = await db.get(SchoolClass, cst.class_id)
        if sc is None:
            continue

        # Load book title if book_id set
        book_title: str | None = None
        if cst.book_id:
            book = await db.get(Book, cst.book_id)
            if book:
                book_title = book.title

        # Count chapter plans for this CST
        cp_result = await db.execute(
            select(ChapterPlan).where(
                ChapterPlan.class_subject_teacher_id == cst.id,
                ChapterPlan.client_id == current_client.id,
            )
        )
        chapter_plans = list(cp_result.scalars().all())
        chapter_count = len(chapter_plans)

        # Count taught slots
        taught_result = await db.execute(
            select(ClassLessonSlot).where(
                ClassLessonSlot.class_subject_teacher_id == cst.id,
                ClassLessonSlot.client_id == current_client.id,
                ClassLessonSlot.status == "taught",
            )
        )
        taught_count = len(list(taught_result.scalars().all()))

        # Resolve display names from lookup tables
        subject_obj = await db.get(Subject, cst.subject_id)
        subject_display = subject_obj.display_name if subject_obj else str(cst.subject_id)
        grade_obj = await db.get(Grade, sc.grade_id)
        grade_code = grade_obj.code if grade_obj else 0

        # Timetable days for this CST
        tt_result = await db.execute(
            select(Timetable).where(
                Timetable.class_subject_teacher_id == cst.id,
                Timetable.client_id == current_client.id,
            )
        )
        timetable_days = sorted(t.day_of_week for t in tt_result.scalars().all())

        # Next planned slot (lowest day_number among planned)
        next_slot_result = await db.execute(
            select(ClassLessonSlot)
            .where(
                ClassLessonSlot.class_subject_teacher_id == cst.id,
                ClassLessonSlot.client_id == current_client.id,
                ClassLessonSlot.status == "planned",
            )
            .order_by(ClassLessonSlot.day_number)
            .limit(1)
        )
        next_slot_obj = next_slot_result.scalar_one_or_none()

        items.append(
            MyClassEntry(
                cst_id=cst.id,
                class_id=sc.id,
                class_name=sc.name,
                subject=subject_display,
                grade=grade_code,
                book_title=book_title,
                chapter_count=chapter_count,
                taught_count=taught_count,
                timetable_days=timetable_days,
                next_slot=(
                    ClassLessonSlotRead.model_validate(next_slot_obj)
                    if next_slot_obj
                    else None
                ),
            )
        )

    logger.info("get_my_classes: returning %d entries", len(items))
    return MyClassListResponse(items=items)


# ---------------------------------------------------------------------------
# Teacher App — create class (Step 8)
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/teacher/classes",
    response_model=TeacherClassCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_teacher_class(
    body: TeacherClassCreate,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> TeacherClassCreated:
    """
    Teacher-owned class creation. Creates SchoolClass + ClassSubjectTeacher in one shot,
    auto-resolves book from client curriculum, upserts chapter plans, fires AI breakdown.
    """
    logger.info(
        "create_teacher_class: client_id=%s grade_id=%s section=%r subject_id=%s academic_year_id=%s",
        current_client.id, body.grade_id, body.section, body.subject_id, body.academic_year_id,
    )

    # 1. Verify default_teacher_id is set
    if current_client.default_teacher_id is None:
        logger.info("create_teacher_class: no default_teacher_id for client_id=%s", current_client.id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No default teacher configured — complete dashboard setup first.",
        )

    # 2. Verify curriculum is set
    if not current_client.curriculum_id:
        logger.info("create_teacher_class: no curriculum for client_id=%s", current_client.id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client curriculum is not set.",
        )

    # 3. Load and validate AcademicYear (must belong to this client)
    year = await db.get(AcademicYear, body.academic_year_id)
    if year is None or year.client_id != current_client.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Academic year not found.",
        )

    # 4. Create SchoolClass
    from dars.lookup.service import get_grade_code as _ggc
    grade_code_for_name = await _ggc(db, body.grade_id) or body.grade_id
    school_class = SchoolClass(
        client_id=current_client.id,
        academic_year_id=body.academic_year_id,
        grade_id=body.grade_id,
        section=body.section,
        name=f"Grade {grade_code_for_name}-{body.section}",
    )
    db.add(school_class)
    await db.flush()
    await db.refresh(school_class)
    logger.info("create_teacher_class: created school_class id=%s", school_class.id)

    # 5. Find Book for curriculum + grade + subject
    book_result = await db.execute(
        select(Book).where(
            Book.curriculum_id == current_client.curriculum_id,
            Book.grade_id == body.grade_id,
            Book.subject_id == body.subject_id,
        ).limit(1)
    )
    book = book_result.scalar_one_or_none()
    if book is None:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No book configured for this grade/subject in your curriculum.",
        )

    # 6. Check no existing CST for this class+subject (defensive: class was just created so no duplicate)
    existing_cst_result = await db.execute(
        select(ClassSubjectTeacher).where(
            ClassSubjectTeacher.class_id == school_class.id,
            ClassSubjectTeacher.subject_id == body.subject_id,
        )
    )
    existing_cst = existing_cst_result.scalar_one_or_none()
    if existing_cst is not None:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Subject already assigned to this class.",
        )

    # 7. Create ClassSubjectTeacher
    cst = ClassSubjectTeacher(
        client_id=current_client.id,
        class_id=school_class.id,
        subject_id=body.subject_id,
        teacher_id=current_client.default_teacher_id,
        book_id=book.id,
    )
    db.add(cst)
    await db.flush()
    await db.refresh(cst)
    await _auto_create_timetable(cst, db)
    logger.info("create_teacher_class: created cst id=%s", cst.id)

    # 8. Load prefill chapter plans (via cst_id — needs to be committed first)
    await db.commit()

    prefill_items = await get_prefill_chapter_plans(cst.id, db)
    logger.info(
        "create_teacher_class: prefill_items=%d for cst_id=%s", len(prefill_items), cst.id
    )

    # 9. Upsert chapter plans for this CST
    chapter_plan_ids: list[int] = []
    for item in prefill_items:
        position = item["suggested_position"] if item["suggested_position"] is not None else 0
        teaching_days = item["suggested_teaching_days"] if item["suggested_teaching_days"] is not None else 5

        existing_plan_result = await db.execute(
            select(ChapterPlan).where(
                ChapterPlan.class_subject_teacher_id == cst.id,
                ChapterPlan.chapter_id == item["chapter_id"],
            )
        )
        existing_plan = existing_plan_result.scalar_one_or_none()
        if existing_plan:
            existing_plan.position = position
            existing_plan.teaching_days = teaching_days
            await db.flush()
            await db.refresh(existing_plan)
            chapter_plan_ids.append(existing_plan.id)
        else:
            plan = ChapterPlan(
                client_id=current_client.id,
                class_subject_teacher_id=cst.id,
                chapter_id=item["chapter_id"],
                position=position,
                teaching_days=teaching_days,
            )
            db.add(plan)
            await db.flush()
            await db.refresh(plan)
            chapter_plan_ids.append(plan.id)

    await db.commit()
    logger.info(
        "create_teacher_class: upserted %d chapter plans for cst_id=%s", len(chapter_plan_ids), cst.id
    )

    # 10. Fire AI breakdown for each chapter plan as background task
    for cp_id in chapter_plan_ids:
        background_tasks.add_task(ai_breakdown_chapter, cp_id, db)

    logger.info(
        "create_teacher_class: done class_id=%s cst_id=%s chapter_count=%d",
        school_class.id, cst.id, len(chapter_plan_ids),
    )
    return TeacherClassCreated(
        class_id=school_class.id,
        cst_id=cst.id,
        chapter_count=len(chapter_plan_ids),
        status="breakdown_pending",
    )


# ---------------------------------------------------------------------------
# Flat chapter-plan list (by cst_id) — used by Teacher App
# ---------------------------------------------------------------------------


@router.get("/api/v1/chapter-plans", response_model=ChapterPlanListResponse)
async def list_chapter_plans_flat(
    cst_id: int = Query(...),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ChapterPlanListResponse:
    """
    List chapter plans for a given cst_id. Flat endpoint (no class_id path param).
    Used by the Teacher App.
    """
    logger.info("list_chapter_plans_flat: cst_id=%s client_id=%s", cst_id, current_client.id)
    cst = await db.get(ClassSubjectTeacher, cst_id)
    if cst is None or cst.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CST not found")

    plans_result = await db.execute(
        select(ChapterPlan)
        .where(ChapterPlan.class_subject_teacher_id == cst_id)
        .order_by(ChapterPlan.position)
    )
    plans = list(plans_result.scalars().all())

    date_ranges_list = await compute_chapter_date_ranges(cst_id, db)
    dr_map = {dr["chapter_plan_id"]: dr for dr in date_ranges_list}

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

    logger.info("list_chapter_plans_flat: cst_id=%s count=%d", cst_id, len(items))
    return ChapterPlanListResponse(items=items)


# ---------------------------------------------------------------------------
# Flat lesson-slot list (by chapter_plan_id) — used by Teacher App
# ---------------------------------------------------------------------------


@router.get("/api/v1/class-lesson-slots", response_model=ClassLessonSlotListResponse)
async def list_lesson_slots_flat(
    chapter_plan_id: int = Query(...),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ClassLessonSlotListResponse:
    """
    List lesson slots for a chapter_plan_id. Flat endpoint — no path params.
    Used by the Teacher App.
    """
    logger.info(
        "list_lesson_slots_flat: chapter_plan_id=%s client_id=%s", chapter_plan_id, current_client.id
    )
    plan = await db.get(ChapterPlan, chapter_plan_id)
    if plan is None or plan.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter plan not found")
    result = await db.execute(
        select(ClassLessonSlot)
        .where(ClassLessonSlot.chapter_plan_id == chapter_plan_id)
        .order_by(ClassLessonSlot.day_number)
    )
    slots = list(result.scalars().all())
    logger.info("list_lesson_slots_flat: chapter_plan_id=%s count=%d", chapter_plan_id, len(slots))
    return ClassLessonSlotListResponse(
        items=[ClassLessonSlotRead.model_validate(s) for s in slots]
    )


# ---------------------------------------------------------------------------
# Flat assessment-slot list (by cst_id) — used by Teacher App
# ---------------------------------------------------------------------------


@router.get("/api/v1/assessment-slots", response_model=AssessmentSlotListResponse)
async def list_assessment_slots_flat(
    cst_id: int = Query(...),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> AssessmentSlotListResponse:
    """
    List assessment slots for a cst_id. Flat endpoint — no path params.
    Used by the Teacher App.
    """
    logger.info(
        "list_assessment_slots_flat: cst_id=%s client_id=%s", cst_id, current_client.id
    )
    cst = await db.get(ClassSubjectTeacher, cst_id)
    if cst is None or cst.client_id != current_client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CST not found")
    result = await db.execute(
        select(AssessmentSlot).where(
            AssessmentSlot.class_subject_teacher_id == cst_id,
            AssessmentSlot.client_id == current_client.id,
        )
    )
    items = list(result.scalars().all())
    logger.info("list_assessment_slots_flat: cst_id=%s count=%d", cst_id, len(items))
    return AssessmentSlotListResponse(
        items=[AssessmentSlotRead.model_validate(s) for s in items]
    )


# ---------------------------------------------------------------------------
# Teacher App — Calendar
# ---------------------------------------------------------------------------


@router.get("/api/v1/me/calendar", response_model=CalendarResponse)
async def get_my_calendar(
    week_start: date | None = Query(default=None, description="Monday of the target week (YYYY-MM-DD). Defaults to current Monday."),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> CalendarResponse:
    """
    Return all lesson slots and assessments for the teacher's classes in the given week.
    Lesson slot dates are computed from timetable days + chapter plan start dates.
    """
    if week_start is None:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

    logger.info(
        "get_my_calendar: client_id=%s teacher_id=%s week_start=%s",
        current_client.id, current_client.default_teacher_id, week_start,
    )

    if current_client.default_teacher_id is None:
        logger.info("get_my_calendar: no default_teacher_id, returning empty calendar")
        week_end = week_start + timedelta(days=6)
        from dars.school.schemas import CalendarDayResponse
        items = [CalendarDayResponse(date=week_start + timedelta(days=i), periods=[]) for i in range(7)]
        return CalendarResponse(items=items, week_start=week_start, week_end=week_end)

    data = await get_calendar_week(
        client_id=current_client.id,
        teacher_id=current_client.default_teacher_id,
        week_start=week_start,
        db=db,
    )

    from dars.school.schemas import CalendarDayResponse, CalendarPeriod
    items = []
    for day in data["items"]:
        items.append(CalendarDayResponse(
            date=day["date"],
            periods=[CalendarPeriod(**p) for p in day["periods"]],
        ))

    logger.info("get_my_calendar: week=%s items=%d", week_start, len(items))
    return CalendarResponse(items=items, week_start=data["week_start"], week_end=data["week_end"])
