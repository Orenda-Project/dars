from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BookResponse(BaseModel):
    id: int
    core_id: int | None = None
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
    id: int
    core_id: int | None = None
    book_id: int
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
    id: int
    chapter_id: int
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
    id: int
    topic_id: int
    day_number: int
    scheduled_date: str | None
    topic_subtopic: str
    lesson_plan_id: int | None
    assessment_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LessonSlotListResponse(BaseModel):
    items: list[LessonSlotResponse]


# ---------------------------------------------------------------------------
# Full curriculum tree
# ---------------------------------------------------------------------------


class CurriculumLesson(BaseModel):
    id: int
    day_number: int
    title: str
    lesson_plan_id: int | None
    assessment_id: int | None


class CurriculumTopic(BaseModel):
    id: int
    topic_number: int
    title: str
    start_page: int | None
    end_page: int | None
    lessons: list[CurriculumLesson]


class CurriculumChapter(BaseModel):
    id: int
    chapter_number: int
    title: str
    start_page: int | None
    end_page: int | None
    topics: list[CurriculumTopic]


class BookCurriculumResponse(BaseModel):
    book_id: int
    book_title: str
    chapters: list[CurriculumChapter]


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


# ---------------------------------------------------------------------------
# SLOs
# ---------------------------------------------------------------------------


class SLORead(BaseModel):
    id: int
    curriculum: str
    grade: int
    subject: str
    code: str
    description: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SLOListResponse(BaseModel):
    items: list[SLORead]
    total: int


class SLOImportItem(BaseModel):
    grade: int
    subject: str
    code: str
    description: str


class SLOImportRequest(BaseModel):
    curriculum: str
    slos: list[SLOImportItem]


class SLOImportResponse(BaseModel):
    imported: int
    updated: int


class TopicSLOMapRequest(BaseModel):
    slo_codes: list[str]


class TopicSLOsResponse(BaseModel):
    topic_id: int
    slos: list[SLORead]


# ---------------------------------------------------------------------------
# Chapter Schedule (admin defaults)
# ---------------------------------------------------------------------------


class ChapterScheduleItem(BaseModel):
    book_id: int
    chapter_id: int
    suggested_teaching_days: int
    suggested_position: int
    term: str | None = None


class ChapterScheduleUpsertRequest(BaseModel):
    items: list[ChapterScheduleItem]


class ChapterScheduleRead(BaseModel):
    id: int
    curriculum: str
    book_id: int
    chapter_id: int
    suggested_teaching_days: int
    suggested_position: int
    term: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ChapterScheduleListResponse(BaseModel):
    items: list[ChapterScheduleRead]
    total: int


class PrefillChapterPlan(BaseModel):
    chapter_id: int
    title: str
    chapter_number: int
    suggested_teaching_days: int | None
    suggested_position: int | None
    term: str | None


class PrefillResponse(BaseModel):
    items: list[PrefillChapterPlan]
