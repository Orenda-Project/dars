"""
F3.6 — Webhook endpoints called by LP Assistant + UG_EG.
F3.7 — Manual refresh endpoints for local dev / debugging.

Path convention: callback URLs sent in F3.4/F3.5 contain our row UUID
(generated_lps.id or generated_exams.id), not the upstream job_id —
that's what we have at dispatch time. The webhook body still carries
the upstream `job_id`; we persist it for debugging.

Auth: X-Webhook-Secret header, hmac.compare_digest against the env
secret (D-41, Critical Rule #5). Refusal: 403.

Idempotency (D-43): each call records an audit row in webhook_events
regardless, then `process_*_result` no-ops if the target row is already
in a terminal state.
"""
import hmac
import json
import logging
from typing import Any
from uuid import UUID

import asyncpg
import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status

from dars.config import settings
from dars.generated_exams.tagging_service import tag_generated_exam
from dars.generated_exams.webhook_processor import (
    process_exam_result,
)
from dars.generated_lps.tagging_service import tag_generated_lp
from dars.generated_lps.webhook_processor import (
    mark_audit_processed,
    process_lp_result,
    record_audit,
)
from dars.v2_api.deps import get_db_conn, get_db_pool

log = logging.getLogger("v2_api.webhooks")

router = APIRouter(prefix="/api/v1", tags=["webhooks"])


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _verify_secret(received: str | None, expected: str) -> None:
    """Constant-time compare; refuse if expected is unconfigured."""
    if not expected:
        log.warning("webhook secret is unconfigured on this server — refusing")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhook auth not configured",
        )
    if not received or not hmac.compare_digest(received, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bad webhook secret",
        )


# ---------------------------------------------------------------------------
# Background task wrappers — open a fresh connection for the task because
# the request-scoped one is released before the task runs.
# ---------------------------------------------------------------------------


async def _bg_tag_lp(generated_lp_id: UUID) -> None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            await tag_generated_lp(conn, generated_lp_id)
        except Exception:  # noqa: BLE001
            log.exception("bg_tag_lp failed for id=%s", generated_lp_id)


async def _bg_tag_exam(generated_exam_id: UUID) -> None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            await tag_generated_exam(conn, generated_exam_id)
        except Exception:  # noqa: BLE001
            log.exception("bg_tag_exam failed for id=%s", generated_exam_id)


# ---------------------------------------------------------------------------
# F3.6 — LP webhook
# ---------------------------------------------------------------------------


@router.post("/webhooks/lp/{generated_lp_id}")
async def lp_webhook(
    generated_lp_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> dict:
    _verify_secret(x_webhook_secret, settings.lp_assistant_webhook_secret)

    try:
        payload = await request.json()
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="webhook body must be a JSON object")

    upstream_job_id = payload.get("job_id") or ""
    audit_id = await record_audit(conn, "lp_assistant", upstream_job_id, payload)

    result = await process_lp_result(conn, generated_lp_id, payload)
    await mark_audit_processed(conn, audit_id)

    if result.get("action") == "not_found":
        raise HTTPException(status_code=404, detail="generated_lp not found")
    if result.get("status") == "READY":
        background_tasks.add_task(_bg_tag_lp, generated_lp_id)

    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# F3.6 — Exam webhook
# ---------------------------------------------------------------------------


@router.post("/webhooks/exam/{generated_exam_id}")
async def exam_webhook(
    generated_exam_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> dict:
    _verify_secret(x_webhook_secret, settings.ug_eg_webhook_secret)

    try:
        payload = await request.json()
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="webhook body must be a JSON object")

    upstream_job_id = payload.get("job_id") or ""
    audit_id = await record_audit(conn, "ug_eg", upstream_job_id, payload)

    result = await process_exam_result(conn, generated_exam_id, payload)
    await mark_audit_processed(conn, audit_id)

    if result.get("action") == "not_found":
        raise HTTPException(status_code=404, detail="generated_exam not found")
    if result.get("status") == "READY":
        background_tasks.add_task(_bg_tag_exam, generated_exam_id)

    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# F3.7 — Manual refresh endpoints
