"""Tests for Phase 1 curriculum read API endpoints."""
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
from dars.teachers.models import Teacher

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


async def _seed_curriculum(db: AsyncSession, book: Book, provider: SloProvider, client_id=None, is_default=True) -> Curriculum:
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name="Test Curriculum",
        book_id=book.id,
        provider_id=provider.id,
        is_default=is_default,
        client_id=client_id,
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
    # chapters should NOT be in list response
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


async def test_list_curriculums_shows_defaults(http_client, db_session):
    c, _ = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    await _seed_curriculum(db_session, book, provider, is_default=True)

    resp = await c.get("/api/v1/curriculums")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["is_default"] is True
    assert data[0]["book_title"] == "English Grade 1"
    assert data[0]["provider_name"] == "NCP"


async def test_list_curriculums_shows_own_client_curriculum(http_client, db_session):
    c, client_obj = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    # curriculum belonging to this client (not default)
    await _seed_curriculum(db_session, book, provider, client_id=client_obj.id, is_default=False)

    resp = await c.get("/api/v1/curriculums")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_list_curriculums_hides_other_clients_curriculum(http_client, db_session):
    c, _ = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    other_client_id = uuid.uuid4()
    # non-default curriculum belonging to a different client
    await _seed_curriculum(db_session, book, provider, client_id=other_client_id, is_default=False)

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
    curriculum = await _seed_curriculum(db_session, book, provider, is_default=True)

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
        skill_type="reading", status="pending",
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


# ---------------------------------------------------------------------------
# GET /api/v1/curriculums/{id}/progress
# ---------------------------------------------------------------------------

async def test_get_curriculum_progress_empty(http_client, db_session):
    c, _ = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider, is_default=True)

    resp = await c.get(f"/api/v1/curriculums/{curriculum.id}/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_topics"] == 0
    assert data["completed"] == 0
    assert data["behind"] == 0
    assert data["on_track"] == 0


async def test_get_curriculum_progress_counts(http_client, db_session):
    from datetime import date, timedelta
    c, _ = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider, is_default=True)

    today = date.today()
    topic1 = Topic(id=uuid.uuid4(), chapter_id=10, title="T1", sequence=1)
    topic2 = Topic(id=uuid.uuid4(), chapter_id=10, title="T2", sequence=2)
    topic3 = Topic(id=uuid.uuid4(), chapter_id=10, title="T3", sequence=3)
    db_session.add_all([topic1, topic2, topic3])
    await db_session.commit()

    # completed topic
    ct1 = CurriculumTopic(
        id=uuid.uuid4(), curriculum_id=curriculum.id, topic_id=topic1.id, sequence=1,
        planned_date=today - timedelta(days=5), completed_date=today - timedelta(days=1),
    )
    # behind: planned in past, not done
    ct2 = CurriculumTopic(
        id=uuid.uuid4(), curriculum_id=curriculum.id, topic_id=topic2.id, sequence=2,
        planned_date=today - timedelta(days=2), completed_date=None,
    )
    # on track: planned in future, not done
    ct3 = CurriculumTopic(
        id=uuid.uuid4(), curriculum_id=curriculum.id, topic_id=topic3.id, sequence=3,
        planned_date=today + timedelta(days=3), completed_date=None,
    )
    db_session.add_all([ct1, ct2, ct3])
    await db_session.commit()

    resp = await c.get(f"/api/v1/curriculums/{curriculum.id}/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_topics"] == 3
    assert data["completed"] == 1
    assert data["behind"] == 1
    assert data["on_track"] == 1


async def test_get_curriculum_progress_not_found(http_client):
    c, _ = http_client
    resp = await c.get(f"/api/v1/curriculums/{uuid.uuid4()}/progress")
    assert resp.status_code == 404


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
        "is_default": True,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Grade 1 English NCP"
    assert data["book_title"] == "English Grade 1"
    assert data["provider_name"] == "NCP"
    assert data["is_default"] is True
    assert data["teacher_id"] is None


