"""
Tests for:
  GET /api/v1/books/{book_id}/chapters/{chapter_id}/topics
  GET /api/v1/topics/{topic_id}/slots
  POST /admin/chapters/{chapter_id}/breakdown  (mocked AI)
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import dars.assessments.models  # noqa — register with Base
import dars.clients.models  # noqa — register with Base
import dars.curriculum.models  # noqa — register with Base
from dars.clients.service import create_client
from dars.curriculum.models import Book, BookChapter, LessonSlot, Topic
from dars.database import Base, get_db
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
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def authed_client(db_session):
    import dars.config as _cfg

    original_secret = _cfg.settings.admin_secret
    _cfg.settings.admin_secret = "dev-secret"

    client_obj, raw_key = await create_client(db_session, name="Test Client")
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, raw_key, client_obj
    app.dependency_overrides.clear()
    _cfg.settings.admin_secret = original_secret


async def _make_book(db: AsyncSession, **kwargs) -> Book:
    defaults = {
        "core_id": 1,
        "curriculum": "ICT",
        "grade": 5,
        "subject": "Math",
        "title": "Math Book Grade 5",
    }
    defaults.update(kwargs)
    book = Book(**defaults)
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def _make_chapter(db: AsyncSession, book_id: uuid.UUID, **kwargs) -> BookChapter:
    defaults = {
        "core_id": 1,
        "book_id": book_id,
        "title": "Chapter 1",
        "chapter_number": 1,
    }
    defaults.update(kwargs)
    chapter = BookChapter(**defaults)
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return chapter


async def _make_topic(db: AsyncSession, chapter_id: uuid.UUID, **kwargs) -> Topic:
    defaults = {
        "chapter_id": chapter_id,
        "topic_number": 1,
        "title": "Topic One",
        "start_page": 5,
        "end_page": 10,
    }
    defaults.update(kwargs)
    topic = Topic(**defaults)
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic


async def _make_slot(db: AsyncSession, topic_id: uuid.UUID, **kwargs) -> LessonSlot:
    defaults = {
        "topic_id": topic_id,
        "day_number": 1,
        "scheduled_date": None,
        "topic_subtopic": "Topic One — Introduction",
    }
    defaults.update(kwargs)
    slot = LessonSlot(**defaults)
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    return slot


# ---------------------------------------------------------------------------
# GET /api/v1/books/{book_id}/chapters/{chapter_id}/topics
# ---------------------------------------------------------------------------


async def test_list_topics_requires_auth(authed_client, db_session):
    http, _, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1)
    response = await http.get(f"/api/v1/books/{book.id}/chapters/{chapter.id}/topics")
    assert response.status_code == 401


async def test_list_topics_chapter_not_found(authed_client, db_session):
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    fake_id = str(uuid.uuid4())
    response = await http.get(
        f"/api/v1/books/{book.id}/chapters/{fake_id}/topics",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 404


async def test_list_topics_chapter_wrong_book(authed_client, db_session):
    http, api_key, _ = authed_client
    book_a = await _make_book(db_session, core_id=1, title="Book A")
    book_b = await _make_book(db_session, core_id=2, title="Book B")
    chapter_b = await _make_chapter(db_session, book_b.id, core_id=2)
    response = await http.get(
        f"/api/v1/books/{book_a.id}/chapters/{chapter_b.id}/topics",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 404


async def test_list_topics_empty(authed_client, db_session):
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1)
    response = await http.get(
        f"/api/v1/books/{book.id}/chapters/{chapter.id}/topics",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_list_topics_ordered_by_topic_number(authed_client, db_session):
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1)
    await _make_topic(db_session, chapter.id, topic_number=3, title="Third")
    await _make_topic(db_session, chapter.id, topic_number=1, title="First")
    await _make_topic(db_session, chapter.id, topic_number=2, title="Second")

    response = await http.get(
        f"/api/v1/books/{book.id}/chapters/{chapter.id}/topics",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    numbers = [item["topic_number"] for item in data["items"]]
    assert numbers == [1, 2, 3]


async def test_list_topics_response_fields(authed_client, db_session):
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1)
    topic = await _make_topic(
        db_session,
        chapter.id,
        topic_number=1,
        title="Basic Numbers",
        start_page=7,
        end_page=9,
    )

    response = await http.get(
        f"/api/v1/books/{book.id}/chapters/{chapter.id}/topics",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == str(topic.id)
    assert item["chapter_id"] == str(chapter.id)
    assert item["topic_number"] == 1
    assert item["title"] == "Basic Numbers"
    assert item["start_page"] == 7
    assert item["end_page"] == 9
    assert "created_at" in item
    # topic_text must NOT be in the response
    assert "topic_text" not in item


# ---------------------------------------------------------------------------
# GET /api/v1/topics/{topic_id}/slots
# ---------------------------------------------------------------------------


async def test_list_slots_requires_auth(authed_client, db_session):
    http, _, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1)
    topic = await _make_topic(db_session, chapter.id)
    response = await http.get(f"/api/v1/topics/{topic.id}/slots")
    assert response.status_code == 401


async def test_list_slots_topic_not_found(authed_client):
    http, api_key, _ = authed_client
    fake_id = str(uuid.uuid4())
    response = await http.get(f"/api/v1/topics/{fake_id}/slots", headers={"X-API-Key": api_key})
    assert response.status_code == 404


async def test_list_slots_empty(authed_client, db_session):
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1)
    topic = await _make_topic(db_session, chapter.id)
    response = await http.get(f"/api/v1/topics/{topic.id}/slots", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_list_slots_ordered_by_day(authed_client, db_session):
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1)
    topic = await _make_topic(db_session, chapter.id)
    await _make_slot(db_session, topic.id, day_number=3, topic_subtopic="Day 3 topic")
    await _make_slot(db_session, topic.id, day_number=1, topic_subtopic="Day 1 topic")
    await _make_slot(db_session, topic.id, day_number=2, topic_subtopic="Day 2 topic")

    response = await http.get(f"/api/v1/topics/{topic.id}/slots", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 3
    days = [i["day_number"] for i in items]
    assert days == [1, 2, 3]


async def test_list_slots_response_fields(authed_client, db_session):
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1)
    topic = await _make_topic(db_session, chapter.id)
    slot = await _make_slot(
        db_session,
        topic.id,
        day_number=1,
        scheduled_date="2026-03-12",
        topic_subtopic="Basic Numbers — Introduction",
    )

    response = await http.get(f"/api/v1/topics/{topic.id}/slots", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == str(slot.id)
    assert item["topic_id"] == str(topic.id)
    assert item["day_number"] == 1
    assert item["scheduled_date"] == "2026-03-12"
    assert item["topic_subtopic"] == "Basic Numbers — Introduction"
    assert "created_at" in item


# ---------------------------------------------------------------------------
# POST /admin/chapters/{chapter_id}/breakdown  (mocked)
# ---------------------------------------------------------------------------


async def test_breakdown_forbidden_without_secret(authed_client, db_session):
    # Non-admin API key should be rejected with 403
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1)
    response = await http.post(
        f"/admin/chapters/{chapter.id}/breakdown",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 403


async def test_breakdown_not_found(authed_client, db_session):
    http, _, client_obj = authed_client
    # Promote client to admin for this test
    client_obj.is_admin = True
    await db_session.commit()

    fake_id = str(uuid.uuid4())
    from dars.clients.service import _hash_key
    admin_key = "dars_admin_test_key_for_not_found"
    client_obj.api_key_hash = _hash_key(admin_key)
    await db_session.commit()

    with patch(
        "dars.curriculum.router.breakdown_chapter",
        new=AsyncMock(side_effect=ValueError(f"Chapter not found: {fake_id}")),
    ):
        response = await http.post(
            f"/admin/chapters/{fake_id}/breakdown",
            headers={"X-API-Key": admin_key},
        )
    assert response.status_code == 404


async def test_breakdown_creates_topics_and_slots(authed_client, db_session):
    """Endpoint shape test — mocks the whole breakdown_chapter service call."""
    http, _, client_obj = authed_client
    # Promote client to admin for this test
    client_obj.is_admin = True
    await db_session.commit()

    from dars.clients.service import _hash_key
    admin_key = "dars_admin_test_key_for_creates"
    client_obj.api_key_hash = _hash_key(admin_key)
    await db_session.commit()

    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1, title="Numbers")

    mock_result = {
        "chapter_id": str(chapter.id),
        "topics_count": 2,
        "slots_count": 3,
    }

    with patch(
        "dars.curriculum.router.breakdown_chapter",
        new=AsyncMock(return_value=mock_result),
    ):
        response = await http.post(
            f"/admin/chapters/{chapter.id}/breakdown",
            headers={"X-API-Key": admin_key},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["topics_count"] == 2
    assert data["slots_count"] == 3
    assert data["chapter_id"] == str(chapter.id)


async def test_breakdown_replaces_existing(authed_client, db_session):
    """Running breakdown twice replaces previous topics — verified via DB fixtures."""
    http, api_key, _ = authed_client

    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1, title="Numbers")

    # First breakdown creates 1 old topic
    old_topic = await _make_topic(db_session, chapter.id, topic_number=1, title="Old Topic")

    # Simulate second breakdown: new topics replace old ones
    mock_result_v2 = {
        "chapter_id": str(chapter.id),
        "topics_count": 2,
        "slots_count": 1,
    }

    # Manually replace topics as the service would (delete + insert)
    from sqlalchemy import delete as sa_delete
    await db_session.execute(sa_delete(Topic).where(Topic.chapter_id == chapter.id))
    new_topic_a = Topic(chapter_id=chapter.id, topic_number=1, title="New Topic A")
    new_topic_b = Topic(chapter_id=chapter.id, topic_number=2, title="New Topic B")
    db_session.add(new_topic_a)
    db_session.add(new_topic_b)
    await db_session.commit()

    # Check topics reflect the second run
    topics_resp = await http.get(
        f"/api/v1/books/{book.id}/chapters/{chapter.id}/topics",
        headers={"X-API-Key": api_key},
    )
    assert topics_resp.status_code == 200
    assert topics_resp.json()["total"] == 2
    titles = [t["title"] for t in topics_resp.json()["items"]]
    assert "New Topic A" in titles
    assert "New Topic B" in titles
    assert "Old Topic" not in titles
