"""Tests for GET /api/v1/grades and GET /api/v1/subjects."""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.database import Base, get_db
from dars.lookup.models import Grade, Subject
from dars.main import app

TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        # Seed lookup data
        session.add_all([
            Grade(code=1, display_name="Grade 1"),
            Grade(code=5, display_name="Grade 5"),
            Subject(code="Eng", display_name="English"),
            Subject(code="Maths", display_name="Mathematics"),
        ])
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


async def test_list_grades(http_client):
    resp = await http_client.get("/api/v1/grades")
    assert resp.status_code == 200
    data = resp.json()
    assert any(g["code"] == 5 and g["display_name"] == "Grade 5" for g in data)


async def test_list_subjects(http_client):
    resp = await http_client.get("/api/v1/subjects")
    assert resp.status_code == 200
    data = resp.json()
    assert any(s["code"] == "Eng" and s["display_name"] == "English" for s in data)


async def test_grades_no_auth_required(http_client):
    resp = await http_client.get("/api/v1/grades")
    assert resp.status_code == 200


async def test_subjects_no_auth_required(http_client):
    resp = await http_client.get("/api/v1/subjects")
    assert resp.status_code == 200
