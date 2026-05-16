"""Pydantic schemas for /today and /me/calendar (F2.15, F2.16)."""
from datetime import date
from uuid import UUID

from pydantic import BaseModel


class LessonSlotEntry(BaseModel):
    slot_id: UUID
    position: int
    slot_type: str  # 'lesson' | 'revision'
    lp_type: str | None
    topic_id: UUID | None
    status: str
    anchor_date: date | None


class AssessmentSlotEntry(BaseModel):
    slot_id: UUID
    position: int
    assessment_type: str  # 'formative' | 'summative'
    status: str
    anchor_date: date | None
    topic_ids: list[UUID] = []


class PreviousTaughtSummary(BaseModel):
    slot_id: UUID
    position: int
    topic_id: UUID | None
    taught_on: date | None


class TodayEntry(BaseModel):
    cst_id: UUID
    subject_id: UUID
    subject_code: str
    grade_id: UUID
    grade_code: int
    day_number: int | None  # the slot's global position; None if today is non-teaching
    lesson_slot: LessonSlotEntry | None = None
    assessment_slot: AssessmentSlotEntry | None = None
    previous_taught: PreviousTaughtSummary | None = None
    is_conflict: bool = False
    is_overflow: bool = False


class TodayResponse(BaseModel):
    items: list[TodayEntry]
    as_of: date


class CalendarDay(BaseModel):
    day: date
    lesson_slots: list[LessonSlotEntry] = []
    assessment_slots: list[AssessmentSlotEntry] = []


class CalendarCSTSchedule(BaseModel):
    cst_id: UUID
    subject_id: UUID
    subject_code: str
    grade_id: UUID
    grade_code: int
    days: list[CalendarDay]


class CalendarResponse(BaseModel):
    week_start: date
    week_end: date
    csts: list[CalendarCSTSchedule]
