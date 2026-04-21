"""Tests for curriculum read/admin API endpoints (master-curriculum-only model)."""
import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.books.models import Book, BookChapter
from dars.clients.models import Client
from dars.clients.service import create_client
from dars.curriculum.models import (
    Curriculum,
    CurriculumLpStub,
    CurriculumTopic,
    SloProvider,
    Slo,
    SubSlo,
    Topic,
    TopicSubSlo,
)
from dars.database import Base, get_db
from dars.main import app

TEST_DB = "sqlite+aiosqlite:///:memory:"


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
async def http_client(db_session):
    client_obj, raw_key = await create_client(db_session, name="Test Client")
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.headers["X-API-Key"] = raw_key
        yield c, client_obj
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def admin_http_client(db_session):
    client_obj, raw_key = await create_client(db_session, name="Admin Client")
    client_obj.is_admin = True
    await db_session.commit()
    await db_session.refresh(client_obj)
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.headers["X-API-Key"] = raw_key
        yield c, client_obj
    app.dependency_overrides.clear()


async def _seed_book(db: AsyncSession) -> Book:
    book = Book(id=1, title="English Grade 1", grade=1, subject="English", board="ICT")
    db.add(book)
    chapter = BookChapter(id=10, book_id=1, title="My Family", chapter_number=1)
    db.add(chapter)
    await db.commit()
    await db.refresh(book)
    return book


async def _seed_provider(db: AsyncSession) -> SloProvider:
    provider = SloProvider(
        id=uuid.uuid4(),
        slug="ncp",
        name="NCP",
        issuing_body="Government",
    )
    db.add(provider)
    await db.commit()
    return provider


async def _seed_curriculum(db: AsyncSession, book: Book, provider: SloProvider) -> Curriculum:
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name="Test Curriculum",
        book_id=book.id,
        provider_id=provider.id,
        is_active=True,
    )
    db.add(curriculum)
    await db.commit()
    return curriculum


# ---------------------------------------------------------------------------
# GET /api/v1/books
# ---------------------------------------------------------------------------

async def test_list_books_empty(http_client):
    c, _ = http_client
    resp = await c.get("/api/v1/books")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_books_returns_book(http_client, db_session):
    c, _ = http_client
    await _seed_book(db_session)
    resp = await c.get("/api/v1/books")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "English Grade 1"
    assert data[0]["board"] == "ICT"
    assert "chapters" not in data[0]


async def test_list_books_filter_by_grade(http_client, db_session):
    c, _ = http_client
    await _seed_book(db_session)
    resp = await c.get("/api/v1/books?grade=2")
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await c.get("/api/v1/books?grade=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_list_books_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/books")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/books/{id}
# ---------------------------------------------------------------------------

async def test_get_book_detail_not_found(http_client):
    c, _ = http_client
    resp = await c.get("/api/v1/books/9999")
    assert resp.status_code == 404


