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
import copy
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


# ---------------------------------------------------------------------------
# F-3.1 — Default per-subject FA (formative-assessment) question config (D-10)
#
# An FA slot has no per-slot config editor in this feature (D-10); when its
# exam is generated on-demand we apply a sensible per-subject default — a
# SHORT formative quiz (formative != summative, so modest counts). Each entry
# is a dict of the question-shaping kwargs that go straight onto an
# `ExamRequest` (see ug_eg_client.ExamRequest): question_types,
# unseen_categories, unseen_objective_types / counts, etc. `generation_type`
# is NOT part of this dict — it's passed separately (see GENERATION_TYPE_FA).
#
# Lookup goes through `default_fa_config(subject)`, which falls back to a
# GENERIC short objective quiz for any subject without a specific entry and
# never raises. (A separate per-subject map already lives in
# generated_lps/batch_service.py for the F5.14 retry path; this is the
# exam-service-local source the on-demand FA entry point reads — kept here
# per the phase spec's "near the exam service".)
# ---------------------------------------------------------------------------

# An FA is a "class assessment" to UG_EG. `ExamRequest.generation_type` only
# accepts {"exam", "class_assessment"} (ug_eg_client._GENERATION_TYPES), so the
# formative slot maps to 'class_assessment' — the valid enum value that also
# round-trips through the F5.14 retry path (which re-reads generation_type from
# the generated_exams row and re-sends it through ExamRequest). D-10 wrote
# "generation_type='formative'", but 'formative' is not in the ExamRequest enum
# and would raise at construction; 'class_assessment' is the faithful mapping.
GENERATION_TYPE_FA = "class_assessment"

# Generic short formative quiz: objective-only, 10 questions. Used for any
# subject without a specific entry below.
_GENERIC_FA_CONFIG: dict = {
    "question_types": ["unseen"],
    "unseen_categories": ["objective"],
    "unseen_objective_types": ["MCQs", "True/False", "Fill in the Blanks"],
    "unseen_subjective_types": [],
    "unseen_objective_counts": {"MCQs": 5, "True/False": 3, "Fill in the Blanks": 2},
    "unseen_subjective_counts": {},
    "include_answer_key": True,
}

DEFAULT_FA_CONFIG: dict[str, dict] = {
    # English — objective-only formative quiz, 10 questions.
    "Eng": {
        "question_types": ["unseen"],
        "unseen_categories": ["objective"],
        "unseen_objective_types": ["MCQs", "True/False", "Fill in the Blanks"],
        "unseen_subjective_types": [],
        "unseen_objective_counts": {"MCQs": 5, "True/False": 3, "Fill in the Blanks": 2},
        "unseen_subjective_counts": {},
        "include_answer_key": True,
    },
    # Urdu — same objective shape; kept explicit so the subject is first-class.
    "Urdu": {
        "question_types": ["unseen"],
        "unseen_categories": ["objective"],
        "unseen_objective_types": ["MCQs", "True/False", "Fill in the Blanks"],
        "unseen_subjective_types": [],
        "unseen_objective_counts": {"MCQs": 5, "True/False": 3, "Fill in the Blanks": 2},
        "unseen_subjective_counts": {},
        "include_answer_key": True,
    },
    # Maths — objective formative quiz; MCQs + Fill in the Blanks only.
    "Maths": {
        "question_types": ["unseen"],
        "unseen_categories": ["objective"],
        "unseen_objective_types": ["MCQs", "Fill in the Blanks"],
        "unseen_subjective_types": [],
        "unseen_objective_counts": {"MCQs": 6, "Fill in the Blanks": 4},
        "unseen_subjective_counts": {},
        "include_answer_key": True,
    },
}


def default_fa_config(subject_code: str) -> dict:
    """Return the default FA question config for a subject (F-3.1, D-10).

    Never raises: an unknown subject falls back to the generic short
    objective quiz. Returns a deep copy so callers can't mutate the
    module-level config (incl. its nested count dicts) in place.
    """
    return copy.deepcopy(DEFAULT_FA_CONFIG.get(subject_code, _GENERIC_FA_CONFIG))


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


# ---------------------------------------------------------------------------
# F-3.2 — On-demand FA exam from an assessment slot (D-10, D-11)
#
# Mirrors generated_lps.service.get_or_generate_lp: a slot-id-in,
# (exam id + status)-out entry point that builds the Exam Generator inputs
# for an FA slot from the per-subject Default FA Config, then reuses the
# existing global-cache + dispatch path (get_or_generate_exam). The slot's
# generated_exam_id is linked here (at insert / cache-hit), NOT by the
# webhook — the exam webhook only fills the generated_exams row in by its own
# id (the callback URL carries our row id, see _build_callback_url).
# ---------------------------------------------------------------------------


