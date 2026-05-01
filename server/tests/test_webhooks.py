import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import dars.clients.models  # noqa — register FK targets
import dars.webhooks.models  # noqa
from dars.database import Base
from dars.webhooks.service import deliver_webhook

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


async def test_deliver_webhook_success(db_session):
    client_id = uuid.uuid4()
    lp_id = uuid.uuid4()
    payload = {"event": "lesson_plan.ready", "lesson_plan": {"id": str(lp_id)}}

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("dars.webhooks.service.httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        delivery = await deliver_webhook(
            db=db_session,
            client_id=client_id,
            lesson_plan_id=lp_id,
            webhook_url="https://example.com/hook",
            event="lesson_plan.ready",
            payload=payload,
        )

    assert delivery.status == "delivered"
    assert delivery.attempts == 1
    assert delivery.response_status == 200


async def test_deliver_webhook_failure_marks_failed_after_max_retries(db_session):
    client_id = uuid.uuid4()
    lp_id = uuid.uuid4()
    payload = {"event": "lesson_plan.error", "lesson_plan": {"id": str(lp_id)}}

    with patch("dars.webhooks.service.httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        delivery = await deliver_webhook(
            db=db_session,
            client_id=client_id,
            lesson_plan_id=lp_id,
            webhook_url="https://example.com/hook",
            event="lesson_plan.error",
            payload=payload,
            max_attempts=1,
        )

    assert delivery.status == "failed"
    assert delivery.attempts == 1
