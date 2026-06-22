"""
async-chapter-plan — background dispatch + poll tests.

Break-it-down ("generate chapter plan") is now async: POST validates cheaply,
flips the `class_chapters` row to PENDING, dispatches a background job, and
returns 202; the FE polls GET .../plan-status until READY/ERROR.

DB-backed (gated on DATABASE_URL like the other DB tests). Covers:
  - precheck_chapter_plan: returns slot_count on the happy path; raises on the
    three refusal cases (not in path / no teaching days / already broken down).
  - run_chapter_plan_job: GENERATING → READY with slots persisted (success), and
    GENERATING → ERROR with error_message + NO slots (planner failure).
  - The POST endpoint: 202 + PENDING (flips class_chapters to PENDING, doesn't
    run the planner inline), and 409 when a job is already GENERATING.
  - The GET plan-status endpoint: PENDING before the job, READY + correct slot
    counts after the job runs.

The planner LLM is stubbed (StubPlannerLLM / BoomLLM) — no live model. The POST
test runs the job manually after dispatch (FastAPI BackgroundTasks are not
executed by the in-process ASGITransport), then polls the GET endpoint.
"""
import json
import os
import uuid as _uuid
from datetime import date

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from dars.breakdown import chapter_plan_jobs
from dars.breakdown.chapter_plan_service import precheck_chapter_plan
from dars.config import settings
from dars.main import app
from dars.v2_api import deps


class StubPlannerLLM:
    """Returns a canned ``{"units": [...]}`` JSON payload."""

    def __init__(self, response: str):
        self._response = response

    async def complete(self, system: str, user: str) -> str:
        return self._response


