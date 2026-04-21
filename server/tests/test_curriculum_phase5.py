"""Tests for stub status endpoint (master-curriculum-only model)."""
import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.books.models import Book, BookChapter
from dars.clients.service import create_client
from dars.curriculum.models import (
    Curriculum,
    CurriculumLpStub,
    CurriculumTopic,
    SloProvider,
    Topic,
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


async def _seed_world(db: AsyncSession):
    """Seed book, chapter, topic, provider, curriculum, curriculum_topic, stub."""
    book = Book(id=1, title="English Grade 3", grade=3, subject="English", board="ICT")
    db.add(book)
    chapter = BookChapter(id=10, book_id=1, title="Chapter 1", chapter_number=1)
    db.add(chapter)
    await db.commit()

    topic = Topic(id=uuid.uuid4(), chapter_id=10, title="My Pets", sequence=1)
    db.add(topic)
    await db.commit()

    provider = SloProvider(id=uuid.uuid4(), slug="ncp", name="NCP", issuing_body="Gov")
    db.add(provider)
    await db.commit()

    curriculum = Curriculum(
        id=uuid.uuid4(),
        name="G3 English",
        book_id=1,
        provider_id=provider.id,
        is_active=True,
    )
    db.add(curriculum)
    await db.commit()

    ct = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        topic_id=topic.id,
        sequence=1,
        planned_date=date(2025, 9, 1),
    )
    db.add(ct)
    await db.commit()

    stub = CurriculumLpStub(
        id=uuid.uuid4(),
        curriculum_topic_id=ct.id,
        skill_type="reading",
        cpa_phase="concrete",
        blooms_level="remember",
        sequence=1,
        planned_date=date(2025, 9, 1),
        lesson_plan_id=None,
    )
    db.add(stub)
    await db.commit()

    return curriculum, ct, stub, topic


# ---------------------------------------------------------------------------
# GET /api/v1/curriculums/{id}/stubs/{stub_id}
# ---------------------------------------------------------------------------

async def test_get_stub_returns_correct_fields(http_client, db_session):
    c, _ = http_client
    curriculum, ct, stub, _ = await _seed_world(db_session)

    resp = await c.get(f"/api/v1/curriculums/{curriculum.id}/stubs/{stub.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(stub.id)
    assert data["curriculum_topic_id"] == str(ct.id)
    assert data["skill_type"] == "reading"
    assert data["cpa_phase"] == "concrete"
    assert data["blooms_level"] == "remember"
    assert data["lesson_plan_id"] is None
    assert data["sequence"] == 1


async def test_get_stub_not_found(http_client, db_session):
    c, _ = http_client
    curriculum, _, _, _ = await _seed_world(db_session)

    resp = await c.get(f"/api/v1/curriculums/{curriculum.id}/stubs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_stub_wrong_curriculum(http_client, db_session):
    c, _ = http_client
    _, _, stub, _ = await _seed_world(db_session)

    resp = await c.get(f"/api/v1/curriculums/{uuid.uuid4()}/stubs/{stub.id}")
    assert resp.status_code == 404


async def test_get_stub_requires_auth(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(f"/api/v1/curriculums/{uuid.uuid4()}/stubs/{uuid.uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Removed endpoints return 404/405
# ---------------------------------------------------------------------------

async def test_generate_stub_endpoint_removed(http_client, db_session):
    """POST .../stubs/{id}/generate no longer exists."""
    c, _ = http_client
    curriculum, _, stub, _ = await _seed_world(db_session)
    resp = await c.post(f"/api/v1/curriculums/{curriculum.id}/stubs/{stub.id}/generate")
    assert resp.status_code == 404


async def test_generate_all_endpoint_removed(http_client, db_session):
    """POST .../generate-all no longer exists."""
    c, _ = http_client
    curriculum, _, _, _ = await _seed_world(db_session)
    resp = await c.post(f"/api/v1/curriculums/{curriculum.id}/generate-all")
    assert resp.status_code == 404
