"""
Tests for Step 7 — Teacher App endpoint:
  GET /api/v1/me/classes
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.clients.models import Client
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
async def http_client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def headers(key: str) -> dict:
    return {"X-API-Key": key}


async def _signup(http_client, email: str, name: str = "School") -> str:
    """Sign up and return API key. Signup auto-creates a default teacher."""
    resp = await http_client.post(
        "/auth/signup",
        json={"email": email, "password": "pass123", "name": name, "curriculum": "NCP"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["api_key"]


async def _get_me(http_client, key: str) -> dict:
    resp = await http_client.get("/api/v1/me", headers=headers(key))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _make_academic_year(http_client, key: str) -> dict:
    resp = await http_client.post(
        "/api/v1/academic-years",
        json={"name": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31"},
        headers=headers(key),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _make_class(http_client, key: str, year_id: str, grade: int = 5) -> dict:
    resp = await http_client.post(
        "/api/v1/classes",
        json={
            "academic_year_id": year_id,
            "grade": grade,
            "section": "A",
            "name": f"Grade {grade}-A",
        },
        headers=headers(key),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _assign_subject(
    http_client, key: str, class_id: str, subject: str = "English", teacher_id: str | None = None
) -> dict:
    body: dict = {"subject": subject}
    if teacher_id:
        body["teacher_id"] = teacher_id
    resp = await http_client.post(
        f"/api/v1/classes/{class_id}/subjects",
        json=body,
        headers=headers(key),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_my_classes_returns_teacher_csts(http_client):
    """
    GET /api/v1/me/classes returns CSTs assigned to the default_teacher_id.
    Signup auto-creates a default teacher; assign a class subject to that teacher.
    """
    key = await _signup(http_client, "teacher1@school.com", "School A")
    me = await _get_me(http_client, key)
    default_teacher_id = me["default_teacher_id"]
    assert default_teacher_id is not None, "signup should auto-create a default teacher"

    year = await _make_academic_year(http_client, key)
    school_class = await _make_class(http_client, key, year["id"], grade=5)
    cst = await _assign_subject(http_client, key, school_class["id"], "English", default_teacher_id)

    resp = await http_client.get("/api/v1/me/classes", headers=headers(key))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["cst_id"] == cst["id"]
    assert item["subject"] == "English"
    assert item["grade"] == 5
    assert item["class_name"] == "Grade 5-A"
    assert item["chapter_count"] == 0
    assert item["taught_count"] == 0
    assert item["next_slot"] is None


@pytest.mark.asyncio
async def test_my_classes_returns_empty_when_default_teacher_has_no_csts(http_client, db_session):
    """
    GET /api/v1/me/classes returns empty list when no CSTs are assigned to
    the default_teacher_id (or when default_teacher_id is explicitly None).
    """
    key = await _signup(http_client, "noteacher@school.com", "School B")

    # Clear default_teacher_id directly in the DB
    result = await db_session.execute(select(Client).where(Client.email == "noteacher@school.com"))
    client = result.scalar_one()
    client.default_teacher_id = None
    await db_session.commit()

    resp = await http_client.get("/api/v1/me/classes", headers=headers(key))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["items"] == []


@pytest.mark.asyncio
async def test_my_classes_client_isolation(http_client):
    """Client A cannot see Client B's classes via GET /api/v1/me/classes."""
    key_a = await _signup(http_client, "clientA@school.com", "School A")
    key_b = await _signup(http_client, "clientB@school.com", "School B")

    # Client B: get default teacher, set up class + subject
    me_b = await _get_me(http_client, key_b)
    teacher_b_id = me_b["default_teacher_id"]

    year_b = await _make_academic_year(http_client, key_b)
    class_b = await _make_class(http_client, key_b, year_b["id"], grade=6)
    await _assign_subject(http_client, key_b, class_b["id"], "Maths", teacher_b_id)

    # Client A: no CSTs assigned to their default teacher
    resp_a = await http_client.get("/api/v1/me/classes", headers=headers(key_a))
    assert resp_a.status_code == 200, resp_a.text
    data_a = resp_a.json()
    # Client A has no CSTs assigned to their teacher, so empty
    assert data_a["items"] == []

    # Client B sees their own data only
    resp_b = await http_client.get("/api/v1/me/classes", headers=headers(key_b))
    assert resp_b.status_code == 200, resp_b.text
    data_b = resp_b.json()
    assert len(data_b["items"]) == 1
    assert data_b["items"][0]["subject"] == "Maths"
    # Confirm B's item does not contain A's class
    assert data_b["items"][0]["grade"] == 6
