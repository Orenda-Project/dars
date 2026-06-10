"""
F-3.2 — DB-gated tests for get_or_generate_exam_for_assessment_slot.

Mirrors test_generated_exams_service.py's seed pattern (the demo CST's first
assessment slot with covered topics). The dispatcher is faked so no UG_EG HTTP
is made. Skipped without DATABASE_URL.

Covered:
  - no prior exam → PENDING/IN_FLIGHT row inserted, dispatched once, slot's
    generated_exam_id linked, generation_type='class_assessment'.
  - second call (cache hit) → same row, no re-dispatch.
  - ERROR row on the same key → retried (new row), not returned.
"""
import os
from uuid import uuid4

import asyncpg
import pytest

from dars.config import settings
from dars.generated_exams.service import (
    GENERATION_TYPE_FA,
    get_or_generate_exam_for_assessment_slot,
)


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DB-backed test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestGetOrGenerateExamForAssessmentSlot:
    async def _seed_slot(self, conn: asyncpg.Connection):
        row = await conn.fetchrow(
            """
            SELECT cas.id AS slot_id, cas.cst_id, cst.curriculum_id
            FROM class_assessment_slots cas
            JOIN class_subject_teachers cst ON cst.id = cas.cst_id
            JOIN organizations o ON o.id = cst.org_id
            JOIN class_assessment_slot_topics cast2
              ON cast2.class_assessment_slot_id = cas.id
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

    async def test_miss_inserts_dispatches_links_then_hit(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            slot = await self._seed_slot(conn)
            calls = []

            async def fake_dispatcher(req) -> str:
                calls.append(req)
                return f"exam-job-{uuid4()}"

            exam1 = await get_or_generate_exam_for_assessment_slot(
                conn, slot["slot_id"], dispatcher=fake_dispatcher
            )
            assert exam1.status == "IN_FLIGHT"
            assert exam1.scope == "global"
            assert exam1.generation_type == GENERATION_TYPE_FA
            assert exam1.cache_key.startswith(f"{slot['curriculum_id']}:")
            assert len(calls) == 1
            # Dispatched with the FA generation_type + a real callback URL.
            assert calls[0].generation_type == GENERATION_TYPE_FA
            assert f"/api/v1/webhooks/exam/{exam1.id}" in calls[0].callback_url
            # page_content was resolved from the slot's topics (not placeholder).
            assert calls[0].page_content
            assert calls[0].page_content != "placeholder"

            linked = await conn.fetchval(
                "SELECT generated_exam_id FROM class_assessment_slots WHERE id = $1",
                slot["slot_id"],
            )
            assert linked == exam1.id

            # Second call → cache hit, no re-dispatch.
            exam2 = await get_or_generate_exam_for_assessment_slot(
                conn, slot["slot_id"], dispatcher=fake_dispatcher
            )
            assert exam2.id == exam1.id
            assert len(calls) == 1

            await conn.execute(
                "UPDATE class_assessment_slots SET generated_exam_id = NULL WHERE id = $1",
                slot["slot_id"],
            )
            await conn.execute("DELETE FROM generated_exams WHERE id = $1", exam1.id)
        finally:
            await conn.close()

    async def test_error_row_is_retried_not_returned(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            slot = await self._seed_slot(conn)
            calls = []

            async def fake_dispatcher(req) -> str:
                calls.append(req)
                return f"exam-job-{uuid4()}"

            exam1 = await get_or_generate_exam_for_assessment_slot(
                conn, slot["slot_id"], dispatcher=fake_dispatcher
            )
            # Force the row to ERROR; a retry must NOT return it.
            await conn.execute(
                "UPDATE generated_exams SET status = 'ERROR' WHERE id = $1",
                exam1.id,
            )
            exam2 = await get_or_generate_exam_for_assessment_slot(
                conn, slot["slot_id"], dispatcher=fake_dispatcher
            )
            assert exam2.id != exam1.id
            assert exam2.status == "IN_FLIGHT"
            assert len(calls) == 2

            await conn.execute(
                "UPDATE class_assessment_slots SET generated_exam_id = NULL WHERE id = $1",
                slot["slot_id"],
            )
            await conn.execute(
                "DELETE FROM generated_exams WHERE id = ANY($1)",
                [exam1.id, exam2.id],
            )
        finally:
            await conn.close()

    async def test_missing_slot_raises_value_error(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            with pytest.raises(ValueError):
                await get_or_generate_exam_for_assessment_slot(
                    conn, uuid4(), dispatcher=lambda req: None  # noqa: ARG005
                )
        finally:
            await conn.close()
