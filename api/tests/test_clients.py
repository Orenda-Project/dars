import hashlib
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dars.database import Base
from dars.clients.models import Client
from dars.clients.service import create_client, get_client_by_api_key


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_create_client_returns_name_and_key(db):
    client, raw_key = await create_client(db, name="Punjab Team")
    assert client.name == "Punjab Team"
    assert client.is_active is True
    assert len(raw_key) > 20
    assert raw_key.startswith("dars_")


async def test_create_client_stores_hash_not_plaintext(db):
    client, raw_key = await create_client(db, name="Sindh Team")
    expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    assert client.api_key_hash == expected_hash
    assert raw_key not in client.api_key_hash


async def test_get_client_by_api_key_found(db):
    client, raw_key = await create_client(db, name="Test Team")
    found = await get_client_by_api_key(db, raw_key)
    assert found is not None
    assert found.id == client.id


async def test_get_client_by_api_key_not_found(db):
    found = await get_client_by_api_key(db, "dars_invalid_key")
    assert found is None


async def test_get_client_by_api_key_inactive(db):
    client, raw_key = await create_client(db, name="Disabled Team")
    client.is_active = False
    await db.commit()
    found = await get_client_by_api_key(db, raw_key)
    assert found is None
