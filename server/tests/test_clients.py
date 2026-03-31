import pytest
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

async def test_patch_client_webhook_url(http_client, db_session):
    client, _ = await create_client(db_session, name="Test Client")
    response = await http_client.patch(
        f"/admin/clients/{client.id}",
        json={"webhook_url": "https://example.com/webhook"},
        headers={"X-Admin-Secret": "dev-secret"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["webhook_url"] == "https://example.com/webhook"

async def test_patch_client_clears_webhook_url(http_client, db_session):
    client, _ = await create_client(db_session, name="Test Client")
    await http_client.patch(
        f"/admin/clients/{client.id}",
        json={"webhook_url": "https://example.com/webhook"},
        headers={"X-Admin-Secret": "dev-secret"},
    )
    response = await http_client.patch(
        f"/admin/clients/{client.id}",
        json={"webhook_url": None},
        headers={"X-Admin-Secret": "dev-secret"},
    )
    assert response.status_code == 200
    assert response.json()["webhook_url"] is None
