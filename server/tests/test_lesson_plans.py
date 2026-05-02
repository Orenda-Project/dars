"""
Lesson plan endpoint tests.

LP Assistant calls are mocked so tests run without network access.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import dars.clients.models  # noqa — register with Base
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
async def http_client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def authed_client(db_session):
    """Returns (http_client, api_key, client_obj) for an active client."""
    client_obj, raw_key = await create_client(db_session, name="Test Client")
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, raw_key, client_obj
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def authed_client_b(db_session):
    """A second independent client — for isolation tests."""
    client_obj, raw_key = await create_client(db_session, name="Client B")
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, raw_key, client_obj
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LP_PAYLOAD = {
    "grade": "5",
    "subject": "Maths",
    "page_number": "12",
    "curriculum": "ICT",
    "class_strength": 30,
}


def _mock_lp_assistant_ok():
    """Patch httpx so the LP Assistant call returns a successful response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "lesson_plan": "# Lesson content here",
        "lesson_plan_bilingual": None,
        "tags": {"topic": "fractions"},
        "metadata": {"duration": 45},
    }
    return mock_response


# ---------------------------------------------------------------------------
# POST /api/v1/lesson-plans
# ---------------------------------------------------------------------------


async def test_create_lesson_plan_returns_202_pending(authed_client):
    http, api_key, _ = authed_client

    # background task will run inline in test; mock LP assistant to avoid network
    with patch("dars.lesson_plans.service.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_mock_lp_assistant_ok())
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await http.post(
            "/api/v1/lesson-plans",
            headers={"X-API-Key": api_key},
            json=LP_PAYLOAD,
        )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "PENDING"
    assert "id" in data
    assert data["grade"] == "5"
    assert data["subject"] == "Maths"


async def test_create_lesson_plan_requires_auth(http_client):
    response = await http_client.post("/api/v1/lesson-plans", json=LP_PAYLOAD)
    assert response.status_code == 401


async def test_create_lesson_plan_with_webhook_url(authed_client):
    http, api_key, _ = authed_client

    with patch("dars.lesson_plans.service.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_mock_lp_assistant_ok())
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await http.post(
            "/api/v1/lesson-plans",
            headers={"X-API-Key": api_key},
            json={**LP_PAYLOAD, "webhook_url": "https://example.com/hook"},
        )

    assert response.status_code == 202
    data = response.json()
    assert data["webhook_url"] == "https://example.com/hook"


# ---------------------------------------------------------------------------
# GET /api/v1/lesson-plans/{id}
# ---------------------------------------------------------------------------


async def test_get_lesson_plan_by_id(authed_client):
    http, api_key, _ = authed_client

    with patch("dars.lesson_plans.service.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_mock_lp_assistant_ok())
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        create_resp = await http.post(
            "/api/v1/lesson-plans",
            headers={"X-API-Key": api_key},
            json=LP_PAYLOAD,
        )
    assert create_resp.status_code == 202
    lp_id = create_resp.json()["id"]

    get_resp = await http.get(
        f"/api/v1/lesson-plans/{lp_id}",
        headers={"X-API-Key": api_key},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == lp_id


async def test_get_lesson_plan_not_found(authed_client):
    http, api_key, _ = authed_client
    fake_id = str(uuid.uuid4())
    response = await http.get(
        f"/api/v1/lesson-plans/{fake_id}",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 404


async def test_get_lesson_plan_global(db_session):
    """LPs are global — any authenticated client can fetch by ID."""
    # Create two clients sharing the same db_session
    client_a, key_a = await create_client(db_session, name="Client A")
    client_b, key_b = await create_client(db_session, name="Client B")

    app.dependency_overrides[get_db] = lambda: db_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        with patch("dars.lesson_plans.service.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=_mock_lp_assistant_ok())
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # Client B creates an LP
            create_resp = await http.post(
                "/api/v1/lesson-plans",
                headers={"X-API-Key": key_b},
                json=LP_PAYLOAD,
            )
        assert create_resp.status_code == 202
        lp_id = create_resp.json()["id"]

        # LPs are global — Client A can also fetch Client B's LP
        get_resp = await http.get(
            f"/api/v1/lesson-plans/{lp_id}",
            headers={"X-API-Key": key_a},
        )
        assert get_resp.status_code == 200

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/v1/lesson-plans (list)
# ---------------------------------------------------------------------------


async def test_list_lesson_plans_global(db_session):
    """LPs are global — all authenticated clients see all lesson plans."""
    client_a, key_a = await create_client(db_session, name="List Client A")
    client_b, key_b = await create_client(db_session, name="List Client B")

    app.dependency_overrides[get_db] = lambda: db_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        with patch("dars.lesson_plans.service.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=_mock_lp_assistant_ok())
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # Client A creates 2 LPs
            for _ in range(2):
                r = await http.post(
                    "/api/v1/lesson-plans",
                    headers={"X-API-Key": key_a},
                    json=LP_PAYLOAD,
                )
                assert r.status_code == 202

            # Client B creates 1 LP
            r = await http.post(
                "/api/v1/lesson-plans",
                headers={"X-API-Key": key_b},
                json=LP_PAYLOAD,
            )
            assert r.status_code == 202

        list_a = await http.get("/api/v1/lesson-plans", headers={"X-API-Key": key_a})
        list_b = await http.get("/api/v1/lesson-plans", headers={"X-API-Key": key_b})

    assert list_a.status_code == 200
    # Global list — both clients see all 3 LPs
    assert list_a.json()["total"] == 3
    assert list_b.json()["total"] == 3

    app.dependency_overrides.clear()


async def test_list_lesson_plans_empty(authed_client):
    http, api_key, _ = authed_client
    response = await http.get("/api/v1/lesson-plans", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []
