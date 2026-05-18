"""
F3.11 — Batch generation on breakdown publish.

When a breakdown is published, fire async generation for every slot
whose LP/Exam isn't yet cached. Cache hits cost nothing; misses fire
new requests upstream.

This module exposes:
    enqueue_for_breakdown(conn, breakdown_id) -> dict
        Synchronous: iterates the breakdown's slots, calls into the
        cache services (which insert + dispatch on miss). Returns the
        same counts shape the status endpoint uses.

    generation_status_for_breakdown(conn, breakdown_id) -> dict
        Reads counts off generated_lps/generated_exams joined back via
        the breakdown's slots.

Scope semantics:
    - For 'class' breakdowns: we iterate class_lesson_slots /
      class_assessment_slots which the realize step (F2.9) has already
      created.
    - For 'global'/'org' breakdowns: we iterate breakdown_slots /
      breakdown_slot_topics directly, without per-CST linkage. This
      pre-warms the global cache so later class-scope publishes get
      cache hits.
"""
import json
import logging
from typing import Awaitable, Callable
from uuid import UUID

import asyncpg

from dars.generated_exams.service import (
    DispatchCallable as ExamDispatch,
    ExamSlotContext,
    build_cache_key_global as build_exam_cache_key_global,
    build_question_config,
    get_or_generate_exam,
    hash_question_config,
    hash_topic_ids,
    load_assessment_slot_context,
)
from dars.generated_exams.ug_eg_client import (
    ExamRequest,
    request_exam_generation as default_request_exam_generation,
)
from dars.generated_lps.lp_assistant_client import (
    LPRequest,
    request_lp_generation as default_request_lp_generation,
)
from dars.generated_lps.service import (
    DispatchCallable as LPDispatch,
    _build_cache_key_global as build_lp_cache_key_global,
    _build_callback_url as build_lp_callback_url,
    _parse_grade_int,
    get_or_generate_lp,
    get_or_generate_revision_lp,
)

log = logging.getLogger("generated_lps.batch_service")


# ---------------------------------------------------------------------------
# Default per-subject FA/SA configs (D-46)
#
# These are the configs used to pre-warm the EXAM cache for global/org
# breakdowns. Class-scope publishes already have per-slot configs
# stored at realize time — those paths use the slot's own config.
# ---------------------------------------------------------------------------


DEFAULT_FA_CONFIG = {
    "Eng": {
        "question_types": ["unseen"],
        "unseen_categories": ["objective"],
        "unseen_objective_types": ["MCQs", "True/False", "Fill in the Blanks"],
        "unseen_subjective_types": [],
        "unseen_objective_counts": {"MCQs": 5, "True/False": 3, "Fill in the Blanks": 2},
        "unseen_subjective_counts": {},
    },
}

DEFAULT_SA_CONFIG = {
    "Eng": {
        "question_types": ["unseen"],
        "unseen_categories": ["objective", "subjective"],
        "unseen_objective_types": ["MCQs", "True/False", "Fill in the Blanks"],
        "unseen_subjective_types": ["Brief Answers", "Word Meanings"],
        "unseen_objective_counts": {"MCQs": 6, "True/False": 3, "Fill in the Blanks": 3},
        "unseen_subjective_counts": {"Brief Answers": 4, "Word Meanings": 2},
    },
}


def _config_for(subject_code: str, slot_type: str) -> dict | None:
    """Return the default exam config for a (subject, slot_type) pair, or None
    if we don't know what to send. Unknown combos cause the slot to be skipped
    (logged WARNING), not 500'd — the user can still publish."""
    if slot_type == "formative_assessment":
        return DEFAULT_FA_CONFIG.get(subject_code)
    if slot_type == "summative_assessment":
        return DEFAULT_SA_CONFIG.get(subject_code)
    return None


# ---------------------------------------------------------------------------
# Direct upstream dispatch for non-class scopes (no slot link).
# ---------------------------------------------------------------------------


