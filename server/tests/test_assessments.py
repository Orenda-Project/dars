"""
Assessment endpoint tests.

Anthropic API calls are mocked — no real network access.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import dars.assessments.models  # noqa — register with Base
import dars.clients.models  # noqa — register with Base
import dars.curriculum.models  # noqa — register with Base
from dars.assessments.models import Assessment
from dars.clients.service import create_client
from dars.curriculum.models import Book, BookChapter, Topic
from dars.database import Base, get_db
from dars.main import app

TEST_DB = "sqlite+aiosqlite:///:memory:"

MOCK_MCQS = [
    {
        "question": "What is the primary purpose of X?",
        "options": {"a": "Option A", "b": "Option B", "c": "Option C", "d": "Option D"},
        "answer": "b",
        "explanation": "Option B is correct because...",
    },
    {
        "question": "Which of the following best describes Y?",
        "options": {"a": "Option A", "b": "Option B", "c": "Option C", "d": "Option D"},
        "answer": "c",
        "explanation": "Option C is correct because...",
    },
]


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
    client_obj, raw_key = await create_client(db_session, name="Test Client")
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, raw_key, client_obj
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_book(db: AsyncSession, **kwargs) -> Book:
    defaults = {
        "core_id": 1,
        "curriculum": "ICT",
        "grade": 5,
        "subject": "Math",
        "title": "Math Book Grade 5",
    }
    defaults.update(kwargs)
    book = Book(**defaults)
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def _make_chapter(db: AsyncSession, book_id: uuid.UUID, **kwargs) -> BookChapter:
    defaults = {
        "core_id": 1,
        "book_id": book_id,
        "title": "Chapter 1",
        "chapter_number": 1,
    }
    defaults.update(kwargs)
    chapter = BookChapter(**defaults)
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return chapter


async def _make_topic(db: AsyncSession, chapter_id: uuid.UUID, **kwargs) -> Topic:
    defaults = {
        "chapter_id": chapter_id,
        "topic_number": 1,
        "title": "Topic One",
        "start_page": 5,
        "end_page": 10,
    }
    defaults.update(kwargs)
    topic = Topic(**defaults)
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic


def _mock_anthropic_response(mcqs: list = None):
    """Patch anthropic so the API call returns a successful MCQ response."""
    import json as _json

    if mcqs is None:
        mcqs = MOCK_MCQS

    mock_content = MagicMock()
    mock_content.text = _json.dumps(mcqs)

    mock_message = MagicMock()
    mock_message.content = [mock_content]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    return mock_client


# ---------------------------------------------------------------------------
# POST /api/v1/topics/{topic_id}/assessment
# ---------------------------------------------------------------------------


async def test_create_assessment_returns_201_pending(authed_client, db_session):
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1)
    topic = await _make_topic(db_session, chapter.id)

    with patch("dars.assessments.service.anthropic.AsyncAnthropic", return_value=_mock_anthropic_response()):
        response = await http.post(
            f"/api/v1/topics/{topic.id}/assessment",
            headers={"X-API-Key": api_key},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["topic_id"] == str(topic.id)
    assert "id" in data
    assert data["content"] is None
    assert data["content_json"] is None


async def test_create_assessment_requires_auth(authed_client, db_session):
    http, _, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1)
    topic = await _make_topic(db_session, chapter.id)

    response = await http.post(f"/api/v1/topics/{topic.id}/assessment")
    assert response.status_code == 401


async def test_create_assessment_topic_not_found(authed_client):
    http, api_key, _ = authed_client
    fake_id = str(uuid.uuid4())
    response = await http.post(
        f"/api/v1/topics/{fake_id}/assessment",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/assessments/{assessment_id}
# ---------------------------------------------------------------------------


async def test_get_assessment_by_id(authed_client, db_session):
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1)
    topic = await _make_topic(db_session, chapter.id)

    with patch("dars.assessments.service.anthropic.AsyncAnthropic", return_value=_mock_anthropic_response()):
        create_resp = await http.post(
            f"/api/v1/topics/{topic.id}/assessment",
            headers={"X-API-Key": api_key},
        )
    assert create_resp.status_code == 201
    assessment_id = create_resp.json()["id"]

    get_resp = await http.get(
        f"/api/v1/assessments/{assessment_id}",
        headers={"X-API-Key": api_key},
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == assessment_id
    assert data["topic_id"] == str(topic.id)


async def test_get_assessment_not_found(authed_client):
    http, api_key, _ = authed_client
    fake_id = str(uuid.uuid4())
    response = await http.get(
        f"/api/v1/assessments/{fake_id}",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 404


async def test_get_assessment_requires_auth(authed_client, db_session):
    http, _, _ = authed_client
    assessment = Assessment(topic_id=uuid.uuid4(), status="PENDING")
    db_session.add(assessment)
    await db_session.commit()
    await db_session.refresh(assessment)

    response = await http.get(f"/api/v1/assessments/{assessment.id}")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Regeneration — creating again for same topic replaces the old one
# ---------------------------------------------------------------------------


async def test_create_assessment_replaces_existing(authed_client, db_session):
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    chapter = await _make_chapter(db_session, book.id, core_id=1)
    topic = await _make_topic(db_session, chapter.id)

    with patch("dars.assessments.service.anthropic.AsyncAnthropic", return_value=_mock_anthropic_response()):
        first_resp = await http.post(
            f"/api/v1/topics/{topic.id}/assessment",
            headers={"X-API-Key": api_key},
        )
    assert first_resp.status_code == 201
    first_id = first_resp.json()["id"]

    with patch("dars.assessments.service.anthropic.AsyncAnthropic", return_value=_mock_anthropic_response()):
        second_resp = await http.post(
            f"/api/v1/topics/{topic.id}/assessment",
            headers={"X-API-Key": api_key},
        )
    assert second_resp.status_code == 201
    second_id = second_resp.json()["id"]

    assert first_id != second_id

    old_get = await http.get(
        f"/api/v1/assessments/{first_id}",
        headers={"X-API-Key": api_key},
    )
    assert old_get.status_code == 404

    new_get = await http.get(
        f"/api/v1/assessments/{second_id}",
        headers={"X-API-Key": api_key},
    )
    assert new_get.status_code == 200


# ---------------------------------------------------------------------------
# Service unit tests — _render_html and _extract_json_array
# ---------------------------------------------------------------------------


def test_extract_json_array_from_plain_json():
    from dars.assessments.service import _extract_json_array
    import json as _json

    mcqs = [{"question": "Q?", "options": {"a": "A"}, "answer": "a", "explanation": "E"}]
    result = _extract_json_array(_json.dumps(mcqs))
    assert result == mcqs


def test_extract_json_array_from_code_block():
    from dars.assessments.service import _extract_json_array

    raw = '```json\n[{"question": "Q?", "options": {}, "answer": "a", "explanation": "E"}]\n```'
    result = _extract_json_array(raw)
    assert len(result) == 1
    assert result[0]["question"] == "Q?"


def test_extract_json_array_empty_on_garbage():
    from dars.assessments.service import _extract_json_array

    result = _extract_json_array("not json at all")
    assert result == []


def test_render_html_marks_correct_answer():
    from dars.assessments.service import _render_html

    mcqs = [
        {
            "question": "What is 2+2?",
            "options": {"a": "3", "b": "4", "c": "5", "d": "6"},
            "answer": "b",
            "explanation": "Basic arithmetic.",
        }
    ]
    html = _render_html(mcqs)
    assert "Q1." in html
    assert "What is 2+2?" in html
    assert "<strong>b) 4</strong>" in html
    assert "Basic arithmetic." in html
