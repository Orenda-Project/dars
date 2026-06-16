"""
F3.4 — Generated-LP cache lookup/insert + class-scope branching.

Per D-46 + D-56 + D-57:
  - Global lesson LPs are cached by (curriculum, topic, lp_type) so the
    same global breakdown slot is generated once across all CSTs.
  - When a CST's slot has a topic combo the global breakdown didn't have
    (custom-added by the teacher), we cache class-scoped instead.

This module only does cache + persistence + outbound dispatch. The
webhook (F3.6) fills in `content`, `cost_usd`, etc.

Lifecycle for a slot's LP:
  - lookup row by cache_key (or class-scope key)
  - if found+READY: link to slot, return
  - if found+PENDING/IN_FLIGHT: caller waits (webhook will finish it)
  - if found+ERROR: treat as miss (re-request)
  - if not found: insert row at PENDING, dispatch to LP Assistant, set
    IN_FLIGHT + job_id in a single follow-up update

Revision LPs (F3.10) use a different keying with revision_topic_set_hash;
they go through `get_or_generate_revision_lp` (TODO in F3.10).
"""
import hashlib
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable
from uuid import UUID

import asyncpg

from dars.config import settings
from dars.generated_lps.lp_assistant_client import (
    LPRequest,
    request_lp_generation as default_request_lp_generation,
)

# F3.10: cap the number of prior topics fed into a revision LP. The
# topic_text concat can balloon past LP Assistant's context window if
# we feed an entire chapter back at once.
REVISION_MAX_PRIOR_TOPICS = 5

log = logging.getLogger("generated_lps.service")

DispatchCallable = Callable[[LPRequest], Awaitable[str]]


@dataclass
class GeneratedLP:
    """A row in `generated_lps`, populated by lookup or fresh insert."""
    id: UUID
    cache_key: str | None
    scope: str
    scope_ref_id: UUID | None
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    topic_id: UUID | None
    lp_type: str
    status: str
    job_id: str | None
    content: str | None


def _build_cache_key_global(curriculum_id: UUID, topic_id: UUID, lp_type: str) -> str:
    """`{curriculum_id}:{topic_id}:{lp_type}` per spec."""
    return f"{curriculum_id}:{topic_id}:{lp_type}"


def _build_cache_key_class(
    curriculum_id: UUID, cst_id: UUID, topic_id: UUID, lp_type: str
) -> str:
    """`{curriculum_id}:{cst_id}:{topic_id}:{lp_type}` per spec.

    Single-topic class-scope key (back-compat). Multi-topic LP units use
    `_build_cache_key_class_topic_set` instead (D-9/D-12).
    """
    return f"{curriculum_id}:{cst_id}:{topic_id}:{lp_type}"


def _build_cache_key_class_topic_set(
    curriculum_id: UUID, cst_id: UUID, topic_ids: list[UUID], lp_type: str
) -> str:
    """Class-scope cache key keyed on the *ordered* topic set (D-12).

    Hashes the ordered list (order is pedagogically meaningful for a merged
    LP unit) so two distinct multi-topic units on the same CST never collide,
    and never collide with a single-topic class key. A single-topic unit still
    hashes to a distinct value from the legacy `_build_cache_key_class` form
    (the `:set:` segment disambiguates).
    """
    canonical = ",".join(str(t) for t in topic_ids)
    topic_set_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{curriculum_id}:{cst_id}:set:{topic_set_hash}:{lp_type}"


def _build_callback_url(job_id: UUID) -> str:
    """Public webhook URL for a given (yet-to-be-known) LP-Assistant job_id.

    Note: at request-time we don't yet have LP Assistant's job_id, so we
    use our `generated_lps.id` as the path segment. The webhook handler
    in F3.6 looks the row up by that UUID and matches the `job_id` body.
    """
    return f"{settings.dars_base_url.rstrip('/')}/api/v1/webhooks/lp/{job_id}"


