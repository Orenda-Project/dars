"""
F3.8 — Post-generation LP tagging.

Background task triggered by the LP webhook (F3.6) after a generation
lands successfully. Loads the candidate sub-SLOs for the LP's topic,
calls into the shared tag_lp() (F3.1), persists `covered_sub_slo_ids`
and updates `tagging_status`.

For revision LPs (F3.10), the candidate set is the union of sub-SLOs
linked to ALL covered topics on the revision row.
"""
import json
import logging
from typing import Awaitable, Callable
from uuid import UUID

import asyncpg

from dars.breakdown.lp_tagging_service import (
    SubSLOCandidate,
    tag_lp as default_tag_lp,
)

log = logging.getLogger("generated_lps.tagging_service")

TagLPCallable = Callable[
    [str, list[SubSLOCandidate]],
    Awaitable["object"],  # actually TaggingResult; importing for typing only
]


async def _load_candidates_for_topic(
    conn: asyncpg.Connection, topic_id: UUID
) -> list[SubSLOCandidate]:
    rows = await conn.fetch(
        """
        SELECT ss.id, ss.code, ss.statement
        FROM topic_sub_slos tss
        JOIN sub_slos ss ON ss.id = tss.sub_slo_id
        WHERE tss.topic_id = $1
        ORDER BY ss.code
        """,
        topic_id,
    )
    return [{"id": r["id"], "code": r["code"], "statement": r["statement"]} for r in rows]


async def _load_candidates_for_revision(
    conn: asyncpg.Connection, generated_lp_id: UUID
) -> list[SubSLOCandidate]:
    """For revision LPs we don't have a single topic_id; we look up the
    `revision_topic_set_hash` membership via a side table written at
    revision-LP creation time (F3.10 reuses the generic topic_set table)."""
    rows = await conn.fetch(
        """
        SELECT DISTINCT ss.id, ss.code, ss.statement
        FROM generated_lp_revision_topics grt
        JOIN topic_sub_slos tss ON tss.topic_id = grt.topic_id
        JOIN sub_slos ss ON ss.id = tss.sub_slo_id
        WHERE grt.generated_lp_id = $1
        ORDER BY ss.code
        """,
        generated_lp_id,
    )
    return [{"id": r["id"], "code": r["code"], "statement": r["statement"]} for r in rows]


async def tag_generated_lp(
    conn: asyncpg.Connection,
    generated_lp_id: UUID,
    *,
    tag_lp: TagLPCallable | None = None,
) -> None:
    """
    Tag a successfully-generated LP and persist the result.

    Idempotent: if `tagging_status` is already 'done', this is a no-op.
    On any error, sets `tagging_status='failed'` but does NOT raise —
    LP usability is independent of tagging status (D-50-adjacent).
    """
    log.info("tag_generated_lp: entry id=%s", generated_lp_id)

    row = await conn.fetchrow(
        """
        SELECT id, status, tagging_status, content, topic_id,
               revision_topic_set_hash
        FROM generated_lps
        WHERE id = $1
        """,
        generated_lp_id,
    )
    if row is None:
        log.warning("tag_generated_lp: id=%s not found", generated_lp_id)
        return
    if row["status"] != "READY":
        log.info(
            "tag_generated_lp: id=%s status=%s — skipping",
            generated_lp_id, row["status"],
        )
        return
    if row["tagging_status"] == "done":
        log.info("tag_generated_lp: id=%s already tagged", generated_lp_id)
        return
    if not row["content"]:
        log.warning("tag_generated_lp: id=%s has empty content", generated_lp_id)
        await _mark_failed(conn, generated_lp_id, "empty content")
        return

    if row["topic_id"]:
        candidates = await _load_candidates_for_topic(conn, row["topic_id"])
    elif row["revision_topic_set_hash"]:
        candidates = await _load_candidates_for_revision(conn, generated_lp_id)
    else:
        log.warning(
            "tag_generated_lp: id=%s has neither topic_id nor revision set",
            generated_lp_id,
        )
        await _mark_failed(conn, generated_lp_id, "no candidate sub-SLOs available")
        return

    if not candidates:
        log.info(
            "tag_generated_lp: id=%s has no candidate sub-SLOs — marking done with empty cover",
            generated_lp_id,
        )
        await conn.execute(
            """
            UPDATE generated_lps
            SET covered_sub_slo_ids = ARRAY[]::UUID[],
                tagging_status = 'done', updated_at = now()
            WHERE id = $1
            """,
            generated_lp_id,
        )
        return

    tagger = tag_lp or default_tag_lp
    try:
        result = await tagger(row["content"], candidates)
    except Exception as exc:  # noqa: BLE001
        log.exception("tag_generated_lp: id=%s tagging failed", generated_lp_id)
        await _mark_failed(conn, generated_lp_id, f"tagging error: {exc}")
        return

    covered = list(result.covered_sub_slo_ids)
    await conn.execute(
        """
        UPDATE generated_lps
        SET covered_sub_slo_ids = $1::UUID[],
            tagging_status = 'done', updated_at = now()
        WHERE id = $2
        """,
        covered, generated_lp_id,
    )
    log.info(
        "tag_generated_lp: id=%s done covered_count=%d",
        generated_lp_id, len(covered),
    )


async def _mark_failed(
    conn: asyncpg.Connection, generated_lp_id: UUID, reason: str
) -> None:
    await conn.execute(
        """
        UPDATE generated_lps
        SET tagging_status = 'failed', updated_at = now()
        WHERE id = $1
        """,
        generated_lp_id,
    )
    log.info("tag_generated_lp: id=%s marked failed (%s)", generated_lp_id, reason)
