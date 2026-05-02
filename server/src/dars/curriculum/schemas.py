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
    start_page: int | None
    end_page: int | None
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


class KnownBookEntry(BaseModel):
    core_id: int
    curriculum: str
    grade: int
    subject: str
    schema: str


class KnownBooksResponse(BaseModel):
    items: list[KnownBookEntry]


class ImportBooksRequest(BaseModel):
    schema_filter: str | None = None  # "fde_staging" | "balochistan_staging" | None
    core_book_ids: list[int] | None = None  # if set, import only these


class ImportBooksResponse(BaseModel):
    imported: int
    skipped: int
    missing: int
    chapters: int


# ---------------------------------------------------------------------------
# Single-book preview + import
# ---------------------------------------------------------------------------


class ChapterPreview(BaseModel):
    id: int
    title: str
    chapter_number: int
    start_page: int | None
    end_page: int | None


class BookPreviewResponse(BaseModel):
    core_id: int
    schema: str
    title: str
    publisher: str | None
    edition: str | None
    published_year: int | None
    total_chapters: int | None
    pdf_url: str | None
    series: str | None
    has_ocr: bool
    chapters: list[ChapterPreview]


class ImportSingleBookRequest(BaseModel):
    core_id: int
    schema: str       # "fde_staging" | "balochistan_staging"
    curriculum: str   # "ICT" | "Punjab"
    grade: int
    subject: str      # "Eng" | "Maths" | "Urdu"


class ImportSingleBookResponse(BaseModel):
    status: str       # "imported" | "updated"
    chapters: int
