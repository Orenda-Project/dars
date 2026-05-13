from datetime import date, datetime, time

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from dars.database import Base



class AcademicYear(Base):
    __tablename__ = "academic_years"

    client_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)


class Holiday(Base):
    __tablename__ = "holidays"

    client_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    academic_year_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class SchoolClass(Base):
    __tablename__ = "school_classes"

    client_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    academic_year_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False
    )
    grade_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("grades.id"), nullable=False)
    section: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class ClassSubjectTeacher(Base):
    __tablename__ = "class_subject_teachers"
    __table_args__ = (UniqueConstraint("class_id", "subject_id", name="uq_cst_class_subject"),)

    client_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    class_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("subjects.id"), nullable=False)
    teacher_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True
    )
    book_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="SET NULL"), nullable=True
    )


class Timetable(Base):
    __tablename__ = "timetables"

    client_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    class_subject_teacher_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("class_subject_teachers.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon ... 6=Sun
    start_time: Mapped[datetime | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(Time, nullable=True)


class ChapterPlan(Base):
    __tablename__ = "chapter_plans"
    __table_args__ = (
        UniqueConstraint(
            "class_subject_teacher_id", "chapter_id", name="uq_chapter_plan_cst_chapter"
        ),
    )

    client_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    class_subject_teacher_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("class_subject_teachers.id", ondelete="CASCADE"),
        nullable=False,
    )
    chapter_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("book_chapters.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    teaching_days: Mapped[int] = mapped_column(Integer, nullable=False)


class ClassLessonSlot(Base):
    __tablename__ = "class_lesson_slots"

    client_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    class_subject_teacher_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("class_subject_teachers.id", ondelete="CASCADE"),
        nullable=False,
    )
    chapter_plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chapter_plans.id", ondelete="CASCADE"), nullable=False
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lp_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    lesson_plan_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("generated_lesson_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="planned")
    taught_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class AssessmentSlot(Base):
    __tablename__ = "assessment_slots"

    client_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    class_subject_teacher_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("class_subject_teachers.id", ondelete="CASCADE"),
        nullable=False,
    )
    chapter_plan_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("chapter_plans.id", ondelete="SET NULL"), nullable=True
    )
    assessment_type: Mapped[str] = mapped_column(Text, nullable=False)  # formative | summative
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    exam_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("generated_exams.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="scheduled")
