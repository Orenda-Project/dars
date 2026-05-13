"""
Tests for Step 2 — Data Bank:
  GET /api/v1/books (auto-filtered by client curriculum)
  GET /api/v1/slos
  GET /api/v1/topics/{id}/slos
  POST /admin/slos/import
  POST /admin/topics/{id}/slos
  DELETE /admin/topics/{id}/slos
"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import dars.clients.models  # noqa
import dars.curriculum.models  # noqa
import dars.curriculum_data.models  # noqa
import dars.generated_lps.models  # noqa
import dars.lookup.models  # noqa
from dars.clients.service import create_client
from dars.curriculum.models import Book, BookChapter, SLO, Topic
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
        # Seed required reference data
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
async def ncp_client(db_session):
    import dars.config as _cfg
    original_secret = _cfg.settings.admin_secret
    _cfg.settings.admin_secret = "dev-secret"

    client_obj, raw_key = await create_client(db_session, name="NCP Client")
    client_obj.curriculum = "NCP"
    await db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, raw_key, client_obj
    app.dependency_overrides.clear()
    _cfg.settings.admin_secret = original_secret


@pytest.fixture(scope="function")
async def snc_client(db_session):
    import dars.config as _cfg
    original_secret = _cfg.settings.admin_secret
    _cfg.settings.admin_secret = "dev-secret"

    client_obj, raw_key = await create_client(db_session, name="SNC Client")
    client_obj.curriculum = "SNC"
    await db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, raw_key, client_obj
    app.dependency_overrides.clear()
    _cfg.settings.admin_secret = original_secret


async def _make_book(db: AsyncSession, curriculum: str = "NCP", **kwargs) -> Book:
    book = Book(
        curriculum=curriculum,
        grade=kwargs.get("grade", 5),
        subject=kwargs.get("subject", "Eng"),
        title=kwargs.get("title", f"Book {curriculum}"),
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def _make_chapter(db: AsyncSession, book_id: int) -> BookChapter:
    chapter = BookChapter(book_id=book_id, title="Ch1", chapter_number=1)
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return chapter


async def _make_topic(db: AsyncSession, chapter_id: int) -> Topic:
    topic = Topic(chapter_id=chapter_id, topic_number=1, title="Topic 1")
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic


async def _make_slo(db: AsyncSession, curriculum: str = "NCP", code: str = "R1.1") -> SLO:
    slo = SLO(curriculum=curriculum, grade=3, subject="Eng", code=code, description=f"SLO {code}")
    db.add(slo)
    await db.commit()
    await db.refresh(slo)
    return slo


def _admin_headers(client_obj, db_session):
    from dars.clients.service import _hash_key
    admin_key = f"dars_admin_test_{uuid.uuid4().hex[:8]}"
    client_obj.is_admin = True
    client_obj.api_key_hash = _hash_key(admin_key)
    return admin_key


# ---------------------------------------------------------------------------
# GET /api/v1/books — auto-filtered by client curriculum
# ---------------------------------------------------------------------------


async def test_books_ncp_client_sees_only_ncp(ncp_client, db_session):
    http, key, _ = ncp_client
    await _make_book(db_session, curriculum="NCP", title="NCP Book")
    await _make_book(db_session, curriculum="SNC", title="SNC Book")

    resp = await http.get("/api/v1/books", headers={"X-API-Key": key})
    assert resp.status_code == 200
    titles = [b["title"] for b in resp.json()["items"]]
    assert "NCP Book" in titles
    assert "SNC Book" not in titles


async def test_books_snc_client_sees_only_snc(snc_client, db_session):
    http, key, _ = snc_client
    await _make_book(db_session, curriculum="NCP", title="NCP Book")
    await _make_book(db_session, curriculum="SNC", title="SNC Book")

    resp = await http.get("/api/v1/books", headers={"X-API-Key": key})
    assert resp.status_code == 200
    titles = [b["title"] for b in resp.json()["items"]]
    assert "SNC Book" in titles
    assert "NCP Book" not in titles


async def test_books_no_curriculum_param_needed(ncp_client, db_session):
    http, key, _ = ncp_client
    await _make_book(db_session, curriculum="NCP")
    resp = await http.get("/api/v1/books", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


# ---------------------------------------------------------------------------
# POST /admin/slos/import
# ---------------------------------------------------------------------------


async def test_import_slos_creates_rows(ncp_client, db_session):
    http, _, client_obj = ncp_client
    admin_key = _admin_headers(client_obj, db_session)
    await db_session.commit()

    payload = {
        "curriculum": "NCP",
        "slos": [
            {"grade": 3, "subject": "Eng", "code": "R1.1", "description": "Read aloud"},
            {"grade": 3, "subject": "Eng", "code": "R1.2", "description": "Comprehend text"},
        ],
    }
    resp = await http.post("/admin/slos/import", json=payload, headers={"X-API-Key": admin_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 2
    assert data["updated"] == 0


async def test_import_slos_upserts_on_duplicate(ncp_client, db_session):
    http, _, client_obj = ncp_client
    admin_key = _admin_headers(client_obj, db_session)
    await db_session.commit()

    payload = {"curriculum": "NCP", "slos": [{"grade": 3, "subject": "Eng", "code": "R1.1", "description": "Original"}]}
    await http.post("/admin/slos/import", json=payload, headers={"X-API-Key": admin_key})

    payload["slos"][0]["description"] = "Updated"
    resp = await http.post("/admin/slos/import", json=payload, headers={"X-API-Key": admin_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 0
    assert data["updated"] == 1


# ---------------------------------------------------------------------------
# GET /api/v1/slos — filtered by client curriculum
# ---------------------------------------------------------------------------


async def test_list_slos_ncp_client_sees_only_ncp(ncp_client, db_session):
    http, key, _ = ncp_client
    await _make_slo(db_session, curriculum="NCP", code="R1.1")
    await _make_slo(db_session, curriculum="SNC", code="R2.1")

    resp = await http.get("/api/v1/slos", headers={"X-API-Key": key})
    assert resp.status_code == 200
    codes = [s["code"] for s in resp.json()["items"]]
    assert "R1.1" in codes
    assert "R2.1" not in codes


async def test_list_slos_filter_by_grade_and_subject(ncp_client, db_session):
    http, key, _ = ncp_client
    await _make_slo(db_session, curriculum="NCP", code="R1.1")  # grade=3, subject=Eng
    slo2 = SLO(curriculum="NCP", grade=4, subject="Maths", code="M4.1", description="Algebra")
    db_session.add(slo2)
    await db_session.commit()

    resp = await http.get("/api/v1/slos?grade=3&subject=Eng", headers={"X-API-Key": key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["code"] == "R1.1"


# ---------------------------------------------------------------------------
# POST /admin/topics/{id}/slos + GET /api/v1/topics/{id}/slos
# ---------------------------------------------------------------------------


async def test_map_and_get_topic_slos(db_session):
    """Use two separate clients: one admin for writing, one regular for reading."""
    import dars.config as _cfg
    original_secret = _cfg.settings.admin_secret
    _cfg.settings.admin_secret = "dev-secret"

    reader, reader_key = await create_client(db_session, name="Reader")
    reader.curriculum = "NCP"
    writer, writer_key = await create_client(db_session, name="Writer")
    writer.curriculum = "NCP"
    writer.is_admin = True
    from dars.clients.service import _hash_key
    admin_key = f"dars_admin_{uuid.uuid4().hex[:8]}"
    writer.api_key_hash = _hash_key(admin_key)
    await db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        book = await _make_book(db_session, curriculum="NCP")
        chapter = await _make_chapter(db_session, book.id)
        topic = await _make_topic(db_session, chapter.id)
        await _make_slo(db_session, curriculum="NCP", code="R1.1")
        await _make_slo(db_session, curriculum="NCP", code="R1.2")

        map_resp = await http.post(
            f"/admin/topics/{topic.id}/slos",
            json={"slo_codes": ["R1.1", "R1.2"]},
            headers={"X-API-Key": admin_key},
        )
        assert map_resp.status_code == 200
        assert map_resp.json()["mapped"] == 2

        get_resp = await http.get(f"/api/v1/topics/{topic.id}/slos", headers={"X-API-Key": reader_key})
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["topic_id"] == topic.id
        codes = [s["code"] for s in data["slos"]]
        assert "R1.1" in codes
        assert "R1.2" in codes

    app.dependency_overrides.clear()
    _cfg.settings.admin_secret = original_secret


async def test_clear_topic_slos(db_session):
    import dars.config as _cfg
    original_secret = _cfg.settings.admin_secret
    _cfg.settings.admin_secret = "dev-secret"

    reader, reader_key = await create_client(db_session, name="Reader2")
    reader.curriculum = "NCP"
    writer, _ = await create_client(db_session, name="Writer2")
    writer.curriculum = "NCP"
    writer.is_admin = True
    from dars.clients.service import _hash_key
    admin_key = f"dars_admin_{uuid.uuid4().hex[:8]}"
    writer.api_key_hash = _hash_key(admin_key)
    await db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        book = await _make_book(db_session, curriculum="NCP")
        chapter = await _make_chapter(db_session, book.id)
        topic = await _make_topic(db_session, chapter.id)
        await _make_slo(db_session, curriculum="NCP", code="R1.1")

        await http.post(
            f"/admin/topics/{topic.id}/slos",
            json={"slo_codes": ["R1.1"]},
            headers={"X-API-Key": admin_key},
        )

        del_resp = await http.delete(f"/admin/topics/{topic.id}/slos", headers={"X-API-Key": admin_key})
        assert del_resp.status_code == 204

        get_resp = await http.get(f"/api/v1/topics/{topic.id}/slos", headers={"X-API-Key": reader_key})
        assert get_resp.status_code == 200
        assert get_resp.json()["slos"] == []

    app.dependency_overrides.clear()
    _cfg.settings.admin_secret = original_secret


async def test_map_unknown_slo_code_returns_422(ncp_client, db_session):
    http, _, client_obj = ncp_client
    admin_key = _admin_headers(client_obj, db_session)
    await db_session.commit()

    book = await _make_book(db_session, curriculum="NCP")
    chapter = await _make_chapter(db_session, book.id)
    topic = await _make_topic(db_session, chapter.id)

    resp = await http.post(
        f"/admin/topics/{topic.id}/slos",
        json={"slo_codes": ["NONEXISTENT"]},
        headers={"X-API-Key": admin_key},
    )
    assert resp.status_code == 422
