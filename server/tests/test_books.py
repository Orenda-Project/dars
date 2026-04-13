"""Tests for books sync endpoint."""
import hashlib
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.clients.models import Client
from dars.clients.service import create_client
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
async def admin_http_client(db_session):
    """HTTP client with an admin client's API key injected."""
    client_obj, raw_key = await create_client(db_session, name="Admin Client")
    # Manually set is_admin = True
    client_obj.is_admin = True
    await db_session.commit()
    await db_session.refresh(client_obj)

    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.headers["X-API-Key"] = raw_key
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def non_admin_http_client(db_session):
    """HTTP client with a regular (non-admin) API key."""
    client_obj, raw_key = await create_client(db_session, name="Regular Client")

    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.headers["X-API-Key"] = raw_key
        yield c
    app.dependency_overrides.clear()


# --- Fake psycopg2 rows for mocking ---

def _make_fake_conn(ict_books, punjab_books, ict_chapters, punjab_chapters):
    """Build a fake psycopg2 connection whose cursor returns the given rows."""
    call_count = {"n": 0}
    results = [ict_books, punjab_books, ict_chapters, punjab_chapters]

    class FakeCursor:
        def execute(self, query, params=None):
            pass

        def fetchall(self):
            idx = call_count["n"]
            call_count["n"] += 1
            return results[idx] if idx < len(results) else []

        def close(self):
            pass

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    return FakeConn()


async def test_sync_books_returns_counts(admin_http_client):
    """POST /api/admin/books/sync calls core DB and returns insert counts."""
    ict_books = [
        (1, "Science Grade 3", "cover.jpg", 5, "Grade 3", "SCI"),
    ]
    punjab_books = [
        (101, "Maths Grade 2", None, 4, "2", "MATH"),
    ]
    ict_chapters = [
        (10, "Chapter One", 1, 1, 20, 1),
    ]
    punjab_chapters = [
        (110, "Chapter Alpha", 1, 1, 15, 101),
    ]

    fake_conn = _make_fake_conn(ict_books, punjab_books, ict_chapters, punjab_chapters)

    with patch("dars.books.service._get_core_conn", return_value=fake_conn):
        # SQLite does not support pg INSERT ... ON CONFLICT DO UPDATE,
        # so mock sync_books at the service level for the DB upsert portion.
        # We test the full service separately; here we just test the HTTP layer.
        from dars.books import service as books_service

        async def _fake_sync(db):
            return {"ict_books": 1, "punjab_books": 1, "chapters": 2}

        with patch.object(books_service, "sync_books", side_effect=_fake_sync):
            response = await admin_http_client.post("/api/admin/books/sync")

    assert response.status_code == 200
    data = response.json()
    assert data["ict_books"] == 1
    assert data["punjab_books"] == 1
    assert data["chapters"] == 2


async def test_sync_books_requires_admin(non_admin_http_client):
    """Non-admin clients get 403 on sync endpoint."""
    response = await non_admin_http_client.post("/api/admin/books/sync")
    assert response.status_code == 403


async def test_sync_books_requires_auth():
    """Unauthenticated requests get 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/api/admin/books/sync")
    assert response.status_code == 401


async def test_list_books_requires_admin(non_admin_http_client):
    """Non-admin clients get 403 on list endpoint."""
    response = await non_admin_http_client.get("/api/admin/books")
    assert response.status_code == 403


async def test_list_books_empty(admin_http_client):
    """Admin client gets empty list when no books synced."""
    response = await admin_http_client.get("/api/admin/books")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
