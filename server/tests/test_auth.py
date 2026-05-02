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


async def test_signup_creates_client(http_client):
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
    await http_client.post(
        "/auth/signup",
        json={"email": "dupe@example.com", "password": "secret123", "name": "First"},
    )
    response = await http_client.post(
        "/auth/signup",
        json={"email": "dupe@example.com", "password": "secret123", "name": "Second"},
    )
    assert response.status_code == 409


async def test_login_rotates_key(http_client):
    signup_resp = await http_client.post(
        "/auth/signup",
        json={"email": "login@example.com", "password": "secret123", "name": "Login Team"},
    )
    assert signup_resp.status_code == 201
    signup_key = signup_resp.json()["api_key"]

    login_resp = await http_client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "secret123"},
    )
    assert login_resp.status_code == 200
    login_key = login_resp.json()["api_key"]
    assert login_key != signup_key
    assert login_key.startswith("dars_")


async def test_login_wrong_password(http_client):
    await http_client.post(
        "/auth/signup",
        json={"email": "user@example.com", "password": "correct", "name": "User"},
    )
    response = await http_client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrongpass"},
    )
    assert response.status_code == 401


async def test_login_unknown_email(http_client):
    response = await http_client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "secret123"},
    )
    assert response.status_code == 401
