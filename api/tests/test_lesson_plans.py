import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.clients.models import Client
from dars.database import Base
from dars.lesson_plans.models import LessonPlan
from dars.lesson_plans.service import create_lesson_plan, get_lesson_plan, list_lesson_plans
from dars.lesson_plans.schemas import LessonPlanCreateRequest
from dars.main import app


@pytest.fixture(scope="function")
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_with_client(db):
    client = Client(
        id=uuid.uuid4(),
        name="Test Team",
        api_key_hash="abc123",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return db, client


LP_REQUEST = LessonPlanCreateRequest(
    grade="3",
    subject="Maths",
    page_number="10",
    curriculum="ICT",
    class_strength=30,
)

LP_ASSISTANT_SUCCESS = {
    "status": "success",
    "lesson_plan": "<html>LP content</html>",
    "lesson_plan_bilingual": "<html>Bilingual</html>",
    "tags": {"topic": "Addition"},
    "metadata": {"timings": {"total_time": 24.0}},
}


# --- Service tests ---

async def test_create_lesson_plan_success(db_with_client):
    db, client = db_with_client
    with patch("dars.lesson_plans.service._call_lp_assistant", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = LP_ASSISTANT_SUCCESS
        lp = await create_lesson_plan(db, client_id=client.id, request=LP_REQUEST)

    assert lp.status == "READY"
    assert lp.content == "<html>LP content</html>"
    assert lp.client_id == client.id
    assert lp.grade == "3"


async def test_create_lesson_plan_error_on_lp_assistant_failure(db_with_client):
    db, client = db_with_client
    with patch("dars.lesson_plans.service._call_lp_assistant", new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = Exception("LP assistant down")
        lp = await create_lesson_plan(db, client_id=client.id, request=LP_REQUEST)

    assert lp.status == "ERROR"
    assert lp.content is None


async def test_list_lesson_plans_empty(db_with_client):
    db, client = db_with_client
    items, total = await list_lesson_plans(db, client_id=client.id)
    assert items == []
    assert total == 0


async def test_list_lesson_plans_returns_own_only(db_with_client):
    db, client = db_with_client
    other_client_id = uuid.uuid4()

    with patch("dars.lesson_plans.service._call_lp_assistant", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = LP_ASSISTANT_SUCCESS
        await create_lesson_plan(db, client_id=client.id, request=LP_REQUEST)
        await create_lesson_plan(db, client_id=client.id, request=LP_REQUEST)

    items, total = await list_lesson_plans(db, client_id=client.id)
    assert total == 2

    items_other, total_other = await list_lesson_plans(db, client_id=other_client_id)
    assert total_other == 0


async def test_get_lesson_plan_found(db_with_client):
    db, client = db_with_client
    with patch("dars.lesson_plans.service._call_lp_assistant", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = LP_ASSISTANT_SUCCESS
        lp = await create_lesson_plan(db, client_id=client.id, request=LP_REQUEST)

    found = await get_lesson_plan(db, client_id=client.id, lp_id=lp.id)
    assert found is not None
    assert found.id == lp.id


async def test_get_lesson_plan_not_found(db_with_client):
    db, client = db_with_client
    found = await get_lesson_plan(db, client_id=client.id, lp_id=uuid.uuid4())
    assert found is None


async def test_get_lesson_plan_cross_client_isolation(db_with_client):
    db, client = db_with_client
    with patch("dars.lesson_plans.service._call_lp_assistant", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = LP_ASSISTANT_SUCCESS
        lp = await create_lesson_plan(db, client_id=client.id, request=LP_REQUEST)

    found = await get_lesson_plan(db, client_id=uuid.uuid4(), lp_id=lp.id)
    assert found is None


# --- Router tests ---

@pytest.fixture
def mock_client_obj():
    return Client(
        id=uuid.uuid4(),
        name="Test Team",
        api_key_hash="abc123",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
async def http_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_create_lp_requires_auth(http_client):
    response = await http_client.post("/api/v1/lesson-plans", json={})
    assert response.status_code == 401


async def test_create_lp_success(http_client, mock_client_obj):
    fake_lp = LessonPlan(
        id=uuid.uuid4(),
        client_id=mock_client_obj.id,
        grade="3",
        subject="Maths",
        page_number="10",
        status="READY",
        content="<html>LP</html>",
        content_bilingual=None,
        tags={},
        metadata_={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    with (
        patch("dars.deps.get_client_by_api_key", new_callable=AsyncMock, return_value=mock_client_obj),
        patch("dars.lesson_plans.router.create_lesson_plan", new_callable=AsyncMock, return_value=fake_lp),
    ):
        response = await http_client.post(
            "/api/v1/lesson-plans",
            headers={"X-API-Key": "dars_valid"},
            json={"grade": "3", "subject": "Maths", "page_number": "10"},
        )
    assert response.status_code == 201
    assert response.json()["status"] == "READY"


async def test_list_lps_requires_auth(http_client):
    response = await http_client.get("/api/v1/lesson-plans")
    assert response.status_code == 401


async def test_list_lps_success(http_client, mock_client_obj):
    with (
        patch("dars.deps.get_client_by_api_key", new_callable=AsyncMock, return_value=mock_client_obj),
        patch("dars.lesson_plans.router.list_lesson_plans", new_callable=AsyncMock, return_value=([], 0)),
    ):
        response = await http_client.get(
            "/api/v1/lesson-plans",
            headers={"X-API-Key": "dars_valid"},
        )
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


async def test_get_lp_not_found(http_client, mock_client_obj):
    with (
        patch("dars.deps.get_client_by_api_key", new_callable=AsyncMock, return_value=mock_client_obj),
        patch("dars.lesson_plans.router.get_lesson_plan", new_callable=AsyncMock, return_value=None),
    ):
        response = await http_client.get(
            f"/api/v1/lesson-plans/{uuid.uuid4()}",
            headers={"X-API-Key": "dars_valid"},
        )
    assert response.status_code == 404
