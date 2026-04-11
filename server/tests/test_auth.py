"""
Auth endpoint tests.

Supabase is an external service; we mock `dars.auth.service.get_supabase`
so these tests run without network access or real credentials.
"""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.clients.service import create_client
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


def _fake_supabase_user(uid: str = "supabase-uid-1"):
    """Return a minimal Supabase-like client mock with a sign_up/sign_in stub."""
    user = SimpleNamespace(id=uid)
    response = SimpleNamespace(user=user)

    sb = MagicMock()
    sb.auth.sign_up.return_value = response
    sb.auth.sign_in_with_password.return_value = response
    return sb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_signup_creates_client(http_client):
    """POST /auth/signup returns 201 with api_key, client_id, name, email."""
    fake_sb = _fake_supabase_user("supabase-uid-1")

    with patch("dars.auth.service.get_supabase", return_value=fake_sb):
        response = await http_client.post(
            "/auth/signup",
            json={"email": "test@example.com", "password": "secret123", "name": "Test Team"},
        )

    assert response.status_code == 201
    data = response.json()
    assert "api_key" in data
    assert "client_id" in data
    assert data["name"] == "Test Team"
    assert data["email"] == "test@example.com"
    assert data["api_key"].startswith("dars_")


async def test_signup_duplicate_email(http_client):
    """POST /auth/signup with a duplicate email returns 409."""
    # Supabase returns user=None when the email is already registered
    sb = MagicMock()
    sb.auth.sign_up.return_value = SimpleNamespace(user=None)

    with patch("dars.auth.service.get_supabase", return_value=sb):
        response = await http_client.post(
            "/auth/signup",
            json={"email": "dupe@example.com", "password": "secret123", "name": "Dupe Team"},
        )

    assert response.status_code == 409


async def test_login_rotates_key(http_client, db_session):
    """POST /auth/login returns 200 and a fresh api_key different from the signup key."""
    uid = str(uuid.uuid4())
    fake_sb = _fake_supabase_user(uid)

    # Signup to create the Client row
    with patch("dars.auth.service.get_supabase", return_value=fake_sb):
        signup_resp = await http_client.post(
            "/auth/signup",
            json={"email": "login@example.com", "password": "secret123", "name": "Login Team"},
        )
    assert signup_resp.status_code == 201
    signup_key = signup_resp.json()["api_key"]

    # Login — should rotate the key
    with patch("dars.auth.service.get_supabase", return_value=fake_sb):
        login_resp = await http_client.post(
            "/auth/login",
            json={"email": "login@example.com", "password": "secret123"},
        )
    assert login_resp.status_code == 200
    login_key = login_resp.json()["api_key"]

    assert login_key != signup_key
    assert login_key.startswith("dars_")


async def test_login_wrong_password(http_client):
    """POST /auth/login with bad credentials returns 401."""
    sb = MagicMock()
    sb.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")

    with patch("dars.auth.service.get_supabase", return_value=sb):
        response = await http_client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "wrongpass"},
        )

    assert response.status_code == 401


async def test_login_no_client_row(http_client):
    """POST /auth/login where Supabase succeeds but no Client row exists returns 404."""
    uid = str(uuid.uuid4())
    fake_sb = _fake_supabase_user(uid)

    # Do NOT create a Client row — the DB is empty for this uid
    with patch("dars.auth.service.get_supabase", return_value=fake_sb):
        response = await http_client.post(
            "/auth/login",
            json={"email": "ghost@example.com", "password": "secret123"},
        )

    assert response.status_code == 404
