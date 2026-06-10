"""Pydantic schemas for v2 syllabus-breakdown CRUD (Phase 2, global-only)."""
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Read models
# ---------------------------------------------------------------------------


class SyllabusChapterRead(BaseModel):
    id: UUID
    syllabus_breakdown_id: UUID
    book_chapter_id: UUID
    position: int
    start_date: date | None = None
    end_date: date | None = None
    # D-2: derived from the date range against the (Mon-Fri, no-holiday) calendar.
    # None when no range is set.
    derived_teaching_days: int | None = None


class DateRangeRead(BaseModel):
    """An exam period or breakdown holiday: a named [start, end] range (D-1/D-14)."""
    id: UUID
    syllabus_breakdown_id: UUID
    start_date: date
    end_date: date
    name: str
    created_at: datetime


class SyllabusBreakdownRead(BaseModel):
    id: UUID
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    book_id: UUID | None
    status: str
    created_at: datetime
    updated_at: datetime
    chapters: list[SyllabusChapterRead] = []
    # D-5: advisory, non-blocking chapter date-range warnings.
    # Each: {"type": "overlap"|"gap"|"zero_teaching_days", "chapter_ids": [UUID, ...]}
    chapter_range_warnings: list[dict] = []
    # F-1.5 (D-1/D-14): reserved non-teaching ranges on this breakdown.
    exam_periods: list[DateRangeRead] = []
    holidays: list[DateRangeRead] = []


class SyllabusBreakdownListItem(BaseModel):
    id: UUID
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    book_id: UUID | None
    status: str
    created_at: datetime
    updated_at: datetime


class SyllabusBreakdownListResponse(BaseModel):
    items: list[SyllabusBreakdownListItem]


# ---------------------------------------------------------------------------
# Write models
# ---------------------------------------------------------------------------


class SyllabusBreakdownCreate(BaseModel):
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    book_id: UUID


class SyllabusBreakdownUpdate(BaseModel):
    book_id: UUID | None = None


class SyllabusChapterCreate(BaseModel):
    book_chapter_id: UUID
    position: int
    start_date: date | None = None
    end_date: date | None = None


class SyllabusChapterUpdate(BaseModel):
    position: int | None = None
    start_date: date | None = None
    end_date: date | None = None


# ---------------------------------------------------------------------------
# Sub-SLO breakdown trigger (F2.6)
# ---------------------------------------------------------------------------


class SubSLOBreakdownResponse(BaseModel):
    slo_id: UUID
    subject_key: str
    inserted_sub_slo_count: int
    skipped: bool
    raw_response_chars: int


class SubSLOBulkRequest(BaseModel):
    slo_ids: list[UUID] = Field(min_length=1)
    force: bool = False


class SubSLOBulkAccepted(BaseModel):
    accepted_slo_count: int
    skipped_slo_count: int
    grouped_by_subject: dict[str, int]
    # When sync=False (default), the work runs in BackgroundTasks; this list
    # is the SLOs that were queued. With sync=true, this is just the input.
    queued_slo_ids: list[UUID]


# ---------------------------------------------------------------------------
# Exam periods + breakdown holidays (F-1.5, D-1/D-5/D-14)
# ---------------------------------------------------------------------------


class DateRangeCreate(BaseModel):
    start_date: date
    end_date: date
    name: str = Field(min_length=1)


class DateRangeUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    name: str | None = Field(default=None, min_length=1)
