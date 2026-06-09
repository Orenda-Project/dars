"""
Chapter-plan service tests (chapter-planner-in-dars Phase 2).

The pure slot-sequence helpers (allocate_chapter_days / plan_chapter_slots /
compute_chapter_day_budget / PlannedSlot / ChapterDayAllocation) were removed in
Phase 2 (F2.3) — break-it-down now delegates sequencing to the intelligent
Chapter Planner (`make_chapter_plan`). What remains to test here:

- `build_plan_request` (F2.1) — DB-gated: shapes a real chapter into a
  PlanRequest (one topic per row, sub-SLOs as `[code] statement`).
- `generate_chapter_plan` (F2.2/F2.4) — DB-gated: persists lessons-only
  (one `class_lesson_slot` per Plan Unit + N `class_lesson_slot_topics` rows,
  lead `topic_id` == first), ZERO assessment slots, with an injected stub
  planner LLM. Plus the refusal paths and the no-fallback rule (D-5).
"""
import json
import os
import uuid as _uuid
from datetime import date

import asyncpg
import pytest

from dars.breakdown.chapter_plan_service import (
    build_plan_request,
    generate_chapter_plan,
)
from dars.breakdown.planner import PlanValidationError
from dars.breakdown.planner_llm import PlannerLLMError
from dars.config import settings


# ---------------------------------------------------------------------------
# Stub planner LLMs (no live model)
# ---------------------------------------------------------------------------
class StubPlannerLLM:
    """Returns a canned ``{"units": [...]}`` JSON payload."""

    def __init__(self, response: str):
        self._response = response

    async def complete(self, system: str, user: str) -> str:
        return self._response


class BoomLLM:
    async def complete(self, system: str, user: str) -> str:
        raise PlannerLLMError("backend down")


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


