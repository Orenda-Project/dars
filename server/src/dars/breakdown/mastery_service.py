"""
F4.13 — Submit exam results and roll up per-sub-SLO mastery.

Inputs: a class_assessment_slot_id + per-question (students_correct,
marks_total). Outputs: rows in exam_results, exam_question_results,
sub_slo_mastery. Idempotent on resubmit (deletes + re-inserts for the
slot).

Question identity:
    F3.9 tags questions with composite keys "{scope}:{category}:{type}:{index}"
    while exam_question_results.question_index is an INT. We resolve
    this by walking the generated_exams.result JSON in the same order
    iter_questions() uses and assigning a flat 0..N-1 index. The same
    walk is used both server-side (here) and client-side (the mastery
    form), so indices line up.

Mastery math:
    For each sub_slo_id that any question is tagged to:
        mastery_percent =
            (sum(students_correct for those questions)
             / (count(those questions) * students_present)) * 100
    Stored per (cst_id, sub_slo_id, class_assessment_slot_id, assessed_on).
"""
import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import Iterable
from uuid import UUID

import asyncpg

from dars.generated_exams.tagging_service import iter_questions

log = logging.getLogger("breakdown.mastery")


@dataclass
class PerQuestionResult:
    question_index: int
    students_correct: int
    marks_total: int = 1  # default — UI doesn't always collect marks


@dataclass
class SubmitResultsInput:
    class_assessment_slot_id: UUID
    students_present: int
    recorded_by_teacher_id: UUID | None
    per_question: list[PerQuestionResult]
    assessed_on: date | None = None  # defaults to today


@dataclass
class SubmitResultsResult:
    exam_result_id: UUID
    sub_slo_mastery_rows: int  # how many sub-SLOs got a mastery row


def _enumerate_questions(exam_json: dict) -> list[tuple[str, int]]:
    """
    Walk exam_json the same way F3.9 does and return a list of
    (composite_key, flat_index). The flat_index is the position in the
    iter_questions() sequence (0..N-1).
    """
    out: list[tuple[str, int]] = []
    for i, (key, _text, _marks) in enumerate(iter_questions(exam_json)):
        out.append((key, i))
    return out