async def _load_lesson_slot_context(
    conn: asyncpg.Connection, lesson_slot_id: UUID
) -> asyncpg.Record:
    """Load everything we need to build the LP request for a lesson slot.

    Returns a row with: cst_id, topic_id, lp_type, slot_type, anchor_date,
    curriculum_id, grade_id, grade_code, subject_id, subject_code,
    topic_text.

    Raises ValueError if the slot is missing, has no topic, or is a
    revision slot (those go through F3.10).
    """
    row = await conn.fetchrow(
        """
        SELECT
            cls.id            AS lesson_slot_id,
            cls.cst_id        AS cst_id,
            cls.topic_id      AS topic_id,
            cls.lp_type       AS lp_type,
            cls.slot_type     AS slot_type,
            cls.generated_lp_id AS generated_lp_id,
            o.curriculum_id   AS curriculum_id,
            sc.grade_id       AS grade_id,
            cst.subject_id    AS subject_id,
            g.code            AS grade_code,
            s.code            AS subject_code,
            t.topic_text      AS topic_text
        FROM class_lesson_slots cls
        JOIN class_subject_teachers cst ON cst.id = cls.cst_id
        JOIN school_classes sc          ON sc.id = cst.school_class_id
        JOIN organizations o            ON o.id = cst.org_id
        JOIN grades g                   ON g.id = sc.grade_id
        JOIN subjects s                 ON s.id = cst.subject_id
        LEFT JOIN topics t              ON t.id = cls.topic_id
        WHERE cls.id = $1
        """,
        lesson_slot_id,
    )
    if row is None:
        raise ValueError(f"lesson_slot_id={lesson_slot_id} not found")
    if row["slot_type"] == "revision":
        raise ValueError(
            f"lesson_slot_id={lesson_slot_id} is a revision slot — use F3.10"
        )
    if row["topic_id"] is None:
        raise ValueError(
            f"lesson_slot_id={lesson_slot_id} has no topic_id; cannot build LP request"
        )
    if not row["lp_type"]:
        raise ValueError(
            f"lesson_slot_id={lesson_slot_id} has no lp_type set on the slot"
        )
    if not row["topic_text"] or not row["topic_text"].strip():
        raise ValueError(
            f"topic_id={row['topic_id']} has empty topic_text — LP Assistant would fall back to DB lookup"
        )
    return row


async def _load_lesson_slot_topic_set(
    conn: asyncpg.Connection, lesson_slot_id: UUID
) -> list[tuple[UUID, str]]:
    """Ordered (topic_id, topic_text) for an LP unit's full topic set (D-4/D-9).

    Reads `class_lesson_slot_topics` (ordered by `position`). Returns [] when
    the slot has no join rows (legacy / single-topic-only slots that predate
    the planner); callers then fall back to the slot's single `topic_id`.
    """
    rows = await conn.fetch(
        """
        SELECT clst.topic_id AS topic_id, t.topic_text AS topic_text
        FROM class_lesson_slot_topics clst
        JOIN topics t ON t.id = clst.topic_id
        WHERE clst.class_lesson_slot_id = $1
        ORDER BY clst.position
        """,
        lesson_slot_id,
    )
    return [(r["topic_id"], r["topic_text"] or "") for r in rows]


async def _load_curriculum_code(conn: asyncpg.Connection, curriculum_id: UUID) -> str:
    code = await conn.fetchval(
        "SELECT code FROM curriculums WHERE id = $1", curriculum_id
    )
    if not code:
        raise ValueError(f"curriculum_id={curriculum_id} not found")
    return code


async def _load_topic_sub_slos(
    conn: asyncpg.Connection, topic_id: UUID
) -> list[tuple[UUID, str]]:
    """Return (sub_slo_id, statement) for a topic, ordered by sub_slos.code.

    D-3: requested sub-SLOs come from the `topic_sub_slos` join, sorted by
    code for stable ordering (matters for D-1's prompt-string determinism
    and easier diffing). D-4: empty result is fine — caller dispatches
    without `custom_prompt`.
    """
    rows = await conn.fetch(
        """
        SELECT ss.id AS id, ss.statement AS statement
        FROM topic_sub_slos tss
        JOIN sub_slos ss ON ss.id = tss.sub_slo_id
        WHERE tss.topic_id = $1
        ORDER BY ss.code
        """,
        topic_id,
    )
    return [(r["id"], r["statement"]) for r in rows]


