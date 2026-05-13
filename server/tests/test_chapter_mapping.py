"""
Tests for Step 4 — Chapter Mapping & Year Plan:
  POST /admin/curriculum/{curriculum_code}/chapter-schedule
  GET  /admin/curriculum/{curriculum_code}/chapter-schedule
  GET  /api/v1/classes/{class_id}/subjects/{cst_id}/chapter-plans/prefill
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
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
from dars.curriculum.models import Book, BookChapter
from dars.curriculum_data.models import CurriculumData
from dars.database import Base, get_db
from dars.lookup.models import Subject
from dars.main import app

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
        session.add(CurriculumData(code="SNC", name="Single National Curriculum"))
        session.add(Subject(code="Eng", display_name="English"))
        session.add(Subject(code="Maths", display_name="Mathematics"))
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
    """Regular client with curriculum=NCP."""
    resp = await http_client.post(
        "/auth/signup",
        json={"email": "school@test.com", "password": "pass123", "name": "School Test", "curriculum": "NCP"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["api_key"]


@pytest.fixture(scope="function")
async def admin_key(http_client, db_session):
    """Admin client."""
    import dars.config as _cfg
    original = _cfg.settings.admin_secret
    _cfg.settings.admin_secret = "test-secret"

    resp = await http_client.post(
        "/auth/signup",
        json={"email": "admin@test.com", "password": "adminpass", "name": "Admin", "curriculum": "NCP"},
    )
    assert resp.status_code == 201, resp.text
    key = resp.json()["api_key"]

    # Promote to admin
    from dars.clients.service import get_client_by_api_key
    client = await get_client_by_api_key(db_session, key)
    client.is_admin = True
    client.curriculum = "NCP"
    await db_session.commit()

    yield key, _cfg.settings
    _cfg.settings.admin_secret = original


def headers(key: str) -> dict:
    return {"X-API-Key": key}


def admin_headers(key: str) -> dict:
    return {"X-API-Key": key}


async def _make_book(db_session, curriculum="NCP") -> Book:
    book = Book(
        curriculum=curriculum,
        grade=5,
        subject="Eng",
        title="Grade 5 English",
    )
    db_session.add(book)
    await db_session.flush()
    await db_session.refresh(book)
    return book


async def _make_chapter(db_session, book_id: uuid.UUID, number: int, title: str) -> BookChapter:
    ch = BookChapter(
        book_id=book_id,
        chapter_number=number,
        title=title,
    )
    db_session.add(ch)
    await db_session.flush()
    await db_session.refresh(ch)
    return ch


async def _make_school_setup(http_client, key: str, book_id: uuid.UUID | None = None) -> tuple[str, str]:
    """Create academic year + class + CST. Returns (class_id, cst_id)."""
    year_resp = await http_client.post(
        "/api/v1/academic-years",
        json={"name": "2025-26", "start_date": "2025-04-01", "end_date": "2026-03-31"},
        headers=headers(key),
    )
    assert year_resp.status_code == 201, year_resp.text
    year_id = year_resp.json()["id"]

    class_resp = await http_client.post(
        "/api/v1/classes",
        json={"academic_year_id": year_id, "grade": 5, "section": "A", "name": "Grade 5-A"},
        headers=headers(key),
    )
    assert class_resp.status_code == 201, class_resp.text
    class_id = class_resp.json()["id"]

    cst_body = {"subject": "Eng"}
    if book_id:
        cst_body["book_id"] = str(book_id)

    cst_resp = await http_client.post(
        f"/api/v1/classes/{class_id}/subjects",
        json=cst_body,
        headers=headers(key),
    )
    assert cst_resp.status_code == 201, cst_resp.text
    cst_id = cst_resp.json()["id"]

    return class_id, cst_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_upsert_chapter_schedule(http_client, admin_key, db_session):
    key, _ = admin_key
    book = await _make_book(db_session, curriculum="NCP")
    await db_session.commit()
    ch1 = await _make_chapter(db_session, book.id, 1, "Chapter One")
    ch2 = await _make_chapter(db_session, book.id, 2, "Chapter Two")
    await db_session.commit()

    payload = {
        "items": [
            {
                "book_id": str(book.id),
                "chapter_id": str(ch1.id),
                "suggested_teaching_days": 10,
                "suggested_position": 1,
                "term": "Term 1",
            },
            {
                "book_id": str(book.id),
                "chapter_id": str(ch2.id),
                "suggested_teaching_days": 12,
                "suggested_position": 2,
                "term": "Term 1",
            },
        ]
    }

    post_resp = await http_client.post(
        "/admin/curriculum/NCP/chapter-schedule",
        json=payload,
        headers=admin_headers(key),
    )
    assert post_resp.status_code == 200, post_resp.text
    data = post_resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    get_resp = await http_client.get(
        "/admin/curriculum/NCP/chapter-schedule",
        headers=admin_headers(key),
    )
    assert get_resp.status_code == 200, get_resp.text
    get_data = get_resp.json()
    assert get_data["total"] == 2
    positions = [item["suggested_position"] for item in get_data["items"]]
    assert positions == sorted(positions)


@pytest.mark.asyncio
async def test_admin_upsert_is_idempotent(http_client, admin_key, db_session):
    key, _ = admin_key
    book = await _make_book(db_session, curriculum="NCP")
    await db_session.commit()
    ch = await _make_chapter(db_session, book.id, 1, "Chapter One")
    await db_session.commit()

    payload = {
        "items": [
            {
                "book_id": str(book.id),
                "chapter_id": str(ch.id),
                "suggested_teaching_days": 10,
                "suggested_position": 1,
            }
        ]
    }

    # First POST
    resp1 = await http_client.post(
        "/admin/curriculum/NCP/chapter-schedule",
        json=payload,
        headers=admin_headers(key),
    )
    assert resp1.status_code == 200, resp1.text

    # Second POST — update days to 15
    payload["items"][0]["suggested_teaching_days"] = 15
    resp2 = await http_client.post(
        "/admin/curriculum/NCP/chapter-schedule",
        json=payload,
        headers=admin_headers(key),
    )
    assert resp2.status_code == 200, resp2.text
    data = resp2.json()
    # Still only 1 row, not duplicated
    assert data["total"] == 1
    assert data["items"][0]["suggested_teaching_days"] == 15


@pytest.mark.asyncio
async def test_prefill_returns_chapters_with_defaults(http_client, api_key, admin_key, db_session):
    client_key = api_key
    admin_k, _ = admin_key

    book = await _make_book(db_session, curriculum="NCP")
    await db_session.commit()
    ch1 = await _make_chapter(db_session, book.id, 1, "The Clever Fox")
    ch2 = await _make_chapter(db_session, book.id, 2, "The Brave Lion")
    await db_session.commit()

    # Admin sets defaults for NCP
    payload = {
        "items": [
            {
                "book_id": str(book.id),
                "chapter_id": str(ch1.id),
                "suggested_teaching_days": 8,
                "suggested_position": 1,
                "term": "Term 1",
            },
            {
                "book_id": str(book.id),
                "chapter_id": str(ch2.id),
                "suggested_teaching_days": 10,
                "suggested_position": 2,
                "term": "Term 2",
            },
        ]
    }
    sched_resp = await http_client.post(
        "/admin/curriculum/NCP/chapter-schedule",
        json=payload,
        headers=admin_headers(admin_k),
    )
    assert sched_resp.status_code == 200, sched_resp.text

    # Client creates class + CST with the book
    class_id, cst_id = await _make_school_setup(http_client, client_key, book_id=book.id)

    prefill_resp = await http_client.get(
        f"/api/v1/classes/{class_id}/subjects/{cst_id}/chapter-plans/prefill",
        headers=headers(client_key),
    )
    assert prefill_resp.status_code == 200, prefill_resp.text
    items = prefill_resp.json()["items"]
    assert len(items) == 2
    assert items[0]["chapter_number"] == 1
    assert items[0]["suggested_teaching_days"] == 8
    assert items[0]["term"] == "Term 1"
    assert items[1]["chapter_number"] == 2
    assert items[1]["suggested_teaching_days"] == 10


@pytest.mark.asyncio
async def test_prefill_no_book_returns_empty(http_client, api_key):
    """CST with no book_id → prefill returns empty list."""
    class_id, cst_id = await _make_school_setup(http_client, api_key, book_id=None)

    resp = await http_client.get(
        f"/api/v1/classes/{class_id}/subjects/{cst_id}/chapter-plans/prefill",
        headers=headers(api_key),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_prefill_no_defaults_returns_nulls(http_client, api_key, db_session):
    """Book set but no admin defaults → chapters returned with suggested_* = None."""
    book = await _make_book(db_session, curriculum="NCP")
    await db_session.commit()
    await _make_chapter(db_session, book.id, 1, "Chapter One")
    await _make_chapter(db_session, book.id, 2, "Chapter Two")
    await db_session.commit()

    class_id, cst_id = await _make_school_setup(http_client, api_key, book_id=book.id)

    resp = await http_client.get(
        f"/api/v1/classes/{class_id}/subjects/{cst_id}/chapter-plans/prefill",
        headers=headers(api_key),
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 2
    for item in items:
        assert item["suggested_teaching_days"] is None
        assert item["suggested_position"] is None
        assert item["term"] is None


@pytest.mark.asyncio
async def test_client_cannot_see_other_client_chapter_plans(http_client, db_session):
    """Two clients cannot see each other's CST prefill data."""
    # Create client A
    resp_a = await http_client.post(
        "/auth/signup",
        json={"email": "clienta@test.com", "password": "pass", "name": "Client A", "curriculum": "NCP"},
    )
    assert resp_a.status_code == 201, resp_a.text
    key_a = resp_a.json()["api_key"]

    # Create client B
    resp_b = await http_client.post(
        "/auth/signup",
        json={"email": "clientb@test.com", "password": "pass", "name": "Client B", "curriculum": "NCP"},
    )
    assert resp_b.status_code == 201, resp_b.text
    key_b = resp_b.json()["api_key"]

    # Client A sets up a class + CST
    class_id_a, cst_id_a = await _make_school_setup(http_client, key_a)

    # Client B tries to access Client A's prefill — should get 404
    resp = await http_client.get(
        f"/api/v1/classes/{class_id_a}/subjects/{cst_id_a}/chapter-plans/prefill",
        headers=headers(key_b),
    )
    assert resp.status_code == 404, resp.text