async def _ensure_global_lp_for_topic(
    conn: asyncpg.Connection,
    *,
    curriculum_id: UUID,
    curriculum_code: str,
    grade_id: UUID,
    grade_code: str,
    subject_id: UUID,
    subject_code: str,
    topic_id: UUID,
    topic_text: str,
    lp_type: str,
    lp_dispatcher: LPDispatch,
) -> str:
    """Cache-first global LP creation that's NOT tied to a class slot.

    Returns one of: 'hit' (already existed), 'dispatched' (new request fired),
    'errored' (insert succeeded but dispatch failed), 'skipped' (no topic_text).
    """
    if not topic_text or not topic_text.strip():
        return "skipped"

    cache_key = build_lp_cache_key_global(curriculum_id, topic_id, lp_type)
    existing = await conn.fetchrow(
        "SELECT id, status FROM generated_lps WHERE cache_key = $1 AND scope = 'global'",
        cache_key,
    )
    if existing is not None and existing["status"] != "ERROR":
        return "hit"

    new_id = await conn.fetchval(
        """
        INSERT INTO generated_lps (
            cache_key, scope, scope_ref_id,
            curriculum_id, grade_id, subject_id,
            topic_id, lp_type, status
        )
        VALUES ($1, 'global', NULL, $2, $3, $4, $5, $6, 'PENDING')
        RETURNING id
        """,
        cache_key, curriculum_id, grade_id, subject_id, topic_id, lp_type,
    )

    try:
        payload = LPRequest(
            curriculum_code=curriculum_code,
            grade=_parse_grade_int(grade_code),
            subject=subject_code,
            page_content=topic_text,
            lp_type=lp_type,
            callback_url=build_lp_callback_url(new_id),
        )
        job_id = await lp_dispatcher(payload)
        await conn.execute(
            "UPDATE generated_lps SET status = 'IN_FLIGHT', job_id = $1, updated_at = now() WHERE id = $2",
            job_id, new_id,
        )
        return "dispatched"
    except Exception as exc:  # noqa: BLE001
        log.exception("_ensure_global_lp_for_topic: dispatch failed id=%s", new_id)
        await conn.execute(
            "UPDATE generated_lps SET status = 'ERROR', error_message = $1, updated_at = now() WHERE id = $2",
            f"dispatch failed: {exc}"[:2000], new_id,
        )
        return "errored"


async def _ensure_global_exam_for_slot(
    conn: asyncpg.Connection,
    *,
    curriculum_id: UUID,
    curriculum_code: str,
    grade_id: UUID,
    grade_code: str,
    subject_id: UUID,
    subject_code: str,
    topic_ids: list[UUID],
    page_content: str,
    generation_type: str,
    config: dict,
    eg_dispatcher: ExamDispatch,
) -> str:
    """Cache-first global exam creation, not tied to a class slot."""
    if not page_content or not page_content.strip():
        return "skipped"

    payload = ExamRequest(
        curriculum_code=curriculum_code,
        grade=_parse_grade_int(grade_code),
        subject=subject_code,
        page_content=page_content,
        callback_url="placeholder",  # overwritten below
        generation_type=generation_type,
        question_types=list(config.get("question_types") or ["unseen"]),
        unseen_categories=list(config.get("unseen_categories") or []),
        unseen_objective_types=list(config.get("unseen_objective_types") or []),
        unseen_subjective_types=list(config.get("unseen_subjective_types") or []),
        unseen_objective_counts=dict(config.get("unseen_objective_counts") or {}),
        unseen_subjective_counts=dict(config.get("unseen_subjective_counts") or {}),
        long_question_sub_types=list(config.get("long_question_sub_types") or []),
        include_answer_key=bool(config.get("include_answer_key", True)),
    )
    cfg_hash = hash_question_config(build_question_config(payload))
    topic_hash = hash_topic_ids(topic_ids)
    cache_key = build_exam_cache_key_global(
        curriculum_id, topic_hash, generation_type, cfg_hash
    )

    existing = await conn.fetchrow(
        "SELECT id, status FROM generated_exams WHERE cache_key = $1 AND scope = 'global'",
        cache_key,
    )
    if existing is not None and existing["status"] != "ERROR":
        return "hit"

    new_id = await conn.fetchval(
        """
        INSERT INTO generated_exams (
            cache_key, scope, scope_ref_id,
            curriculum_id, grade_id, subject_id,
            topic_ids_hash, generation_type, question_config_hash,
            status
        )
        VALUES ($1, 'global', NULL, $2, $3, $4, $5, $6, $7, 'PENDING')
        RETURNING id
        """,
        cache_key, curriculum_id, grade_id, subject_id,
        topic_hash, generation_type, cfg_hash,
    )

    try:
        from dars.config import settings as _settings
        callback_url = f"{_settings.dars_base_url.rstrip('/')}/api/v1/webhooks/exam/{new_id}"
        request = ExamRequest(
            **{**payload.model_dump(), "callback_url": callback_url}
        )
        job_id = await eg_dispatcher(request)
        await conn.execute(
            "UPDATE generated_exams SET status = 'IN_FLIGHT', job_id = $1, updated_at = now() WHERE id = $2",
            job_id, new_id,
        )
        return "dispatched"
    except Exception as exc:  # noqa: BLE001
        log.exception("_ensure_global_exam_for_slot: dispatch failed id=%s", new_id)
        await conn.execute(
            "UPDATE generated_exams SET status = 'ERROR', error_message = $1, updated_at = now() WHERE id = $2",
            f"dispatch failed: {exc}"[:2000], new_id,
        )
        return "errored"


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


