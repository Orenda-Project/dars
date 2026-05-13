"""
Tests for Step 8 — Teacher-owned class creation.
POST /api/v1/teacher/classes

Scenarios:
1. Happy path: SchoolClass + CST created, chapter_count > 0, status = "breakdown_pending"
2. No default_teacher_id → 422
3. No book for this grade/subject → 422
4. Invalid academic_year_id (not found) → 404
5. Client isolation: academic_year from another client → 404
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import dars.clients.models  # noqa: F401
import dars.curriculum.models  # noqa: F401
import dars.curriculum_data.models  # noqa: F401
import dars.generated_exams.models  # noqa: F401
import dars.generated_lps.models  # noqa: F401
import dars.lookup.models  # noqa: F401
import dars.school.models  # noqa: F401
import dars.teachers.models  # noqa: F401
import dars.webhooks.models  # noqa: F401

from dars.clients.models import Client
from dars.curriculum.models import Book, BookChapter, CurriculumChapterSchedule
from dars.curriculum_data.models import CurriculumData
from dars.database import Base, get_db
from dars.lookup.models import Grade, Subject
from dars.main import app
from dars.school.models import AcademicYear, ChapterPlan, ClassSubjectTeacher, SchoolClass

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
        # Seed required lookup tables
        session.add(CurriculumData(code="NCP", name="National Curriculum of Pakistan"))
        session.add(Subject(code="english", display_name="English"))
        session.add(Subject(code="maths", display_name="Maths"))
        session.add(Grade(code=5, display_name="Grade 5"))
        session.add(Grade(code=6, display_name="Grade 6"))
        await session.commit()
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def http_client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def api_key(http_client):
    """Create a client with curriculum=NCP and return the API key."""
    resp = await http_client.post(
        "/auth/signup",
        json={
            "email": "teacher@school.com",
            "password": "pass123",
            "name": "Test School",
            "curriculum": "NCP",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["api_key"]


@pytest.fixture(scope="function")
async def api_key2(http_client):
    """A second client for isolation tests."""
    resp = await http_client.post(
        "/auth/signup",
        json={
            "email": "other@school.com",
            "password": "pass456",
            "name": "Other School",
            "curriculum": "NCP",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["api_key"]


def headers(key: str) -> dict:
    return {"X-API-Key": key}


async def _make_academic_year(http_client, key: str) -> dict:
    resp = await http_client.post(
        "/api/v1/academic-years",
        json={"name": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31"},
        headers=headers(key),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _seed_book_and_chapters(db_session: AsyncSession) -> tuple[Book, list[BookChapter]]:
    """Seed a Book + 3 BookChapters + CurriculumChapterSchedule rows for NCP/grade5/english."""
    book = Book(
        curriculum="NCP",
        grade=5,
        subject="english",
        title="Grade 5 English NCP",
    )
    db_session.add(book)
    await db_session.flush()
    await db_session.refresh(book)

    chapters = []
    for i in range(1, 4):
        bc = BookChapter(
            book_id=book.id,
            chapter_number=i,
            title=f"Chapter {i}",
        )
        db_session.add(bc)
        await db_session.flush()
        await db_session.refresh(bc)
        chapters.append(bc)

        # Add curriculum schedule
        sched = CurriculumChapterSchedule(
            curriculum="NCP",
            book_id=book.id,
            chapter_id=bc.id,
            suggested_teaching_days=5,
            suggested_position=i,
        )
        db_session.add(sched)

    await db_session.commit()
    return book, chapters


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_teacher_class_happy_path(http_client, api_key, db_session):
    """Happy path: SchoolClass + CST created, chapter_count > 0, status = breakdown_pending."""
    await _seed_book_and_chapters(db_session)
    # signup auto-creates default_teacher_id
    year = await _make_academic_year(http_client, api_key)

    resp = await http_client.post(
        "/api/v1/teacher/classes",
        json={
            "grade": 5,
            "section": "A",
            "subject": "english",
            "academic_year_id": year["id"],
        },
        headers=headers(api_key),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert "class_id" in data
    assert "cst_id" in data
    assert data["chapter_count"] == 3  # seeded 3 chapters
    assert data["status"] == "breakdown_pending"

    # Verify SchoolClass in DB
    sc_result = await db_session.execute(
        select(SchoolClass).where(SchoolClass.id == uuid.UUID(data["class_id"]))
    )
    sc = sc_result.scalar_one_or_none()
    assert sc is not None
    assert sc.grade == 5
    assert sc.section == "A"
    assert sc.name == "Grade 5-A"

    # Verify CST in DB
    cst_result = await db_session.execute(
        select(ClassSubjectTeacher).where(ClassSubjectTeacher.id == uuid.UUID(data["cst_id"]))
    )
    cst = cst_result.scalar_one_or_none()
    assert cst is not None
    assert cst.subject == "english"
    assert cst.book_id is not None

    # Verify chapter plans upserted
    cp_result = await db_session.execute(
        select(ChapterPlan).where(ChapterPlan.class_subject_teacher_id == uuid.UUID(data["cst_id"]))
    )
    plans = list(cp_result.scalars().all())
    assert len(plans) == 3


@pytest.mark.asyncio
async def test_create_teacher_class_no_default_teacher_422(http_client, api_key, db_session):
    """No default_teacher_id on client → 422."""
    await _seed_book_and_chapters(db_session)

    # Clear default_teacher_id on the client (signup auto-creates one, so we undo it)
    resp = await http_client.get("/api/v1/me", headers=headers(api_key))
    assert resp.status_code == 200, resp.text
    client_id = uuid.UUID(resp.json()["id"])

    from dars.clients.models import Client
    client_result = await db_session.execute(select(Client).where(Client.id == client_id))
    client = client_result.scalar_one()
    client.default_teacher_id = None
    await db_session.commit()

    year = await _make_academic_year(http_client, api_key)

    resp = await http_client.post(
        "/api/v1/teacher/classes",
        json={
            "grade": 5,
            "section": "A",
            "subject": "english",
            "academic_year_id": year["id"],
        },
        headers=headers(api_key),
    )
    assert resp.status_code == 422, resp.text
    assert "default teacher" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_teacher_class_no_book_422(http_client, api_key, db_session):
    """No book for this grade/subject combination → 422."""
    # signup auto-creates default_teacher_id; no book seeded for grade 5 / maths
    year = await _make_academic_year(http_client, api_key)

    resp = await http_client.post(
        "/api/v1/teacher/classes",
        json={
            "grade": 5,
            "section": "B",
            "subject": "maths",  # No book seeded for this
            "academic_year_id": year["id"],
        },
        headers=headers(api_key),
    )
    assert resp.status_code == 422, resp.text
    assert "book" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_teacher_class_invalid_year_404(http_client, api_key, db_session):
    """Invalid academic_year_id (non-existent) → 404."""
    await _seed_book_and_chapters(db_session)
    # signup auto-creates default_teacher_id

    resp = await http_client.post(
        "/api/v1/teacher/classes",
        json={
            "grade": 5,
            "section": "A",
            "subject": "english",
            "academic_year_id": str(uuid.uuid4()),  # random non-existent
        },
        headers=headers(api_key),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_create_teacher_class_client_isolation_404(http_client, api_key, api_key2, db_session):
    """Client A cannot use Client B's academic year → 404."""
    await _seed_book_and_chapters(db_session)
    # signup auto-creates default_teacher_id for both clients

    # Create academic year for client2
    year2 = await _make_academic_year(http_client, api_key2)

    # Client1 tries to use client2's academic year
    resp = await http_client.post(
        "/api/v1/teacher/classes",
        json={
            "grade": 5,
            "section": "A",
            "subject": "english",
            "academic_year_id": year2["id"],
        },
        headers=headers(api_key),
    )
    assert resp.status_code == 404, resp.text
