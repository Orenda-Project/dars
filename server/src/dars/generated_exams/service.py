"""
F3.5 — Generated-Exam cache lookup/insert + class-scope branching.

Mirrors F3.4 (generated_lps/service.py) but the cache key includes a
hash of the covered topic_ids AND a hash of the exact question config,
since an FA and an SA over the same topics produce different exams.

Cache key:
    f"{curriculum_id}:{topic_ids_hash}:{generation_type}:{question_config_hash}"

Both hashes are SHA-256 over a *canonical* representation so dict
ordering / list ordering doesn't cause spurious misses.

Class-scope variant adds cst_id (via scope_ref_id) so a CST with a
teacher-customised assessment doesn't collide with the global row.
"""
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable
from uuid import UUID

import asyncpg

from dars.config import settings
from dars.generated_exams.ug_eg_client import (
    ExamRequest,
    request_exam_generation as default_request_exam_generation,
)

log = logging.getLogger("generated_exams.service")

DispatchCallable = Callable[[ExamRequest], Awaitable[str]]


@dataclass
class GeneratedExam:
    id: UUID
    cache_key: str | None
    scope: str
    scope_ref_id: UUID | None
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    topic_ids_hash: str
    generation_type: str
    question_config_hash: str
    status: str
    job_id: str | None
    result: dict | None


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def hash_topic_ids(topic_ids: list[UUID]) -> str:
    """SHA-256 over sorted, dash-joined UUID strings."""
    canonical = ",".join(sorted(str(t) for t in topic_ids))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonicalise(value):
    """Recursively turn dicts/lists into a canonical form for stable hashing.

    - dicts: sort keys
    - lists/tuples: keep order (callers preserve question-order semantics)
    - everything else: pass through
    """
    if isinstance(value, dict):
        return {k: _canonicalise(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonicalise(v) for v in value]
    return value


def hash_question_config(config: dict) -> str:
    """SHA-256 over canonical JSON of the question config."""
    canonical = _canonicalise(config)
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_question_config(payload: ExamRequest) -> dict:
    """Extract the question-shaping fields from an ExamRequest into a dict.

    This is the dict we hash — page_content + curriculum + grade are
    NOT part of this dict because they're hashed separately via
    cache_key components, and including them would double-count.
    """
    cfg: dict = {
        "subject": payload.subject,
        "generation_type": payload.generation_type,
        "question_types": list(payload.question_types),
        "unseen_categories": list(payload.unseen_categories),
        "unseen_objective_types": list(payload.unseen_objective_types),
        "unseen_subjective_types": list(payload.unseen_subjective_types),
        "unseen_objective_counts": dict(payload.unseen_objective_counts),
        "unseen_subjective_counts": dict(payload.unseen_subjective_counts),
        "long_question_sub_types": list(payload.long_question_sub_types),
        "include_answer_key": payload.include_answer_key,
    }
    return cfg


def build_cache_key_global(
    curriculum_id: UUID,
    topic_ids_hash: str,
    generation_type: str,
    question_config_hash: str,
) -> str:
    return f"{curriculum_id}:{topic_ids_hash}:{generation_type}:{question_config_hash}"


def build_cache_key_class(
    curriculum_id: UUID,
    cst_id: UUID,
    topic_ids_hash: str,
    generation_type: str,
    question_config_hash: str,
) -> str:
    return (
        f"{curriculum_id}:{cst_id}:{topic_ids_hash}:"
        f"{generation_type}:{question_config_hash}"
    )


def _build_callback_url(generated_exam_id: UUID) -> str:
    return f"{settings.dars_base_url.rstrip('/')}/api/v1/webhooks/exam/{generated_exam_id}"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


@dataclass
class ExamSlotContext:
    """Inputs for cache lookup + dispatch.

    The caller builds this from a class_assessment_slot — including the
    topic_ids list, generation_type, and the question config that was
    set at breakdown time. Service.py here does not assume how that
    config is stored on the slot; F3.11 (batch publish) will pass it
    in explicitly when iterating slots.
    """
    class_assessment_slot_id: UUID
    cst_id: UUID
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    curriculum_code: str
    grade_code: str
    subject_code: str
    topic_ids: list[UUID]
    page_content: str
    payload: ExamRequest  # built by the caller from slot config


async def load_assessment_slot_context(
    conn: asyncpg.Connection,
    class_assessment_slot_id: UUID,
    *,
    payload: ExamRequest,
) -> ExamSlotContext:
    """
    Load DB-side context for an assessment slot.

    `payload` is constructed by the caller (F3.11 / F3.5 callers) because
    the question config is per-slot policy, not per-row data. This
    function fills in tenancy + curriculum + topics + page_content.

    Raises ValueError if the slot is missing or has no topics.
    """
    row = await conn.fetchrow(
        """
        SELECT
            cas.id            AS class_assessment_slot_id,
            cas.cst_id        AS cst_id,
            cst.curriculum_id AS curriculum_id,
            cst.grade_id      AS grade_id,
            cst.subject_id    AS subject_id,
            c.code            AS curriculum_code,
            g.code            AS grade_code,
            s.code            AS subject_code
        FROM class_assessment_slots cas
        JOIN class_subject_teachers cst ON cst.id = cas.cst_id
        JOIN curriculums c              ON c.id = cst.curriculum_id
        JOIN grades g                   ON g.id = cst.grade_id
        JOIN subjects s                 ON s.id = cst.subject_id
        WHERE cas.id = $1
        """,
        class_assessment_slot_id,
    )
    if row is None:
        raise ValueError(f"class_assessment_slot_id={class_assessment_slot_id} not found")

    topic_rows = await conn.fetch(
        """
        SELECT t.id, t.topic_text
        FROM class_assessment_slot_topics cast2
        JOIN topics t ON t.id = cast2.topic_id
        WHERE cast2.class_assessment_slot_id = $1
        ORDER BY cast2.position
        """,
        class_assessment_slot_id,
    )
    if not topic_rows:
        raise ValueError(
            f"class_assessment_slot_id={class_assessment_slot_id} has no covered topics"
        )

    topic_ids: list[UUID] = [r["id"] for r in topic_rows]
    page_content = "\n\n".join(
        (r["topic_text"] or "").strip() for r in topic_rows if (r["topic_text"] or "").strip()
    )
    if not page_content:
        raise ValueError(
            f"class_assessment_slot_id={class_assessment_slot_id} topics have no text"
        )

    return ExamSlotContext(
        class_assessment_slot_id=class_assessment_slot_id,
        cst_id=row["cst_id"],
        curriculum_id=row["curriculum_id"],
        grade_id=row["grade_id"],
        subject_id=row["subject_id"],
        curriculum_code=row["curriculum_code"],
        grade_code=row["grade_code"],
        subject_code=row["subject_code"],
        topic_ids=topic_ids,
        page_content=page_content,
        payload=payload,
    )


def _record_to_dataclass(row: asyncpg.Record) -> GeneratedExam:
    return GeneratedExam(
        id=row["id"],
        cache_key=row["cache_key"],
        scope=row["scope"],
        scope_ref_id=row["scope_ref_id"],
        curriculum_id=row["curriculum_id"],
        grade_id=row["grade_id"],
        subject_id=row["subject_id"],
        topic_ids_hash=row["topic_ids_hash"],
        generation_type=row["generation_type"],
        question_config_hash=row["question_config_hash"],
        status=row["status"],
        job_id=row["job_id"],
        result=row["result"],
    )


async def _find_existing_global(
    conn: asyncpg.Connection, cache_key: str
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT id, cache_key, scope, scope_ref_id, curriculum_id, grade_id,
               subject_id, topic_ids_hash, generation_type, question_config_hash,
               status, job_id, result
        FROM generated_exams
        WHERE cache_key = $1 AND scope = 'global'
        """,
        cache_key,
    )


async def _find_existing_class(
    conn: asyncpg.Connection, cst_id: UUID, cache_key: str
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT id, cache_key, scope, scope_ref_id, curriculum_id, grade_id,
               subject_id, topic_ids_hash, generation_type, question_config_hash,
               status, job_id, result
        FROM generated_exams
        WHERE scope = 'class' AND scope_ref_id = $1 AND cache_key = $2
        ORDER BY created_at DESC
        LIMIT 1
        """,
        cst_id, cache_key,
    )


async def _link_slot_to_exam(
    conn: asyncpg.Connection,
    class_assessment_slot_id: UUID,
    generated_exam_id: UUID,
) -> None:
    await conn.execute(
        """
        UPDATE class_assessment_slots
        SET generated_exam_id = $1, updated_at = now()
        WHERE id = $2 AND COALESCE(generated_exam_id::text, '') <> $1::text
        """,
        generated_exam_id, class_assessment_slot_id,
    )


async def _insert_pending_exam(
    conn: asyncpg.Connection,
    *,
    scope: str,
    scope_ref_id: UUID | None,
    cache_key: str,
    curriculum_id: UUID,
    grade_id: UUID,
    subject_id: UUID,
    topic_ids_hash: str,
    generation_type: str,
    question_config_hash: str,
) -> UUID:
    return await conn.fetchval(
        """
        INSERT INTO generated_exams (
            cache_key, scope, scope_ref_id,
            curriculum_id, grade_id, subject_id,
            topic_ids_hash, generation_type, question_config_hash,
            status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'PENDING')
        RETURNING id
        """,
        cache_key, scope, scope_ref_id,
        curriculum_id, grade_id, subject_id,
        topic_ids_hash, generation_type, question_config_hash,
    )


async def _mark_in_flight(
    conn: asyncpg.Connection, generated_exam_id: UUID, job_id: str
) -> None:
    await conn.execute(
        """
        UPDATE generated_exams
        SET status = 'IN_FLIGHT', job_id = $1, updated_at = now()
        WHERE id = $2
        """,
        job_id, generated_exam_id,
    )


async def _mark_error(
    conn: asyncpg.Connection, generated_exam_id: UUID, error_message: str
) -> None:
    await conn.execute(
        """
        UPDATE generated_exams
        SET status = 'ERROR', error_message = $1, updated_at = now()
        WHERE id = $2
        """,
        error_message[:2000], generated_exam_id,
    )


async def _dispatch_and_mark(
    conn: asyncpg.Connection,
    *,
    generated_exam_id: UUID,
    ctx: ExamSlotContext,
    dispatcher: DispatchCallable,
) -> str | None:
    """Send to UG_EG and update the row to IN_FLIGHT (or ERROR)."""
    # The caller's `payload` was built before this service got its
    # generated_exam_id; rebuild the request with the correct
    # callback_url + the page_content/curriculum we resolved from DB.
    base = ctx.payload
    request = ExamRequest(
        curriculum_code=ctx.curriculum_code,
        grade=base.grade,
        subject=ctx.subject_code,
        page_content=ctx.page_content,
        callback_url=_build_callback_url(generated_exam_id),
        generation_type=base.generation_type,
        question_types=base.question_types,
        unseen_categories=base.unseen_categories,
        unseen_objective_types=base.unseen_objective_types,
        unseen_subjective_types=base.unseen_subjective_types,
        unseen_objective_counts=base.unseen_objective_counts,
        unseen_subjective_counts=base.unseen_subjective_counts,
        long_question_sub_types=base.long_question_sub_types,
        include_answer_key=base.include_answer_key,
    )
    try:
        job_id = await dispatcher(request)
    except Exception as exc:  # noqa: BLE001
        log.exception(
            "dispatch_exam_generation: failed generated_exam_id=%s", generated_exam_id
        )
        await _mark_error(conn, generated_exam_id, f"dispatch failed: {exc}")
        return None
    await _mark_in_flight(conn, generated_exam_id, job_id)
    return job_id


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


async def get_or_generate_exam(
    conn: asyncpg.Connection,
    ctx: ExamSlotContext,
    *,
    dispatcher: DispatchCallable | None = None,
) -> GeneratedExam:
    """
    Global-cache path for a class assessment slot.

    Cache key is `(curriculum, topic_ids_hash, generation_type,
    question_config_hash)` at global scope. Returns existing row if
    PENDING/IN_FLIGHT/READY; re-requests on ERROR; otherwise inserts
    PENDING + dispatches to UG_EG.
    """
    log.info(
        "get_or_generate_exam: entry slot_id=%s gen_type=%s topic_count=%d",
        ctx.class_assessment_slot_id, ctx.payload.generation_type, len(ctx.topic_ids),
    )

    topic_ids_hash = hash_topic_ids(ctx.topic_ids)
    config_hash = hash_question_config(build_question_config(ctx.payload))
    cache_key = build_cache_key_global(
        ctx.curriculum_id, topic_ids_hash, ctx.payload.generation_type, config_hash,
    )

    existing = await _find_existing_global(conn, cache_key)
    if existing is not None and existing["status"] != "ERROR":
        await _link_slot_to_exam(conn, ctx.class_assessment_slot_id, existing["id"])
        log.info(
            "get_or_generate_exam: cache hit slot_id=%s gen_exam_id=%s status=%s",
            ctx.class_assessment_slot_id, existing["id"], existing["status"],
        )
        return _record_to_dataclass(existing)

    new_id = await _insert_pending_exam(
        conn,
        scope="global", scope_ref_id=None, cache_key=cache_key,
        curriculum_id=ctx.curriculum_id, grade_id=ctx.grade_id,
        subject_id=ctx.subject_id, topic_ids_hash=topic_ids_hash,
        generation_type=ctx.payload.generation_type,
        question_config_hash=config_hash,
    )
    await _link_slot_to_exam(conn, ctx.class_assessment_slot_id, new_id)
    await _dispatch_and_mark(
        conn,
        generated_exam_id=new_id,
        ctx=ctx,
        dispatcher=dispatcher or default_request_exam_generation,
    )

    fresh = await _find_existing_global(conn, cache_key)
    assert fresh is not None
    log.info(
        "get_or_generate_exam: inserted slot_id=%s gen_exam_id=%s status=%s",
        ctx.class_assessment_slot_id, fresh["id"], fresh["status"],
    )
    return _record_to_dataclass(fresh)


async def get_or_generate_class_specific_exam(
    conn: asyncpg.Connection,
    ctx: ExamSlotContext,
    *,
    dispatcher: DispatchCallable | None = None,
) -> GeneratedExam:
    """
    Class-scope path. Used when the assessment slot's topic combo or
    question config differs from the global breakdown's (CST-level
    customisation per D-57).
    """
    log.info(
        "get_or_generate_class_specific_exam: entry slot_id=%s cst_id=%s",
        ctx.class_assessment_slot_id, ctx.cst_id,
    )

    topic_ids_hash = hash_topic_ids(ctx.topic_ids)
    config_hash = hash_question_config(build_question_config(ctx.payload))
    cache_key = build_cache_key_class(
        ctx.curriculum_id, ctx.cst_id, topic_ids_hash,
        ctx.payload.generation_type, config_hash,
    )

    existing = await _find_existing_class(conn, ctx.cst_id, cache_key)
    if existing is not None and existing["status"] != "ERROR":
        await _link_slot_to_exam(conn, ctx.class_assessment_slot_id, existing["id"])
        log.info(
            "get_or_generate_class_specific_exam: cache hit gen_exam_id=%s status=%s",
            existing["id"], existing["status"],
        )
        return _record_to_dataclass(existing)

    new_id = await _insert_pending_exam(
        conn,
        scope="class", scope_ref_id=ctx.cst_id, cache_key=cache_key,
        curriculum_id=ctx.curriculum_id, grade_id=ctx.grade_id,
        subject_id=ctx.subject_id, topic_ids_hash=topic_ids_hash,
        generation_type=ctx.payload.generation_type,
        question_config_hash=config_hash,
    )
    await _link_slot_to_exam(conn, ctx.class_assessment_slot_id, new_id)
    await _dispatch_and_mark(
        conn,
        generated_exam_id=new_id,
        ctx=ctx,
        dispatcher=dispatcher or default_request_exam_generation,
    )

    fresh = await conn.fetchrow(
        "SELECT id, cache_key, scope, scope_ref_id, curriculum_id, grade_id, "
        "subject_id, topic_ids_hash, generation_type, question_config_hash, "
        "status, job_id, result "
        "FROM generated_exams WHERE id = $1",
        new_id,
    )
    assert fresh is not None
    return _record_to_dataclass(fresh)
