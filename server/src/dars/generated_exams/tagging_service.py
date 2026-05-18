"""
F3.9 — Post-generation exam question tagging.

Background task triggered by the exam webhook (F3.6) after generation
lands. For each question in the exam, asks an LLM which (one or zero)
of the candidate sub-SLOs (derived from the assessment's covered
topics) it tests. Persists the mapping as a JSONB blob on
`generated_exams.question_sub_slo_tags` keyed by
`"{category}:{type}:{index}"`.

Performance note: an exam with 20 questions = 20 LLM calls. The exam
itself is cache-keyed so re-runs are no-ops; we also skip re-tagging if
`tagging_status='done'`.
"""
import json
import logging
import re
from typing import Awaitable, Callable
from uuid import UUID

import asyncpg

from dars.breakdown.llm_client import call_llm as default_call_llm

log = logging.getLogger("generated_exams.tagging_service")

LLMCallable = Callable[[str, str], Awaitable[str]]


_SYSTEM_PROMPT = """You are an instructional alignment expert.

You will be given:
1. An exam question (the text the student sees).
2. A numbered list of candidate Sub-SLOs that the exam is supposed to assess.

Your task: pick the ONE sub-SLO that the question most directly tests, OR pick none if the question doesn't clearly test any of the candidates.

OUTPUT INSTRUCTIONS — STRICT JSON ONLY
Return only a valid JSON object, no markdown, no prose, exactly this shape:
{ "sub_slo_code": "<code from the candidate list>" }
or, if none apply:
{ "sub_slo_code": null }
"""


_FENCE_RE = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text
    text = _FENCE_RE.sub("", text)
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _build_user_message(question_text: str, candidates: list[dict]) -> str:
    block = "\n".join(f"- {c['code']}: {c['statement']}" for c in candidates)
    return (
        f"QUESTION:\n{question_text}\n\n"
        f"CANDIDATE SUB-SLOs:\n{block}\n\n"
        "Pick at most one code; return null if none fit."
    )


def iter_questions(exam_json: dict):
    """
    Walk the exam_json's question tree and yield
        (key, question_text, marks)
    for each question. key format: '<scope>:<category>:<type>:<index>'.

    scope ∈ {'unseen', 'seen'}; category ∈ {'objective', 'subjective'};
    type is the question_type bucket (e.g. 'MCQs', 'Brief Answers').
    index is the position within that bucket.
    """
    if not isinstance(exam_json, dict):
        return
    for scope in ("unseen", "seen"):
        scope_block = exam_json.get(scope)
        if not isinstance(scope_block, dict):
            continue
        for category in ("objective", "subjective"):
            cat_block = scope_block.get(category)
            if not isinstance(cat_block, dict):
                continue
            for qtype, items in cat_block.items():
                if not isinstance(items, list):
                    continue
                for i, q in enumerate(items):
                    if not isinstance(q, dict):
                        continue
                    text_parts: list[str] = []
                    for fld in ("main_question", "question", "passage"):
                        v = q.get(fld)
                        if isinstance(v, str) and v.strip():
                            text_parts.append(v.strip())
                    if not text_parts:
                        continue
                    key = f"{scope}:{category}:{qtype}:{i}"
                    yield key, "\n".join(text_parts), q.get("marks")


async def _load_candidates_for_assessment(
    conn: asyncpg.Connection, generated_exam_id: UUID
) -> list[dict]:
    """
    Candidate sub-SLOs = sub-SLOs linked to any topic covered by the
    assessment slots that point at this generated_exam.
    """
    rows = await conn.fetch(
        """
        SELECT DISTINCT ss.id, ss.code, ss.statement
        FROM class_assessment_slots cas
        JOIN class_assessment_slot_topics cast2
            ON cast2.class_assessment_slot_id = cas.id
        JOIN topic_sub_slos tss ON tss.topic_id = cast2.topic_id
        JOIN sub_slos ss ON ss.id = tss.sub_slo_id
        WHERE cas.generated_exam_id = $1
        ORDER BY ss.code
        """,
        generated_exam_id,
    )
    return [{"id": r["id"], "code": r["code"], "statement": r["statement"]} for r in rows]


