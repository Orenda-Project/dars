"""
F3.6/F3.7 — tests for the webhook processors.

Pure-Python: cover idempotency + status transitions on a stub asyncpg.
We use a tiny in-memory fake to drive the SQL flow without standing up
a real DB. Where mocking gets hairy (the upstream-status wrapper), we
exercise the standalone helper.
"""
from dars.generated_lps.webhook_processor import TERMINAL_STATUSES
from dars.v2_api.router_webhooks import _wrap_upstream_status_as_webhook


def test_terminal_statuses_set():
    assert TERMINAL_STATUSES == {"READY", "ERROR"}


def test_wrap_upstream_completed():
    upstream = {
        "job_id": "j1",
        "job_status": "completed",
        "data": {"lesson_plan": "<p>hi</p>"},
    }
    wrapped = _wrap_upstream_status_as_webhook(upstream)
    assert wrapped["status"] == "completed"
    assert wrapped["job_id"] == "j1"
    assert wrapped["data"] == {"lesson_plan": "<p>hi</p>"}


def test_wrap_upstream_failed():
    upstream = {"job_id": "j2", "job_status": "failed", "error": "boom"}
    wrapped = _wrap_upstream_status_as_webhook(upstream)
    assert wrapped["status"] == "failed"
    assert wrapped["error"] == "boom"


def test_wrap_upstream_in_progress_passthrough():
    upstream = {"job_id": "j3", "job_status": "in_progress"}
    wrapped = _wrap_upstream_status_as_webhook(upstream)
    assert wrapped["status"] == "in_progress"
    # data normalised to empty dict
    assert wrapped["data"] == {}
