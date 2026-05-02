"""
Tests for:
  POST /api/v1/custom-lesson-plans
  GET  /api/v1/custom-lesson-plans
  GET  /api/v1/custom-lesson-plans/{id}

Covers:
  - auth required
  - 422 if client has no curriculum
  - create with external_id, fetch by external_id filter
  - fetch by id
  - client isolation (client A can't see client B's LPs)
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import dars.assessments.models  # noqa — register with Base
import dars.clients.models  # noqa — register with Base
import dars.curriculum.models  # noqa — register with Base
import dars.custom_lesson_plans.models  # noqa — register with Base
import dars.custom_exam_generations.models  # noqa — register with Base
import dars.exam_generations.models  # noqa — register with Base
import dars.lesson_plans.models  # noqa — register with Base
import dars.webhooks.models  # noqa — register with Base
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
async def authed_client(db_session):
    """HTTP client + API key for a client that HAS a curriculum set."""
    import dars.config as _cfg

    original_secret = _cfg.settings.admin_secret
    _cfg.settings.admin_secret = "dev-secret"

    client_obj, raw_key = await create_client(db_session, name="Test Client")
    # Give the client a curriculum so LP creation works
    client_obj.curriculum = "ICT"
    await db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, raw_key, client_obj
    app.dependency_overrides.clear()
    _cfg.settings.admin_secret = original_secret


@pytest.fixture(scope="function")
async def authed_client_no_curriculum(db_session):
    """HTTP client + API key for a client that has NO curriculum."""
    import dars.config as _cfg

    original_secret = _cfg.settings.admin_secret
    _cfg.settings.admin_secret = "dev-secret"

    client_obj, raw_key = await create_client(db_session, name="No Curriculum Client")
    # curriculum stays None

    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, raw_key, client_obj
    app.dependency_overrides.clear()
    _cfg.settings.admin_secret = original_secret


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LP_PAYLOAD = {
    "grade": 3,
    "subject": "Eng",
    "topic": "Nouns",
    "page_number": "10",
}


def _mock_lp_response():
    """Return a mock httpx response that simulates LP assistant success."""
    mock_resp = MagicMock()
    mock_resp.is_error = False
    mock_resp.json.return_value = {
        "lesson_plan": "Lesson content here",
        "lesson_plan_bilingual": None,
        "tags": {"key": "val"},
        "metadata": {},
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


async def test_create_custom_lp_requires_auth(authed_client):
    http, _, _ = authed_client
    response = await http.post("/api/v1/custom-lesson-plans", json=LP_PAYLOAD)
    assert response.status_code == 401


async def test_list_custom_lps_requires_auth(authed_client):
    http, _, _ = authed_client
    response = await http.get("/api/v1/custom-lesson-plans")
    assert response.status_code == 401


async def test_get_custom_lp_requires_auth(authed_client):
    http, _, _ = authed_client
    fake_id = str(uuid.uuid4())
    response = await http.get(f"/api/v1/custom-lesson-plans/{fake_id}")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 422 when client has no curriculum
# ---------------------------------------------------------------------------


async def test_create_custom_lp_no_curriculum_raises_422(authed_client_no_curriculum):
    http, api_key, _ = authed_client_no_curriculum
    response = await http.post(
        "/api/v1/custom-lesson-plans",
        json=LP_PAYLOAD,
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 422
    assert "curriculum" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Create + list + get by id
# ---------------------------------------------------------------------------


async def test_create_custom_lp_returns_202_pending(authed_client):
    http, api_key, _ = authed_client

    with patch("dars.custom_lesson_plans.router.generate_custom_lesson_plan_task", new=AsyncMock()):
        response = await http.post(
            "/api/v1/custom-lesson-plans",
            json=LP_PAYLOAD,
            headers={"X-API-Key": api_key},
        )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["curriculum"] == "ICT"
    assert data["grade"] == "3"
    assert "id" in data
    assert "client_id" in data


async def test_create_custom_lp_with_external_id(authed_client):
    http, api_key, _ = authed_client
    payload = {**LP_PAYLOAD, "external_id": "teacher-42"}

    with patch("dars.custom_lesson_plans.router.generate_custom_lesson_plan_task", new=AsyncMock()):
        response = await http.post(
            "/api/v1/custom-lesson-plans",
            json=payload,
            headers={"X-API-Key": api_key},
        )
    assert response.status_code == 202
    data = response.json()
    assert data["external_id"] == "teacher-42"


async def test_list_custom_lps_empty(authed_client):
    http, api_key, _ = authed_client
    response = await http.get(
        "/api/v1/custom-lesson-plans",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_list_custom_lps_shows_created(authed_client):
    http, api_key, _ = authed_client

    with patch("dars.custom_lesson_plans.router.generate_custom_lesson_plan_task", new=AsyncMock()):
        await http.post(
            "/api/v1/custom-lesson-plans",
            json=LP_PAYLOAD,
            headers={"X-API-Key": api_key},
        )

    response = await http.get(
        "/api/v1/custom-lesson-plans",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


async def test_list_custom_lps_filter_by_external_id(authed_client):
    http, api_key, _ = authed_client

    with patch("dars.custom_lesson_plans.router.generate_custom_lesson_plan_task", new=AsyncMock()):
        await http.post(
            "/api/v1/custom-lesson-plans",
            json={**LP_PAYLOAD, "external_id": "teacher-A"},
            headers={"X-API-Key": api_key},
        )
        await http.post(
            "/api/v1/custom-lesson-plans",
            json={**LP_PAYLOAD, "external_id": "teacher-B"},
            headers={"X-API-Key": api_key},
        )

    # Filter by teacher-A only
    response = await http.get(
        "/api/v1/custom-lesson-plans?external_id=teacher-A",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["external_id"] == "teacher-A"


async def test_get_custom_lp_by_id(authed_client):
    http, api_key, _ = authed_client

    with patch("dars.custom_lesson_plans.router.generate_custom_lesson_plan_task", new=AsyncMock()):
        create_resp = await http.post(
            "/api/v1/custom-lesson-plans",
            json=LP_PAYLOAD,
            headers={"X-API-Key": api_key},
        )
    created_id = create_resp.json()["id"]

    response = await http.get(
        f"/api/v1/custom-lesson-plans/{created_id}",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_id


async def test_get_custom_lp_not_found(authed_client):
    http, api_key, _ = authed_client
    fake_id = str(uuid.uuid4())
    response = await http.get(
        f"/api/v1/custom-lesson-plans/{fake_id}",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Client isolation
# ---------------------------------------------------------------------------


async def test_client_isolation(db_session):
    """Client A cannot see Client B's custom lesson plans."""
    import dars.config as _cfg

    original_secret = _cfg.settings.admin_secret
    _cfg.settings.admin_secret = "dev-secret"

    client_a, key_a = await create_client(db_session, name="Client A")
    client_a.curriculum = "ICT"
    client_b, key_b = await create_client(db_session, name="Client B")
    client_b.curriculum = "ICT"
    await db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            # Client A creates an LP
            with patch(
                "dars.custom_lesson_plans.router.generate_custom_lesson_plan_task",
                new=AsyncMock(),
            ):
                create_resp = await http.post(
                    "/api/v1/custom-lesson-plans",
                    json=LP_PAYLOAD,
                    headers={"X-API-Key": key_a},
                )
            assert create_resp.status_code == 202
            lp_id = create_resp.json()["id"]

            # Client B lists — should see nothing
            list_resp = await http.get(
                "/api/v1/custom-lesson-plans",
                headers={"X-API-Key": key_b},
            )
            assert list_resp.status_code == 200
            assert list_resp.json()["total"] == 0

            # Client B fetches by ID — should get 404
            get_resp = await http.get(
                f"/api/v1/custom-lesson-plans/{lp_id}",
                headers={"X-API-Key": key_b},
            )
            assert get_resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
        _cfg.settings.admin_secret = original_secret