async def test_create_curriculum_invalid_book(admin_http_client, db_session):
    c, _ = admin_http_client
    provider = await _seed_provider(db_session)
    resp = await c.post("/api/admin/curriculums", json={
        "name": "Test",
        "book_id": 9999,
        "provider_id": str(provider.id),
        "is_default": False,
    })
    assert resp.status_code == 422


async def test_create_curriculum_invalid_provider(admin_http_client, db_session):
    c, _ = admin_http_client
    await _seed_book(db_session)
    resp = await c.post("/api/admin/curriculums", json={
        "name": "Test",
        "book_id": 1,
        "provider_id": str(uuid.uuid4()),
        "is_default": False,
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
        "is_default": False,
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

    # Set initial topics
    await c.post(f"/api/admin/curriculums/{curriculum.id}/topics", json={
        "topics": [
            {"topic_id": str(topic1.id)},
            {"topic_id": str(topic2.id)},
        ]
    })

    # Replace with just topic2
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

    # Delete middle topic
    resp = await c.delete(f"/api/admin/curriculums/{curriculum.id}/topics/{ct2.id}")
    assert resp.status_code == 204

    # Verify re-sequencing: remaining should be seq 1 and 2
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
# Phase 3 — Teacher clone + progress tracking
# ---------------------------------------------------------------------------

async def _seed_teacher(db: AsyncSession, client_id: uuid.UUID) -> Teacher:
    teacher = Teacher(
        id=uuid.uuid4(),
        client_id=client_id,
        name="Test Teacher",
    )
    db.add(teacher)
    await db.commit()
    return teacher


async def _seed_topic(db: AsyncSession, chapter_id: int = 10, sequence: int = 1) -> Topic:
    topic = Topic(id=uuid.uuid4(), chapter_id=chapter_id, title=f"Topic {sequence}", sequence=sequence)
    db.add(topic)
    await db.commit()
    return topic


async def _seed_curriculum_topic(
    db: AsyncSession,
    curriculum: Curriculum,
    topic: Topic,
    sequence: int = 1,
    planned_date=None,
) -> CurriculumTopic:
    ct = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        topic_id=topic.id,
        sequence=sequence,
        planned_date=planned_date,
    )
    db.add(ct)
    await db.commit()
    return ct


# POST /api/v1/curriculums/{id}/clone

async def test_clone_curriculum_requires_teacher_header(http_client, db_session):
    c, client_obj = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider, is_default=True)

    resp = await c.post(f"/api/v1/curriculums/{curriculum.id}/clone")
    assert resp.status_code == 422


async def test_clone_default_curriculum(http_client, db_session):
    c, client_obj = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider, is_default=True)
    teacher = await _seed_teacher(db_session, client_obj.id)
    topic = await _seed_topic(db_session)
    ct = await _seed_curriculum_topic(db_session, curriculum, topic, sequence=1)

    resp = await c.post(
        f"/api/v1/curriculums/{curriculum.id}/clone",
        headers={"X-Teacher-ID": str(teacher.id)},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_default"] is False
    assert data["teacher_id"] == str(teacher.id)
    assert len(data["topics"]) == 1
    assert data["topics"][0]["topic_id"] == str(topic.id)


async def test_clone_copies_stubs(http_client, db_session):
    c, client_obj = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider, is_default=True)
    teacher = await _seed_teacher(db_session, client_obj.id)
    topic = await _seed_topic(db_session)
    ct = await _seed_curriculum_topic(db_session, curriculum, topic, sequence=1)

    stub = CurriculumLpStub(
        id=uuid.uuid4(),
        curriculum_topic_id=ct.id,
        sequence=1,
        status="pending",
        skill_type="reading",
    )
    db_session.add(stub)
    await db_session.commit()

    resp = await c.post(
        f"/api/v1/curriculums/{curriculum.id}/clone",
        headers={"X-Teacher-ID": str(teacher.id)},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["topics"][0]["lp_stubs"]) == 1
    assert data["topics"][0]["lp_stubs"][0]["status"] == "pending"
    # cloned stub should have a different id
    assert data["topics"][0]["lp_stubs"][0]["id"] != str(stub.id)


