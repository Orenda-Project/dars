"""
Shared logic for processing LP generation results — used by:
  - F3.6 webhook handler (POST /api/v1/webhooks/lp/{generated_lp_id})
  - F3.7 manual refresh   (POST /api/v1/generated-lps/{id}/refresh)

Both paths converge here so the idempotency + audit + tagging trigger
is in one place.
"""
import json
import logging
from typing import Any
from uuid import UUID

import asyncpg

log = logging.getLogger("generated_lps.webhook_processor")


TERMINAL_STATUSES = {"READY", "ERROR"}


async def record_audit(
    conn: asyncpg.Connection, source: str, job_id: str, payload: dict
) -> UUID:
    """Insert a row into `webhook_events`. Always called regardless of
    whether processing succeeds, so we have an audit trail."""
    return await conn.fetchval(
        """
        INSERT INTO webhook_events (source, job_id, payload, processed)
        VALUES ($1, $2, $3::JSONB, FALSE)
        RETURNING id
        """,
        source, job_id or "", json.dumps(payload),
    )


async def mark_audit_processed(
    conn: asyncpg.Connection, audit_id: UUID
) -> None:
    await conn.execute(
        "UPDATE webhook_events SET processed = TRUE WHERE id = $1",
        audit_id,
    )


async def process_lp_result(
    conn: asyncpg.Connection,
    generated_lp_id: UUID,
    payload: dict,
) -> dict:
    """
    Apply an LP Assistant webhook (or refresh) result to the row.

    Returns a small dict describing what happened:
        { "action": "noop" | "stored" | "errored",
          "status": "READY" | "ERROR" | <current> }

    Behaviour:
      - Look up the row; 404 if missing.
      - If row.status is terminal (READY/ERROR), return noop.
      - If payload.status == "completed" and data is present → store
        content, cost, tokens, model; mark READY.
      - If payload.status == "failed" or data missing → mark ERROR with
        the upstream error message.

    The body's `job_id` is recorded into `generated_lps.job_id` if we
    didn't already have it. We do NOT 4xx on job_id mismatch — the
    cache row may have been created by another path; we trust the path
    UUID.
    """
    log.info(
        "process_lp_result: entry generated_lp_id=%s body_status=%s",
        generated_lp_id, payload.get("status"),
    )

    row = await conn.fetchrow(
        "SELECT id, status, job_id FROM generated_lps WHERE id = $1",
        generated_lp_id,
    )
    if row is None:
        log.warning("process_lp_result: generated_lp_id=%s not found", generated_lp_id)
        return {"action": "not_found", "status": None}

    if row["status"] in TERMINAL_STATUSES:
        log.info(
            "process_lp_result: id=%s already terminal (%s) — noop",
            generated_lp_id, row["status"],
        )
        return {"action": "noop", "status": row["status"]}

    upstream_status = payload.get("status")
    data = payload.get("data") or {}
    if upstream_status == "failed" or (upstream_status == "completed" and not data):
        err = payload.get("error") or data.get("error") or "upstream generation failed"
        await conn.execute(
            """
            UPDATE generated_lps
            SET status = 'ERROR', error_message = $1, updated_at = now(),
                lp_assistant_response_raw = $2::JSONB
            WHERE id = $3
            """,
            str(err)[:2000], json.dumps(payload), generated_lp_id,
        )
        return {"action": "errored", "status": "ERROR"}

    if upstream_status != "completed":
        # Still in flight upstream — record raw + leave status alone
        await conn.execute(
            """
            UPDATE generated_lps
            SET lp_assistant_response_raw = $1::JSONB, updated_at = now()
            WHERE id = $2
            """,
            json.dumps(payload), generated_lp_id,
        )
        return {"action": "noop", "status": row["status"]}

    content = data.get("lesson_plan") or ""
    bilingual = data.get("lesson_plan_bilingual") or None
    if not content:
        await conn.execute(
            """
            UPDATE generated_lps
            SET status = 'ERROR', error_message = 'upstream returned empty lesson_plan',
                updated_at = now(),
                lp_assistant_response_raw = $1::JSONB
            WHERE id = $2
            """,
            json.dumps(payload), generated_lp_id,
        )
        return {"action": "errored", "status": "ERROR"}

    metadata = data.get("metadata") or {}
    tokens_block = (metadata.get("tokens") or {}).get("lesson_plan_generation") or {}
    cost_usd = tokens_block.get("cost_usd")
    if cost_usd is None:
        # fallback to top-level total
        cost_usd = (metadata.get("tokens") or {}).get("costs", {}).get("total_usd")
    tokens_in = tokens_block.get("input_tokens")
    tokens_out = tokens_block.get("output_tokens")
    model = tokens_block.get("model")
    upstream_job_id = payload.get("job_id")

    await conn.execute(
        """
        UPDATE generated_lps
        SET status = 'READY',
            content = $1,
            content_bilingual = $2,
            cost_usd = $3,
            tokens_input = $4,
            tokens_output = $5,
            model = $6,
            job_id = COALESCE(job_id, $7),
            lp_assistant_response_raw = $8::JSONB,
            updated_at = now()
        WHERE id = $9
        """,
        content, bilingual, cost_usd, tokens_in, tokens_out, model,
        upstream_job_id, json.dumps(payload), generated_lp_id,
    )
    log.info(
        "process_lp_result: id=%s stored READY content_chars=%d cost=%s",
        generated_lp_id, len(content), cost_usd,
    )
    return {"action": "stored", "status": "READY"}
