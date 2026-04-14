import uuid
from datetime import datetime, timezone

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from dars.database import Base


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    short_code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    short_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)


class SloProvider(Base):
    __tablename__ = "slo_providers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuing_body: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    slos: Mapped[list["Slo"]] = relationship("Slo", back_populates="provider")


class Slo(Base):
    __tablename__ = "slos"
    __table_args__ = (UniqueConstraint("provider_id", "code", "grade_id", "subject_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("slo_providers.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subjects.id"), nullable=False
    )
    grade_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("grades.id"), nullable=False
    )
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language_skills: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    sub_strand: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    provider: Mapped["SloProvider"] = relationship("SloProvider", back_populates="slos")


class SubSlo(Base):
    __tablename__ = "sub_slos"
    __table_args__ = (UniqueConstraint("slo_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("slos.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("chapter_id", "sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("book_chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TopicSubSlo(Base):
    __tablename__ = "topic_sub_slos"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    sub_slo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sub_slos.id"), primary_key=True
    )


class Curriculum(Base):
    __tablename__ = "curriculums"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    grade_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("grades.id"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subjects.id"), nullable=False
    )
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"), nullable=False)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("slo_providers.id"), nullable=False
    )
    academic_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class CurriculumTopic(Base):
    __tablename__ = "curriculum_topics"
    __table_args__ = (UniqueConstraint("curriculum_id", "sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("curriculums.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("topics.id"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)


class CurriculumLpStub(Base):
    __tablename__ = "curriculum_lp_stubs"
    __table_args__ = (UniqueConstraint("curriculum_topic_id", "sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    curriculum_topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("curriculum_topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cpa_phase: Mapped[str | None] = mapped_column(String(50), nullable=True)
    blooms_level: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    lesson_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lesson_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