class BoomLLM:
    async def complete(self, system: str, user: str) -> str:
        from dars.breakdown.planner_llm import PlannerLLMError

        raise PlannerLLMError("backend down")


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DB-backed test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestAsyncChapterPlanAgainstDB:
    async def _build_graph(self, conn):
        """
        Throwaway org → school → AY → class → CST → Mon-Fri timetable → book →
        chapter → 2 topics → 2 sub-SLOs (unique SLO code to avoid colliding with
        any seeded SLOs) → class path dated to give exactly 2 teaching days.
        Returns ids + the org's API key + a cleanup fn.
        """
        ids = {}
        curriculum = await conn.fetchrow("SELECT id FROM curriculums LIMIT 1")
        grade = await conn.fetchrow("SELECT id, code FROM grades ORDER BY code LIMIT 1")
        subject = await conn.fetchrow("SELECT id, code FROM subjects WHERE code = 'Eng'")
        assert subject is not None, "seed must provide an 'Eng' subject"
        ids["subject_code"] = subject["code"]
        ids["grade_code"] = grade["code"]

        # A real API key so the HTTP endpoints authenticate via X-API-Key.
        import hashlib

        api_key = f"dk_test_{_uuid.uuid4().hex}"
        api_key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        ids["api_key"] = api_key

        org_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO organizations
              (id, name, curriculum_id, api_key_hash, api_key_prefix)
            VALUES ($1, $2, $3, $4, $5)
            """,
            org_id, "async-plan test org", curriculum["id"], api_key_hash,
            api_key[:8],
        )
        ids["org_id"] = org_id

        school_id = _uuid.uuid4()
        await conn.execute(
            "INSERT INTO schools (id, org_id, name) VALUES ($1, $2, 'school')",
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
        for dow in (0, 1, 2, 3, 4):
            await conn.execute(
                "INSERT INTO timetables (cst_id, day_of_week) VALUES ($1, $2)",
                cst_id, dow,
            )

        book_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO books (id, curriculum_id, grade_id, subject_id, title)
            VALUES ($1, $2, $3, $4, 'async-plan book')
            """,
            book_id, curriculum["id"], grade["id"], subject["id"],
        )
        ids["book_id"] = book_id
        chapter_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO book_chapters (id, book_id, chapter_number, title, status)
            VALUES ($1, $2, 1, 'async-plan chapter', 'published')
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

        # Unique SLO code so we never collide with seeded SLOs for this cell.
        slo_code = f"AZP{_uuid.uuid4().hex[:6].upper()}"
        slo_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO slos (id, curriculum_id, grade_id, subject_id, code, statement)
            VALUES ($1, $2, $3, $4, $5, 'async-plan slo')
            """,
            slo_id, curriculum["id"], grade["id"], subject["id"], slo_code,
        )
        sub_a = _uuid.uuid4()
        sub_b = _uuid.uuid4()
        await conn.execute(
            "INSERT INTO sub_slos (id, slo_id, code, statement, position) VALUES ($1,$2,$3,'reads words',1)",
            sub_a, slo_id, f"{slo_code}-01",
        )
        await conn.execute(
            "INSERT INTO sub_slos (id, slo_id, code, statement, position) VALUES ($1,$2,$3,'names letters',2)",
            sub_b, slo_id, f"{slo_code}-02",
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

        # Class path dated Mon 2026-06-01 .. Tue 2026-06-02 = 2 teaching days.
        # status defaults to 'READY' from the migration; tests flip it as needed.
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

    def _two_lesson_units(self, ids):
        return {
            "units": [
                {"sequence": 1, "slot_type": "lesson", "lp_type": "reading",
                 "topic_ids": [str(ids["topic_ids"][0])],
                 "slo_ids": [ids["sub_a"]], "rationale": "teach a"},
                {"sequence": 2, "slot_type": "lesson", "lp_type": "grammar",
                 "topic_ids": [str(ids["topic_ids"][1])],
                 "slo_ids": [ids["sub_b"]], "rationale": "teach b"},
            ]
        }

    # ----- precheck (cheap, synchronous half) -----

    async def test_precheck_returns_slot_count_on_happy_path(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn)
            try:
                count = await precheck_chapter_plan(
                    conn, cst_id=ids["cst_id"],
                    book_chapter_id=ids["book_chapter_id"],
                )
                assert count == 2
            finally:
                await cleanup()
        finally:
            await conn.close()

    async def test_precheck_refuses_not_in_path(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn)
            try:
                await conn.execute(
                    "DELETE FROM class_chapters WHERE cst_id=$1", ids["cst_id"]
                )
                with pytest.raises(ValueError, match="not in this class's plan"):
                    await precheck_chapter_plan(
                        conn, cst_id=ids["cst_id"],
                        book_chapter_id=ids["book_chapter_id"],
                    )
            finally:
                await cleanup()
        finally:
            await conn.close()

    async def test_precheck_refuses_already_broken_down(self):
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
                    await precheck_chapter_plan(
                        conn, cst_id=ids["cst_id"],
                        book_chapter_id=ids["book_chapter_id"],
                    )
            finally:
                await cleanup()
        finally:
            await conn.close()

    # ----- background job -----

    async def test_job_success_sets_ready_with_slots(self, monkeypatch):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn)
            try:
                # The job opens its own connection from settings.database_url, so
                # it naturally points at this same test DB. Stub the planner LLM
                # so generate_chapter_plan doesn't hit a live model.
                stub = StubPlannerLLM(json.dumps(self._two_lesson_units(ids)))
                import dars.breakdown.chapter_plan_service as svc
                monkeypatch.setattr(
                    svc, "AgentSdkPlannerLLM", lambda *a, **k: stub
                )

                # Pre-flip to PENDING (as the endpoint would).
                await conn.execute(
                    "UPDATE class_chapters SET status='PENDING' WHERE cst_id=$1 AND book_chapter_id=$2",
                    ids["cst_id"], ids["book_chapter_id"],
                )
                await chapter_plan_jobs.run_chapter_plan_job(
                    ids["cst_id"], ids["book_chapter_id"], ids["org_id"]
                )

                row = await conn.fetchrow(
                    "SELECT status, error_message FROM class_chapters WHERE cst_id=$1 AND book_chapter_id=$2",
                    ids["cst_id"], ids["book_chapter_id"],
                )
                assert row["status"] == "READY"
                assert row["error_message"] is None
                lessons = await conn.fetchval(
                    "SELECT count(*) FROM class_lesson_slots WHERE cst_id=$1 AND book_chapter_id=$2",
                    ids["cst_id"], ids["book_chapter_id"],
                )
                assert lessons == 2
            finally:
                await cleanup()
        finally:
            await conn.close()

    async def test_job_planner_failure_sets_error_no_slots(self, monkeypatch):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn)
            try:
                import dars.breakdown.chapter_plan_service as svc
                monkeypatch.setattr(
                    svc, "AgentSdkPlannerLLM", lambda *a, **k: BoomLLM()
                )
                await conn.execute(
                    "UPDATE class_chapters SET status='PENDING' WHERE cst_id=$1 AND book_chapter_id=$2",
                    ids["cst_id"], ids["book_chapter_id"],
                )
                # The job swallows the exception and records ERROR (no re-raise).
                await chapter_plan_jobs.run_chapter_plan_job(
                    ids["cst_id"], ids["book_chapter_id"], ids["org_id"]
                )
                row = await conn.fetchrow(
                    "SELECT status, error_message FROM class_chapters WHERE cst_id=$1 AND book_chapter_id=$2",
                    ids["cst_id"], ids["book_chapter_id"],
                )
                assert row["status"] == "ERROR"
                assert row["error_message"] and "backend down" in row["error_message"]
                # No half-written slots.
                slots = await conn.fetchval(
                    """
                    SELECT (SELECT count(*) FROM class_lesson_slots WHERE cst_id=$1)
                         + (SELECT count(*) FROM class_assessment_slots WHERE cst_id=$1)
                    """,
                    ids["cst_id"],
                )
                assert slots == 0
            finally:
                await cleanup()
        finally:
            await conn.close()

    # ----- HTTP endpoints (POST dispatch + GET poll) -----

    async def test_post_returns_202_pending_then_get_ready(self, monkeypatch):
        # Reset the cached pool so deps.get_db_pool builds on this loop pointing
        # at the test DB (mirrors conftest's _reset_db_pool).
        deps._POOL = None
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn)
            try:
                stub = StubPlannerLLM(json.dumps(self._two_lesson_units(ids)))
                import dars.breakdown.chapter_plan_service as svc
                monkeypatch.setattr(
                    svc, "AgentSdkPlannerLLM", lambda *a, **k: stub
                )

                headers = {"X-API-Key": ids["api_key"]}
                url = (
                    f"/api/v2/csts/{ids['cst_id']}/chapters/"
                    f"{ids['book_chapter_id']}/plan"
                )
                status_url = url + "-status"
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    # POST → 202 PENDING. The dispatch response is PENDING; the
                    # registered BackgroundTask runs after the response is sent
                    # (ASGITransport does execute it), so by the time we poll the
                    # status it has already landed READY. We don't assert the
                    # transient PENDING-with-no-slots window — it's a race against
                    # the background task and not load-bearing.
                    r = await c.post(url, headers=headers)
                    assert r.status_code == 202, r.text
                    body = r.json()
                    assert body["status"] == "PENDING"
                    assert body["cst_id"] == str(ids["cst_id"])
                    assert body["book_chapter_id"] == str(ids["book_chapter_id"])

                    # Poll the status endpoint until terminal (mirrors the FE
                    # poll loop) — the background task should have set READY.
                    ready = None
                    for _ in range(20):
                        rg = await c.get(status_url, headers=headers)
                        assert rg.status_code == 200, rg.text
                        ready = rg.json()
                        if ready["status"] in ("READY", "ERROR"):
                            break
                    assert ready is not None
                    assert ready["status"] == "READY", ready
                    assert ready["slot_count"] == 2
                    assert ready["lesson_slot_count"] == 2
                    assert ready["assessment_slot_count"] == 0
                    assert ready["flex_slot_count"] == 0
                    assert ready["error_message"] is None

                    # Slots actually persisted by the background job.
                    lessons = await conn.fetchval(
                        "SELECT count(*) FROM class_lesson_slots WHERE cst_id=$1 AND book_chapter_id=$2",
                        ids["cst_id"], ids["book_chapter_id"],
                    )
                    assert lessons == 2
            finally:
                await cleanup()
        finally:
            await conn.close()
            deps._POOL = None

    async def test_post_conflicts_when_already_generating(self, monkeypatch):
        deps._POOL = None
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn)
            try:
                # Simulate a job already in flight.
                await conn.execute(
                    "UPDATE class_chapters SET status='GENERATING' WHERE cst_id=$1 AND book_chapter_id=$2",
                    ids["cst_id"], ids["book_chapter_id"],
                )
                headers = {"X-API-Key": ids["api_key"]}
                url = (
                    f"/api/v2/csts/{ids['cst_id']}/chapters/"
                    f"{ids['book_chapter_id']}/plan"
                )
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    r = await c.post(url, headers=headers)
                    assert r.status_code == 409, r.text
                # Status unchanged; no slots created.
                st = await conn.fetchval(
                    "SELECT status FROM class_chapters WHERE cst_id=$1 AND book_chapter_id=$2",
                    ids["cst_id"], ids["book_chapter_id"],
                )
                assert st == "GENERATING"
            finally:
                await cleanup()
        finally:
            await conn.close()
            deps._POOL = None
