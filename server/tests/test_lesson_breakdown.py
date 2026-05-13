"""
Tests for Step 5 — AI Lesson Breakdown:
  ai_breakdown_chapter()
  ai_breakdown_all()

Uses SQLite in-memory, mocks anthropic.AsyncAnthropic to avoid real API calls.
"""

import json
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

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
from dars.lookup.models import Subject
from dars.school.models import (
    AcademicYear,
    AssessmentSlot,
    ChapterPlan,
    ClassLessonSlot,
    ClassSubjectTeacher,
    SchoolClass,
)
from dars.school.service import ai_breakdown_all, ai_breakdown_chapter

TEST_DB = "sqlite+aiosqlite:///:memory:"

# ---------------------------------------------------------------------------
# Sample Claude response
# ---------------------------------------------------------------------------

SAMPLE_RESPONSE_JSON = [
    {"day": 1, "type": "lesson", "lp_type": "Reading", "title": "Day 1 Reading"},
    {"day": 2, "type": "lesson", "lp_type": "Grammar", "title": "Day 2 Grammar"},
    {"day": 3, "type": "lesson", "lp_type": "Revision", "title": "Day 3 Revision"},
]

SAMPLE_WITH_FA_JSON = [
    {"day": 1, "type": "lesson", "lp_type": "Reading", "title": "Day 1 Reading"},
    {"day": 2, "type": "lesson", "lp_type": "Grammar", "title": "Day 2 Grammar"},
    {"day": 3, "type": "lesson", "lp_type": "Comprehension (Q&A)", "title": "Day 3 Comprehension"},
    {"day": 4, "type": "assessment", "assessment_type": "formative", "title": "Chapter FA 1"},
    {"day": 5, "type": "lesson", "lp_type": "Creative Writing", "title": "Day 5 Writing"},
    {"day": 6, "type": "lesson", "lp_type": "Revision", "title": "Day 6 Revision"},
]