async def tag_generated_exam(
    conn: asyncpg.Connection,
    generated_exam_id: UUID,
    *,
    llm: LLMCallable | None = None,
) -> None:
    """
    Iterate the exam's question tree, ask the LLM to map each to a
    candidate sub-SLO, store mapping on `generated_exams.question_sub_slo_tags`.

    Idempotent: if `tagging_status='done'`, no-op.
    On error: sets `tagging_status='failed'` and returns without raising.
    """
    log.info("tag_generated_exam: entry id=%s", generated_exam_id)

    row = await conn.fetchrow(
        """
        SELECT id, status, tagging_status, result
        FROM generated_exams
        WHERE id = $1
        """,
        generated_exam_id,
    )
    if row is None:
        log.warning("tag_generated_exam: id=%s not found", generated_exam_id)
        return
    if row["status"] != "READY":
        log.info(
            "tag_generated_exam: id=%s status=%s — skipping",
            generated_exam_id, row["status"],
        )
        return
    if row["tagging_status"] == "done":
        log.info("tag_generated_exam: id=%s already tagged", generated_exam_id)
        return

    result = row["result"]
    # asyncpg may return JSONB as str or dict depending on codec config
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            result = None
    if not isinstance(result, dict):
        log.warning("tag_generated_exam: id=%s has no usable result", generated_exam_id)
        await _mark_failed(conn, generated_exam_id)
        return

    candidates = await _load_candidates_for_assessment(conn, generated_exam_id)
    if not candidates:
        log.info(
            "tag_generated_exam: id=%s has no candidate sub-SLOs — done empty",
            generated_exam_id,
        )
        await conn.execute(
            """
            UPDATE generated_exams
            SET question_sub_slo_tags = '{}'::JSONB,
                tagging_status = 'done', updated_at = now()
            WHERE id = $1
            """,
            generated_exam_id,
        )
        return

    code_to_id = {c["code"]: c["id"] for c in candidates}
    tags: dict[str, str] = {}
    llm_call = llm or default_call_llm
    questions = list(iter_questions(result))
    if not questions:
        log.info(
            "tag_generated_exam: id=%s has no parsable questions — done empty",
            generated_exam_id,
        )
        await conn.execute(
            """
            UPDATE generated_exams
            SET question_sub_slo_tags = '{}'::JSONB,
                tagging_status = 'done', updated_at = now()
            WHERE id = $1
            """,
            generated_exam_id,
        )
        return

    failures = 0
    for key, qtext, _marks in questions:
        try:
            raw = await llm_call(_SYSTEM_PROMPT, _build_user_message(qtext, candidates))
            cleaned = _strip_fences(raw)
            parsed = json.loads(cleaned)
            code = parsed.get("sub_slo_code")
            if code and code in code_to_id:
                tags[key] = str(code_to_id[code])
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "tag_generated_exam: question %s tagging failed: %s",
                key, exc,
            )
            failures += 1

    # If literally every call failed, mark failed; otherwise commit what we got.
    if failures > 0 and not tags:
        await _mark_failed(conn, generated_exam_id)
        return

    await conn.execute(
        """
        UPDATE generated_exams
        SET question_sub_slo_tags = $1::JSONB,
            tagging_status = 'done', updated_at = now()
        WHERE id = $2
        """,
        json.dumps(tags), generated_exam_id,
    )
    log.info(
        "tag_generated_exam: id=%s done tagged_questions=%d total_questions=%d failures=%d",
        generated_exam_id, len(tags), len(questions), failures,
    )


async def _mark_failed(conn: asyncpg.Connection, generated_exam_id: UUID) -> None:
    await conn.execute(
        """
        UPDATE generated_exams
        SET tagging_status = 'failed', updated_at = now()
        WHERE id = $1
        """,
        generated_exam_id,
    )