# ---------------------------------------------------------------------------


async def _fetch_upstream_lp_status(job_id: str) -> dict:
    if not settings.lp_assistant_api_key:
        raise HTTPException(status_code=500, detail="LP_ASSISTANT_API_KEY not configured")
    url = (
        settings.lp_assistant_url.rstrip("/")
        + f"/api/webhook-status/{job_id}"
    )
    headers = {"api-key": settings.lp_assistant_api_key}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="upstream job not found")
    response.raise_for_status()
    return response.json()


async def _fetch_upstream_exam_status(job_id: str) -> dict:
    if not settings.eg_assistant_api_key:
        raise HTTPException(status_code=500, detail="UG_EG_API_KEY not configured")
    url = (
        settings.eg_assistant_url.rstrip("/")
        + f"/api/v2/webhook-status/{job_id}"
    )
    headers = {"api-key": settings.eg_assistant_api_key}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="upstream job not found")
    response.raise_for_status()
    return response.json()


def _wrap_upstream_status_as_webhook(upstream: dict) -> dict:
    """
    Upstream's GET /webhook-status response has `job_status` not `status`,
    and the result lives under `data`. Convert to the same shape webhook
    callbacks use so we can re-use process_*_result.
    """
    job_status = upstream.get("job_status") or upstream.get("status") or "in_progress"
    return {
        "job_id": upstream.get("job_id") or "",
        "status": "completed" if job_status == "completed" else
                  "failed" if job_status == "failed" else job_status,
        "data": upstream.get("data") or upstream.get("result") or {},
        "error": upstream.get("error"),
    }


@router.post("/generated-lps/{generated_lp_id}/refresh")
async def refresh_lp(
    generated_lp_id: UUID,
    background_tasks: BackgroundTasks,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> dict:
    row = await conn.fetchrow(
        "SELECT id, status, job_id FROM generated_lps WHERE id = $1",
        generated_lp_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="generated_lp not found")
    if row["status"] in {"READY", "ERROR"}:
        return {"ok": True, "action": "noop", "status": row["status"]}
    if not row["job_id"]:
        raise HTTPException(
            status_code=409,
            detail="no upstream job_id recorded yet; nothing to refresh",
        )

    upstream = await _fetch_upstream_lp_status(row["job_id"])
    wrapped = _wrap_upstream_status_as_webhook(upstream)
    audit_id = await record_audit(conn, "lp_assistant", row["job_id"], wrapped)
    result = await process_lp_result(conn, generated_lp_id, wrapped)
    await mark_audit_processed(conn, audit_id)

    if result.get("status") == "READY":
        background_tasks.add_task(_bg_tag_lp, generated_lp_id)
    return {"ok": True, **result}


@router.post("/generated-exams/{generated_exam_id}/refresh")
async def refresh_exam(
    generated_exam_id: UUID,
    background_tasks: BackgroundTasks,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> dict:
    row = await conn.fetchrow(
        "SELECT id, status, job_id FROM generated_exams WHERE id = $1",
        generated_exam_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="generated_exam not found")
    if row["status"] in {"READY", "ERROR"}:
        return {"ok": True, "action": "noop", "status": row["status"]}
    if not row["job_id"]:
        raise HTTPException(
            status_code=409,
            detail="no upstream job_id recorded yet; nothing to refresh",
        )

    upstream = await _fetch_upstream_exam_status(row["job_id"])
    wrapped = _wrap_upstream_status_as_webhook(upstream)
    audit_id = await record_audit(conn, "ug_eg", row["job_id"], wrapped)
    result = await process_exam_result(conn, generated_exam_id, wrapped)
    await mark_audit_processed(conn, audit_id)

    if result.get("status") == "READY":
        background_tasks.add_task(_bg_tag_exam, generated_exam_id)
    return {"ok": True, **result}
