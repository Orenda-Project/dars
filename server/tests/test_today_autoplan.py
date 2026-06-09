"""
today-prev-current-next — /today auto-plans the current chapter lazily.

The teacher demo must be useful even when nothing has been broken down: on the
Today GET, the endpoint seeds the org-decided class path and, if the current
chapter (first non-done chapter by position) has no slots yet, breaks it down
on the fly so Today can show current_chapter / previous_taught / lesson_slot /
next_up.

These are DB-backed (gated on DATABASE_URL, like the other chapter-plan tests):
each test builds a throwaway org -> school -> AY -> class -> CST -> timetable ->
book -> chapter -> topic -> sub-SLO, plus a published syllabus breakdown so the
path seeds. The planner LLM is monkeypatched to a deterministic stub — NO real
model call (the endpoint calls generate_chapter_plan without an injectable llm,
so we patch the symbol the router imported).
"""
import hashlib
import json
import os
import uuid as _uuid
from datetime import date

import asyncpg
import pytest
from httpx import AsyncClient

import dars.v2_api.router_today_calendar as router_today
from dars.breakdown.chapter_plan_service import (
    generate_chapter_plan as _real_generate_chapter_plan,
)
from dars.config import settings

# AY + chapter share a start so slot positions map 1:1 onto weekdays:
#   pos 1 -> Mon 2026-06-01 ... pos 5 -> Fri 2026-06-05,
#   pos 6 -> Mon 2026-06-08 ... pos 10 -> Fri 2026-06-12.
AY_START = date(2026, 6, 1)
AY_END = date(2026, 12, 31)
CHAPTER_START = date(2026, 6, 1)
CHAPTER_END = date(2026, 6, 12)  # Mon..Fri x2 = 10 teaching days -> 10 slots
EXPECTED_SLOTS = 10


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


def _units_json(n: int, topic_id, slo_id) -> str:
    """A valid {"units": [...]} of n single-topic 'reading' units (Eng).

    Each unit covers the one topic + one sub-SLO, so validate_plan passes
    (every SLO covered, sequence is 1..n, lp_type allowed for Eng)."""
    return json.dumps(
        {
            "units": [
                {
                    "sequence": i,
                    "lp_type": "reading",
                    "topic_ids": [str(topic_id)],
                    "slo_ids": [str(slo_id)],
                    "rationale": f"unit {i}",
                }
                for i in range(1, n + 1)
            ]
        }
    )


class _StubLLM:
    def __init__(self, response: str):
        self._response = response

    async def complete(self, system: str, user: str) -> str:
        return self._response