async def submit_exam_results(
    conn: asyncpg.Connection,
    payload: SubmitResultsInput,
) -> SubmitResultsResult:
    log.info(
        "submit_exam_results: entry slot=%s present=%d questions=%d",
        payload.class_assessment_slot_id, payload.students_present,
        len(payload.per_question),
    )

    if payload.students_present <= 0:
        raise ValueError("students_present must be > 0")
    for q in payload.per_question:
        if q.students_correct < 0:
            raise ValueError(f"students_correct must be >= 0 (got {q.students_correct})")
        if q.students_correct > payload.students_present:
            raise ValueError(
                f"students_correct={q.students_correct} > students_present={payload.students_present}"
            )

    slot_row = await conn.fetchrow(
        """
        SELECT cas.id, cas.cst_id, cas.generated_exam_id
        FROM class_assessment_slots cas
        WHERE cas.id = $1
        """,
        payload.class_assessment_slot_id,
    )
    if slot_row is None:
        raise ValueError(f"class_assessment_slot_id={payload.class_assessment_slot_id} not found")

    if slot_row["generated_exam_id"] is None:
        raise ValueError("assessment slot has no generated_exam yet; cannot record results")

    exam_row = await conn.fetchrow(
        """
        SELECT result, question_sub_slo_tags
        FROM generated_exams
        WHERE id = $1
        """,
        slot_row["generated_exam_id"],
    )
    if exam_row is None:
        raise ValueError("generated_exam not found")

    exam_json = exam_row["result"]
    if isinstance(exam_json, str):
        try:
            exam_json = json.loads(exam_json)
        except json.JSONDecodeError:
            exam_json = None
    if not isinstance(exam_json, dict):
        raise ValueError("generated_exam.result is empty or invalid; cannot record results")

    question_tags = exam_row["question_sub_slo_tags"] or {}
    if isinstance(question_tags, str):
        try:
            question_tags = json.loads(question_tags)
        except json.JSONDecodeError:
            question_tags = {}
    if not isinstance(question_tags, dict):
        question_tags = {}

    # Walk the exam to build flat_index → composite_key, then composite_key → sub_slo_id.
    enumeration = _enumerate_questions(exam_json)
    flat_to_key: dict[int, str] = {idx: key for key, idx in enumeration}

    # Validate every submitted question_index exists.
    for q in payload.per_question:
        if q.question_index not in flat_to_key:
            raise ValueError(
                f"question_index={q.question_index} is out of range for this exam "
                f"(0..{len(enumeration) - 1})"
            )

    assessed_on = payload.assessed_on or date.today()

    # Wrap inserts in a transaction so a partial failure leaves nothing behind.
    async with conn.transaction():
        # Idempotent: nuke prior results for this slot.
        await conn.execute(
            """
            DELETE FROM sub_slo_mastery
            WHERE class_assessment_slot_id = $1
            """,
            payload.class_assessment_slot_id,
        )
        await conn.execute(
            """
            DELETE FROM exam_results
            WHERE class_assessment_slot_id = $1
            """,
            payload.class_assessment_slot_id,
        )

        exam_result_id = await conn.fetchval(
            """
            INSERT INTO exam_results (
                class_assessment_slot_id, students_present, recorded_by_teacher_id
            ) VALUES ($1, $2, $3)
            RETURNING id
            """,
            payload.class_assessment_slot_id,
            payload.students_present,
            payload.recorded_by_teacher_id,
        )

        # Per-question result rows
        for q in payload.per_question:
            key = flat_to_key[q.question_index]
            sub_slo_raw = question_tags.get(key)
            sub_slo_id: UUID | None
            try:
                sub_slo_id = UUID(sub_slo_raw) if sub_slo_raw else None
            except (TypeError, ValueError):
                sub_slo_id = None
            await conn.execute(
                """
                INSERT INTO exam_question_results (
                    exam_result_id, question_index, sub_slo_id,
                    students_correct, marks_total
                ) VALUES ($1, $2, $3, $4, $5)
                """,
                exam_result_id, q.question_index, sub_slo_id,
                q.students_correct, q.marks_total,
            )

        # Mastery rollup: bucket per sub_slo_id, aggregate.
        buckets: dict[UUID, list[int]] = {}
        for q in payload.per_question:
            key = flat_to_key[q.question_index]
            sub_slo_raw = question_tags.get(key)
            try:
                sub_slo_id = UUID(sub_slo_raw) if sub_slo_raw else None
            except (TypeError, ValueError):
                sub_slo_id = None
            if sub_slo_id is None:
                continue
            buckets.setdefault(sub_slo_id, []).append(q.students_correct)

        mastery_rows = 0
        for sub_slo_id, corrects in buckets.items():
            n = len(corrects)
            denom = n * payload.students_present
            mastery = (sum(corrects) / denom) * 100 if denom > 0 else 0.0
            await conn.execute(
                """
                INSERT INTO sub_slo_mastery (
                    cst_id, sub_slo_id, class_assessment_slot_id,
                    mastery_percent, assessed_on
                ) VALUES ($1, $2, $3, $4, $5)
                """,
                slot_row["cst_id"], sub_slo_id,
                payload.class_assessment_slot_id,
                round(mastery, 2), assessed_on,
            )
            mastery_rows += 1

        # Flip the slot to completed.
        await conn.execute(
            """
            UPDATE class_assessment_slots
            SET status = 'completed', updated_at = now()
            WHERE id = $1
            """,
            payload.class_assessment_slot_id,
        )

    log.info(
        "submit_exam_results: exam_result_id=%s slot=%s mastery_rows=%d",
        exam_result_id, payload.class_assessment_slot_id, mastery_rows,
    )
    return SubmitResultsResult(
        exam_result_id=exam_result_id,
        sub_slo_mastery_rows=mastery_rows,
    )
