import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import dars.clients.models  # noqa: F401
import dars.curriculum.models  # noqa: F401
import dars.curriculum_data.models  # noqa: F401
import dars.generated_exams.models  # noqa: F401
import dars.generated_lps.models  # noqa: F401
import dars.lookup.models  # noqa: F401
import dars.school.models  # noqa: F401
import dars.teachers.models  # noqa: F401
import dars.webhooks.models  # noqa: F401

from dars.clients.models import Client
from dars.curriculum_data.models import CurriculumData
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
        session.add(CurriculumData(code="NCP", name="National Curriculum of Pakistan"))
        session.add(CurriculumData(code="SNC", name="Single National Curriculum"))
        await session.commit()
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
        json={"email": "test@example.com", "password": "secret123", "name": "Test Team", "curriculum": "NCP"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "api_key" in data
    assert "client_id" in data
    assert data["name"] == "Test Team"
    assert data["email"] == "test@example.com"
    assert data["api_key"].startswith("dars_")
    assert data["curriculum"] == "NCP"


async def test_signup_duplicate_email(http_client):
    await http_client.post(
        "/auth/signup",
        json={"email": "dupe@example.com", "password": "secret123", "name": "First", "curriculum": "NCP"},
    )
    response = await http_client.post(
        "/auth/signup",
        json={"email": "dupe@example.com", "password": "secret123", "name": "Second", "curriculum": "NCP"},
    )
    assert response.status_code == 409


async def test_login_rotates_key(http_client):
    signup_resp = await http_client.post(
        "/auth/signup",
        json={"email": "login@example.com", "password": "secret123", "name": "Login Team", "curriculum": "SNC"},
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
        json={"email": "user@example.com", "password": "correct", "name": "User", "curriculum": "NCP"},
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


async def test_signup_without_curriculum_returns_422(http_client):
    response = await http_client.post(
        "/auth/signup",
        json={"email": "nocurr@example.com", "password": "secret123", "name": "No Curr"},
    )
    assert response.status_code == 422


async def test_signup_with_invalid_curriculum_returns_422(http_client):
    response = await http_client.post(
        "/auth/signup",
        json={"email": "badcurr@example.com", "password": "secret123", "name": "Bad Curr", "curriculum": "INVALID"},
    )
    assert response.status_code == 422


async def test_signup_ncp_default_teacher_created(http_client, db_session):
    response = await http_client.post(
        "/auth/signup",
        json={"email": "ncp@example.com", "password": "secret123", "name": "NCP School", "curriculum": "NCP"},
    )
    assert response.status_code == 201
    client_id = int(response.json()["client_id"])

    # Check default_teacher_id is set
    result = await db_session.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one()
    assert client.default_teacher_id is not None


async def test_get_me_returns_curriculum_object(http_client):
    signup_resp = await http_client.post(
        "/auth/signup",
        json={"email": "me@example.com", "password": "secret123", "name": "Me Client", "curriculum": "NCP"},
    )
    assert signup_resp.status_code == 201
    api_key = signup_resp.json()["api_key"]

    me_resp = await http_client.get("/api/v1/me", headers={"X-API-Key": api_key})
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["curriculum"] is not None
    assert data["curriculum"]["code"] == "NCP"
    assert data["curriculum"]["name"] == "National Curriculum of Pakistan"


async def test_signup_snc_curriculum(http_client):
    response = await http_client.post(
        "/auth/signup",
        json={"email": "snc@example.com", "password": "secret123", "name": "SNC School", "curriculum": "SNC"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["curriculum"] == "SNC"
