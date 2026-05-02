import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BookResponse(BaseModel):
    id: uuid.UUID
    core_id: int
    curriculum: str
    grade: int
    subject: str
    title: str
    publisher: str | None
    edition: str | None
    published_year: int | None
    total_chapters: int | None
    pdf_url: str | None
    series: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookListResponse(BaseModel):
    items: list[BookResponse]
    total: int


class BookChapterResponse(BaseModel):
    id: uuid.UUID
    core_id: int
    book_id: uuid.UUID
    title: str
    chapter_number: int
    start_page: int | None
    end_page: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookChapterListResponse(BaseModel):
    items: list[BookChapterResponse]


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------


class TopicResponse(BaseModel):
    id: uuid.UUID
    chapter_id: uuid.UUID
    topic_number: int
    title: str
    page_number: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TopicListResponse(BaseModel):
    items: list[TopicResponse]
    total: int


# ---------------------------------------------------------------------------
# Lesson Slots
# ---------------------------------------------------------------------------


class LessonSlotResponse(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    day_number: int
    scheduled_date: str | None
    topic_subtopic: str
    lesson_plan_id: uuid.UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LessonSlotListResponse(BaseModel):
    items: list[LessonSlotResponse]


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


class BreakdownResponse(BaseModel):
    chapter_id: str
    topics_count: int
    slots_count: int


class ImportBooksRequest(BaseModel):
    schema_filter: str | None = None  # "fde_staging" | "balochistan_staging" | None


class ImportBooksResponse(BaseModel):
    imported: int
    skipped: int
    missing: int
    chapters: int
