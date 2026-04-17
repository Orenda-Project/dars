"""Tests for Phase 5 — LP generation from stubs."""
import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.books.models import Book, BookChapter
from dars.clients.models import Client
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
from dars.teachers.models import Teacher

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
async def http_client(db_session):
    client_obj, raw_key = await create_client(db_session, name="Test Client")
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.headers["X-API-Key"] = raw_key
        yield c, client_obj
    app.dependency_overrides.clear()


async def _seed_world(db: AsyncSession, client_id=None, is_default=True):
    """Seed book, chapter, topic, provider, curriculum, curriculum_topic, stub, and teacher."""
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
        is_default=is_default,
        client_id=client_id,
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
        status="pending",
    )
    db.add(stub)
    await db.commit()

    return curriculum, ct, stub, topic


# ---------------------------------------------------------------------------
# GET /api/v1/curriculums/{id}/stubs/{stub_id}
# ---------------------------------------------------------------------------

async def test_get_stub_returns_correct_fields(http_client, db_session):
    c, client_obj = http_client
    curriculum, ct, stub, _ = await _seed_world(db_session, is_default=True)

    resp = await c.get(f"/api/v1/curriculums/{curriculum.id}/stubs/{stub.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(stub.id)
    assert data["curriculum_topic_id"] == str(ct.id)
    assert data["skill_type"] == "reading"
    assert data["cpa_phase"] == "concrete"
    assert data["blooms_level"] == "remember"
    assert data["status"] == "pending"
    assert data["lesson_plan_id"] is None
    assert data["sequence"] == 1


async def test_get_stub_not_found(http_client, db_session):
    c, _ = http_client
    curriculum, _, _, _ = await _seed_world(db_session, is_default=True)

    resp = await c.get(f"/api/v1/curriculums/{curriculum.id}/stubs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_stub_wrong_curriculum(http_client, db_session):
    c, _ = http_client
    _, _, stub, _ = await _seed_world(db_session, is_default=True)

    resp = await c.get(f"/api/v1/curriculums/{uuid.uuid4()}/stubs/{stub.id}")
    assert resp.status_code == 404


async def test_get_stub_requires_auth(db_session):
    book = Book(id=2, title="Urdu Grade 1", grade=1, subject="Urdu", board="ICT")
    db_session.add(book)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(f"/api/v1/curriculums/{uuid.uuid4()}/stubs/{uuid.uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/curriculums/{id}/stubs/{stub_id}/generate
# ---------------------------------------------------------------------------

async def test_generate_stub_sets_status_generating(http_client, db_session):
    c, client_obj = http_client
    curriculum, ct, stub, _ = await _seed_world(db_session, is_default=True)

    # Mock the background task so LP Assistant is not actually called
    with patch("dars.curriculum.router._generate_stub_background", new=AsyncMock()) as mock_bg:
        resp = await c.post(
            f"/api/v1/curriculums/{curriculum.id}/stubs/{stub.id}/generate"
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["stub_id"] == str(stub.id)
    assert data["status"] == "generating"

    # DB should have been updated to "generating"
    await db_session.refresh(stub)
    assert stub.status == "generating"


async def test_generate_stub_not_found(http_client, db_session):
    c, _ = http_client
    curriculum, _, _, _ = await _seed_world(db_session, is_default=True)

    resp = await c.post(
        f"/api/v1/curriculums/{curriculum.id}/stubs/{uuid.uuid4()}/generate"
    )
    assert resp.status_code == 404


async def test_generate_stub_wrong_curriculum(http_client, db_session):
    c, _ = http_client
    _, _, stub, _ = await _seed_world(db_session, is_default=True)

    resp = await c.post(
        f"/api/v1/curriculums/{uuid.uuid4()}/stubs/{stub.id}/generate"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/curriculums/{id}/generate-all
# ---------------------------------------------------------------------------

async def test_generate_all_queues_pending_stubs(http_client, db_session):
    c, client_obj = http_client
    curriculum, ct, stub, _ = await _seed_world(db_session, is_default=True)

    # Add a second stub in same curriculum_topic
    stub2 = CurriculumLpStub(
        id=uuid.uuid4(),
        curriculum_topic_id=ct.id,
        skill_type="writing",
        sequence=2,
        status="pending",
    )
    db_session.add(stub2)
    await db_session.commit()

    with patch("dars.curriculum.router._generate_stub_background", new=AsyncMock()):
        resp = await c.post(f"/api/v1/curriculums/{curriculum.id}/generate-all")

    assert resp.status_code == 200
    data = resp.json()
    assert data["queued"] == 2

    await db_session.refresh(stub)
    await db_session.refresh(stub2)
    assert stub.status == "generating"
    assert stub2.status == "generating"


async def test_generate_all_skips_non_pending(http_client, db_session):
    c, client_obj = http_client
    curriculum, ct, stub, _ = await _seed_world(db_session, is_default=True)

    # Already generated stub — should not be re-queued
    stub.status = "generated"
    await db_session.commit()

    # Add a new pending stub
    stub_pending = CurriculumLpStub(
        id=uuid.uuid4(),
        curriculum_topic_id=ct.id,
        skill_type="writing",
        sequence=2,
        status="pending",
    )
    db_session.add(stub_pending)
    await db_session.commit()

    with patch("dars.curriculum.router._generate_stub_background", new=AsyncMock()):
        resp = await c.post(f"/api/v1/curriculums/{curriculum.id}/generate-all")

    assert resp.status_code == 200
    assert resp.json()["queued"] == 1

    await db_session.refresh(stub)
    assert stub.status == "generated"  # unchanged


async def test_generate_all_empty_returns_zero(http_client, db_session):
    c, _ = http_client
    curriculum, ct, stub, _ = await _seed_world(db_session, is_default=True)

    # Mark the only stub as already done
    stub.status = "generated"
    await db_session.commit()

    with patch("dars.curriculum.router._generate_stub_background", new=AsyncMock()):
        resp = await c.post(f"/api/v1/curriculums/{curriculum.id}/generate-all")

    assert resp.status_code == 200
    assert resp.json()["queued"] == 0


async def test_generate_all_wrong_curriculum(http_client, db_session):
    c, _ = http_client
    resp = await c.post(f"/api/v1/curriculums/{uuid.uuid4()}/generate-all")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Background task unit test
# ---------------------------------------------------------------------------

async def test_generate_stub_background_success(db_session):
    """Test the background task flow with a mocked LP Assistant call."""
    from dars.curriculum.router import _generate_stub_background

    # Seed world
    client_obj, raw_key = await create_client(db_session, name="BG Client")

    teacher = Teacher(
        id=uuid.uuid4(),
        client_id=client_obj.id,
        name="Default Teacher",
        email="teacher@example.com",
    )
    db_session.add(teacher)
    client_obj.default_teacher_id = teacher.id
    await db_session.commit()

    book = Book(id=99, title="Science G4", grade=4, subject="Science", board="Punjab")
    db_session.add(book)
    chapter = BookChapter(id=99, book_id=99, title="Ch1", chapter_number=1)
    db_session.add(chapter)
    await db_session.commit()

    topic = Topic(id=uuid.uuid4(), chapter_id=99, title="Plants", sequence=1)
    db_session.add(topic)
    await db_session.commit()

    provider = SloProvider(id=uuid.uuid4(), slug="bg-prov", name="BGProv", issuing_body="Gov")
    db_session.add(provider)
    await db_session.commit()

    curriculum = Curriculum(
        id=uuid.uuid4(), name="G4 Sci", book_id=99, provider_id=provider.id,
        is_default=True, is_active=True,
    )
    db_session.add(curriculum)
    await db_session.commit()

    ct = CurriculumTopic(
        id=uuid.uuid4(), curriculum_id=curriculum.id, topic_id=topic.id, sequence=1,
    )
    db_session.add(ct)
    await db_session.commit()

    stub = CurriculumLpStub(
        id=uuid.uuid4(), curriculum_topic_id=ct.id,
        skill_type="reading", cpa_phase="concrete", blooms_level="remember",
        sequence=1, status="generating",
    )
    db_session.add(stub)
    await db_session.commit()

    mock_lp_response = {
        "lesson_plan": "<html>LP content</html>",
        "lesson_plan_bilingual": None,
        "tags": {"topic": "Plants"},
        "metadata": {},
    }

    # Patch AsyncSessionLocal to yield the test db_session
    class _FakeSessionCM:
        async def __aenter__(self):
            return db_session
        async def __aexit__(self, *args):
            pass  # don't close the shared session

    with (
        patch("dars.lesson_plans.service._call_lp_assistant", new=AsyncMock(return_value=mock_lp_response)),
        patch("dars.database.AsyncSessionLocal", side_effect=lambda: _FakeSessionCM()),
    ):
        await _generate_stub_background(stub_id=stub.id, client_id=client_obj.id)

    await db_session.refresh(stub)
    assert stub.status == "generated"
    assert stub.lesson_plan_id is not None


async def test_generate_stub_background_failure(db_session):
    """When LP Assistant raises, stub status becomes 'failed'."""
    from dars.curriculum.router import _generate_stub_background

    client_obj, _ = await create_client(db_session, name="Fail Client")

    teacher = Teacher(
        id=uuid.uuid4(), client_id=client_obj.id,
        name="T", email="t@t.com",
    )
    db_session.add(teacher)
    client_obj.default_teacher_id = teacher.id
    await db_session.commit()

    book = Book(id=98, title="Maths G2", grade=2, subject="Maths", board="ICT")
    db_session.add(book)
    chapter = BookChapter(id=98, book_id=98, title="Ch1", chapter_number=1)
    db_session.add(chapter)
    await db_session.commit()

    topic = Topic(id=uuid.uuid4(), chapter_id=98, title="Numbers", sequence=1)
    db_session.add(topic)
    await db_session.commit()

    provider = SloProvider(id=uuid.uuid4(), slug="fp", name="FP", issuing_body="Gov")
    db_session.add(provider)
    await db_session.commit()

    curriculum = Curriculum(
        id=uuid.uuid4(), name="G2 Maths", book_id=98, provider_id=provider.id,
        is_default=True, is_active=True,
    )
    db_session.add(curriculum)
    await db_session.commit()

    ct = CurriculumTopic(id=uuid.uuid4(), curriculum_id=curriculum.id, topic_id=topic.id, sequence=1)
    db_session.add(ct)
    await db_session.commit()

    stub = CurriculumLpStub(
        id=uuid.uuid4(), curriculum_topic_id=ct.id,
        sequence=1, status="generating",
    )
    db_session.add(stub)
    await db_session.commit()

    class _FakeSessionCM:
        async def __aenter__(self):
            return db_session
        async def __aexit__(self, *args):
            pass

    with (
        patch(
            "dars.lesson_plans.service._call_lp_assistant",
            new=AsyncMock(side_effect=RuntimeError("LP Assistant down")),
        ),
        patch("dars.database.AsyncSessionLocal", side_effect=lambda: _FakeSessionCM()),
    ):
        await _generate_stub_background(stub_id=stub.id, client_id=client_obj.id)

    await db_session.refresh(stub)
    assert stub.status == "failed"
    assert stub.lesson_plan_id is None
