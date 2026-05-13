import uuid
from datetime import date, datetime, time

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# AcademicYear
# ---------------------------------------------------------------------------


class AcademicYearCreate(BaseModel):
    name: str
    start_date: date
    end_date: date


class AcademicYearRead(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
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
    id: uuid.UUID
    client_id: uuid.UUID
    academic_year_id: uuid.UUID
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
    academic_year_id: uuid.UUID
    grade: int
    section: str
    name: str
    start_date: date | None = None
    end_date: date | None = None


class SchoolClassRead(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    academic_year_id: uuid.UUID
    grade: int
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
    subject: str
    teacher_id: uuid.UUID | None = None
    book_id: uuid.UUID | None = None


class CSTUpdate(BaseModel):
    teacher_id: uuid.UUID | None = None
    book_id: uuid.UUID | None = None


class CSTRead(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    class_id: uuid.UUID
    subject: str
    teacher_id: uuid.UUID | None
    book_id: uuid.UUID | None
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
    id: uuid.UUID
    client_id: uuid.UUID
    class_subject_teacher_id: uuid.UUID
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
    chapter_id: uuid.UUID
    position: int
    teaching_days: int


class ChapterPlanBulkUpsertRequest(BaseModel):
    plans: list[ChapterPlanItem]


class ChapterPlanRead(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    class_subject_teacher_id: uuid.UUID
    chapter_id: uuid.UUID
    position: int
    teaching_days: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChapterPlanWithDates(ChapterPlanRead):
    start_date: date | None = None
    end_date: date | None = None


class ChapterPlanUpdate(BaseModel):
    teaching_days: int | None = None
    position: int | None = None


class ChapterPlanListResponse(BaseModel):
    items: list[ChapterPlanWithDates]


# ---------------------------------------------------------------------------
# ClassLessonSlot
# ---------------------------------------------------------------------------


class ClassLessonSlotRead(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    class_subject_teacher_id: uuid.UUID
    chapter_plan_id: uuid.UUID
    day_number: int
    lp_type: str
    title: str
    lesson_plan_id: uuid.UUID | None
    status: str
    taught_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClassLessonSlotListResponse(BaseModel):
    items: list[ClassLessonSlotRead]


class ClassLessonSlotUpdate(BaseModel):
    lp_type: str | None = None
    title: str | None = None
    lesson_plan_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# AssessmentSlot
# ---------------------------------------------------------------------------


class AssessmentSlotCreate(BaseModel):
    chapter_plan_id: uuid.UUID | None = None
    assessment_type: str
    scheduled_date: date
    title: str | None = None


class AssessmentSlotRead(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    class_subject_teacher_id: uuid.UUID
    chapter_plan_id: uuid.UUID | None
    assessment_type: str
    scheduled_date: date
    title: str | None
    exam_id: uuid.UUID | None = None
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
    class_id: uuid.UUID
    class_name: str
    subject: str
    cst_id: uuid.UUID
    teacher_id: uuid.UUID | None
    teacher_name: str | None
    next_planned_slot: ClassLessonSlotRead | None
    previous_taught_slot: ClassLessonSlotRead | None
