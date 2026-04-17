import uuid
from datetime import date, datetime

from pydantic import BaseModel


class GradeResponse(BaseModel):
    id: uuid.UUID
    label: str
    short_code: str
    order_index: int

    model_config = {"from_attributes": True}


class SubjectResponse(BaseModel):
    id: uuid.UUID
    label: str
    short_code: str

    model_config = {"from_attributes": True}


class CurriculumResponse(BaseModel):
    id: uuid.UUID
    name: str
    book_id: int
    provider_id: uuid.UUID
    is_default: bool
    teacher_id: uuid.UUID | None
    client_id: uuid.UUID | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------

class SubSloSummary(BaseModel):
    id: uuid.UUID
    code: str
    statement: str
    slo_code: str  # parent SLO code

    model_config = {"from_attributes": True}


class TopicDetail(BaseModel):
    id: uuid.UUID
    title: str
    text: str | None
    sequence: int
    sub_slos: list[SubSloSummary]

    model_config = {"from_attributes": True}


class ChapterDetail(BaseModel):
    id: int
    chapter_number: int
    title: str
    start_page: int | None
    end_page: int | None
    topics: list[TopicDetail]

    model_config = {"from_attributes": True}


class BookListItem(BaseModel):
    id: int
    title: str
    grade: int
    subject: str
    board: str
    cover_image: str | None
    total_chapters: int | None

    model_config = {"from_attributes": True}


class BookDetailResponse(BaseModel):
    id: int
    title: str
    grade: int
    subject: str
    board: str
    cover_image: str | None
    total_chapters: int | None
    chapters: list[ChapterDetail]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Curriculums
# ---------------------------------------------------------------------------

class CurriculumListItem(BaseModel):
    id: uuid.UUID
    name: str
    book_id: int
    book_title: str
    provider_name: str
    is_default: bool
    teacher_id: uuid.UUID | None
    is_active: bool

    model_config = {"from_attributes": True}


class LpStubSummary(BaseModel):
    id: uuid.UUID
    sequence: int
    skill_type: str | None
    cpa_phase: str | None
    blooms_level: str | None
    planned_date: date | None
    status: str
    lesson_plan_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class CurriculumTopicDetail(BaseModel):
    id: uuid.UUID
    sequence: int
    topic_id: uuid.UUID
    topic_title: str
    topic_text: str | None
    planned_date: date | None
    completed_date: date | None
    lp_stubs: list[LpStubSummary]

    model_config = {"from_attributes": True}


class CurriculumDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    book_id: int
    book_title: str
    provider_name: str
    is_default: bool
    teacher_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    topics: list[CurriculumTopicDetail]

    model_config = {"from_attributes": True}


class CurriculumProgressResponse(BaseModel):
    total_topics: int
    completed: int
    behind: int
    on_track: int


# ---------------------------------------------------------------------------
# Admin request schemas (Phase 2)
# ---------------------------------------------------------------------------

class CurriculumCreateRequest(BaseModel):
    name: str
    book_id: int
    provider_id: uuid.UUID
    is_default: bool = False


class TopicEntry(BaseModel):
    topic_id: uuid.UUID
    planned_date: date | None = None


class CurriculumSetTopicsRequest(BaseModel):
    topics: list[TopicEntry]


class CurriculumUpdateRequest(BaseModel):
    name: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None
