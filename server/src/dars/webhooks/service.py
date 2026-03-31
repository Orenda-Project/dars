import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from dars.webhooks.models import WebhookDelivery

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
# Retry delays in seconds: immediate, 30s, 5min. Attempts beyond index reuse the last value.
RETRY_DELAYS = [0, 30, 300]


async def deliver_webhook(
    db: AsyncSession,
    client_id: uuid.UUID,
    lesson_plan_id: uuid.UUID,
    webhook_url: str,
    event: str,
    payload: dict,
    max_attempts: int = MAX_ATTEMPTS,
) -> WebhookDelivery:
    delivery = WebhookDelivery(
        client_id=client_id,
        lesson_plan_id=lesson_plan_id,
        event=event,
        payload=payload,
        status="pending",
    )
    db.add(delivery)
    await db.commit()
    await db.refresh(delivery)

    for attempt in range(max_attempts):
        delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
        if delay > 0:
            await asyncio.sleep(delay)

        delivery.attempts += 1
        delivery.last_attempt_at = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                response = await http.post(webhook_url, json=payload)
            delivery.response_status = response.status_code
            if 200 <= response.status_code < 300:
                delivery.status = "delivered"
                delivery.next_attempt_at = None
                await db.commit()
                logger.info("Webhook delivered for event=%s lp=%s", event, lesson_plan_id)
                return delivery
            logger.warning(
                "Webhook attempt %d failed with status=%d for lp=%s",
                attempt + 1, response.status_code, lesson_plan_id,
            )
        except Exception as e:
            logger.warning(
                "Webhook attempt %d raised exception for lp=%s: %s",
                attempt + 1, lesson_plan_id, e,
            )

        # Set next_attempt_at if there are retries remaining
        is_last_attempt = attempt == max_attempts - 1
        if not is_last_attempt:
            next_delay = RETRY_DELAYS[attempt + 1] if attempt + 1 < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
            delivery.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=next_delay)
        await db.commit()

    delivery.status = "failed"
    delivery.next_attempt_at = None
    await db.commit()
    logger.error(
        "Webhook delivery failed after %d attempts for event=%s lp=%s",
        max_attempts, event, lesson_plan_id,
    )
    return delivery
