"""
Exam generation endpoint tests.

EG Assistant calls are mocked so tests run without network access.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import dars.clients.models  # noqa — register with Base
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
async def http_client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def authed_client(db_session):
    """Returns (http_client, api_key, client_obj) for an active client."""
    client_obj, raw_key = await create_client(db_session, name="Test EG Client")
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, raw_key, client_obj
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EG_PAYLOAD = {
    "generation_type": "exam",
    "curriculum": "ICT",
    "grade": 5,
    "subject": "Eng",
    "page_ranges": "1-5, 10",
    "question_types": ["seen", "unseen"],
    "seen_categories": ["objective", "subjective"],
    "unseen_categories": ["objective"],
    "image_generation_enabled": False,
    "include_answer_key": False,
    "enable_review": False,
}


def _mock_eg_assistant_ok():
    """Patch httpx so the EG Assistant call returns a successful response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_error = False
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "exam": {"sections": []},
        "metadata": {"pages": "1-5, 10"},
    }
    return mock_response


# ---------------------------------------------------------------------------
# POST /api/v1/exam-generations
# ---------------------------------------------------------------------------


async def test_create_exam_generation_returns_202_pending(authed_client):
    http, api_key, _ = authed_client

    with patch("dars.exam_generations.service.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_mock_eg_assistant_ok())
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await http.post(
            "/api/v1/exam-generations",
            headers={"X-API-Key": api_key},
            json=EG_PAYLOAD,
        )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "PENDING"
    assert "id" in data
    assert data["grade"] == 5
    assert data["subject"] == "Eng"
    assert data["curriculum"] == "ICT"
    assert data["generation_type"] == "exam"


async def test_create_exam_generation_requires_auth(http_client):
    response = await http_client.post("/api/v1/exam-generations", json=EG_PAYLOAD)
    assert response.status_code == 401


async def test_create_exam_generation_with_webhook_url(authed_client):
    http, api_key, _ = authed_client

    with patch("dars.exam_generations.service.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_mock_eg_assistant_ok())
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await http.post(
            "/api/v1/exam-generations",
            headers={"X-API-Key": api_key},
            json={**EG_PAYLOAD, "webhook_url": "https://example.com/eg-hook"},
        )

    assert response.status_code == 202
    data = response.json()
    assert data["webhook_url"] == "https://example.com/eg-hook"


async def test_create_exam_generation_with_external_ref(authed_client):
    http, api_key, _ = authed_client

    with patch("dars.exam_generations.service.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_mock_eg_assistant_ok())
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await http.post(
            "/api/v1/exam-generations",
            headers={"X-API-Key": api_key},
            json={**EG_PAYLOAD, "external_ref": "school-term-1-exam"},
        )

    assert response.status_code == 202
    data = response.json()
    assert data["external_ref"] == "school-term-1-exam"


# ---------------------------------------------------------------------------
# GET /api/v1/exam-generations/{id}
# ---------------------------------------------------------------------------


async def test_get_exam_generation_by_id(authed_client):
    http, api_key, _ = authed_client

    with patch("dars.exam_generations.service.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_mock_eg_assistant_ok())
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        create_resp = await http.post(
            "/api/v1/exam-generations",
            headers={"X-API-Key": api_key},
            json=EG_PAYLOAD,
        )
    assert create_resp.status_code == 202
    eg_id = create_resp.json()["id"]

    get_resp = await http.get(
        f"/api/v1/exam-generations/{eg_id}",
        headers={"X-API-Key": api_key},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == eg_id


async def test_get_exam_generation_not_found(authed_client):
    http, api_key, _ = authed_client
    fake_id = str(uuid.uuid4())
    response = await http.get(
        f"/api/v1/exam-generations/{fake_id}",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 404


async def test_get_exam_generation_wrong_client(db_session):
    """Client A cannot fetch an exam generation belonging to Client B."""
    client_a, key_a = await create_client(db_session, name="EG Client A")
    client_b, key_b = await create_client(db_session, name="EG Client B")

    app.dependency_overrides[get_db] = lambda: db_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        with patch("dars.exam_generations.service.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=_mock_eg_assistant_ok())
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # Client B creates an exam generation
            create_resp = await http.post(
                "/api/v1/exam-generations",
                headers={"X-API-Key": key_b},
                json=EG_PAYLOAD,
            )
        assert create_resp.status_code == 202
        eg_id = create_resp.json()["id"]

        # Client A tries to fetch it — should 404
        get_resp = await http.get(
            f"/api/v1/exam-generations/{eg_id}",
            headers={"X-API-Key": key_a},
        )
        assert get_resp.status_code == 404

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/v1/exam-generations (list)
# ---------------------------------------------------------------------------


async def test_list_exam_generations_filtered_by_client(db_session):
    """Each client only sees their own exam generations."""
    client_a, key_a = await create_client(db_session, name="EG List Client A")
    client_b, key_b = await create_client(db_session, name="EG List Client B")

    app.dependency_overrides[get_db] = lambda: db_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        with patch("dars.exam_generations.service.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=_mock_eg_assistant_ok())
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # Client A creates 2 exam generations
            for _ in range(2):
                r = await http.post(
                    "/api/v1/exam-generations",
                    headers={"X-API-Key": key_a},
                    json=EG_PAYLOAD,
                )
                assert r.status_code == 202

            # Client B creates 1 exam generation
            r = await http.post(
                "/api/v1/exam-generations",
                headers={"X-API-Key": key_b},
                json=EG_PAYLOAD,
            )
            assert r.status_code == 202

        list_a = await http.get("/api/v1/exam-generations", headers={"X-API-Key": key_a})
        list_b = await http.get("/api/v1/exam-generations", headers={"X-API-Key": key_b})

    assert list_a.status_code == 200
    assert list_a.json()["total"] == 2

    assert list_b.status_code == 200
    assert list_b.json()["total"] == 1

    app.dependency_overrides.clear()


async def test_list_exam_generations_empty(authed_client):
    http, api_key, _ = authed_client
    response = await http.get("/api/v1/exam-generations", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


async def test_list_exam_generations_requires_auth(http_client):
    response = await http_client.get("/api/v1/exam-generations")
    assert response.status_code == 401