async def enqueue_for_breakdown(
    conn: asyncpg.Connection,
    breakdown_id: UUID,
    *,
    lp_dispatcher: LPDispatch | None = None,
    eg_dispatcher: ExamDispatch | None = None,
) -> dict:
    """
    Walk the breakdown's slots and ensure every one has a generation in
    flight (or cached). Idempotent: calling repeatedly only triggers
    misses; existing READY/PENDING/IN_FLIGHT rows are reused.

    Returns:
        {
          "lp": {"hit": int, "dispatched": int, "errored": int, "skipped": int},
          "exam": {...same...},
        }
    """
    lp_dispatch = lp_dispatcher or default_request_lp_generation
    eg_dispatch = eg_dispatcher or default_request_exam_generation

    bd = await conn.fetchrow(
        """
        SELECT b.id, b.scope, b.scope_ref_id, b.curriculum_id, b.grade_id,
               b.subject_id, c.code AS curriculum_code, g.code AS grade_code,
               s.code AS subject_code, b.status
        FROM breakdowns b
        JOIN curriculums c ON c.id = b.curriculum_id
        JOIN grades g      ON g.id = b.grade_id
        JOIN subjects s    ON s.id = b.subject_id
        WHERE b.id = $1
        """,
        breakdown_id,
    )
    if bd is None:
        raise ValueError(f"breakdown_id={breakdown_id} not found")
    if bd["status"] != "published":
        log.info(
            "enqueue_for_breakdown: id=%s status=%s — proceeding anyway (caller's call)",
            breakdown_id, bd["status"],
        )

    lp_counts = {"hit": 0, "dispatched": 0, "errored": 0, "skipped": 0}
    exam_counts = {"hit": 0, "dispatched": 0, "errored": 0, "skipped": 0}

    if bd["scope"] == "class":
        await _enqueue_class_scope(
            conn, breakdown_id, bd, lp_dispatch, eg_dispatch, lp_counts, exam_counts,
        )
    else:
        await _enqueue_non_class_scope(
            conn, breakdown_id, bd, lp_dispatch, eg_dispatch, lp_counts, exam_counts,
        )

    log.info(
        "enqueue_for_breakdown: id=%s scope=%s lp=%s exam=%s",
        breakdown_id, bd["scope"], lp_counts, exam_counts,
    )
    return {"lp": lp_counts, "exam": exam_counts}


async def _enqueue_class_scope(
    conn: asyncpg.Connection,
    breakdown_id: UUID,
    bd: asyncpg.Record,
    lp_dispatch: LPDispatch,
    eg_dispatch: ExamDispatch,
    lp_counts: dict,
    exam_counts: dict,
) -> None:
    cst_id = bd["scope_ref_id"]
    if cst_id is None:
        raise ValueError(f"class-scope breakdown {breakdown_id} has no scope_ref_id")

    lesson_rows = await conn.fetch(
        """
        SELECT cls.id, cls.slot_type, cls.topic_id, cls.lp_type, cls.generated_lp_id
        FROM class_lesson_slots cls
        WHERE cls.cst_id = $1
        ORDER BY cls.position
        """,
        cst_id,
    )
    for row in lesson_rows:
        if row["generated_lp_id"] is not None:
            lp_counts["hit"] += 1
            continue
        try:
            if row["slot_type"] == "revision":
                lp = await get_or_generate_revision_lp(conn, row["id"], dispatcher=lp_dispatch)
            else:
                lp = await get_or_generate_lp(conn, row["id"], dispatcher=lp_dispatch)
            if lp.status == "ERROR":
                lp_counts["errored"] += 1
            elif lp.status == "IN_FLIGHT":
                lp_counts["dispatched"] += 1
            else:
                lp_counts["hit"] += 1
        except ValueError as exc:
            log.warning(
                "enqueue lesson slot %s: skipped — %s", row["id"], exc,
            )
            lp_counts["skipped"] += 1

    assessment_rows = await conn.fetch(
        """
        SELECT cas.id, cas.assessment_type, cas.generated_exam_id, s.code AS subject_code
        FROM class_assessment_slots cas
        JOIN class_subject_teachers cst ON cst.id = cas.cst_id
        JOIN subjects s ON s.id = cst.subject_id
        WHERE cas.cst_id = $1
        ORDER BY cas.position
        """,
        cst_id,
    )
    for row in assessment_rows:
        if row["generated_exam_id"] is not None:
            exam_counts["hit"] += 1
            continue
        slot_type_long = (
            "formative_assessment" if row["assessment_type"] == "formative"
            else "summative_assessment"
        )
        config = _config_for(row["subject_code"], slot_type_long)
        if config is None:
            log.warning(
                "enqueue assessment slot %s: no default config for subject=%s type=%s",
                row["id"], row["subject_code"], slot_type_long,
            )
            exam_counts["skipped"] += 1
            continue
        payload = ExamRequest(
            curriculum_code=bd["curriculum_code"],
            grade=_parse_grade_int(bd["grade_code"]),
            subject=row["subject_code"],
            page_content="placeholder",  # rebuilt from DB topics
            callback_url="placeholder",   # rebuilt with row id
            generation_type="exam",
            **config,
        )
        try:
            ctx = await load_assessment_slot_context(conn, row["id"], payload=payload)
            exam = await get_or_generate_exam(conn, ctx, dispatcher=eg_dispatch)
            if exam.status == "ERROR":
                exam_counts["errored"] += 1
            elif exam.status == "IN_FLIGHT":
                exam_counts["dispatched"] += 1
            else:
                exam_counts["hit"] += 1
        except ValueError as exc:
            log.warning(
                "enqueue assessment slot %s: skipped — %s", row["id"], exc,
            )
            exam_counts["skipped"] += 1


