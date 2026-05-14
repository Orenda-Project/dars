from datetime import date, datetime, time

from pydantic import BaseModel, model_validator


# ---------------------------------------------------------------------------
# AcademicYear
# ---------------------------------------------------------------------------


class AcademicYearCreate(BaseModel):
    name: str
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def end_after_start(self) -> "AcademicYearCreate":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class TeachingDaysResponse(BaseModel):
    academic_year_id: int
    teaching_days: int


class AcademicYearRead(BaseModel):
    id: int
    client_id: int
    name: str
    start_date: date
    end_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class AcademicYearListResponse(BaseModel):
    items: list[AcademicYearRead]
    total: int


# ---------------------------------------------------------------------------
# Holiday
# ---------------------------------------------------------------------------


class HolidayCreate(BaseModel):
    date: date
    name: str


class HolidayRead(BaseModel):
    id: int
    client_id: int
    academic_year_id: int
    date: date
    name: str

    model_config = {"from_attributes": True}


class HolidayListResponse(BaseModel):
    items: list[HolidayRead]
    total: int


# ---------------------------------------------------------------------------
# SchoolClass
# ---------------------------------------------------------------------------


class SchoolClassCreate(BaseModel):
    academic_year_id: int
    grade_id: int
    section: str
    name: str
    start_date: date | None = None
    end_date: date | None = None


class SchoolClassRead(BaseModel):
    id: int
    client_id: int
    academic_year_id: int
    grade_id: int
    section: str
    name: str
    start_date: date | None
    end_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SchoolClassListResponse(BaseModel):
    items: list[SchoolClassRead]
    total: int


# ---------------------------------------------------------------------------
# ClassSubjectTeacher
# ---------------------------------------------------------------------------


class CSTCreate(BaseModel):
    subject_id: int
    teacher_id: int | None = None
    book_id: int | None = None


class CSTUpdate(BaseModel):
    teacher_id: int | None = None
    book_id: int | None = None


class CSTRead(BaseModel):
    id: int
    client_id: int
    class_id: int
    subject_id: int
    teacher_id: int | None
    book_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SchoolClassWithSubjects(SchoolClassRead):
    subjects: list[CSTRead] = []


# ---------------------------------------------------------------------------
# Timetable
# ---------------------------------------------------------------------------


class TimetableSlotCreate(BaseModel):
    day_of_week: int  # 0=Mon ... 6=Sun
    start_time: time | None = None
    end_time: time | None = None


class TimetableSlotRead(BaseModel):
    id: int
    client_id: int
    class_subject_teacher_id: int
    day_of_week: int
    start_time: time | None
    end_time: time | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TimetableSetRequest(BaseModel):
    slots: list[TimetableSlotCreate]


class TimetableResponse(BaseModel):
    items: list[TimetableSlotRead]


# ---------------------------------------------------------------------------
# ChapterPlan
# ---------------------------------------------------------------------------


class ChapterPlanItem(BaseModel):
    chapter_id: int
    position: int
    teaching_days: int


class ChapterPlanBulkUpsertRequest(BaseModel):
    plans: list[ChapterPlanItem]


class ChapterPlanRead(BaseModel):
    id: int
    client_id: int
    class_subject_teacher_id: int
    chapter_id: int
    position: int
    teaching_days: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChapterPlanWithDates(ChapterPlanRead):
    start_date: date | None = None
    end_date: date | None = None
    suggested_teaching_days: int | None = None
    suggested_position: int | None = None


class ChapterPlanUpdate(BaseModel):
    teaching_days: int | None = None
    position: int | None = None


class ChapterPlanListResponse(BaseModel):
    items: list[ChapterPlanWithDates]


# ---------------------------------------------------------------------------
# ClassLessonSlot
# ---------------------------------------------------------------------------


class ClassLessonSlotRead(BaseModel):
    id: int
    client_id: int
    class_subject_teacher_id: int
    chapter_plan_id: int
    day_number: int
    lp_type: str
    title: str
    lesson_plan_id: int | None
    status: str
    taught_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClassLessonSlotListResponse(BaseModel):
    items: list[ClassLessonSlotRead]


class ClassLessonSlotUpdate(BaseModel):
    lp_type: str | None = None
    title: str | None = None
    lesson_plan_id: int | None = None


# ---------------------------------------------------------------------------
# AssessmentSlot
# ---------------------------------------------------------------------------


class AssessmentSlotCreate(BaseModel):
    chapter_plan_id: int | None = None
    assessment_type: str
    scheduled_date: date
    title: str | None = None


class AssessmentSlotRead(BaseModel):
    id: int
    client_id: int
    class_subject_teacher_id: int
    chapter_plan_id: int | None
    assessment_type: str
    scheduled_date: date
    title: str | None
    exam_id: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssessmentSlotListResponse(BaseModel):
    items: list[AssessmentSlotRead]


class AssessmentSlotUpdate(BaseModel):
    scheduled_date: date | None = None
    status: str | None = None
    title: str | None = None


# ---------------------------------------------------------------------------
# Today endpoint
# ---------------------------------------------------------------------------


class TodaySlotEntry(BaseModel):
    class_id: int
    class_name: str
    subject_id: int
    cst_id: int
    teacher_id: int | None
    teacher_name: str | None
    next_planned_slot: ClassLessonSlotRead | None
    previous_taught_slot: ClassLessonSlotRead | None


# ---------------------------------------------------------------------------
# AI Lesson Breakdown
# ---------------------------------------------------------------------------


class BreakdownYearResponse(BaseModel):
    status: str
    chapters: int


# ---------------------------------------------------------------------------
# LP & Exam generation responses
# ---------------------------------------------------------------------------


class GenerateLPResponse(BaseModel):
    lesson_plan_id: int
    status: str


class GenerateAllLPsResponse(BaseModel):
    queued: int
    skipped: int


class GenerateExamResponse(BaseModel):
    exam_id: int
    status: str


# ---------------------------------------------------------------------------
# Teacher App — My Classes
# ---------------------------------------------------------------------------


class MyClassEntry(BaseModel):
    cst_id: int
    class_id: int
    class_name: str
    subject: str
    grade: int
    book_title: str | None
    chapter_count: int
    taught_count: int
    timetable_days: list[int]
    next_slot: ClassLessonSlotRead | None


class MyClassListResponse(BaseModel):
    items: list[MyClassEntry]


# ---------------------------------------------------------------------------
# Teacher App — class creation (Step 8)
# ---------------------------------------------------------------------------


class TeacherClassCreate(BaseModel):
    grade_id: int
    section: str
    subject_id: int
    academic_year_id: int


class TeacherClassCreated(BaseModel):
    class_id: int
    cst_id: int
    chapter_count: int
    status: str
