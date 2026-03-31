import hashlib
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.clients.models import Client
from dars.clients.service import create_client, get_client_by_api_key
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


@pytest.fixture(scope="function")
def mock_client_obj():
    return Client(
        id=uuid.uuid4(),
        name="Test Team",
        api_key_hash="abc123",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


# --- Service tests ---

async def test_create_client_returns_name_and_key(db_session):
    client, raw_key = await create_client(db_session, name="Punjab Team")
    assert client.name == "Punjab Team"
    assert client.is_active is True
    assert len(raw_key) > 20
    assert raw_key.startswith("dars_")


async def test_create_client_stores_hash_not_plaintext(db_session):
    client, raw_key = await create_client(db_session, name="Sindh Team")
    expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    assert client.api_key_hash == expected_hash
    assert raw_key not in client.api_key_hash


async def test_get_client_by_api_key_found(db_session):
    client, raw_key = await create_client(db_session, name="Test Team")
    found = await get_client_by_api_key(db_session, raw_key)
    assert found is not None
    assert found.id == client.id


async def test_get_client_by_api_key_not_found(db_session):
    found = await get_client_by_api_key(db_session, "dars_invalid_key")
    assert found is None


async def test_get_client_by_api_key_inactive(db_session):
    client, raw_key = await create_client(db_session, name="Disabled Team")
    client.is_active = False
    await db_session.commit()
    found = await get_client_by_api_key(db_session, raw_key)
    assert found is None


# --- Router + auth tests ---

async def test_create_client_endpoint_requires_admin_secret(http_client):
    response = await http_client.post("/admin/clients", json={"name": "Punjab Team"})
    assert response.status_code == 403


async def test_create_client_endpoint_success(http_client, mock_client_obj):
    with patch("dars.clients.router.create_client", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = (mock_client_obj, "dars_fake_raw_key")
        response = await http_client.post(
            "/admin/clients",
            headers={"X-Admin-Secret": "dev-secret"},
            json={"name": "Punjab Team"},
        )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Team"
    assert data["api_key"] == "dars_fake_raw_key"
    assert "api_key_hash" not in data


async def test_api_key_auth_missing(http_client):
    response = await http_client.get("/api/v1/me")
    assert response.status_code == 401


async def test_api_key_auth_invalid(http_client):
    response = await http_client.get("/api/v1/me", headers={"X-API-Key": "dars_invalid"})
    assert response.status_code == 401


async def test_api_key_auth_valid(http_client, mock_client_obj):
    with patch("dars.deps.get_client_by_api_key", new_callable=AsyncMock) as mock_lookup:
        mock_lookup.return_value = mock_client_obj
        response = await http_client.get("/api/v1/me", headers={"X-API-Key": "dars_valid_key"})
    assert response.status_code == 200
    assert response.json()["name"] == "Test Team"


# --- Webhook URL tests ---

async def test_patch_client_webhook_url(http_client, db_session):
    client, _ = await create_client(db_session, name="Test Client")
    response = await http_client.patch(
        f"/admin/clients/{client.id}",
        json={"webhook_url": "https://example.com/webhook"},
        headers={"X-Admin-Secret": "dev-secret"},
    )
    assert response.status_code == 200
    assert response.json()["webhook_url"] == "https://example.com/webhook"


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
