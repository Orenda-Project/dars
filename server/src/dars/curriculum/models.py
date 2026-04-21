import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from dars.database import Base


class Grade(Base):
    """UI catalog — not a FK on any core table, kept for display/filter convenience."""
    __tablename__ = "grades"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    short_code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)


class Subject(Base):
    """UI catalog — not a FK on any core table, kept for display/filter convenience."""
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
    """SLOs issued by a provider for a specific book. Grade/subject are derived from the book."""
    __tablename__ = "slos"
    __table_args__ = (UniqueConstraint("provider_id", "book_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("slo_providers.id"), nullable=False, index=True
    )
    book_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("books.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language_skills: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    sub_strand: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    provider: Mapped["SloProvider"] = relationship("SloProvider", back_populates="slos")
    sub_slos: Mapped[list["SubSlo"]] = relationship("SubSlo", back_populates="slo")


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

    slo: Mapped["Slo"] = relationship("Slo", back_populates="sub_slos")


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("chapter_id", "sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("book_chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sub_slos: Mapped[list["TopicSubSlo"]] = relationship("TopicSubSlo", back_populates="topic")


class TopicSubSlo(Base):
    __tablename__ = "topic_sub_slos"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    sub_slo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sub_slos.id"), primary_key=True
    )

    topic: Mapped["Topic"] = relationship("Topic", back_populates="sub_slos")
    sub_slo: Mapped["SubSlo"] = relationship("SubSlo")


class Curriculum(Base):
    """Named teaching plan for a specific book + SLO provider (master-owned, no client/teacher)."""
    __tablename__ = "curriculums"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("slo_providers.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    topics: Mapped[list["CurriculumTopic"]] = relationship(
        "CurriculumTopic", back_populates="curriculum", order_by="CurriculumTopic.sequence"
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
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    curriculum: Mapped["Curriculum"] = relationship("Curriculum", back_populates="topics")
    stubs: Mapped[list["CurriculumLpStub"]] = relationship(
        "CurriculumLpStub", back_populates="curriculum_topic", order_by="CurriculumLpStub.sequence"
    )


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
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
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

    curriculum_topic: Mapped["CurriculumTopic"] = relationship("CurriculumTopic", back_populates="stubs")
