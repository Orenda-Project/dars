import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from dars.database import Base


class Book(Base):
    __tablename__ = "books"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    core_id: Mapped[int] = mapped_column(Integer, nullable=False)
    curriculum: Mapped[str] = mapped_column(Text, nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str | None] = mapped_column(Text, nullable=True)
    edition: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_chapters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    series: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class BookChapter(Base):
    __tablename__ = "book_chapters"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    core_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    book_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("book_chapters.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    # topic_text not in ORM — loaded separately for AI calls (raw SQL)
    sub_slos: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class LessonSlot(Base):
    __tablename__ = "lesson_slots"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_subtopic: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
