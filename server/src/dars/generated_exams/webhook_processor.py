"""
Shared logic for processing exam generation results — used by:
  - F3.6 webhook handler (POST /api/v1/webhooks/exam/{generated_exam_id})
  - F3.7 manual refresh   (POST /api/v1/generated-exams/{id}/refresh)
"""
import json
import logging
from uuid import UUID

import asyncpg

log = logging.getLogger("generated_exams.webhook_processor")


TERMINAL_STATUSES = {"READY", "ERROR"}


async def process_exam_result(
    conn: asyncpg.Connection,
    generated_exam_id: UUID,
    payload: dict,
) -> dict:
    """
    Apply a UG_EG webhook (or refresh) result to the row. Mirrors
    process_lp_result.
    """
    log.info(
        "process_exam_result: entry generated_exam_id=%s body_status=%s",
        generated_exam_id, payload.get("status"),
    )

    row = await conn.fetchrow(
        "SELECT id, status FROM generated_exams WHERE id = $1",
        generated_exam_id,
    )
    if row is None:
        log.warning("process_exam_result: id=%s not found", generated_exam_id)
        return {"action": "not_found", "status": None}

    if row["status"] in TERMINAL_STATUSES:
        log.info(
            "process_exam_result: id=%s already terminal (%s) — noop",
            generated_exam_id, row["status"],
        )
        return {"action": "noop", "status": row["status"]}

    upstream_status = payload.get("status")
    data = payload.get("data") or {}
    if upstream_status == "failed" or (upstream_status == "completed" and not data):
        err = payload.get("error") or data.get("error") or "upstream generation failed"
        await conn.execute(
            """
            UPDATE generated_exams
            SET status = 'ERROR', error_message = $1, updated_at = now(),
                ug_eg_response_raw = $2::JSONB
            WHERE id = $3
            """,
            str(err)[:2000], json.dumps(payload), generated_exam_id,
        )
        return {"action": "errored", "status": "ERROR"}

    if upstream_status != "completed":
        await conn.execute(
            """
            UPDATE generated_exams
            SET ug_eg_response_raw = $1::JSONB, updated_at = now()
            WHERE id = $2
            """,
            json.dumps(payload), generated_exam_id,
        )
        return {"action": "noop", "status": row["status"]}

    # UG_EG calls it `exam_json` in the reference doc; tolerate both names.
    exam_json = data.get("exam_json") or data.get("result") or {}
    exam_paper_html = data.get("exam_paper") or ""
    if not exam_json:
        await conn.execute(
            """
            UPDATE generated_exams
            SET status = 'ERROR', error_message = 'upstream returned empty exam_json',
                updated_at = now(),
                ug_eg_response_raw = $1::JSONB
            WHERE id = $2
            """,
            json.dumps(payload), generated_exam_id,
        )
        return {"action": "errored", "status": "ERROR"}

    metadata = data.get("metadata") or {}
    tokens_block = metadata.get("tokens") or {}
    cost_usd = metadata.get("total_cost_usd")
    if cost_usd is None:
        cost_usd = tokens_block.get("cost_usd")
    tokens_in = tokens_block.get("input_tokens")
    tokens_out = tokens_block.get("output_tokens")
    model = tokens_block.get("model")
    upstream_job_id = payload.get("job_id")

    await conn.execute(
        """
        UPDATE generated_exams
        SET status = 'READY',
            result = $1::JSONB,
            exam_paper_html = $2,
            cost_usd = $3,
            tokens_input = $4,
            tokens_output = $5,
            model = $6,
            job_id = COALESCE(job_id, $7),
            ug_eg_response_raw = $8::JSONB,
            updated_at = now()
        WHERE id = $9
        """,
        json.dumps(exam_json), exam_paper_html, cost_usd, tokens_in, tokens_out, model,
        upstream_job_id, json.dumps(payload), generated_exam_id,
    )
    log.info(
        "process_exam_result: id=%s stored READY html_chars=%d cost=%s",
        generated_exam_id, len(exam_paper_html), cost_usd,
    )
    return {"action": "stored", "status": "READY"}