async def test_clone_rejects_other_client_curriculum(http_client, db_session):
    c, client_obj = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    # Curriculum owned by a different client (not default)
    other_curriculum = await _seed_curriculum(
        db_session, book, provider, client_id=uuid.uuid4(), is_default=False
    )
    teacher = await _seed_teacher(db_session, client_obj.id)

    resp = await c.post(
        f"/api/v1/curriculums/{other_curriculum.id}/clone",
        headers={"X-Teacher-ID": str(teacher.id)},
    )
    assert resp.status_code == 404


# PATCH /api/v1/curriculums/{id}/topics/{ct_id}

async def test_patch_topic_planned_date(http_client, db_session):
    c, client_obj = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider, client_id=client_obj.id, is_default=False)
    topic = await _seed_topic(db_session)
    ct = await _seed_curriculum_topic(db_session, curriculum, topic, sequence=1)

    resp = await c.patch(
        f"/api/v1/curriculums/{curriculum.id}/topics/{ct.id}",
        json={"planned_date": "2025-09-05"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["planned_date"] == "2025-09-05"


async def test_patch_topic_sequence_reorders(http_client, db_session):
    c, client_obj = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider, client_id=client_obj.id, is_default=False)
    topic1 = await _seed_topic(db_session, sequence=1)
    topic2 = await _seed_topic(db_session, sequence=2)
    topic3 = await _seed_topic(db_session, sequence=3)
    ct1 = await _seed_curriculum_topic(db_session, curriculum, topic1, sequence=1)
    ct2 = await _seed_curriculum_topic(db_session, curriculum, topic2, sequence=2)
    ct3 = await _seed_curriculum_topic(db_session, curriculum, topic3, sequence=3)

    # Move ct1 (seq 1) to position 3
    resp = await c.patch(
        f"/api/v1/curriculums/{curriculum.id}/topics/{ct1.id}",
        json={"sequence": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["sequence"] == 3

    # Verify others shifted
    await db_session.refresh(ct2)
    await db_session.refresh(ct3)
    assert ct2.sequence == 1
    assert ct3.sequence == 2


async def test_patch_topic_on_default_curriculum_returns_403(http_client, db_session):
    c, client_obj = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    # Default curriculum
    curriculum = await _seed_curriculum(db_session, book, provider, is_default=True)
    topic = await _seed_topic(db_session)
    ct = await _seed_curriculum_topic(db_session, curriculum, topic, sequence=1)

    resp = await c.patch(
        f"/api/v1/curriculums/{curriculum.id}/topics/{ct.id}",
        json={"planned_date": "2025-09-05"},
    )
    assert resp.status_code == 403
    assert "clone it first" in resp.json()["detail"]


# POST /api/v1/curriculums/{id}/topics/{ct_id}/complete

async def test_complete_topic_sets_completed_date(http_client, db_session):
    c, client_obj = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider, client_id=client_obj.id, is_default=False)
    topic = await _seed_topic(db_session)
    ct = await _seed_curriculum_topic(db_session, curriculum, topic)

    resp = await c.post(f"/api/v1/curriculums/{curriculum.id}/topics/{ct.id}/complete")
    assert resp.status_code == 200
    data = resp.json()
    assert data["completed_date"] is not None


async def test_complete_topic_on_default_curriculum_returns_403(http_client, db_session):
    c, client_obj = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider, is_default=True)
    topic = await _seed_topic(db_session)
    ct = await _seed_curriculum_topic(db_session, curriculum, topic)

    resp = await c.post(f"/api/v1/curriculums/{curriculum.id}/topics/{ct.id}/complete")
    assert resp.status_code == 403


# DELETE /api/v1/curriculums/{id}/topics/{ct_id} (teacher endpoint)

async def test_delete_teacher_topic_removes_and_resequences(http_client, db_session):
    from sqlalchemy import select as sa_select
    from dars.curriculum.models import CurriculumTopic as CT

    c, client_obj = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider, client_id=client_obj.id, is_default=False)
    topic1 = await _seed_topic(db_session, sequence=1)
    topic2 = await _seed_topic(db_session, sequence=2)
    topic3 = await _seed_topic(db_session, sequence=3)
    ct1 = await _seed_curriculum_topic(db_session, curriculum, topic1, sequence=1)
    ct2 = await _seed_curriculum_topic(db_session, curriculum, topic2, sequence=2)
    ct3 = await _seed_curriculum_topic(db_session, curriculum, topic3, sequence=3)

    resp = await c.delete(f"/api/v1/curriculums/{curriculum.id}/topics/{ct2.id}")
    assert resp.status_code == 204

    remaining = (await db_session.execute(
        sa_select(CT).where(CT.curriculum_id == curriculum.id).order_by(CT.sequence)
    )).scalars().all()
    assert len(remaining) == 2
    assert remaining[0].sequence == 1
    assert remaining[1].sequence == 2


async def test_delete_teacher_topic_on_default_curriculum_returns_403(http_client, db_session):
    c, client_obj = http_client
    book = await _seed_book(db_session)
    provider = await _seed_provider(db_session)
    curriculum = await _seed_curriculum(db_session, book, provider, is_default=True)
    topic = await _seed_topic(db_session)
    ct = await _seed_curriculum_topic(db_session, curriculum, topic)

    resp = await c.delete(f"/api/v1/curriculums/{curriculum.id}/topics/{ct.id}")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Phase 4 — POST /api/admin/curriculums/generate
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date as _date


def _make_tool_use_block(name: str, input_data: dict):
    """Build a mock tool_use content block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = input_data
    return block


def _make_message_response(tool_block):
    """Wrap a tool block in a mock Anthropic message response."""
    resp = MagicMock()
    resp.content = [tool_block]
    return resp


async def _seed_book_with_topics(db: AsyncSession) -> tuple[Book, SloProvider]:
    """Seed a book with 2 chapters, 2 topics each, and a provider."""
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
    """Full happy-path: mocked Step A + Step B return valid stubs → curriculum created."""
    c, client_obj = admin_http_client
    book, provider, topics = await _seed_book_with_topics(db_session)
    t1, t2, t3, t4 = topics

    # Step A mock: 5 days for ch1, 5 days for ch2
    step_a_block = _make_tool_use_block("allocate_chapter_days", {
        "allocations": [
            {"chapter_id": 201, "days": 5},
            {"chapter_id": 202, "days": 5},
        ]
    })
    step_a_resp = _make_message_response(step_a_block)

    # Step B mock for ch1: 2 stubs
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

    # Step B mock for ch2: 2 stubs
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

    mock_create = AsyncMock(side_effect=[step_a_resp, step_b1_resp, step_b2_resp])

    with patch("dars.config.settings.anthropic_api_key", "test-key"), \
         patch("anthropic.AsyncAnthropic") as MockAnthropic:
        mock_instance = MagicMock()
        mock_instance.messages.create = mock_create
        MockAnthropic.return_value = mock_instance

        resp = await c.post("/api/admin/curriculums/generate", json={
            "book_id": 20,
            "provider_id": str(provider.id),
            "name": "Grade 3 NCP 2025-26",
            "start_date": "2025-09-01",
            "end_date": "2025-09-30",
            "days_per_week": 5,
            "is_default": True,
        })

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Grade 3 NCP 2025-26"
    assert data["is_default"] is True
    assert len(data["topics"]) == 4
    # All stubs should be pending
    for topic in data["topics"]:
        for stub in topic["lp_stubs"]:
            assert stub["status"] == "pending"

    # Check LLM was called 3 times: once for Step A, twice for Step B
    assert mock_create.call_count == 3


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
            "is_default": True,
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
            "is_default": True,
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
            "is_default": True,
        })
    assert resp.status_code == 500
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]


async def test_generate_curriculum_requires_admin(http_client, db_session):
    """Non-admin client must get 403."""
    c, _ = http_client
    resp = await c.post("/api/admin/curriculums/generate", json={
        "book_id": 1,
        "provider_id": str(uuid.uuid4()),
        "name": "Test",
        "start_date": "2025-09-01",
        "end_date": "2025-09-30",
        "days_per_week": 5,
        "is_default": True,
    })
    assert resp.status_code == 403


