import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.main import app
from dars.database import Base, get_db
from dars.clients.service import create_client

TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
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


@pytest.fixture(scope="function")
async def api_key(db_session):
    _, raw_key = await create_client(db_session, name="Test Client")
    return raw_key


async def test_create_lesson_plan_returns_202_pending(http_client, api_key):
    with patch("dars.lesson_plans.router.generate_lesson_plan_task"):
        response = await http_client.post(
            "/api/v1/lesson-plans",
            json={"grade": "3", "subject": "Maths", "page_number": "10"},
            headers={"X-API-Key": api_key},
        )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["content"] is None
    assert "id" in data


async def test_get_lesson_plan_returns_pending(http_client, api_key):
    with patch("dars.lesson_plans.router.generate_lesson_plan_task"):
        create_resp = await http_client.post(
            "/api/v1/lesson-plans",
            json={"grade": "3", "subject": "Maths", "page_number": "10"},
            headers={"X-API-Key": api_key},
        )
    lp_id = create_resp.json()["id"]
    get_resp = await http_client.get(
        f"/api/v1/lesson-plans/{lp_id}",
        headers={"X-API-Key": api_key},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "PENDING"