async def _enqueue_non_class_scope(
    conn: asyncpg.Connection,
    breakdown_id: UUID,
    bd: asyncpg.Record,
    lp_dispatch: LPDispatch,
    eg_dispatch: ExamDispatch,
    lp_counts: dict,
    exam_counts: dict,
) -> None:
    """Global / org breakdowns — directly drive the global cache."""
    slot_rows = await conn.fetch(
        """
        SELECT bs.id, bs.slot_type, bs.lp_type, bs.topic_id, t.topic_text
        FROM breakdown_slots bs
        LEFT JOIN topics t ON t.id = bs.topic_id
        WHERE bs.breakdown_id = $1
        ORDER BY bs.position
        """,
        breakdown_id,
    )
    for row in slot_rows:
        if row["slot_type"] == "lesson":
            if row["topic_id"] is None or not row["lp_type"]:
                lp_counts["skipped"] += 1
                continue
            outcome = await _ensure_global_lp_for_topic(
                conn,
                curriculum_id=bd["curriculum_id"],
                curriculum_code=bd["curriculum_code"],
                grade_id=bd["grade_id"], grade_code=bd["grade_code"],
                subject_id=bd["subject_id"], subject_code=bd["subject_code"],
                topic_id=row["topic_id"], topic_text=row["topic_text"] or "",
                lp_type=row["lp_type"],
                lp_dispatcher=lp_dispatch,
            )
            lp_counts[outcome] += 1
        elif row["slot_type"] in ("formative_assessment", "summative_assessment"):
            config = _config_for(bd["subject_code"], row["slot_type"])
            if config is None:
                exam_counts["skipped"] += 1
                continue
            topic_ids = await conn.fetch(
                """
                SELECT bst.topic_id, t.topic_text
                FROM breakdown_slot_topics bst
                JOIN topics t ON t.id = bst.topic_id
                WHERE bst.breakdown_slot_id = $1
                ORDER BY bst.position
                """,
                row["id"],
            )
            if not topic_ids:
                exam_counts["skipped"] += 1
                continue
            page_content = "\n\n".join(
                (r["topic_text"] or "").strip()
                for r in topic_ids
                if (r["topic_text"] or "").strip()
            )
            outcome = await _ensure_global_exam_for_slot(
                conn,
                curriculum_id=bd["curriculum_id"],
                curriculum_code=bd["curriculum_code"],
                grade_id=bd["grade_id"], grade_code=bd["grade_code"],
                subject_id=bd["subject_id"], subject_code=bd["subject_code"],
                topic_ids=[r["topic_id"] for r in topic_ids],
                page_content=page_content,
                generation_type="exam",
                config=config,
                eg_dispatcher=eg_dispatch,
            )
            exam_counts[outcome] += 1
        else:
            # 'revision' on a non-class breakdown — only realized class
            # slots have prior-topic context, so we don't pre-warm
            # revision LPs at global/org publish time.
            lp_counts["skipped"] += 1


# ---------------------------------------------------------------------------
# F3.11 — status endpoint
# ---------------------------------------------------------------------------