async def test_get_book_detail_returns_chapters(http_client, db_session):
    c, _ = http_client
    await _seed_book(db_session)
    resp = await c.get("/api/v1/books/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 1
    assert data["title"] == "English Grade 1"
    assert len(data["chapters"]) == 1
    assert data["chapters"][0]["title"] == "My Family"
    assert data["chapters"][0]["topics"] == []


async def test_get_book_detail_with_topics_and_sub_slos(http_client, db_session):
    c, _ = http_client
    await _seed_book(db_session)
    provider = await _seed_provider(db_session)

    slo = Slo(
        id=uuid.uuid4(), provider_id=provider.id, book_id=1,
        code="E1-01", statement="Base SLO",
    )
    db_session.add(slo)
    await db_session.commit()

    sub_slo = SubSlo(id=uuid.uuid4(), slo_id=slo.id, code="E1-01.1", statement="Sub SLO 1")
    db_session.add(sub_slo)

    topic = Topic(id=uuid.uuid4(), chapter_id=10, title="Family Members", sequence=1)
    db_session.add(topic)
    await db_session.commit()

    tslo = TopicSubSlo(topic_id=topic.id, sub_slo_id=sub_slo.id)
    db_session.add(tslo)
    await db_session.commit()

    resp = await c.get("/api/v1/books/1")
    assert resp.status_code == 200
    data = resp.json()
    chapter = data["chapters"][0]
    assert len(chapter["topics"]) == 1
    t = chapter["topics"][0]
    assert t["title"] == "Family Members"
    assert len(t["sub_slos"]) == 1
    assert t["sub_slos"][0]["code"] == "E1-01.1"
    assert t["sub_slos"][0]["slo_code"] == "E1-01"


# ---------------------------------------------------------------------------
# GET /api/v1/curriculums
# ---------------------------------------------------------------------------

async def test_list_curriculums_empty(http_client):
    c, _ = http_client
    resp = await c.get("/api/v1/curriculums")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_curriculums_returns_all_active(http_client, db_session):
    c, _ = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    await _seed_curriculum(db_session, book, provider)

    resp = await c.get("/api/v1/curriculums")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["book_title"] == "English Grade 1"
    assert data[0]["provider_name"] == "NCP"
    # no is_default or teacher_id in response
    assert "is_default" not in data[0]
    assert "teacher_id" not in data[0]


async def test_list_curriculums_hides_inactive(http_client, db_session):
    c, _ = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider)
    curriculum.is_active = False
    await db_session.commit()

    resp = await c.get("/api/v1/curriculums")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/v1/curriculums/{id}
# ---------------------------------------------------------------------------

