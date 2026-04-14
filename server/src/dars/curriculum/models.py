import uuid
from datetime import datetime, timezone

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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


class Curriculum(Base):
    __tablename__ = "curriculums"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    board: Mapped[str] = mapped_column(String(50), nullable=False)
    academic_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class CurriculumGradeSubject(Base):
    __tablename__ = "curriculum_grade_subjects"

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("curriculums.id", ondelete="CASCADE"), primary_key=True
    )
    grade_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("grades.id"), primary_key=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subjects.id"), primary_key=True
    )


class CurriculumDay(Base):
    __tablename__ = "curriculum_days"
    __table_args__ = (
        Index("ix_curriculum_days_curriculum_grade_subject", "curriculum_id", "grade_id", "subject_id"),
        Index("ix_curriculum_days_sequence", "sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("curriculums.id", ondelete="CASCADE"), nullable=False
    )
    grade_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("grades.id"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subjects.id"), nullable=False
    )
    book_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("books.id"), nullable=True)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_title: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    day_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    day_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    segment_type: Mapped[str] = mapped_column(String(30), nullable=False, default="lesson")
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    skill_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cpa_phase: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pages: Mapped[str | None] = mapped_column(String(50), nullable=True)
    blooms_level: Mapped[str | None] = mapped_column(String(30), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slide_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_enriched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    slos: Mapped[list["CurriculumDaySlo"]] = relationship(
        "CurriculumDaySlo", back_populates="day", cascade="all, delete-orphan"
    )


class CurriculumDaySlo(Base):
    __tablename__ = "curriculum_day_slos"

    curriculum_day_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("curriculum_days.id", ondelete="CASCADE"), primary_key=True
    )
    slo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("slos.id"), primary_key=True
    )

    day: Mapped["CurriculumDay"] = relationship("CurriculumDay", back_populates="slos")


class ClientCurriculum(Base):
    __tablename__ = "client_curriculums"
    __table_args__ = (UniqueConstraint("client_id", "curriculum_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("curriculums.id"), nullable=False
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
