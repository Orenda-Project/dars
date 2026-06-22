"""
async-chapter-plan — background break-it-down job.

`break_down_chapter` (router_class_actions) no longer runs the planner inline. It
validates cheaply, flips the `class_chapters` row to PENDING, and dispatches
`run_chapter_plan_job` as a FastAPI BackgroundTask. The job runs the slow
planner LLM + slot persistence off the request path and records its outcome on
the `class_chapters` row's `status` / `error_message` columns; the frontend
polls `GET .../plan-status` until READY or ERROR.

The job opens its OWN asyncpg connection from a fresh DSN — it must NOT reuse the
request connection, which is released back to the pool the moment the 202
response is sent (mirrors `router_book_import._run_import_task`, D-8).
"""
import logging
from uuid import UUID

import asyncpg

from dars.breakdown.chapter_plan_service import generate_chapter_plan
from dars.config import settings
from dars.v2_api.deps import _asyncpg_url

log = logging.getLogger("breakdown.chapter_plan_jobs")


async def _set_status(
    conn: asyncpg.Connection,
    *,
    cst_id: UUID,
    book_chapter_id: UUID,
    org_id: UUID,
    status: str,
    error_message: str | None = None,
) -> None:
    """Set the (cst, chapter) class_chapters row status (+ optional error). Scoped
    by org_id (Critical Rule #3)."""
    await conn.execute(
        """
        UPDATE class_chapters
           SET status = $1, error_message = $2, updated_at = now()
         WHERE cst_id = $3 AND book_chapter_id = $4 AND org_id = $5
        """,
        status, error_message, cst_id, book_chapter_id, org_id,
    )


async def run_chapter_plan_job(
    cst_id: UUID,
    book_chapter_id: UUID,
    org_id: UUID,
) -> None:
    """
    Background break-it-down job. Opens its own connection, flips the
    `class_chapters` row GENERATING → READY (with slots persisted) or → ERROR
    (with the failure message), never leaving it stuck at GENERATING.

    No fallback (D-5): a planner failure is recorded as ERROR; the slot inserts
    inside `generate_chapter_plan` run in one transaction, so a failure leaves no
    half-written slots.
    """
    log.info(
        "run_chapter_plan_job: entry cst=%s chapter=%s org=%s",
        cst_id, book_chapter_id, org_id,
    )
    conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
    try:
        await _set_status(
            conn, cst_id=cst_id, book_chapter_id=book_chapter_id,
            org_id=org_id, status="GENERATING",
        )
        try:
            result = await generate_chapter_plan(
                conn, cst_id=cst_id, book_chapter_id=book_chapter_id,
                org_id=org_id,
            )
        except Exception as exc:
            # No fallback (D-5): record the failure so the FE poll surfaces it.
            # generate_chapter_plan wraps its inserts in a transaction, so a
            # failure leaves no half-written slots; the status update below is a
            # standalone statement on a clean connection.
            await _set_status(
                conn, cst_id=cst_id, book_chapter_id=book_chapter_id,
                org_id=org_id, status="ERROR", error_message=str(exc),
            )
            log.error(
                "run_chapter_plan_job: error cst=%s chapter=%s org=%s status=ERROR",
                cst_id, book_chapter_id, org_id, exc_info=True,
            )
            return

        await _set_status(
            conn, cst_id=cst_id, book_chapter_id=book_chapter_id,
            org_id=org_id, status="READY",
        )
        log.info(
            "run_chapter_plan_job: exit cst=%s chapter=%s org=%s status=READY "
            "slots=%d lessons=%d (flex=%d) assessments=%d",
            cst_id, book_chapter_id, org_id, result.slot_count,
            result.lesson_slot_count, result.flex_slot_count,
            result.assessment_slot_count,
        )
    finally:
        await conn.close()
