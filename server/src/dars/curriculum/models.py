from sqlalchemy import BigInteger, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from dars.database import Base


class SLO(Base):
    __tablename__ = "slos"

    curriculum_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("curriculums.id"), nullable=False)
    grade_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("grades.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("subjects.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class TopicSLO(Base):
    __tablename__ = "topic_slos"
    __table_args__ = (UniqueConstraint("topic_id", "slo_id", name="uq_topic_slo"),)

    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    slo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("slos.id", ondelete="CASCADE"), nullable=False
    )


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------


class Book(Base):
    __tablename__ = "books"

    core_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    curriculum_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("curriculums.id"), nullable=False)
    grade_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("grades.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("subjects.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str | None] = mapped_column(Text, nullable=True)
    edition: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_chapters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    series: Mapped[str | None] = mapped_column(Text, nullable=True)


class BookChapter(Base):
    __tablename__ = "book_chapters"

    core_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Topic(Base):
    __tablename__ = "topics"

    chapter_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("book_chapters.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    start_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # topic_text not in ORM — stored/loaded via raw SQL


class CurriculumChapterSchedule(Base):
    __tablename__ = "curriculum_chapter_schedule"
    __table_args__ = (
        UniqueConstraint("curriculum_id", "chapter_id", name="uq_ccs_curriculum_chapter"),
    )

    curriculum_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("curriculums.id"), nullable=False)
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    chapter_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("book_chapters.id", ondelete="CASCADE"), nullable=False
    )
    suggested_teaching_days: Mapped[int] = mapped_column(Integer, nullable=False)
    suggested_position: Mapped[int] = mapped_column(Integer, nullable=False)
    term: Mapped[str | None] = mapped_column(Text, nullable=True)


class LessonSlot(Base):
    __tablename__ = "lesson_slots"

    topic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_subtopic: Mapped[str] = mapped_column(Text, nullable=False)
    lesson_plan_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("generated_lesson_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
