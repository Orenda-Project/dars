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
    topic_title: str | None = None
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


class NextUpSummary(BaseModel):
    """The next lesson slot after today's position (by global position).

    Symmetric to PreviousTaughtSummary, plus the lp_type and the projected
    teaching date so the teacher app can say what's coming and when.
    """
    slot_id: UUID
    position: int
    topic_id: UUID | None
    lp_type: str | None
    projected_date: date | None


class CurrentChapterSummary(BaseModel):
    """The chapter the class is currently on (first non-done chapter in the
    org-breakdown / class path order). Set whenever a path exists, even if
    today is not a teaching day."""
    book_chapter_id: UUID
    chapter_number: int | None
    title: str | None
    status: str  # 'yet_to_start' | 'in_progress' | 'done'


class TodayEntry(BaseModel):
    cst_id: UUID
    subject_id: UUID
    subject_code: str
    grade_id: UUID
    grade_code: int
    day_number: int | None  # the slot's global position; None if today is non-teaching
    current_chapter: CurrentChapterSummary | None = None
    lesson_slot: LessonSlotEntry | None = None
    assessment_slot: AssessmentSlotEntry | None = None
    previous_taught: PreviousTaughtSummary | None = None
    next_up: NextUpSummary | None = None
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
