"""Tests for POST/GET /api/v1/lesson-plans (generated_lps module)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _signup(http_client, email: str, curriculum: str = "NCP") -> str:
    resp = await http_client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "pass123",
            "name": f"Client {email}",
            "curriculum": curriculum,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["api_key"]


async def test_create_lp_requires_auth(http_client):
    resp = await http_client.post(
        "/api/v1/lesson-plans",
        json={"grade": 5, "subject": "Maths", "topic": "Fractions"},
    )
    assert resp.status_code == 401


async def test_create_lp_returns_202_pending(http_client):
    api_key = await _signup(http_client, "lp1@test.com", "NCP")
    resp = await http_client.post(
        "/api/v1/lesson-plans",
        json={"grade": 5, "subject": "Maths", "topic": "Fractions"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["curriculum"] == "NCP"
    assert "id" in data


async def test_get_lp_by_id(http_client):
    api_key = await _signup(http_client, "lp2@test.com", "NCP")
    create_resp = await http_client.post(
        "/api/v1/lesson-plans",
        json={"grade": 5, "subject": "Maths", "topic": "Fractions"},
        headers={"X-API-Key": api_key},
    )
    lp_id = create_resp.json()["id"]

    get_resp = await http_client.get(
        f"/api/v1/lesson-plans/{lp_id}",
        headers={"X-API-Key": api_key},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == lp_id


async def test_list_lps_shows_own(http_client):
    api_key = await _signup(http_client, "lp3@test.com", "NCP")
    await http_client.post(
        "/api/v1/lesson-plans",
        json={"grade": 5, "subject": "Maths"},
        headers={"X-API-Key": api_key},
    )
    await http_client.post(
        "/api/v1/lesson-plans",
        json={"grade": 4, "subject": "English"},
        headers={"X-API-Key": api_key},
    )

    list_resp = await http_client.get(
        "/api/v1/lesson-plans",
        headers={"X-API-Key": api_key},
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 2


async def test_client_isolation_get(http_client):
    """Client B cannot fetch Client A's lesson plan."""
    key_a = await _signup(http_client, "lp_a@test.com", "NCP")
    key_b = await _signup(http_client, "lp_b@test.com", "SNC")

    create_resp = await http_client.post(
        "/api/v1/lesson-plans",
        json={"grade": 5, "subject": "Maths"},
        headers={"X-API-Key": key_a},
    )
    lp_id = create_resp.json()["id"]

    get_resp = await http_client.get(
        f"/api/v1/lesson-plans/{lp_id}",
        headers={"X-API-Key": key_b},
    )
    assert get_resp.status_code == 404


async def test_client_isolation_list(http_client):
    """Client B's list shows 0 when only Client A has LPs."""
    key_a = await _signup(http_client, "lp_iso_a@test.com", "NCP")
    key_b = await _signup(http_client, "lp_iso_b@test.com", "SNC")

    await http_client.post(
        "/api/v1/lesson-plans",
        json={"grade": 5, "subject": "Maths"},
        headers={"X-API-Key": key_a},
    )

    list_resp = await http_client.get(
        "/api/v1/lesson-plans",
        headers={"X-API-Key": key_b},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 0