# ---------------------------------------------------------------------------
# DB-backed integration tests (gated on DATABASE_URL, like the other DB tests)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DB-backed test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestGenerateChapterPlanAgainstDB:
    async def _build_graph(self, conn):
        """
        Create a throwaway org → school → AY → class → CST → timetable → book →
        chapter → 2 topics → 2 sub-SLOs → class path with dates giving exactly
        2 teaching days. Returns ids + a cleanup fn.
        """
        ids = {}
        curriculum = await conn.fetchrow("SELECT id FROM curriculums LIMIT 1")
        grade = await conn.fetchrow("SELECT id, code FROM grades ORDER BY code LIMIT 1")
        subject = await conn.fetchrow("SELECT id, code FROM subjects WHERE code = 'Eng'")
        assert subject is not None, "seed must provide an 'Eng' subject"
        ids["subject_code"] = subject["code"]
        ids["grade_code"] = grade["code"]

        org_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO organizations
              (id, name, curriculum_id, api_key_hash, api_key_prefix)
            VALUES ($1, $2, $3, 'x', 'xxxxxxxx')
            """,
            org_id, "F2 test org", curriculum["id"],
        )
        ids["org_id"] = org_id

        school_id = _uuid.uuid4()
        await conn.execute(
            "INSERT INTO schools (id, org_id, name) VALUES ($1, $2, 'F2 school')",
            school_id, org_id,
        )
        ay_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO academic_years (id, org_id, school_id, name, start_date, end_date)
            VALUES ($1, $2, $3, 'AY', $4, $5)
            """,
            ay_id, org_id, school_id, date(2026, 1, 1), date(2026, 12, 31),
        )
        class_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO school_classes
              (id, org_id, school_id, academic_year_id, grade_id, section, name)
            VALUES ($1, $2, $3, $4, $5, 'A', 'Class A')
            """,
            class_id, org_id, school_id, ay_id, grade["id"],
        )
        cst_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO class_subject_teachers (id, org_id, school_class_id, subject_id)
            VALUES ($1, $2, $3, $4)
            """,
            cst_id, org_id, class_id, subject["id"],
        )
        ids["cst_id"] = cst_id
        # Mon-Fri timetable.
        for dow in (0, 1, 2, 3, 4):
            await conn.execute(
                "INSERT INTO timetables (cst_id, day_of_week) VALUES ($1, $2)",
                cst_id, dow,
            )

        # Book + chapter + 2 topics.
        book_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO books (id, curriculum_id, grade_id, subject_id, title)
            VALUES ($1, $2, $3, $4, 'F2 book')
            """,
            book_id, curriculum["id"], grade["id"], subject["id"],
        )
        chapter_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO book_chapters (id, book_id, chapter_number, title, status)
            VALUES ($1, $2, 1, 'F2 chapter', 'published')
            """,
            chapter_id, book_id,
        )
        ids["book_chapter_id"] = chapter_id
        topic_ids = []
        for n, title in ((1, "Topic One"), (2, "Topic Two")):
            tid = _uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO topics
                  (id, book_chapter_id, topic_number, title, topic_text, status)
                VALUES ($1, $2, $3, $4, $5, 'published')
                """,
                tid, chapter_id, n, title, f"text for {title}",
            )
            topic_ids.append(tid)
        ids["topic_ids"] = topic_ids

        # SLO + 2 sub-SLOs, one mapped to each topic (each topic ≥1 SLO).
        slo_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO slos (id, curriculum_id, grade_id, subject_id, code, statement)
            VALUES ($1, $2, $3, $4, 'R1', 'reading slo')
            """,
            slo_id, curriculum["id"], grade["id"], subject["id"],
        )
        sub_a = _uuid.uuid4()
        sub_b = _uuid.uuid4()
        await conn.execute(
            "INSERT INTO sub_slos (id, slo_id, code, statement, position) VALUES ($1,$2,'R1-01','reads words',1)",
            sub_a, slo_id,
        )
        await conn.execute(
            "INSERT INTO sub_slos (id, slo_id, code, statement, position) VALUES ($1,$2,'R1-02','names letters',2)",
            sub_b, slo_id,
        )
        ids["sub_a"] = str(sub_a)
        ids["sub_b"] = str(sub_b)
        await conn.execute(
            "INSERT INTO topic_sub_slos (topic_id, sub_slo_id) VALUES ($1,$2)",
            topic_ids[0], sub_a,
        )
        await conn.execute(
            "INSERT INTO topic_sub_slos (topic_id, sub_slo_id) VALUES ($1,$2)",
            topic_ids[1], sub_b,
        )

        # Class path with dates = Mon 2026-06-01 .. Tue 2026-06-02 = 2 teaching days.
        await conn.execute(
            """
            INSERT INTO class_chapters
              (org_id, cst_id, book_chapter_id, position, start_date, end_date)
            VALUES ($1, $2, $3, 1, $4, $5)
            """,
            org_id, cst_id, chapter_id, date(2026, 6, 1), date(2026, 6, 2),
        )

        async def cleanup():
            await conn.execute("DELETE FROM organizations WHERE id=$1", org_id)
            await conn.execute("DELETE FROM books WHERE id=$1", book_id)

        return ids, cleanup

    async def test_build_plan_request_shapes_chapter(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn)
            try:
                req = await build_plan_request(
                    conn,
                    book_chapter_id=ids["book_chapter_id"],
                    subject=ids["subject_code"],
                    grade=ids["grade_code"],
                    period_count=2,
                )
                assert len(req.chapter.topics) == 2
                assert req.chapter.topics[0].slos[0].statement.startswith("[R1-01]")
                all_slo_ids = {s.id for t in req.chapter.topics for s in t.slos}
                assert all_slo_ids == {ids["sub_a"], ids["sub_b"]}
            finally:
                await cleanup()
        finally:
            await conn.close()

    async def test_generate_persists_lessons_only_with_topic_grouping(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn)
            try:
                # 2 teaching days → planner returns 2 units. Unit 1 GROUPS both
                # topics (K=2); unit 2 is single-topic. Both SLOs covered.
                units = {
                    "units": [
                        {"sequence": 1, "lp_type": "reading",
                         "topic_ids": [str(ids["topic_ids"][0]), str(ids["topic_ids"][1])],
                         "slo_ids": [ids["sub_a"], ids["sub_b"]], "rationale": "combined"},
                        {"sequence": 2, "lp_type": "grammar",
                         "topic_ids": [str(ids["topic_ids"][1])],
                         "slo_ids": [ids["sub_b"]], "rationale": "letters"},
                    ]
                }
                result = await generate_chapter_plan(
                    conn,
                    cst_id=ids["cst_id"],
                    book_chapter_id=ids["book_chapter_id"],
                    org_id=ids["org_id"],
                    llm=StubPlannerLLM(json.dumps(units)),
                )
                assert result.slot_count == 2
                assert result.lesson_slot_count == 2
                assert result.assessment_slot_count == 0
                assert result.source == "cpe"

                slot_rows = await conn.fetch(
                    """
                    SELECT id, position, lp_type, topic_id
                      FROM class_lesson_slots
                     WHERE cst_id=$1 AND book_chapter_id=$2
                     ORDER BY position
                    """,
                    ids["cst_id"], ids["book_chapter_id"],
                )
                assert len(slot_rows) == 2
                assert slot_rows[0]["lp_type"] == "reading"
                assert slot_rows[0]["topic_id"] == ids["topic_ids"][0]
                assert slot_rows[1]["topic_id"] == ids["topic_ids"][1]

                asmt = await conn.fetchval(
                    "SELECT count(*) FROM class_assessment_slots WHERE cst_id=$1 AND book_chapter_id=$2",
                    ids["cst_id"], ids["book_chapter_id"],
                )
                assert asmt == 0

                # Multi-topic unit → K=2 join rows, position 1..2 in list order.
                join = await conn.fetch(
                    """
                    SELECT topic_id, position FROM class_lesson_slot_topics
                     WHERE class_lesson_slot_id=$1 ORDER BY position
                    """,
                    slot_rows[0]["id"],
                )
                assert [r["position"] for r in join] == [1, 2]
                assert [r["topic_id"] for r in join] == ids["topic_ids"]
                join2 = await conn.fetch(
                    "SELECT topic_id, position FROM class_lesson_slot_topics WHERE class_lesson_slot_id=$1",
                    slot_rows[1]["id"],
                )
                assert len(join2) == 1 and join2[0]["position"] == 1
            finally:
                await cleanup()
        finally:
            await conn.close()

    async def test_refuses_chapter_not_in_class_path(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn)
            try:
                await conn.execute(
                    "DELETE FROM class_chapters WHERE cst_id=$1", ids["cst_id"]
                )
                with pytest.raises(ValueError, match="not in this class's plan"):
                    await generate_chapter_plan(
                        conn,
                        cst_id=ids["cst_id"],
                        book_chapter_id=ids["book_chapter_id"],
                        org_id=ids["org_id"],
                        llm=StubPlannerLLM('{"units": []}'),
                    )
            finally:
                await cleanup()
        finally:
            await conn.close()

    async def test_refuses_when_already_broken_down(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn)
            try:
                await conn.execute(
                    """
                    INSERT INTO class_lesson_slots
                      (org_id, cst_id, position, slot_type, book_chapter_id, status)
                    VALUES ($1, $2, 1, 'lesson', $3, 'planned')
                    """,
                    ids["org_id"], ids["cst_id"], ids["book_chapter_id"],
                )
                with pytest.raises(ValueError, match="already broken down"):
                    await generate_chapter_plan(
                        conn,
                        cst_id=ids["cst_id"],
                        book_chapter_id=ids["book_chapter_id"],
                        org_id=ids["org_id"],
                        llm=StubPlannerLLM('{"units": []}'),
                    )
            finally:
                await cleanup()
        finally:
            await conn.close()

    async def test_planner_failure_propagates_no_fallback(self):
        # D-5: a planner transport error raises; nothing is persisted.
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn)
            try:
                with pytest.raises(PlannerLLMError):
                    await generate_chapter_plan(
                        conn,
                        cst_id=ids["cst_id"],
                        book_chapter_id=ids["book_chapter_id"],
                        org_id=ids["org_id"],
                        llm=BoomLLM(),
                    )
                count = await conn.fetchval(
                    "SELECT count(*) FROM class_lesson_slots WHERE cst_id=$1",
                    ids["cst_id"],
                )
                assert count == 0
            finally:
                await cleanup()
        finally:
            await conn.close()

    async def test_invalid_plan_raises_validation_error(self):
        # Planner returns wrong unit count → PlanValidationError (a ValueError).
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn)
            try:
                bad = {"units": [
                    {"sequence": 1, "lp_type": "reading",
                     "topic_ids": [str(ids["topic_ids"][0])],
                     "slo_ids": [ids["sub_a"], ids["sub_b"]], "rationale": "x"},
                ]}  # only 1 unit, but slot_count == 2
                with pytest.raises(PlanValidationError):
                    await generate_chapter_plan(
                        conn,
                        cst_id=ids["cst_id"],
                        book_chapter_id=ids["book_chapter_id"],
                        org_id=ids["org_id"],
                        llm=StubPlannerLLM(json.dumps(bad)),
                    )
            finally:
                await cleanup()
        finally:
            await conn.close()