def _make_mock_claude_response(items: list) -> MagicMock:
    """Build a fake Claude message response with .content[0].text."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock()]
    mock_msg.content[0].text = json.dumps(items)
    return mock_msg


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
        await session.commit()
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _make_school_setup(session: AsyncSession) -> tuple[Client, ClassSubjectTeacher, ChapterPlan]:
    """Create a minimal school hierarchy and return (client, cst, chapter_plan)."""
    client = Client(
        email="test@school.com",
        name="Test School",
        api_key_hash="deadbeef",
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

    await session.commit()
    return client, cst, plan


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai_breakdown_chapter_creates_slots(db_session):
    """ai_breakdown_chapter should create ClassLessonSlots from Claude response."""
    client, cst, plan = await _make_school_setup(db_session)

    mock_response = _make_mock_claude_response(SAMPLE_RESPONSE_JSON)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    mock_constructor = MagicMock(return_value=mock_client)

    with patch("dars.school.service.anthropic.AsyncAnthropic", mock_constructor):
        with patch("dars.school.service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "fake-key"
            result = await ai_breakdown_chapter(plan.id, db_session)

    assert "lesson_slots" in result
    assert "assessment_slots" in result
    assert len(result["lesson_slots"]) == 3

    # Verify DB
    slots_result = await db_session.execute(
        select(ClassLessonSlot).where(ClassLessonSlot.chapter_plan_id == plan.id)
    )
    db_slots = list(slots_result.scalars().all())
    assert len(db_slots) == 3


@pytest.mark.asyncio
async def test_last_slot_is_revision(db_session):
    """The last lesson slot must have lp_type == 'Revision'."""
    client, cst, plan = await _make_school_setup(db_session)

    mock_response = _make_mock_claude_response(SAMPLE_RESPONSE_JSON)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("dars.school.service.anthropic.AsyncAnthropic", MagicMock(return_value=mock_client)):
        with patch("dars.school.service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "fake-key"
            result = await ai_breakdown_chapter(plan.id, db_session)

    lesson_slots = result["lesson_slots"]
    assert len(lesson_slots) > 0
    last_slot = max(lesson_slots, key=lambda s: s.day_number)
    assert last_slot.lp_type == "Revision"


@pytest.mark.asyncio
async def test_formative_assessments_created(db_session):
    """Chapters with >3 days should have at least one AssessmentSlot with type formative."""
    client, cst, plan = await _make_school_setup(db_session)
    # Update teaching_days to support FAs
    plan.teaching_days = 6
    await db_session.commit()

    mock_response = _make_mock_claude_response(SAMPLE_WITH_FA_JSON)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("dars.school.service.anthropic.AsyncAnthropic", MagicMock(return_value=mock_client)):
        with patch("dars.school.service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "fake-key"
            result = await ai_breakdown_chapter(plan.id, db_session)

    assert len(result["assessment_slots"]) >= 1
    fa_types = [a.assessment_type for a in result["assessment_slots"]]
    assert "formative" in fa_types

    # Verify DB
    aslots_result = await db_session.execute(
        select(AssessmentSlot).where(
            AssessmentSlot.chapter_plan_id == plan.id,
            AssessmentSlot.assessment_type == "formative",
        )
    )
    db_aslots = list(aslots_result.scalars().all())
    assert len(db_aslots) >= 1


@pytest.mark.asyncio
async def test_regenerate_wipes_existing(db_session):
    """Calling ai_breakdown_chapter twice should replace old slots, not accumulate."""
    client, cst, plan = await _make_school_setup(db_session)

    first_response = _make_mock_claude_response(SAMPLE_RESPONSE_JSON)
    second_response_json = [
        {"day": 1, "type": "lesson", "lp_type": "Vocabulary", "title": "New Day 1"},
        {"day": 2, "type": "lesson", "lp_type": "Revision", "title": "New Day 2 Revision"},
    ]
    second_response = _make_mock_claude_response(second_response_json)

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    with patch("dars.school.service.anthropic.AsyncAnthropic", MagicMock(return_value=mock_client)):
        with patch("dars.school.service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "fake-key"
            result1 = await ai_breakdown_chapter(plan.id, db_session)
            assert len(result1["lesson_slots"]) == 3

            result2 = await ai_breakdown_chapter(plan.id, db_session)
            assert len(result2["lesson_slots"]) == 2

    # Only 2 slots should remain in DB
    slots_result = await db_session.execute(
        select(ClassLessonSlot).where(ClassLessonSlot.chapter_plan_id == plan.id)
    )
    db_slots = list(slots_result.scalars().all())
    assert len(db_slots) == 2


@pytest.mark.asyncio
async def test_fallback_on_claude_failure(db_session):
    """If Claude raises an exception, fallback to generate_lesson_sequence (cycling)."""
    client, cst, plan = await _make_school_setup(db_session)

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=Exception("API timeout"))

    with patch("dars.school.service.anthropic.AsyncAnthropic", MagicMock(return_value=mock_client)):
        with patch("dars.school.service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "fake-key"
            result = await ai_breakdown_chapter(plan.id, db_session)

    # Fallback must still produce slots
    assert len(result["lesson_slots"]) > 0
    # assessment_slots is empty in fallback
    assert result["assessment_slots"] == []

    # DB must have slots from fallback
    slots_result = await db_session.execute(
        select(ClassLessonSlot).where(ClassLessonSlot.chapter_plan_id == plan.id)
    )
    db_slots = list(slots_result.scalars().all())
    assert len(db_slots) > 0


@pytest.mark.asyncio
async def test_breakdown_all_creates_slots_for_all_chapters(db_session):
    """ai_breakdown_all should process all chapter plans for the CST."""
    client, cst, plan1 = await _make_school_setup(db_session)

    # Add a second book chapter and chapter plan
    book_result = await db_session.execute(select(BookChapter).where(BookChapter.id == plan1.chapter_id))
    first_book_chapter = book_result.scalar_one()

    chapter2 = BookChapter(
        book_id=first_book_chapter.book_id,
        chapter_number=2,
        title="The Brave Lion",
    )
    db_session.add(chapter2)
    await db_session.flush()
    await db_session.refresh(chapter2)

    plan2 = ChapterPlan(
        client_id=client.id,
        class_subject_teacher_id=cst.id,
        chapter_id=chapter2.id,
        position=2,
        teaching_days=3,
    )
    db_session.add(plan2)
    await db_session.commit()

    three_slot_response = _make_mock_claude_response(SAMPLE_RESPONSE_JSON)

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        side_effect=[three_slot_response, three_slot_response]
    )

    with patch("dars.school.service.anthropic.AsyncAnthropic", MagicMock(return_value=mock_client)):
        with patch("dars.school.service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "fake-key"
            summary = await ai_breakdown_all(cst.id, db_session)

    assert summary["chapters_planned"] == 2
    assert summary["total_lesson_slots"] == 6  # 3 per chapter

    # Verify both chapters have slots in DB
    for plan_id in [plan1.id, plan2.id]:
        slots_result = await db_session.execute(
            select(ClassLessonSlot).where(ClassLessonSlot.chapter_plan_id == plan_id)
        )
        db_slots = list(slots_result.scalars().all())
        assert len(db_slots) == 3, f"Expected 3 slots for plan {plan_id}, got {len(db_slots)}"