async def _load_union_topic_sub_slos(
    conn: asyncpg.Connection, topic_ids: list[UUID]
) -> list[tuple[UUID, str]]:
    """Union of sub-SLOs across topics (D-5: used by the revision path).

    De-duped by sub_slo.id; ordered by code so the prompt string and the
    persisted array are stable.
    """
    if not topic_ids:
        return []
    rows = await conn.fetch(
        """
        SELECT DISTINCT ss.id AS id, ss.statement AS statement, ss.code AS code
        FROM topic_sub_slos tss
        JOIN sub_slos ss ON ss.id = tss.sub_slo_id
        WHERE tss.topic_id = ANY($1::uuid[])
        ORDER BY ss.code
        """,
        topic_ids,
    )
    return [(r["id"], r["statement"]) for r in rows]


async def _find_existing(
    conn: asyncpg.Connection, *, scope: str, cache_key: str
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT id, cache_key, scope, scope_ref_id, curriculum_id, grade_id,
               subject_id, topic_id, lp_type, status, job_id, content
        FROM generated_lps
        WHERE cache_key = $1 AND scope = $2
        """,
        cache_key, scope,
    )


def _record_to_dataclass(row: asyncpg.Record) -> GeneratedLP:
    return GeneratedLP(
        id=row["id"],
        cache_key=row["cache_key"],
        scope=row["scope"],
        scope_ref_id=row["scope_ref_id"],
        curriculum_id=row["curriculum_id"],
        grade_id=row["grade_id"],
        subject_id=row["subject_id"],
        topic_id=row["topic_id"],
        lp_type=row["lp_type"],
        status=row["status"],
        job_id=row["job_id"],
        content=row["content"],
    )


async def _link_slot_to_lp(
    conn: asyncpg.Connection, lesson_slot_id: UUID, generated_lp_id: UUID
) -> None:
    """Idempotent: only update if not already pointing at this LP."""
    await conn.execute(
        """
        UPDATE class_lesson_slots
        SET generated_lp_id = $1::uuid, updated_at = now()
        WHERE id = $2 AND generated_lp_id IS DISTINCT FROM $1::uuid
        """,
        generated_lp_id, lesson_slot_id,
    )


async def _insert_pending_lp(
    conn: asyncpg.Connection,
    *,
    scope: str,
    scope_ref_id: UUID | None,
    cache_key: str,
    curriculum_id: UUID,
    grade_id: UUID,
    subject_id: UUID,
    topic_id: UUID,
    lp_type: str,
    requested_sub_slo_ids: list[UUID],
) -> UUID:
    """Insert a row at PENDING and return its UUID.

    D-2: `requested_sub_slo_ids` captures intent at dispatch time; empty
    list is persisted as `[]` (not NULL) so we can distinguish "we did
    request, and the topic had no sub-SLOs" from legacy/pre-feature rows
    where the column is NULL.
    """
    new_id = await conn.fetchval(
        """
        INSERT INTO generated_lps (
            cache_key, scope, scope_ref_id,
            curriculum_id, grade_id, subject_id,
            topic_id, lp_type, status, requested_sub_slo_ids
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'PENDING', $9)
        RETURNING id
        """,
        cache_key, scope, scope_ref_id,
        curriculum_id, grade_id, subject_id,
        topic_id, lp_type, requested_sub_slo_ids,
    )
    return new_id


async def _mark_in_flight(
    conn: asyncpg.Connection, generated_lp_id: UUID, job_id: str
) -> None:
    await conn.execute(
        """
        UPDATE generated_lps
        SET status = 'IN_FLIGHT', job_id = $1, updated_at = now()
        WHERE id = $2
        """,
        job_id, generated_lp_id,
    )


async def _mark_error(
    conn: asyncpg.Connection, generated_lp_id: UUID, error_message: str
) -> None:
    await conn.execute(
        """
        UPDATE generated_lps
        SET status = 'ERROR', error_message = $1, updated_at = now()
        WHERE id = $2
        """,
        error_message[:2000], generated_lp_id,
    )


async def _dispatch_and_mark(
    conn: asyncpg.Connection,
    *,
    generated_lp_id: UUID,
    curriculum_code: str,
    grade_code: int | str,
    subject_code: str,
    topic_text: str,
    lp_type: str,
    sub_slo_statements: list[str],
    dispatcher: DispatchCallable,
) -> str | None:
    """Send to LP Assistant and update the row to IN_FLIGHT (or ERROR).

    Returns the LP Assistant job_id on success, None on dispatch failure.
    """
    payload = LPRequest(
        curriculum_code=curriculum_code,
        grade=_parse_grade_int(grade_code),
        subject=subject_code,
        page_content=topic_text,
        lp_type=lp_type,
        callback_url=_build_callback_url(generated_lp_id),
        sub_slo_statements=sub_slo_statements or None,
    )
    try:
        job_id = await dispatcher(payload)
    except Exception as exc:  # noqa: BLE001
        log.exception("dispatch_lp_generation: failed generated_lp_id=%s", generated_lp_id)
        await _mark_error(conn, generated_lp_id, f"dispatch failed: {exc}")
        return None
    await _mark_in_flight(conn, generated_lp_id, job_id)
    return job_id


def _parse_grade_int(grade_code: int | str) -> int:
    """Map `grades.code` to LP Assistant's int grade.

    `grades.code` is an INT column (1..5), so asyncpg hands us a plain int —
    pass it through. A legacy 'G<n>' string is tolerated defensively. Anything
    else raises so we never silently send a bogus grade.
    """
    if isinstance(grade_code, int):
        return grade_code
    if not grade_code or not grade_code.startswith("G"):
        raise ValueError(f"grade_code={grade_code!r} doesn't match expected int or 'G<n>'")
    try:
        return int(grade_code[1:])
    except ValueError as e:
        raise ValueError(f"grade_code={grade_code!r} is not 'G<int>'") from e


async def get_or_generate_lp(
    conn: asyncpg.Connection,
    lesson_slot_id: UUID,
    *,
    dispatcher: DispatchCallable | None = None,
) -> GeneratedLP:
    """
    Global-cache path for a class lesson slot.

    Looks up `generated_lps` keyed on (curriculum, topic, lp_type) at
    global scope. Returns the row if found (READY / PENDING / IN_FLIGHT);
    re-requests on ERROR; otherwise inserts a fresh PENDING row and
    dispatches to LP Assistant.

    The slot's `generated_lp_id` is updated to point at the (existing or
    newly-inserted) row.
    """
    log.info("get_or_generate_lp: entry lesson_slot_id=%s", lesson_slot_id)

    ctx = await _load_lesson_slot_context(conn, lesson_slot_id)
    curriculum_id = ctx["curriculum_id"]
    topic_id = ctx["topic_id"]
    lp_type = ctx["lp_type"]

    cache_key = _build_cache_key_global(curriculum_id, topic_id, lp_type)
    existing = await _find_existing(conn, scope="global", cache_key=cache_key)

    if existing is not None and existing["status"] != "ERROR":
        log.info(
            "get_or_generate_lp: cache hit lesson_slot_id=%s gen_lp_id=%s status=%s",
            lesson_slot_id, existing["id"], existing["status"],
        )
        await _link_slot_to_lp(conn, lesson_slot_id, existing["id"])
        return _record_to_dataclass(existing)

    # Cache miss or ERROR — fresh insert + dispatch.
    if existing is not None and existing["status"] == "ERROR":
        log.info(
            "get_or_generate_lp: prior ERROR for cache_key=%s — re-requesting",
            cache_key,
        )

    sub_slo_pairs = await _load_topic_sub_slos(conn, topic_id)
    requested_ids = [p[0] for p in sub_slo_pairs]
    sub_slo_statements = [p[1] for p in sub_slo_pairs]

    new_id = await _insert_pending_lp(
        conn,
        scope="global", scope_ref_id=None, cache_key=cache_key,
        curriculum_id=curriculum_id, grade_id=ctx["grade_id"],
        subject_id=ctx["subject_id"], topic_id=topic_id,
        lp_type=lp_type,
        requested_sub_slo_ids=requested_ids,
    )
    await _link_slot_to_lp(conn, lesson_slot_id, new_id)

    curriculum_code = await _load_curriculum_code(conn, curriculum_id)
    await _dispatch_and_mark(
        conn,
        generated_lp_id=new_id,
        curriculum_code=curriculum_code,
        grade_code=ctx["grade_code"],
        subject_code=ctx["subject_code"],
        topic_text=ctx["topic_text"],
        lp_type=lp_type,
        sub_slo_statements=sub_slo_statements,
        dispatcher=dispatcher or default_request_lp_generation,
    )

    fresh = await _find_existing(conn, scope="global", cache_key=cache_key)
    assert fresh is not None
    log.info(
        "get_or_generate_lp: inserted lesson_slot_id=%s gen_lp_id=%s status=%s requested_sub_slos=%d",
        lesson_slot_id, fresh["id"], fresh["status"], len(requested_ids),
    )
    return _record_to_dataclass(fresh)


async def get_or_generate_class_specific_lp(
    conn: asyncpg.Connection,
    lesson_slot_id: UUID,
    *,
    dispatcher: DispatchCallable | None = None,
) -> GeneratedLP:
    """
    Class-scope path. Used when a teacher's slot has a topic combo the
    global breakdown didn't have (custom-added at the CST level — D-57).

    cache_key includes `cst_id` so two CSTs with the same topic+lp_type
    still get separate rows; this prevents collisions with the global
    cache.
    """
    log.info("get_or_generate_class_specific_lp: entry lesson_slot_id=%s", lesson_slot_id)

    ctx = await _load_lesson_slot_context(conn, lesson_slot_id)
    curriculum_id = ctx["curriculum_id"]
    cst_id = ctx["cst_id"]
    topic_id = ctx["topic_id"]  # primary topic (D-4)
    lp_type = ctx["lp_type"]

    # D-9/D-12: an LP unit may merge >1 topic. Load the ordered topic set from
    # class_lesson_slot_topics. When the unit spans multiple topics we key the
    # cache on the ordered set (so two distinct multi-topic units don't
    # collide), concatenate their topic_texts in order as page_content, and
    # union their sub-SLOs. Single-topic / legacy slots keep the old behaviour.
    topic_set = await _load_lesson_slot_topic_set(conn, lesson_slot_id)
    topic_ids = [t[0] for t in topic_set] or [topic_id]
    is_multi_topic = len(topic_ids) > 1

    if is_multi_topic:
        cache_key = _build_cache_key_class_topic_set(
            curriculum_id, cst_id, topic_ids, lp_type
        )
        page_content = "\n\n".join(text for _, text in topic_set)
        sub_slo_pairs = await _load_union_topic_sub_slos(conn, topic_ids)
    else:
        cache_key = _build_cache_key_class(curriculum_id, cst_id, topic_id, lp_type)
        page_content = ctx["topic_text"]
        sub_slo_pairs = await _load_topic_sub_slos(conn, topic_id)

    # Class-scoped rows are not in the partial unique index (only `global`
    # is enforced UNIQUE). We do best-effort dedup at the service layer.
    existing = await conn.fetchrow(
        """
        SELECT id, cache_key, scope, scope_ref_id, curriculum_id, grade_id,
               subject_id, topic_id, lp_type, status, job_id, content
        FROM generated_lps
        WHERE scope = 'class' AND scope_ref_id = $1 AND cache_key = $2
        ORDER BY created_at DESC
        LIMIT 1
        """,
        cst_id, cache_key,
    )
    if existing is not None and existing["status"] != "ERROR":
        await _link_slot_to_lp(conn, lesson_slot_id, existing["id"])
        log.info(
            "get_or_generate_class_specific_lp: cache hit gen_lp_id=%s status=%s",
            existing["id"], existing["status"],
        )
        return _record_to_dataclass(existing)

    requested_ids = [p[0] for p in sub_slo_pairs]
    sub_slo_statements = [p[1] for p in sub_slo_pairs]

    new_id = await _insert_pending_lp(
        conn,
        scope="class", scope_ref_id=cst_id, cache_key=cache_key,
        curriculum_id=curriculum_id, grade_id=ctx["grade_id"],
        subject_id=ctx["subject_id"], topic_id=topic_id,
        lp_type=lp_type,
        requested_sub_slo_ids=requested_ids,
    )
    await _link_slot_to_lp(conn, lesson_slot_id, new_id)

    curriculum_code = await _load_curriculum_code(conn, curriculum_id)
    await _dispatch_and_mark(
        conn,
        generated_lp_id=new_id,
        curriculum_code=curriculum_code,
        grade_code=ctx["grade_code"],
        subject_code=ctx["subject_code"],
        topic_text=page_content,
        lp_type=lp_type,
        sub_slo_statements=sub_slo_statements,
        dispatcher=dispatcher or default_request_lp_generation,
    )

    fresh = await conn.fetchrow(
        "SELECT id, cache_key, scope, scope_ref_id, curriculum_id, grade_id, "
        "subject_id, topic_id, lp_type, status, job_id, content "
        "FROM generated_lps WHERE id = $1",
        new_id,
    )
    assert fresh is not None
    return _record_to_dataclass(fresh)


# ---------------------------------------------------------------------------
# F3.10 — Revision LP path
# ---------------------------------------------------------------------------


async def _load_revision_slot_context(
    conn: asyncpg.Connection, lesson_slot_id: UUID
) -> dict:
    """For a revision-type class_lesson_slot, gather the slot's CST/curriculum
    info AND the list of prior topics in the same chapter, ordered."""
    base = await conn.fetchrow(
        """
        SELECT
            cls.id            AS lesson_slot_id,
            cls.cst_id        AS cst_id,
            cls.position      AS slot_position,
            cls.slot_type     AS slot_type,
            cls.book_chapter_id AS book_chapter_id,
            o.curriculum_id   AS curriculum_id,
            sc.grade_id       AS grade_id,
            cst.subject_id    AS subject_id,
            g.code            AS grade_code,
            s.code            AS subject_code
        FROM class_lesson_slots cls
        JOIN class_subject_teachers cst ON cst.id = cls.cst_id
        JOIN school_classes sc          ON sc.id = cst.school_class_id
        JOIN organizations o            ON o.id = cst.org_id
        JOIN grades g                   ON g.id = sc.grade_id
        JOIN subjects s                 ON s.id = cst.subject_id
        WHERE cls.id = $1
        """,
        lesson_slot_id,
    )
    if base is None:
        raise ValueError(f"lesson_slot_id={lesson_slot_id} not found")
    if base["slot_type"] != "revision":
        raise ValueError(
            f"lesson_slot_id={lesson_slot_id} is not a revision slot "
            f"(slot_type={base['slot_type']!r}); use get_or_generate_lp instead"
        )

    # Walk class_lesson_slots within the same chapter & cst, position
    # below the revision slot. This is what `chapter.topics_before(this_slot)`
    # resolves to in code.
    prior_rows = await conn.fetch(
        """
        SELECT cls.topic_id, t.topic_text, cls.position
        FROM class_lesson_slots cls
        JOIN topics t            ON t.id = cls.topic_id
        WHERE cls.cst_id = $1
          AND cls.book_chapter_id = $2
          AND cls.position < $3
          AND cls.slot_type = 'lesson'
          AND cls.topic_id IS NOT NULL
        ORDER BY cls.position
        """,
        base["cst_id"], base["book_chapter_id"], base["slot_position"],
    )
    return {**base, "prior_topics": prior_rows}


def _hash_topic_id_list(topic_ids: list[UUID]) -> str:
    canonical = ",".join(sorted(str(t) for t in topic_ids))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def get_or_generate_revision_lp(
    conn: asyncpg.Connection,
    lesson_slot_id: UUID,
    *,
    dispatcher: DispatchCallable | None = None,
) -> GeneratedLP:
    """
    F3.10 — Revision LP path.

    Cache key: f"{curriculum_id}:revision:{topic_ids_hash}" where
    topic_ids = the chapter's lesson-slot topics PRECEDING this revision
    slot (capped at REVISION_MAX_PRIOR_TOPICS for context-window safety).

    `page_content` = "\\n\\n".join(prior topic_texts).

    The list of topic_ids is persisted to `generated_lp_revision_topics`
    so the F3.8 tagging service can union their sub-SLOs as candidates.
    """
    log.info("get_or_generate_revision_lp: entry lesson_slot_id=%s", lesson_slot_id)

    ctx = await _load_revision_slot_context(conn, lesson_slot_id)
    prior = ctx["prior_topics"]
    if not prior:
        raise ValueError(
            f"revision slot {lesson_slot_id} has no preceding lesson topics"
        )

    # Cap to last N topics; sort by position (already sorted by query).
    if len(prior) > REVISION_MAX_PRIOR_TOPICS:
        log.info(
            "get_or_generate_revision_lp: truncating %d -> %d prior topics",
            len(prior), REVISION_MAX_PRIOR_TOPICS,
        )
        prior = prior[-REVISION_MAX_PRIOR_TOPICS:]

    topic_ids = [r["topic_id"] for r in prior]
    topic_ids_hash = _hash_topic_id_list(topic_ids)
    cache_key = f"{ctx['curriculum_id']}:revision:{topic_ids_hash}"

    existing = await conn.fetchrow(
        """
        SELECT id, cache_key, scope, scope_ref_id, curriculum_id, grade_id,
               subject_id, topic_id, lp_type, status, job_id, content
        FROM generated_lps
        WHERE cache_key = $1 AND scope = 'global'
        """,
        cache_key,
    )
    if existing is not None and existing["status"] != "ERROR":
        await _link_slot_to_lp(conn, lesson_slot_id, existing["id"])
        log.info(
            "get_or_generate_revision_lp: cache hit gen_lp_id=%s",
            existing["id"],
        )
        return _record_to_dataclass(existing)

    # D-5: requested sub-SLOs = union over the capped prior topics. Use the
    # *capped* set so steering matches what we actually sent in page_content.
    sub_slo_pairs = await _load_union_topic_sub_slos(conn, topic_ids)
    requested_ids = [p[0] for p in sub_slo_pairs]
    sub_slo_statements = [p[1] for p in sub_slo_pairs]

    # Insert PENDING with topic_id NULL and revision_topic_set_hash set.
    new_id = await conn.fetchval(
        """
        INSERT INTO generated_lps (
            cache_key, scope, scope_ref_id,
            curriculum_id, grade_id, subject_id,
            topic_id, revision_topic_set_hash, lp_type, status,
            requested_sub_slo_ids
        )
        VALUES ($1, 'global', NULL, $2, $3, $4, NULL, $5, 'revision', 'PENDING', $6)
        RETURNING id
        """,
        cache_key, ctx["curriculum_id"], ctx["grade_id"], ctx["subject_id"],
        topic_ids_hash, requested_ids,
    )

    # Persist topic membership so tagging (F3.8) can union sub-SLOs.
    await conn.executemany(
        """
        INSERT INTO generated_lp_revision_topics (generated_lp_id, topic_id, position)
        VALUES ($1, $2, $3)
        ON CONFLICT (generated_lp_id, topic_id) DO NOTHING
        """,
        [(new_id, r["topic_id"], i + 1) for i, r in enumerate(prior)],
    )
    await _link_slot_to_lp(conn, lesson_slot_id, new_id)

    page_content = "\n\n".join(
        (r["topic_text"] or "").strip()
        for r in prior
        if (r["topic_text"] or "").strip()
    )
    if not page_content:
        await _mark_error(conn, new_id, "all prior topic_texts were empty")
        fresh = await conn.fetchrow(
            "SELECT id, cache_key, scope, scope_ref_id, curriculum_id, grade_id, "
            "subject_id, topic_id, lp_type, status, job_id, content "
            "FROM generated_lps WHERE id = $1",
            new_id,
        )
        return _record_to_dataclass(fresh)

    curriculum_code = await _load_curriculum_code(conn, ctx["curriculum_id"])
    await _dispatch_and_mark(
        conn,
        generated_lp_id=new_id,
        curriculum_code=curriculum_code,
        grade_code=ctx["grade_code"],
        subject_code=ctx["subject_code"],
        topic_text=page_content,
        lp_type="revision",
        sub_slo_statements=sub_slo_statements,
        dispatcher=dispatcher or default_request_lp_generation,
    )

    fresh = await conn.fetchrow(
        "SELECT id, cache_key, scope, scope_ref_id, curriculum_id, grade_id, "
        "subject_id, topic_id, lp_type, status, job_id, content "
        "FROM generated_lps WHERE id = $1",
        new_id,
    )
    assert fresh is not None
    log.info(
        "get_or_generate_revision_lp: inserted gen_lp_id=%s prior_topics=%d",
        new_id, len(prior),
    )
    return _record_to_dataclass(fresh)