def _parse_grade_int(grade_code: str) -> int:
    """Map `grades.code` (e.g. 'G1') to UG_EG's int grade (1..5).

    `ExamRequest.grade` is an int constrained to 1..5. Anything that doesn't
    match 'G<int>' raises ValueError so we never silently send a bogus grade.
    """
    if not grade_code or not grade_code.startswith("G"):
        raise ValueError(
            f"grade_code={grade_code!r} doesn't match expected 'G<n>' pattern"
        )
    try:
        return int(grade_code[1:])
    except ValueError as e:
        raise ValueError(f"grade_code={grade_code!r} is not 'G<int>'") from e


def _build_fa_payload(*, curriculum_code: str, grade_code: str, subject_code: str) -> ExamRequest:
    """Build the seed `ExamRequest` for an FA slot from the Default FA Config.

    page_content / callback_url are placeholders here; the service's
    `_dispatch_and_mark` rebuilds the request with the DB-resolved
    page_content + the real callback_url once the generated_exam id exists.
    What matters at this stage is the question config (drives the cache key)
    and generation_type. Raises ValueError on a bad grade or a subject
    UG_EG doesn't accept (surfaced as 422 by the endpoint).
    """
    config = default_fa_config(subject_code)
    return ExamRequest(
        curriculum_code=curriculum_code,
        grade=_parse_grade_int(grade_code),
        subject=subject_code,
        page_content="placeholder",  # overwritten in _dispatch_and_mark
        callback_url="https://dars.invalid/placeholder",  # overwritten there too
        generation_type=GENERATION_TYPE_FA,
        **config,
    )


async def get_or_generate_exam_for_assessment_slot(
    conn: asyncpg.Connection,
    class_assessment_slot_id: UUID,
    *,
    dispatcher: DispatchCallable | None = None,
) -> GeneratedExam:
    """
    On-demand FA exam generation for a class assessment slot (F-3.2).

    1. Load the slot's context (curriculum/grade/subject, covered topic_ids,
       joined page_content) via load_assessment_slot_context.
    2. question_config = DEFAULT_FA_CONFIG[subject] (generic fallback);
       generation_type = 'class_assessment' (the FA mapping).
    3. Cache-first via get_or_generate_exam: a non-ERROR generated_exams row
       on the (curriculum, topics, generation_type, config) key is linked to
       the slot and returned; an ERROR row is retried; a miss inserts PENDING,
       dispatches to UG_EG, and links the slot's generated_exam_id.

    Raises ValueError (→ 422 at the endpoint) when the slot is missing, has no
    covered topics, the topics have no text, the grade is unparseable, or the
    subject isn't a UG_EG subject. Idempotent: a second call returns the same
    non-ERROR row without re-dispatching.
    """
    log.info(
        "get_or_generate_exam_for_assessment_slot: entry slot_id=%s",
        class_assessment_slot_id,
    )

    # Resolve tenancy/curriculum/subject first so we can build the seed payload
    # from the per-subject default config; this is a cheap pre-read of the slot
    # row (load_assessment_slot_context re-reads it with topics + page_content).
    base = await conn.fetchrow(
        """
        SELECT c.code AS curriculum_code,
               g.code AS grade_code,
               s.code AS subject_code
        FROM class_assessment_slots cas
        JOIN class_subject_teachers cst ON cst.id = cas.cst_id
        JOIN curriculums c              ON c.id = cst.curriculum_id
        JOIN grades g                   ON g.id = cst.grade_id
        JOIN subjects s                 ON s.id = cst.subject_id
        WHERE cas.id = $1
        """,
        class_assessment_slot_id,
    )
    if base is None:
        raise ValueError(
            f"class_assessment_slot_id={class_assessment_slot_id} not found"
        )

    payload = _build_fa_payload(
        curriculum_code=base["curriculum_code"],
        grade_code=base["grade_code"],
        subject_code=base["subject_code"],
    )
    ctx = await load_assessment_slot_context(
        conn, class_assessment_slot_id, payload=payload
    )

    exam = await get_or_generate_exam(conn, ctx, dispatcher=dispatcher)
    log.info(
        "get_or_generate_exam_for_assessment_slot: exit slot_id=%s gen_exam_id=%s status=%s",
        class_assessment_slot_id, exam.id, exam.status,
    )
    return exam
