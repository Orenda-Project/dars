"""Pydantic response schemas for v2 book entities (F1.8)."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class BookRead(BaseModel):
    id: UUID
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    title: str
    publisher: str | None
    edition: str | None
    published_year: int | None
    total_chapters: int | None
    pdf_url: str | None
    # book_text only included when ?include=book_text
    book_text: list[dict[str, Any]] | None = None
    created_at: datetime
    updated_at: datetime


class BookListResponse(BaseModel):
    items: list[BookRead]


class BookChapterRead(BaseModel):
    id: UUID
    book_id: UUID
    chapter_number: int
    title: str
    start_page: int | None
    end_page: int | None
    # chapter_text only included when ?include=chapter_text
    chapter_text: list[dict[str, Any]] | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class BookChapterListResponse(BaseModel):
    items: list[BookChapterRead]


class TopicRead(BaseModel):
    id: UUID
    book_chapter_id: UUID
    topic_number: int
    title: str
    start_line: int | None
    end_line: int | None
    topic_text: str | None  # always included (small)
    status: str
    created_at: datetime
    updated_at: datetime


class TopicListResponse(BaseModel):
    items: list[TopicRead]


class SLOMiniRead(BaseModel):
    """SLO shape used in chapter→SLO and topic→sub-SLO list responses."""
    id: UUID
    code: str
    statement: str


class SubSLOMiniRead(BaseModel):
    id: UUID
    code: str
    statement: str


class ChapterSLOsResponse(BaseModel):
    items: list[SLOMiniRead]


class TopicSubSLOsResponse(BaseModel):
    items: list[SubSLOMiniRead]