async def test_get_curriculum_detail_not_found(http_client):
    c, _ = http_client
    resp = await c.get(f"/api/v1/curriculums/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_curriculum_detail_invalid_uuid(http_client):
    c, _ = http_client
    resp = await c.get("/api/v1/curriculums/not-a-uuid")
    assert resp.status_code == 404


async def test_get_curriculum_detail_returns_topics(http_client, db_session):
    c, _ = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider)

    topic = Topic(id=uuid.uuid4(), chapter_id=10, title="Topic 1", sequence=1)
    db_session.add(topic)
    await db_session.commit()

    ct = CurriculumTopic(
        id=uuid.uuid4(), curriculum_id=curriculum.id, topic_id=topic.id,
        sequence=1,
    )
    db_session.add(ct)
    await db_session.commit()

    stub = CurriculumLpStub(
        id=uuid.uuid4(), curriculum_topic_id=ct.id, sequence=1,
        skill_type="reading",
    )
    db_session.add(stub)
    await db_session.commit()

    resp = await c.get(f"/api/v1/curriculums/{curriculum.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Curriculum"
    assert data["book_title"] == "English Grade 1"
    assert len(data["topics"]) == 1
    t = data["topics"][0]
    assert t["topic_title"] == "Topic 1"
    assert len(t["lp_stubs"]) == 1
    assert t["lp_stubs"][0]["skill_type"] == "reading"
    # no completed_date in topics
    assert "completed_date" not in t


# ---------------------------------------------------------------------------
# Phase 2 — Admin CRUD
# ---------------------------------------------------------------------------

# POST /api/admin/curriculums

async def test_create_curriculum_success(admin_http_client, db_session):
    c, _ = admin_http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)

    resp = await c.post("/api/admin/curriculums", json={
        "name": "Grade 1 English NCP",
        "book_id": book.id,
        "provider_id": str(provider.id),
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Grade 1 English NCP"
    assert data["book_title"] == "English Grade 1"
    assert data["provider_name"] == "NCP"
    assert "is_default" not in data
    assert "teacher_id" not in data


async def test_create_curriculum_invalid_book(admin_http_client, db_session):
    c, _ = admin_http_client
    provider = await _seed_provider(db_session)
    resp = await c.post("/api/admin/curriculums", json={
        "name": "Test",
        "book_id": 9999,
        "provider_id": str(provider.id),
    })
    assert resp.status_code == 422


async def test_create_curriculum_invalid_provider(admin_http_client, db_session):
    c, _ = admin_http_client
    await _seed_book(db_session)
    resp = await c.post("/api/admin/curriculums", json={
        "name": "Test",
        "book_id": 1,
        "provider_id": str(uuid.uuid4()),
    })
    assert resp.status_code == 422


async def test_create_curriculum_requires_admin(http_client, db_session):
    c, _ = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    resp = await c.post("/api/admin/curriculums", json={
        "name": "Should fail",
        "book_id": book.id,
        "provider_id": str(provider.id),
    })
    assert resp.status_code == 403


# POST /api/admin/curriculums/{id}/topics

async def test_set_curriculum_topics_success(admin_http_client, db_session):
    c, _ = admin_http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider)

    topic1 = Topic(id=uuid.uuid4(), chapter_id=10, title="T1", sequence=1)
    topic2 = Topic(id=uuid.uuid4(), chapter_id=10, title="T2", sequence=2)
    db_session.add_all([topic1, topic2])
    await db_session.commit()

    resp = await c.post(f"/api/admin/curriculums/{curriculum.id}/topics", json={
        "topics": [
            {"topic_id": str(topic1.id), "planned_date": "2025-09-01"},
            {"topic_id": str(topic2.id), "planned_date": "2025-09-02"},
        ]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["topics"]) == 2
    assert data["topics"][0]["topic_title"] == "T1"
    assert data["topics"][0]["sequence"] == 1
    assert data["topics"][1]["topic_title"] == "T2"
    assert data["topics"][1]["sequence"] == 2
    assert data["topics"][0]["planned_date"] == "2025-09-01"


async def test_set_curriculum_topics_replaces_existing(admin_http_client, db_session):
    c, _ = admin_http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider)

    topic1 = Topic(id=uuid.uuid4(), chapter_id=10, title="T1", sequence=1)
    topic2 = Topic(id=uuid.uuid4(), chapter_id=10, title="T2", sequence=2)
    db_session.add_all([topic1, topic2])
    await db_session.commit()

    await c.post(f"/api/admin/curriculums/{curriculum.id}/topics", json={
        "topics": [
            {"topic_id": str(topic1.id)},
            {"topic_id": str(topic2.id)},
        ]
    })

    resp = await c.post(f"/api/admin/curriculums/{curriculum.id}/topics", json={
        "topics": [{"topic_id": str(topic2.id)}]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["topics"]) == 1
    assert data["topics"][0]["topic_title"] == "T2"


async def test_set_curriculum_topics_invalid_topic_id(admin_http_client, db_session):
    c, _ = admin_http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider)

    resp = await c.post(f"/api/admin/curriculums/{curriculum.id}/topics", json={
        "topics": [{"topic_id": str(uuid.uuid4())}]
    })
    assert resp.status_code == 422


# PATCH /api/admin/curriculums/{id}

async def test_patch_curriculum_name(admin_http_client, db_session):
    c, _ = admin_http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider)

    resp = await c.patch(f"/api/admin/curriculums/{curriculum.id}", json={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


async def test_patch_curriculum_deactivate(admin_http_client, db_session):
    c, _ = admin_http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider)

    resp = await c.patch(f"/api/admin/curriculums/{curriculum.id}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_patch_curriculum_not_found(admin_http_client):
    c, _ = admin_http_client
    resp = await c.patch(f"/api/admin/curriculums/{uuid.uuid4()}", json={"name": "X"})
    assert resp.status_code == 404


# DELETE /api/admin/curriculums/{id}/topics/{topic_id}

async def test_delete_curriculum_topic_success(admin_http_client, db_session):
    c, _ = admin_http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider)

    topic1 = Topic(id=uuid.uuid4(), chapter_id=10, title="T1", sequence=1)
    topic2 = Topic(id=uuid.uuid4(), chapter_id=10, title="T2", sequence=2)
    topic3 = Topic(id=uuid.uuid4(), chapter_id=10, title="T3", sequence=3)
    db_session.add_all([topic1, topic2, topic3])
    await db_session.commit()

    ct1 = CurriculumTopic(id=uuid.uuid4(), curriculum_id=curriculum.id, topic_id=topic1.id, sequence=1)
    ct2 = CurriculumTopic(id=uuid.uuid4(), curriculum_id=curriculum.id, topic_id=topic2.id, sequence=2)
    ct3 = CurriculumTopic(id=uuid.uuid4(), curriculum_id=curriculum.id, topic_id=topic3.id, sequence=3)
    db_session.add_all([ct1, ct2, ct3])
    await db_session.commit()

    resp = await c.delete(f"/api/admin/curriculums/{curriculum.id}/topics/{ct2.id}")
    assert resp.status_code == 204

    from sqlalchemy import select as sa_select
    from dars.curriculum.models import CurriculumTopic as CT
    remaining = (await db_session.execute(
        sa_select(CT).where(CT.curriculum_id == curriculum.id).order_by(CT.sequence)
    )).scalars().all()
    assert len(remaining) == 2
    assert remaining[0].sequence == 1
    assert remaining[1].sequence == 2


async def test_delete_curriculum_topic_not_found(admin_http_client, db_session):
    c, _ = admin_http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider)

    resp = await c.delete(f"/api/admin/curriculums/{curriculum.id}/topics/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Removed Phase 3 endpoints return 404 (routes gone)
# ---------------------------------------------------------------------------

async def test_clone_endpoint_removed(http_client, db_session):
    """POST /api/v1/curriculums/{id}/clone no longer exists."""
    c, _ = http_client
    resp = await c.post(f"/api/v1/curriculums/{uuid.uuid4()}/clone")
    assert resp.status_code == 404


async def test_progress_endpoint_removed(http_client, db_session):
    """GET /api/v1/curriculums/{id}/progress no longer exists."""
    c, _ = http_client
    resp = await c.get(f"/api/v1/curriculums/{uuid.uuid4()}/progress")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Phase 4 — POST /api/admin/curriculums/generate
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date as _date


def _make_tool_use_block(name: str, input_data: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = input_data
    return block


def _make_message_response(tool_block):
    resp = MagicMock()
    resp.content = [tool_block]
    return resp


async def _seed_book_with_topics(db: AsyncSession) -> tuple[Book, SloProvider]:
    book = Book(id=20, title="Eng Grade 3", grade=3, subject="English", board="NCP")
    db.add(book)
    ch1 = BookChapter(id=201, book_id=20, title="Chapter One", chapter_number=1)
    ch2 = BookChapter(id=202, book_id=20, title="Chapter Two", chapter_number=2)
    db.add(ch1)
    db.add(ch2)

    t1 = Topic(id=uuid.uuid4(), chapter_id=201, title="Topic A", sequence=1)
    t2 = Topic(id=uuid.uuid4(), chapter_id=201, title="Topic B", sequence=2)
    t3 = Topic(id=uuid.uuid4(), chapter_id=202, title="Topic C", sequence=1)
    t4 = Topic(id=uuid.uuid4(), chapter_id=202, title="Topic D", sequence=2)
    db.add_all([t1, t2, t3, t4])

    provider = SloProvider(
        id=uuid.uuid4(),
        slug="ncp-gen",
        name="NCP Gen",
        issuing_body="Government",
    )
    db.add(provider)
    await db.commit()
    return book, provider, [t1, t2, t3, t4]


async def test_generate_curriculum_success(admin_http_client, db_session):
    """Full happy-path: mocked LLM + mocked LP assistant → curriculum created with generated stubs."""
    c, client_obj = admin_http_client
    book, provider, topics = await _seed_book_with_topics(db_session)
    t1, t2, t3, t4 = topics

    step_a_block = _make_tool_use_block("allocate_chapter_days", {
        "allocations": [
            {"chapter_id": 201, "days": 5},
            {"chapter_id": 202, "days": 5},
        ]
    })
    step_a_resp = _make_message_response(step_a_block)

    step_b1_block = _make_tool_use_block("plan_lp_stubs", {
        "stubs": [
            {
                "topic_id": str(t1.id),
                "planned_date": "2025-09-01",
                "skill_type": "reading",
                "cpa_phase": "concrete",
                "blooms_level": "remember",
                "sequence": 1,
            },
            {
                "topic_id": str(t2.id),
                "planned_date": "2025-09-02",
                "skill_type": "writing",
                "cpa_phase": "pictorial",
                "blooms_level": "understand",
                "sequence": 2,
            },
        ]
    })
    step_b1_resp = _make_message_response(step_b1_block)

    step_b2_block = _make_tool_use_block("plan_lp_stubs", {
        "stubs": [
            {
                "topic_id": str(t3.id),
                "planned_date": "2025-09-08",
                "skill_type": "comprehension",
                "cpa_phase": "abstract",
                "blooms_level": "apply",
                "sequence": 1,
            },
            {
                "topic_id": str(t4.id),
                "planned_date": "2025-09-09",
                "skill_type": "revision",
                "cpa_phase": "abstract",
                "blooms_level": "analyze",
                "sequence": 2,
            },
        ]
    })
    step_b2_resp = _make_message_response(step_b2_block)

    mock_llm_create = AsyncMock(side_effect=[step_a_resp, step_b1_resp, step_b2_resp])
    mock_lp_result = {
        "lesson_plan": "<html>LP content</html>",
        "lesson_plan_bilingual": None,
        "tags": {},
        "metadata": {},
    }

    with patch("dars.config.settings.anthropic_api_key", "test-key"), \
         patch("anthropic.AsyncAnthropic") as MockAnthropic, \
         patch("dars.lesson_plans.service._call_lp_assistant", new_callable=AsyncMock, return_value=mock_lp_result):
        mock_instance = MagicMock()
        mock_instance.messages.create = mock_llm_create
        MockAnthropic.return_value = mock_instance

        resp = await c.post("/api/admin/curriculums/generate", json={
            "book_id": 20,
            "provider_id": str(provider.id),
            "name": "Grade 3 NCP 2025-26",
            "start_date": "2025-09-01",
            "end_date": "2025-09-30",
            "days_per_week": 5,
        })

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Grade 3 NCP 2025-26"
    assert len(data["topics"]) == 4
    # All stubs should have a lesson_plan_id since LP assistant was mocked successfully
    for topic in data["topics"]:
        for stub in topic["lp_stubs"]:
            assert stub["lesson_plan_id"] is not None

    assert mock_llm_create.call_count == 3


async def test_generate_curriculum_invalid_book(admin_http_client, db_session):
    provider = await _seed_provider(db_session)
    c, _ = admin_http_client

    with patch("dars.config.settings.anthropic_api_key", "test-key"):
        resp = await c.post("/api/admin/curriculums/generate", json={
            "book_id": 9999,
            "provider_id": str(provider.id),
            "name": "Test",
            "start_date": "2025-09-01",
            "end_date": "2025-09-30",
            "days_per_week": 5,
        })
    assert resp.status_code == 422


async def test_generate_curriculum_invalid_provider(admin_http_client, db_session):
    await _seed_book(db_session)
    c, _ = admin_http_client

    with patch("dars.config.settings.anthropic_api_key", "test-key"):
        resp = await c.post("/api/admin/curriculums/generate", json={
            "book_id": 1,
            "provider_id": str(uuid.uuid4()),
            "name": "Test",
            "start_date": "2025-09-01",
            "end_date": "2025-09-30",
            "days_per_week": 5,
        })
    assert resp.status_code == 422


async def test_generate_curriculum_no_api_key(admin_http_client, db_session):
    book, provider, _ = await _seed_book_with_topics(db_session)
    c, _ = admin_http_client

    with patch("dars.config.settings.anthropic_api_key", ""):
        resp = await c.post("/api/admin/curriculums/generate", json={
            "book_id": book.id,
            "provider_id": str(provider.id),
            "name": "Test",
            "start_date": "2025-09-01",
            "end_date": "2025-09-30",
            "days_per_week": 5,
        })
    assert resp.status_code == 500
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]


async def test_generate_curriculum_requires_admin(http_client, db_session):
    c, _ = http_client
    resp = await c.post("/api/admin/curriculums/generate", json={
        "book_id": 1,
        "provider_id": str(uuid.uuid4()),
        "name": "Test",
        "start_date": "2025-09-01",
        "end_date": "2025-09-30",
        "days_per_week": 5,
    })
    assert resp.status_code == 403