def _patch_planner(monkeypatch, response: str) -> None:
    """Make the endpoint's generate_chapter_plan inject our stub LLM instead of
    the default AgentSdkPlannerLLM (which would hit a real model)."""

    async def _stub_generate(conn, *, cst_id, book_chapter_id, org_id, llm=None):
        return await _real_generate_chapter_plan(
            conn,
            cst_id=cst_id,
            book_chapter_id=book_chapter_id,
            org_id=org_id,
            llm=_StubLLM(response),
        )

    monkeypatch.setattr(router_today, "generate_chapter_plan", _stub_generate)


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DB-backed test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestTodayAutoPlan:
    async def _build_graph(self, conn, *, with_breakdown: bool, seed_path: bool):
        """
        Throwaway org with a known API key + one Eng CST whose class is on a
        Mon-Fri timetable. Optionally publishes a syllabus breakdown (so the
        endpoint can seed the class path) and/or seeds class_chapters directly.

        Returns (ids, api_key, cleanup).
        """
        ids: dict = {}
        curriculum = await conn.fetchrow("SELECT id FROM curriculums LIMIT 1")
        grade = await conn.fetchrow("SELECT id, code FROM grades ORDER BY code LIMIT 1")
        subject = await conn.fetchrow("SELECT id, code FROM subjects WHERE code = 'Eng'")
        assert subject is not None, "seed must provide an 'Eng' subject"

        raw_key = f"dk_test_{_uuid.uuid4().hex}"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        org_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO organizations
              (id, name, curriculum_id, api_key_hash, api_key_prefix)
            VALUES ($1, 'today-autoplan org', $2, $3, $4)
            """,
            org_id, curriculum["id"], key_hash, raw_key[:8],
        )
        ids["org_id"] = org_id

        school_id = _uuid.uuid4()
        await conn.execute(
            "INSERT INTO schools (id, org_id, name) VALUES ($1, $2, 'school')",
            school_id, org_id,
        )
        teacher_id = _uuid.uuid4()
        await conn.execute(
            "INSERT INTO teachers (id, org_id, school_id, name) VALUES ($1,$2,$3,'T')",
            teacher_id, org_id, school_id,
        )
        await conn.execute(
            "UPDATE organizations SET default_teacher_id = $1 WHERE id = $2",
            teacher_id, org_id,
        )
        ay_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO academic_years (id, org_id, school_id, name, start_date, end_date)
            VALUES ($1, $2, $3, 'AY', $4, $5)
            """,
            ay_id, org_id, school_id, AY_START, AY_END,
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
            INSERT INTO class_subject_teachers
              (id, org_id, school_class_id, subject_id, teacher_id)
            VALUES ($1, $2, $3, $4, $5)
            """,
            cst_id, org_id, class_id, subject["id"], teacher_id,
        )
        ids["cst_id"] = cst_id
        for dow in (0, 1, 2, 3, 4):  # Mon-Fri
            await conn.execute(
                "INSERT INTO timetables (cst_id, day_of_week) VALUES ($1, $2)",
                cst_id, dow,
            )

        # Book + chapter + 1 topic + 1 sub-SLO.
        book_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO books (id, curriculum_id, grade_id, subject_id, title)
            VALUES ($1, $2, $3, $4, 'book')
            """,
            book_id, curriculum["id"], grade["id"], subject["id"],
        )
        chapter_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO book_chapters (id, book_id, chapter_number, title, status)
            VALUES ($1, $2, 3, 'Phonics', 'published')
            """,
            chapter_id, book_id,
        )
        ids["book_chapter_id"] = chapter_id
        topic_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO topics
              (id, book_chapter_id, topic_number, title, topic_text, status)
            VALUES ($1, $2, 1, 'Sounds', 'sound text', 'published')
            """,
            topic_id, chapter_id,
        )
        ids["topic_id"] = topic_id
        # SLO code must be unique per (curriculum, grade, subject); these rows
        # aren't org-scoped, so make the code unique per run + delete in cleanup.
        slo_code = f"R{_uuid.uuid4().hex[:8]}"
        slo_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO slos (id, curriculum_id, grade_id, subject_id, code, statement)
            VALUES ($1, $2, $3, $4, $5, 'reading slo')
            """,
            slo_id, curriculum["id"], grade["id"], subject["id"], slo_code,
        )
        sub_id = _uuid.uuid4()
        await conn.execute(
            "INSERT INTO sub_slos (id, slo_id, code, statement, position) "
            "VALUES ($1,$2,$3,'reads words',1)",
            sub_id, slo_id, f"{slo_code}-01",
        )
        ids["sub_slo_id"] = sub_id
        await conn.execute(
            "INSERT INTO topic_sub_slos (topic_id, sub_slo_id) VALUES ($1,$2)",
            topic_id, sub_id,
        )

        sb_id = None
        if with_breakdown:
            sb_id = _uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO syllabus_breakdowns
                  (id, curriculum_id, grade_id, subject_id, book_id, status)
                VALUES ($1, $2, $3, $4, $5, 'published')
                """,
                sb_id, curriculum["id"], grade["id"], subject["id"], book_id,
            )
            await conn.execute(
                """
                INSERT INTO syllabus_chapters
                  (syllabus_breakdown_id, book_chapter_id, position, start_date, end_date)
                VALUES ($1, $2, 1, $3, $4)
                """,
                sb_id, chapter_id, CHAPTER_START, CHAPTER_END,
            )

        if seed_path:
            await conn.execute(
                """
                INSERT INTO class_chapters
                  (org_id, cst_id, book_chapter_id, position, start_date, end_date)
                VALUES ($1, $2, $3, 1, $4, $5)
                """,
                org_id, cst_id, chapter_id, CHAPTER_START, CHAPTER_END,
            )

        async def cleanup():
            # Org cascade clears tenancy + class slots/path. syllabus_breakdowns
            # and slos are curriculum-scoped (not org-scoped, no cascade from
            # org/book) so they're removed explicitly to keep runs isolated.
            # Order: org -> breakdown (refs book) -> book -> slo (refs sub_slos).
            await conn.execute("DELETE FROM organizations WHERE id=$1", org_id)
            if sb_id is not None:
                await conn.execute("DELETE FROM syllabus_breakdowns WHERE id=$1", sb_id)
            await conn.execute("DELETE FROM books WHERE id=$1", book_id)
            await conn.execute("DELETE FROM slos WHERE id=$1", slo_id)

        return ids, raw_key, cleanup

    # -- 1. seeded breakdown, no slots -> endpoint auto-plans ------------------
    async def test_today_autoplans_current_chapter_when_no_slots(
        self, client: AsyncClient, monkeypatch
    ):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, raw_key, cleanup = await self._build_graph(
                conn, with_breakdown=True, seed_path=False
            )
            try:
                _patch_planner(
                    monkeypatch,
                    _units_json(EXPECTED_SLOTS, ids["topic_id"], ids["sub_slo_id"]),
                )
                # No class slots, no class path yet.
                pre = await conn.fetchval(
                    "SELECT count(*) FROM class_lesson_slots WHERE cst_id=$1",
                    ids["cst_id"],
                )
                assert pre == 0

                r = await client.get(
                    "/api/v2/today?as_of=2026-06-01",
                    headers={"X-API-Key": raw_key},
                )
                assert r.status_code == 200, r.text
                body = r.json()
                assert len(body["items"]) == 1
                entry = body["items"][0]

                # current_chapter is set from the seeded path.
                assert entry["current_chapter"] is not None
                assert entry["current_chapter"]["book_chapter_id"] == str(
                    ids["book_chapter_id"]
                )
                assert entry["current_chapter"]["chapter_number"] == 3
                assert entry["current_chapter"]["title"] == "Phonics"
                # 2026-06-01 (Mon) is the first teaching day -> position 1.
                assert entry["day_number"] == 1
                assert entry["lesson_slot"] is not None
                assert entry["lesson_slot"]["position"] == 1
                assert entry["previous_taught"] is None
                assert entry["next_up"] is not None
                assert entry["next_up"]["position"] == 2

                # The chapter is now broken down: slots exist in the DB.
                post = await conn.fetchval(
                    "SELECT count(*) FROM class_lesson_slots WHERE cst_id=$1",
                    ids["cst_id"],
                )
                assert post == EXPECTED_SLOTS
            finally:
                await cleanup()
        finally:
            await conn.close()

    # -- 2. prev / today / next correctness on a teaching day ------------------
    async def test_prev_today_next_on_teaching_day(
        self, client: AsyncClient, monkeypatch
    ):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, raw_key, cleanup = await self._build_graph(
                conn, with_breakdown=True, seed_path=True
            )
            try:
                # Pre-break-down the chapter directly (slot positions 1..10),
                # so the endpoint's auto-plan is a no-op and we control history.
                _patch_planner(
                    monkeypatch,
                    _units_json(EXPECTED_SLOTS, ids["topic_id"], ids["sub_slo_id"]),
                )
                await _real_generate_chapter_plan(
                    conn,
                    cst_id=ids["cst_id"],
                    book_chapter_id=ids["book_chapter_id"],
                    org_id=ids["org_id"],
                    llm=_StubLLM(
                        _units_json(EXPECTED_SLOTS, ids["topic_id"], ids["sub_slo_id"])
                    ),
                )
                slots = await conn.fetch(
                    "SELECT id, position FROM class_lesson_slots WHERE cst_id=$1 "
                    "ORDER BY position",
                    ids["cst_id"],
                )
                by_pos = {s["position"]: s["id"] for s in slots}
                # Mark positions 1 and 2 as taught.
                for pos, day in ((1, date(2026, 6, 1)), (2, date(2026, 6, 2))):
                    await conn.execute(
                        """
                        INSERT INTO slot_progress
                          (cst_id, slot_kind, slot_id, action, occurred_on)
                        VALUES ($1, 'lesson', $2, 'taught', $3)
                        """,
                        ids["cst_id"], by_pos[pos], day,
                    )
                    await conn.execute(
                        "UPDATE class_lesson_slots SET status='taught' WHERE id=$1",
                        by_pos[pos],
                    )

                # Wed 2026-06-03 = position 3.
                r = await client.get(
                    "/api/v2/today?as_of=2026-06-03",
                    headers={"X-API-Key": raw_key},
                )
                assert r.status_code == 200, r.text
                entry = r.json()["items"][0]
                assert entry["day_number"] == 3
                assert entry["lesson_slot"]["position"] == 3
                # previous = last taught strictly before today = position 2.
                assert entry["previous_taught"]["position"] == 2
                assert entry["previous_taught"]["taught_on"] == "2026-06-02"
                # next = position 4, projected to Thu 2026-06-04.
                assert entry["next_up"]["position"] == 4
                assert entry["next_up"]["projected_date"] == "2026-06-04"
                assert entry["next_up"]["lp_type"] == "reading"
            finally:
                await cleanup()
        finally:
            await conn.close()

    # -- 3. non-teaching day with a planned path -------------------------------
    async def test_non_teaching_day_returns_entry_with_next_up(
        self, client: AsyncClient, monkeypatch
    ):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, raw_key, cleanup = await self._build_graph(
                conn, with_breakdown=True, seed_path=True
            )
            try:
                await _real_generate_chapter_plan(
                    conn,
                    cst_id=ids["cst_id"],
                    book_chapter_id=ids["book_chapter_id"],
                    org_id=ids["org_id"],
                    llm=_StubLLM(
                        _units_json(EXPECTED_SLOTS, ids["topic_id"], ids["sub_slo_id"])
                    ),
                )
                # Sat 2026-06-06 — not a teaching day. Positions 1..5 are on
                # Mon-Fri 06-01..06-05 (past); position 6 is Mon 06-08 (future).
                saturday = date(2026, 6, 6)
                assert saturday.weekday() == 5
                r = await client.get(
                    f"/api/v2/today?as_of={saturday.isoformat()}",
                    headers={"X-API-Key": raw_key},
                )
                assert r.status_code == 200, r.text
                items = r.json()["items"]
                # A planned path always yields an entry, even off a teaching day.
                assert len(items) == 1
                entry = items[0]
                assert entry["lesson_slot"] is None
                assert entry["assessment_slot"] is None
                assert entry["day_number"] is None
                assert entry["current_chapter"] is not None
                # next future slot after the last past slot (pos 5) = pos 6.
                assert entry["next_up"] is not None
                assert entry["next_up"]["position"] == 6
                assert entry["next_up"]["projected_date"] == "2026-06-08"
            finally:
                await cleanup()
        finally:
            await conn.close()

    # -- 4. already broken down -> auto-plan no-op, no duplicate slots ---------
    async def test_already_broken_down_is_noop(
        self, client: AsyncClient, monkeypatch
    ):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, raw_key, cleanup = await self._build_graph(
                conn, with_breakdown=True, seed_path=True
            )
            try:
                await _real_generate_chapter_plan(
                    conn,
                    cst_id=ids["cst_id"],
                    book_chapter_id=ids["book_chapter_id"],
                    org_id=ids["org_id"],
                    llm=_StubLLM(
                        _units_json(EXPECTED_SLOTS, ids["topic_id"], ids["sub_slo_id"])
                    ),
                )
                before = await conn.fetchval(
                    "SELECT count(*) FROM class_lesson_slots WHERE cst_id=$1",
                    ids["cst_id"],
                )
                assert before == EXPECTED_SLOTS

                # If the endpoint were to re-plan, generate_chapter_plan would
                # raise "already broken down" (ValueError). The endpoint must
                # catch it -> request still succeeds, slots unchanged. Use a
                # stub that would BLOW UP if actually invoked for the plan, to
                # prove the guard short-circuits before the LLM.
                def _boom(*a, **k):  # noqa: ANN001
                    raise AssertionError("planner LLM must not be called")

                async def _spy_generate(conn, *, cst_id, book_chapter_id, org_id, llm=None):
                    class _BoomLLM:
                        async def complete(self, system, user):
                            _boom()
                    return await _real_generate_chapter_plan(
                        conn,
                        cst_id=cst_id,
                        book_chapter_id=book_chapter_id,
                        org_id=org_id,
                        llm=_BoomLLM(),
                    )

                monkeypatch.setattr(router_today, "generate_chapter_plan", _spy_generate)

                r = await client.get(
                    "/api/v2/today?as_of=2026-06-02",
                    headers={"X-API-Key": raw_key},
                )
                assert r.status_code == 200, r.text
                after = await conn.fetchval(
                    "SELECT count(*) FROM class_lesson_slots WHERE cst_id=$1",
                    ids["cst_id"],
                )
                assert after == EXPECTED_SLOTS  # no duplicates
            finally:
                await cleanup()
        finally:
            await conn.close()
