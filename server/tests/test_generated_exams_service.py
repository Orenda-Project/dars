"""
F3.5 — tests for generated_exams cache service.

Unit tests cover the hashing helpers (deterministic + order-independent
where it should be). DB-gated tests cover cache miss/hit/class-scope
against the seeded demo CST.
"""
import os
from uuid import UUID, uuid4

import asyncpg
import pytest

from dars.config import settings
from dars.generated_exams.service import (
    build_cache_key_class,
    build_cache_key_global,
    build_question_config,
    get_or_generate_class_specific_exam,
    get_or_generate_exam,
    hash_question_config,
    hash_topic_ids,
    load_assessment_slot_context,
)
from dars.generated_exams.ug_eg_client import ExamRequest


# ---------------------------------------------------------------------------
# Hashing — pure
# ---------------------------------------------------------------------------


def test_hash_topic_ids_is_order_independent():
    a = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    b = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    c = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    h1 = hash_topic_ids([a, b, c])
    h2 = hash_topic_ids([c, a, b])
    h3 = hash_topic_ids([b, c, a])
    assert h1 == h2 == h3


def test_hash_topic_ids_differs_for_different_sets():
    a = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    b = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    c = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    assert hash_topic_ids([a, b]) != hash_topic_ids([a, c])


def test_hash_question_config_is_key_order_independent():
    cfg1 = {"a": 1, "b": [3, 2, 1], "c": {"x": 1, "y": 2}}
    cfg2 = {"c": {"y": 2, "x": 1}, "b": [3, 2, 1], "a": 1}
    assert hash_question_config(cfg1) == hash_question_config(cfg2)


def test_hash_question_config_respects_list_order():
    """We intentionally keep list order, since question type order matters."""
    assert hash_question_config({"x": [1, 2]}) != hash_question_config({"x": [2, 1]})


def test_build_question_config_extracts_right_fields():
    req = ExamRequest(
        curriculum_code="DARS", grade=1, subject="Eng",
        page_content="x", callback_url="https://dars.example/cb",
        question_types=["unseen"], unseen_categories=["objective"],
        unseen_objective_types=["MCQs"],
        unseen_objective_counts={"MCQs": 5},
    )
    cfg = build_question_config(req)
    assert cfg["subject"] == "Eng"
    assert cfg["question_types"] == ["unseen"]
    assert cfg["unseen_objective_counts"] == {"MCQs": 5}
    # `page_content` and `curriculum_code` are NOT in the config hash
    # (curriculum is part of cache_key separately; page_content is
    # derived from topics).
    assert "page_content" not in cfg
    assert "curriculum_code" not in cfg


def test_cache_key_global_vs_class_differ():
    cur = UUID("11111111-1111-1111-1111-111111111111")
    cst = UUID("22222222-2222-2222-2222-222222222222")
    h1 = "topichash"
    h2 = "confighash"
    gk = build_cache_key_global(cur, h1, "exam", h2)
    ck = build_cache_key_class(cur, cst, h1, "exam", h2)
    assert gk == f"{cur}:topichash:exam:confighash"
    assert str(cst) in ck
    assert ck != gk


# ---------------------------------------------------------------------------
# DB-gated — end-to-end against seeded assessment slot
# ---------------------------------------------------------------------------


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


def _fa_payload() -> ExamRequest:
    """Default FA config — overwritten by service to set curriculum/page_content."""
    return ExamRequest(
        curriculum_code="DARS", grade=1, subject="Eng",
        page_content="placeholder",
        callback_url="https://dars.example/placeholder",
        question_types=["unseen"], unseen_categories=["objective"],
        unseen_objective_types=["MCQs", "True/False", "Fill in the Blanks"],
        unseen_objective_counts={"MCQs": 5, "True/False": 3, "Fill in the Blanks": 2},
    )


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DB-backed test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestGeneratedExamCache:
    async def _seed_slot(self, conn: asyncpg.Connection):
        row = await conn.fetchrow(
            """
            SELECT cas.id AS slot_id, cas.cst_id, cst.curriculum_id
            FROM class_assessment_slots cas
            JOIN class_subject_teachers cst ON cst.id = cas.cst_id
            JOIN organizations o ON o.id = cst.org_id
            JOIN class_assessment_slot_topics cast2 ON cast2.class_assessment_slot_id = cas.id
            WHERE o.api_key_prefix = 'dk_demo'
            GROUP BY cas.id, cst.curriculum_id
            HAVING COUNT(cast2.topic_id) > 0
            ORDER BY cas.position
            LIMIT 1
            """
        )
        assert row is not None, "demo CST has no eligible assessment slot"
        await conn.execute(
            "UPDATE class_assessment_slots SET generated_exam_id = NULL WHERE id = $1",
            row["slot_id"],
        )
        return row

    async def test_cache_miss_then_hit(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            slot = await self._seed_slot(conn)
            calls = []

            async def fake_dispatcher(req) -> str:
                calls.append(req.callback_url)
                return f"exam-job-{uuid4()}"

            ctx = await load_assessment_slot_context(
                conn, slot["slot_id"], payload=_fa_payload()
            )
            exam1 = await get_or_generate_exam(
                conn, ctx, dispatcher=fake_dispatcher
            )
            assert exam1.status == "IN_FLIGHT"
            assert exam1.scope == "global"
            assert exam1.cache_key.startswith(f"{slot['curriculum_id']}:")
            assert f"/api/v1/webhooks/exam/{exam1.id}" in calls[0]
            assert len(calls) == 1

            linked = await conn.fetchval(
                "SELECT generated_exam_id FROM class_assessment_slots WHERE id = $1",
                slot["slot_id"],
            )
            assert linked == exam1.id

            # Hit
            exam2 = await get_or_generate_exam(
                conn, ctx, dispatcher=fake_dispatcher
            )
            assert exam2.id == exam1.id
            assert len(calls) == 1

            # Cleanup
            await conn.execute(
                "UPDATE class_assessment_slots SET generated_exam_id = NULL WHERE id = $1",
                slot["slot_id"],
            )
            await conn.execute("DELETE FROM generated_exams WHERE id = $1", exam1.id)
        finally:
            await conn.close()

    async def test_class_specific_creates_separate_row(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            slot = await self._seed_slot(conn)
            calls = []

            async def fake_dispatcher(req) -> str:
                calls.append(req.callback_url)
                return f"exam-job-{uuid4()}"

            ctx = await load_assessment_slot_context(
                conn, slot["slot_id"], payload=_fa_payload()
            )
            global_exam = await get_or_generate_exam(
                conn, ctx, dispatcher=fake_dispatcher
            )
            class_exam = await get_or_generate_class_specific_exam(
                conn, ctx, dispatcher=fake_dispatcher
            )
            assert class_exam.id != global_exam.id
            assert class_exam.scope == "class"
            assert class_exam.scope_ref_id == slot["cst_id"]
            assert len(calls) == 2

            # Cleanup
            await conn.execute(
                "UPDATE class_assessment_slots SET generated_exam_id = NULL WHERE id = $1",
                slot["slot_id"],
            )
            await conn.execute(
                "DELETE FROM generated_exams WHERE id = ANY($1)",
                [global_exam.id, class_exam.id],
            )
        finally:
            await conn.close()
