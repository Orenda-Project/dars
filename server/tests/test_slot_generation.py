"""
Tests for Step 6 — LP & Exam Generation from lesson/assessment slots:
  generate_lp_for_slot()
  generate_all_lps_for_chapter()
  generate_exam_for_slot()
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import dars.clients.models  # noqa
import dars.curriculum.models  # noqa
import dars.curriculum_data.models  # noqa
import dars.generated_exams.models  # noqa
import dars.generated_lps.models  # noqa
import dars.lookup.models  # noqa
import dars.school.models  # noqa
import dars.teachers.models  # noqa
import dars.webhooks.models  # noqa

from dars.clients.models import Client
from dars.curriculum.models import Book, BookChapter
from dars.curriculum_data.models import CurriculumData
from dars.database import Base
from dars.generated_exams.models import GeneratedExam
from dars.generated_lps.models import GeneratedLP
from dars.lookup.models import Grade, Subject
from dars.school.models import (
    AcademicYear,
    AssessmentSlot,
    ChapterPlan,
    ClassLessonSlot,
    ClassSubjectTeacher,
    SchoolClass,
)
from dars.school.service import (
    generate_all_lps_for_chapter,
    generate_exam_for_slot,
    generate_lp_for_slot,
)

TEST_DB = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add(CurriculumData(code="NCP", name="National Curriculum of Pakistan"))
        session.add(Subject(code="Eng", display_name="English"))
        session.add(Grade(code=5, display_name="Grade 5"))
        session.add(Grade(code=6, display_name="Grade 6"))
        await session.commit()
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _make_school_setup(
    session: AsyncSession,
) -> tuple[Client, ClassSubjectTeacher, ChapterPlan, ClassLessonSlot, AssessmentSlot]:
    """Create a full school hierarchy; return (client, cst, chapter_plan, lesson_slot, assessment_slot)."""
    client = Client(
        email="gen@school.com",
        name="Gen School",
        api_key_hash="deadbeef01",
        curriculum="NCP",
    )
    session.add(client)
    await session.flush()
    await session.refresh(client)

    year = AcademicYear(
        client_id=client.id,
        name="2026-27",
        start_date=date(2026, 4, 1),
        end_date=date(2027, 3, 31),
    )
    session.add(year)
    await session.flush()
    await session.refresh(year)

    school_class = SchoolClass(
        client_id=client.id,
        academic_year_id=year.id,
        grade=5,
        section="A",
        name="Grade 5-A",
    )
    session.add(school_class)
    await session.flush()
    await session.refresh(school_class)

    book = Book(
        curriculum="NCP",
        grade=5,
        subject="Eng",
        title="Grade 5 English",
    )
    session.add(book)
    await session.flush()
    await session.refresh(book)

    book_chapter = BookChapter(
        book_id=book.id,
        chapter_number=1,
        title="The Clever Fox",
    )
    session.add(book_chapter)
    await session.flush()
    await session.refresh(book_chapter)

    cst = ClassSubjectTeacher(
        client_id=client.id,
        class_id=school_class.id,
        subject="English",
        book_id=book.id,
    )
    session.add(cst)
    await session.flush()
    await session.refresh(cst)

    plan = ChapterPlan(
        client_id=client.id,
        class_subject_teacher_id=cst.id,
        chapter_id=book_chapter.id,
        position=1,
        teaching_days=3,
    )
    session.add(plan)
    await session.flush()
    await session.refresh(plan)

    lesson_slot = ClassLessonSlot(
        client_id=client.id,
        class_subject_teacher_id=cst.id,
        chapter_plan_id=plan.id,
        day_number=1,
        lp_type="Reading",
        title="Day 1: Reading",
        status="planned",
    )
    session.add(lesson_slot)
    await session.flush()
    await session.refresh(lesson_slot)

    assessment_slot = AssessmentSlot(
        client_id=client.id,
        class_subject_teacher_id=cst.id,
        chapter_plan_id=plan.id,
        assessment_type="formative",
        scheduled_date=date(2026, 5, 1),
        title="Chapter 1 FA",
        status="scheduled",
    )
    session.add(assessment_slot)
    await session.flush()
    await session.refresh(assessment_slot)

    await session.commit()
    return client, cst, plan, lesson_slot, assessment_slot


async def _make_second_client_setup(
    session: AsyncSession,
) -> tuple[Client, ClassLessonSlot, AssessmentSlot]:
    """Create a second client with their own slot (for isolation tests)."""
    client2 = Client(
        email="other@school.com",
        name="Other School",
        api_key_hash="deadbeef02",
        curriculum="NCP",
    )
    session.add(client2)
    await session.flush()
    await session.refresh(client2)

    year2 = AcademicYear(
        client_id=client2.id,
        name="2026-27",
        start_date=date(2026, 4, 1),
        end_date=date(2027, 3, 31),
    )
    session.add(year2)
    await session.flush()
    await session.refresh(year2)

    class2 = SchoolClass(
        client_id=client2.id,
        academic_year_id=year2.id,
        grade=6,
        section="B",
        name="Grade 6-B",
    )
    session.add(class2)
    await session.flush()
    await session.refresh(class2)

    book2 = Book(curriculum="NCP", grade=6, subject="Eng", title="Grade 6 English")
    session.add(book2)
    await session.flush()
    await session.refresh(book2)

    bc2 = BookChapter(book_id=book2.id, chapter_number=1, title="Ch 1")
    session.add(bc2)
    await session.flush()
    await session.refresh(bc2)

    cst2 = ClassSubjectTeacher(
        client_id=client2.id,
        class_id=class2.id,
        subject="English",
        book_id=book2.id,
    )
    session.add(cst2)
    await session.flush()
    await session.refresh(cst2)

    plan2 = ChapterPlan(
        client_id=client2.id,
        class_subject_teacher_id=cst2.id,
        chapter_id=bc2.id,
        position=1,
        teaching_days=2,
    )
    session.add(plan2)
    await session.flush()
    await session.refresh(plan2)

    slot2 = ClassLessonSlot(
        client_id=client2.id,
        class_subject_teacher_id=cst2.id,
        chapter_plan_id=plan2.id,
        day_number=1,
        lp_type="Reading",
        title="Day 1",
        status="planned",
    )
    session.add(slot2)
    await session.flush()
    await session.refresh(slot2)

    aslot2 = AssessmentSlot(
        client_id=client2.id,
        class_subject_teacher_id=cst2.id,
        chapter_plan_id=plan2.id,
        assessment_type="formative",
        scheduled_date=date(2026, 5, 10),
        status="scheduled",
    )
    session.add(aslot2)
    await session.flush()
    await session.refresh(aslot2)

    await session.commit()
    return client2, slot2, aslot2


# ---------------------------------------------------------------------------
# Tests: generate_lp_for_slot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_lp_for_slot_creates_lp_and_links(db_session):
    """generate_lp_for_slot should create a PENDING GeneratedLP and link it to the slot."""
    client, cst, plan, lesson_slot, _ = await _make_school_setup(db_session)

    lp = await generate_lp_for_slot(db_session, lesson_slot.id, client.id, "NCP")

    assert lp.id is not None
    assert lp.status == "PENDING"
    assert lp.client_id == client.id

    # Verify slot.lesson_plan_id is set in DB
    refreshed_slot_result = await db_session.execute(
        select(ClassLessonSlot).where(ClassLessonSlot.id == lesson_slot.id)
    )
    refreshed_slot = refreshed_slot_result.scalar_one()
    assert refreshed_slot.lesson_plan_id == lp.id

    # Verify GeneratedLP record in DB
    lp_db_result = await db_session.execute(
        select(GeneratedLP).where(GeneratedLP.id == lp.id)
    )
    lp_db = lp_db_result.scalar_one()
    assert lp_db.status == "PENDING"
    assert lp_db.curriculum == "NCP"


@pytest.mark.asyncio
async def test_generate_lp_for_slot_already_has_lp_raises_409(db_session):
    """Calling generate_lp_for_slot on a slot that already has lesson_plan_id should raise 409."""
    client, cst, plan, lesson_slot, _ = await _make_school_setup(db_session)

    # First call succeeds
    lp1 = await generate_lp_for_slot(db_session, lesson_slot.id, client.id, "NCP")
    assert lp1.status == "PENDING"

    # Second call should raise 409
    with pytest.raises(HTTPException) as exc_info:
        await generate_lp_for_slot(db_session, lesson_slot.id, client.id, "NCP")
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Tests: generate_all_lps_for_chapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_all_lps_queues_all_unlinked_slots(db_session):
    """generate_all_lps_for_chapter should queue LP for every slot without lesson_plan_id."""
    client, cst, plan, lesson_slot, _ = await _make_school_setup(db_session)

    # Add more slots to the chapter plan
    slot2 = ClassLessonSlot(
        client_id=client.id,
        class_subject_teacher_id=cst.id,
        chapter_plan_id=plan.id,
        day_number=2,
        lp_type="Grammar",
        title="Day 2: Grammar",
        status="planned",
    )
    slot3 = ClassLessonSlot(
        client_id=client.id,
        class_subject_teacher_id=cst.id,
        chapter_plan_id=plan.id,
        day_number=3,
        lp_type="Revision",
        title="Day 3: Revision",
        status="planned",
    )
    db_session.add(slot2)
    db_session.add(slot3)
    await db_session.commit()

    queued_pairs, skipped = await generate_all_lps_for_chapter(
        db_session, plan.id, client.id, "NCP"
    )

    assert len(queued_pairs) == 3  # lesson_slot + slot2 + slot3
    assert skipped == 0

    # All slots in DB should now have lesson_plan_id
    slots_result = await db_session.execute(
        select(ClassLessonSlot).where(ClassLessonSlot.chapter_plan_id == plan.id)
    )
    db_slots = list(slots_result.scalars().all())
    for s in db_slots:
        assert s.lesson_plan_id is not None, f"Slot {s.id} still has no lesson_plan_id"


@pytest.mark.asyncio
async def test_generate_all_lps_skips_already_linked(db_session):
    """Second call to generate_all_lps_for_chapter should skip already-linked slots."""
    client, cst, plan, lesson_slot, _ = await _make_school_setup(db_session)

    # First call: queue all
    pairs1, skipped1 = await generate_all_lps_for_chapter(
        db_session, plan.id, client.id, "NCP"
    )
    assert len(pairs1) == 1
    assert skipped1 == 0

    # Second call: everything already linked
    pairs2, skipped2 = await generate_all_lps_for_chapter(
        db_session, plan.id, client.id, "NCP"
    )
    assert len(pairs2) == 0
    assert skipped2 == 1


# ---------------------------------------------------------------------------
# Tests: generate_exam_for_slot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_exam_for_slot_creates_exam_and_links(db_session):
    """generate_exam_for_slot should create a PENDING GeneratedExam and link it to the slot."""
    client, cst, plan, _, assessment_slot = await _make_school_setup(db_session)

    exam = await generate_exam_for_slot(db_session, assessment_slot.id, client.id, "NCP")

    assert exam.id is not None
    assert exam.status == "PENDING"
    assert exam.client_id == client.id

    # Verify slot.exam_id is set in DB
    refreshed_slot_result = await db_session.execute(
        select(AssessmentSlot).where(AssessmentSlot.id == assessment_slot.id)
    )
    refreshed_slot = refreshed_slot_result.scalar_one()
    assert refreshed_slot.exam_id == exam.id

    # Verify GeneratedExam record in DB
    exam_db_result = await db_session.execute(
        select(GeneratedExam).where(GeneratedExam.id == exam.id)
    )
    exam_db = exam_db_result.scalar_one()
    assert exam_db.status == "PENDING"


@pytest.mark.asyncio
async def test_generate_exam_for_slot_already_has_exam_raises_409(db_session):
    """Calling generate_exam_for_slot twice should raise 409 on second call."""
    client, cst, plan, _, assessment_slot = await _make_school_setup(db_session)

    # First call succeeds
    exam1 = await generate_exam_for_slot(db_session, assessment_slot.id, client.id, "NCP")
    assert exam1.status == "PENDING"

    # Second call should raise 409
    with pytest.raises(HTTPException) as exc_info:
        await generate_exam_for_slot(db_session, assessment_slot.id, client.id, "NCP")
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Tests: client isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_lp_for_slot_wrong_client_raises_404(db_session):
    """Client A cannot generate LP for Client B's slot."""
    client1, cst1, plan1, slot1, _ = await _make_school_setup(db_session)
    client2, slot2, _ = await _make_second_client_setup(db_session)

    # Client 1 tries to access Client 2's slot
    with pytest.raises(HTTPException) as exc_info:
        await generate_lp_for_slot(db_session, slot2.id, client1.id, "NCP")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_generate_exam_for_slot_wrong_client_raises_404(db_session):
    """Client A cannot generate exam for Client B's assessment slot."""
    client1, cst1, plan1, _, aslot1 = await _make_school_setup(db_session)
    client2, _, aslot2 = await _make_second_client_setup(db_session)

    # Client 1 tries to access Client 2's assessment slot
    with pytest.raises(HTTPException) as exc_info:
        await generate_exam_for_slot(db_session, aslot2.id, client1.id, "NCP")
    assert exc_info.value.status_code == 404
