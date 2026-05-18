"""
F3.6 — HTTP-level smoke tests for the webhook router.

Covers the auth + idempotency layer that's hard to exercise from unit
tests alone. The actual DB writes are deferred to the DB-gated tests
(test_generated_lps_service.py et al.).
"""
import json
import os

import pytest

ADMIN_TOKEN = "test-admin-token-f3"
os.environ.setdefault("DARS_ADMIN_TOKEN", ADMIN_TOKEN)
os.environ.setdefault("LP_ASSISTANT_WEBHOOK_SECRET", "lp-secret-for-tests")
os.environ.setdefault("UG_EG_WEBHOOK_SECRET", "eg-secret-for-tests")

from dars.config import settings  # noqa: E402

# Pydantic-settings reads env at import time; force-update if the test
# is rerun in-process with different env.
object.__setattr__(settings, "lp_assistant_webhook_secret", "lp-secret-for-tests")
object.__setattr__(settings, "ug_eg_webhook_secret", "eg-secret-for-tests")


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="HTTP webhook smoke needs a DB to hit (via get_db_conn dep).",
)
class TestWebhookSecretGate:
    async def test_lp_webhook_rejects_missing_secret(self, client):
        r = await client.post(
            "/api/v1/webhooks/lp/00000000-0000-0000-0000-000000000000",
            json={"job_id": "j", "status": "completed"},
        )
        assert r.status_code == 403

    async def test_lp_webhook_rejects_wrong_secret(self, client):
        r = await client.post(
            "/api/v1/webhooks/lp/00000000-0000-0000-0000-000000000000",
            json={"job_id": "j", "status": "completed"},
            headers={"X-Webhook-Secret": "WRONG"},
        )
        assert r.status_code == 403

    async def test_lp_webhook_404_on_unknown_row(self, client):
        r = await client.post(
            "/api/v1/webhooks/lp/00000000-0000-0000-0000-000000000000",
            json={"job_id": "j", "status": "completed", "data": {"lesson_plan": "<p>x</p>"}},
            headers={"X-Webhook-Secret": "lp-secret-for-tests"},
        )
        # Audit row still recorded, but the target row doesn't exist
        assert r.status_code == 404

    async def test_exam_webhook_rejects_missing_secret(self, client):
        r = await client.post(
            "/api/v1/webhooks/exam/00000000-0000-0000-0000-000000000000",
            json={"job_id": "j", "status": "completed"},
        )
        assert r.status_code == 403