async def generation_status_for_breakdown(
    conn: asyncpg.Connection, breakdown_id: UUID
) -> dict:
    """
    Returns counts of generated_lps + generated_exams in each status
    for slots that belong to this breakdown.

    For class-scope: count the rows linked from class_*_slots of the CST.
    For global/org: count via the global cache keys produced from
                    breakdown_slots' (topic_id, lp_type) pairs.
    """
    bd = await conn.fetchrow(
        "SELECT id, scope, scope_ref_id, curriculum_id FROM breakdowns WHERE id = $1",
        breakdown_id,
    )
    if bd is None:
        raise ValueError(f"breakdown_id={breakdown_id} not found")

    if bd["scope"] == "class":
        lp_counts = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE gl.status = 'PENDING')   AS pending,
                COUNT(*) FILTER (WHERE gl.status = 'IN_FLIGHT') AS in_flight,
                COUNT(*) FILTER (WHERE gl.status = 'READY')     AS ready,
                COUNT(*) FILTER (WHERE gl.status = 'ERROR')     AS error,
                COUNT(*)                                        AS total
            FROM class_lesson_slots cls
            LEFT JOIN generated_lps gl ON gl.id = cls.generated_lp_id
            WHERE cls.cst_id = $1
            """,
            bd["scope_ref_id"],
        )
        exam_counts = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE ge.status = 'PENDING')   AS pending,
                COUNT(*) FILTER (WHERE ge.status = 'IN_FLIGHT') AS in_flight,
                COUNT(*) FILTER (WHERE ge.status = 'READY')     AS ready,
                COUNT(*) FILTER (WHERE ge.status = 'ERROR')     AS error,
                COUNT(*)                                        AS total
            FROM class_assessment_slots cas
            LEFT JOIN generated_exams ge ON ge.id = cas.generated_exam_id
            WHERE cas.cst_id = $1
            """,
            bd["scope_ref_id"],
        )
    else:
        # Build the expected cache_key set from breakdown_slots and
        # count generated_lps matching by cache_key.
        lp_keys = await conn.fetch(
            """
            SELECT bs.lp_type, bs.topic_id
            FROM breakdown_slots bs
            WHERE bs.breakdown_id = $1
              AND bs.slot_type = 'lesson'
              AND bs.topic_id IS NOT NULL
              AND bs.lp_type IS NOT NULL
            """,
            breakdown_id,
        )
        cache_keys = [
            f"{bd['curriculum_id']}:{r['topic_id']}:{r['lp_type']}"
            for r in lp_keys
        ]
        lp_counts = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE gl.status = 'PENDING')   AS pending,
                COUNT(*) FILTER (WHERE gl.status = 'IN_FLIGHT') AS in_flight,
                COUNT(*) FILTER (WHERE gl.status = 'READY')     AS ready,
                COUNT(*) FILTER (WHERE gl.status = 'ERROR')     AS error,
                $1::INT                                         AS total
            FROM generated_lps gl
            WHERE gl.cache_key = ANY($2::TEXT[]) AND gl.scope = 'global'
            """,
            len(cache_keys), cache_keys,
        )
        # Exam keys would require building both topic_ids_hash + config_hash
        # ourselves; for the dashboard endpoint we report against the global
        # exam universe filtered by curriculum/grade/subject.
        exam_counts = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE ge.status = 'PENDING')   AS pending,
                COUNT(*) FILTER (WHERE ge.status = 'IN_FLIGHT') AS in_flight,
                COUNT(*) FILTER (WHERE ge.status = 'READY')     AS ready,
                COUNT(*) FILTER (WHERE ge.status = 'ERROR')     AS error,
                COUNT(*)                                        AS total
            FROM breakdown_slots bs
            LEFT JOIN generated_exams ge
                ON ge.scope = 'global'
                AND ge.curriculum_id = $1
                AND ge.generation_type = 'exam'
            WHERE bs.breakdown_id = $2
              AND bs.slot_type IN ('formative_assessment', 'summative_assessment')
            """,
            bd["curriculum_id"], breakdown_id,
        )

    def _shape(r: asyncpg.Record | None) -> dict:
        if r is None:
            return {"total": 0, "pending": 0, "in_flight": 0, "ready": 0, "error": 0}
        return {
            "total": int(r["total"] or 0),
            "pending": int(r["pending"] or 0),
            "in_flight": int(r["in_flight"] or 0),
            "ready": int(r["ready"] or 0),
            "error": int(r["error"] or 0),
        }

    return {"lp": _shape(lp_counts), "exam": _shape(exam_counts)}
