"""Phase 2 DB-gated integration tests — Intelligent Chapter Planner.

Covers F-2.2 (build_plan_inputs), F-2.3 (persist_chapter_plan, multi-topic),
F-2.4 (POST /csts/{}/chapters/{}/plan end-to-end with an injected fake
PlannerLLM and via fallback; 4xx guards), and F-2.5 (multi-topic LP unit
produces a topic-set-aware class-scope LP request).

Gated on DATABASE_URL like the other DB-backed tests (test_today_calendar_e2e,
test_v2_smoke). Self-provisioning: each test builds its own curriculum/grade/
subject/book/chapter/topics/sub-SLOs + org/class/cst/syllabus, then tears it
down by cascade. No reliance on a pre-seeded operational fixture.
"""
import hashlib
import json
import os
from datetime import date
from uuid import UUID, uuid4

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from dars.breakdown import chapter_planner_service as cps
from dars.breakdown.chapter_planner_service import (
    PlanInputs,
    build_plan_inputs,
    persist_chapter_plan,
)
from dars.config import settings
from dars.main import app

pytestmark = pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DB-backed test requires DATABASE_URL pointing at a migrated Postgres",
)

SUBJECT_CODE = "Eng"


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


class _Fixture:
    """IDs of a freshly created planner fixture."""

    def __init__(self) -> None:
        self.api_key = f"dk_test_{uuid4().hex}"
        self.curriculum_id = uuid4()
        self.grade_id = uuid4()
        self.subject_id = uuid4()
        self.book_id = uuid4()
        self.book_chapter_id = uuid4()
        self.org_id = uuid4()
        self.school_id = uuid4()
        self.teacher_id = uuid4()
        self.academic_year_id = uuid4()
        self.school_class_id = uuid4()
        self.cst_id = uuid4()
        self.syllabus_id = uuid4()
        # 3 topics, each with 2 sub-SLOs.
        self.topic_ids: list[UUID] = [uuid4(), uuid4(), uuid4()]
        self.sub_slo_ids: list[UUID] = []


async def _build_fixture(conn: asyncpg.Connection) -> _Fixture:
    fx = _Fixture()
    grade_code = 9000 + (uuid4().int % 900)  # unlikely to collide with seed
    await conn.execute(
        "INSERT INTO curriculums (id, code, name) VALUES ($1,$2,$3)",
        fx.curriculum_id, f"CUR-{uuid4().hex[:8]}", "Test Curriculum",
    )
    await conn.execute(
        "INSERT INTO grades (id, code, display_name) VALUES ($1,$2,$3)",
        fx.grade_id, grade_code, f"Grade {grade_code}",
    )
    await conn.execute(
        "INSERT INTO subjects (id, code, display_name) VALUES ($1,$2,$3)",
        fx.subject_id, f"SUBJ-{uuid4().hex[:8]}", "Test Subject",
    )
    # The planner's subject_code comes from subjects.code; override the row's
    # code to the real 'Eng' so valid lp types resolve. Use a unique-safe code.
    await conn.execute(
        "UPDATE subjects SET code=$1 WHERE id=$2", SUBJECT_CODE + "-" + uuid4().hex[:6], fx.subject_id
    )
    await conn.execute(
        """INSERT INTO books (id, curriculum_id, grade_id, subject_id, title)
           VALUES ($1,$2,$3,$4,$5)""",
        fx.book_id, fx.curriculum_id, fx.grade_id, fx.subject_id, "Test Book",
    )
    await conn.execute(
        """INSERT INTO book_chapters (id, book_id, chapter_number, title, status)
           VALUES ($1,$2,1,'Ch1','published')""",
        fx.book_chapter_id, fx.book_id,
    )
    # SLOs + sub-SLOs (one SLO per topic, two sub-SLOs each), chapter SLOs.
    for i, t_id in enumerate(fx.topic_ids):
        slo_id = uuid4()
        await conn.execute(
            """INSERT INTO slos (id, curriculum_id, grade_id, subject_id, code,
                                 statement, position, recommended_lp_type)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
            slo_id, fx.curriculum_id, fx.grade_id, fx.subject_id,
            f"SLO{i}", f"slo statement {i}", i, "reading",
        )
        await conn.execute(
            "INSERT INTO book_chapter_slos (book_chapter_id, slo_id) VALUES ($1,$2)",
            fx.book_chapter_id, slo_id,
        )
        await conn.execute(
            """INSERT INTO topics (id, book_chapter_id, topic_number, title,
                                   topic_text, status)
               VALUES ($1,$2,$3,$4,$5,'published')""",
            t_id, fx.book_chapter_id, i + 1, f"Topic {i + 1}",
            f"topic text body {i + 1}",
        )
        for j in range(2):
            ss_id = uuid4()
            fx.sub_slo_ids.append(ss_id)
            await conn.execute(
                """INSERT INTO sub_slos (id, slo_id, code, statement, position,
                                         recommended_lp_type)
                   VALUES ($1,$2,$3,$4,$5,$6)""",
                ss_id, slo_id, f"SS{i}.{j}", f"sub-slo {i}.{j}", j, "reading",
            )
            await conn.execute(
                "INSERT INTO topic_sub_slos (topic_id, sub_slo_id) VALUES ($1,$2)",
                t_id, ss_id,
            )

    # Tenancy chain.
    await conn.execute(
        """INSERT INTO organizations (id, name, curriculum_id, api_key_hash, api_key_prefix)
           VALUES ($1,$2,$3,$4,$5)""",
        fx.org_id, "Test Org", fx.curriculum_id,
        hashlib.sha256(fx.api_key.encode()).hexdigest(), fx.api_key[:8],
    )
    await conn.execute(
        "INSERT INTO schools (id, org_id, name) VALUES ($1,$2,$3)",
        fx.school_id, fx.org_id, "Test School",
    )
    await conn.execute(
        "INSERT INTO teachers (id, org_id, school_id, name) VALUES ($1,$2,$3,$4)",
        fx.teacher_id, fx.org_id, fx.school_id, "Test Teacher",
    )
    await conn.execute(
        """INSERT INTO academic_years (id, org_id, school_id, name, start_date, end_date)
           VALUES ($1,$2,$3,$4,$5,$6)""",
        fx.academic_year_id, fx.org_id, fx.school_id, "AY",
        date(2026, 4, 1), date(2027, 3, 31),
    )
    await conn.execute(
        """INSERT INTO school_classes (id, org_id, school_id, academic_year_id,
                                       grade_id, section, name)
           VALUES ($1,$2,$3,$4,$5,'A','Class A')""",
        fx.school_class_id, fx.org_id, fx.school_id, fx.academic_year_id, fx.grade_id,
    )
    await conn.execute(
        """INSERT INTO class_subject_teachers (id, org_id, school_class_id,
                                               subject_id, teacher_id, book_id)
           VALUES ($1,$2,$3,$4,$5,$6)""",
        fx.cst_id, fx.org_id, fx.school_class_id, fx.subject_id, fx.teacher_id, fx.book_id,
    )
    for dow in (0, 1, 2, 3, 4):  # Mon-Fri
        await conn.execute(
            "INSERT INTO timetables (id, cst_id, day_of_week) VALUES ($1,$2,$3)",
            uuid4(), fx.cst_id, dow,
        )
    # Published syllabus with the chapter dated over two Mon-Fri weeks (10 days).
    await conn.execute(
        """INSERT INTO syllabus_breakdowns (id, curriculum_id, grade_id, subject_id,
                                            book_id, status)
           VALUES ($1,$2,$3,$4,$5,'published')""",
        fx.syllabus_id, fx.curriculum_id, fx.grade_id, fx.subject_id, fx.book_id,
    )
    await conn.execute(
        """INSERT INTO syllabus_chapters (id, syllabus_breakdown_id, book_chapter_id,
                                          position, start_date, end_date)
           VALUES ($1,$2,$3,1,$4,$5)""",
        uuid4(), fx.syllabus_id, fx.book_chapter_id,
        date(2026, 6, 1), date(2026, 6, 12),
    )
    # Resolve the subject_code we stored (the planner reads subjects.code).
    fx.subject_code = await conn.fetchval(
        "SELECT code FROM subjects WHERE id=$1", fx.subject_id
    )
    return fx


async def _teardown(conn: asyncpg.Connection, fx: _Fixture) -> None:
    # org cascade clears tenancy + class slots; curriculum cascade clears
    # slos/sub_slos/books/chapters/topics.
    await conn.execute("DELETE FROM organizations WHERE id=$1", fx.org_id)
    await conn.execute("DELETE FROM curriculums WHERE id=$1", fx.curriculum_id)


@pytest.fixture
async def fx():
    conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
    try:
        fixture = await _build_fixture(conn)
        yield fixture, conn
    finally:
        try:
            await _teardown(conn, fixture)  # type: ignore[possibly-undefined]
        finally:
            await conn.close()


# ---------------------------------------------------------------------------
# F-2.2 — build_plan_inputs
# ---------------------------------------------------------------------------


async def test_build_plan_inputs_loads_topics_sub_slos_and_slos(fx):
    fixture, conn = fx
    inputs = await build_plan_inputs(
        conn,
        book_chapter_id=fixture.book_chapter_id,
        subject_code=fixture.subject_code,
        period_count=10,
    )
    assert len(inputs.topics) == 3
    for t in inputs.topics:
        assert t.topic_text.strip()
        assert len(t.sub_slos) >= 1
    assert len(inputs.chapter_slos) == 3
    # Ordered by topic_number.
    assert [t.title for t in inputs.topics] == ["Topic 1", "Topic 2", "Topic 3"]


# ---------------------------------------------------------------------------
# F-2.3 — persist_chapter_plan (multi-topic aware)
# ---------------------------------------------------------------------------


async def test_persist_multi_topic_plan(fx):
    fixture, conn = fx
    inputs = await build_plan_inputs(
        conn, book_chapter_id=fixture.book_chapter_id,
        subject_code=fixture.subject_code, period_count=3,
    )
    t = inputs.topics
    # 2 LP units (first merges topics 0+1) + 1 FA.
    plan = cps.ChapterPlan(
        items=[
            cps.PlanItem(
                kind="lp",
                topic_ids=[t[0].topic_id, t[1].topic_id],
                sub_slo_ids=[t[0].sub_slos[0].sub_slo_id, t[1].sub_slos[0].sub_slo_id],
                lp_type="reading",
            ),
            cps.PlanItem(
                kind="lp",
                topic_ids=[t[2].topic_id],
                sub_slo_ids=[t[2].sub_slos[0].sub_slo_id],
                lp_type="reading",
            ),
            cps.PlanItem(
                kind="fa",
                topic_ids=[t[0].topic_id, t[1].topic_id, t[2].topic_id],
                sub_slo_ids=[ss.sub_slo_id for tt in t for ss in tt.sub_slos],
            ),
        ],
        source="llm",
    )
    counts = await persist_chapter_plan(
        conn, cst_id=fixture.cst_id, org_id=fixture.org_id,
        book_chapter_id=fixture.book_chapter_id, plan=plan,
    )
    assert counts.lesson_slot_count == 2
    assert counts.assessment_slot_count == 1

    lessons = await conn.fetch(
        "SELECT id, topic_id, position FROM class_lesson_slots "
        "WHERE cst_id=$1 ORDER BY position",
        fixture.cst_id,
    )
    assert len(lessons) == 2
    # Merged LP's primary topic == its first topic (D-4).
    assert lessons[0]["topic_id"] == t[0].topic_id
    # 2 join rows for the merged unit.
    join_rows = await conn.fetch(
        "SELECT topic_id, position FROM class_lesson_slot_topics "
        "WHERE class_lesson_slot_id=$1 ORDER BY position",
        lessons[0]["id"],
    )
    assert [r["topic_id"] for r in join_rows] == [t[0].topic_id, t[1].topic_id]

    # Positions contiguous and start after existing (none) -> 1,2,3.
    assess = await conn.fetch(
        "SELECT position FROM class_assessment_slots WHERE cst_id=$1", fixture.cst_id
    )
    all_pos = sorted([r["position"] for r in lessons] + [r["position"] for r in assess])
    assert all_pos == [1, 2, 3]


# ---------------------------------------------------------------------------
# F-2.4 — POST /plan end-to-end
# ---------------------------------------------------------------------------


class _FakePlannerLLM:
    def __init__(self, *, returns=None, raises=None):
        self._returns = returns
        self._raises = raises

    async def complete(self, system: str, user: str) -> str:
        if self._raises is not None:
            raise self._raises
        return self._returns


def _valid_plan_json(inputs: PlanInputs) -> str:
    """A validator-clean plan: one LP per topic + one FA (period_count must
    equal the slot_count the endpoint computes = 10 over 2026-06-01..12)."""
    items = []
    for t in inputs.topics:
        items.append({
            "kind": "lp",
            "topic_ids": [str(t.topic_id)],
            "lp_type": "reading",
            "sub_slo_ids": [str(t.sub_slos[0].sub_slo_id)],
        })
    # pad to 9 LPs then 1 FA = 10 items.
    while len(items) < 9:
        t = inputs.topics[len(items) % len(inputs.topics)]
        items.append({
            "kind": "lp",
            "topic_ids": [str(t.topic_id)],
            "lp_type": "reading",
            "sub_slo_ids": [str(t.sub_slos[0].sub_slo_id)],
        })
    items.append({
        "kind": "fa",
        "topic_ids": [str(t.topic_id) for t in inputs.topics],
        "sub_slo_ids": [str(ss.sub_slo_id) for t in inputs.topics for ss in t.sub_slos],
    })
    return json.dumps({"items": items})


async def _post_plan(api_key: str, cst_id, book_chapter_id):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        return await c.post(
            f"/api/v2/csts/{cst_id}/chapters/{book_chapter_id}/plan",
            headers={"X-API-Key": api_key},
        )


async def test_plan_endpoint_llm_path(fx, monkeypatch):
    fixture, conn = fx
    inputs = await build_plan_inputs(
        conn, book_chapter_id=fixture.book_chapter_id,
        subject_code=fixture.subject_code, period_count=10,
    )
    fake = _FakePlannerLLM(returns=_valid_plan_json(inputs))
    monkeypatch.setattr(cps, "get_planner_llm", lambda *_a, **_k: fake)

    resp = await _post_plan(fixture.api_key, fixture.cst_id, fixture.book_chapter_id)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["slot_count"] == 10
    assert body["lesson_slot_count"] + body["assessment_slot_count"] == 10
    assert body["lesson_slot_count"] == 9
    assert body["assessment_slot_count"] == 1

    total = await conn.fetchval(
        "SELECT (SELECT count(*) FROM class_lesson_slots WHERE cst_id=$1) "
        "+ (SELECT count(*) FROM class_assessment_slots WHERE cst_id=$1)",
        fixture.cst_id,
    )
    assert total == 10


async def test_plan_endpoint_falls_back_when_llm_raises(fx, monkeypatch):
    fixture, conn = fx
    fake = _FakePlannerLLM(raises=RuntimeError("llm down"))
    monkeypatch.setattr(cps, "get_planner_llm", lambda *_a, **_k: fake)

    resp = await _post_plan(fixture.api_key, fixture.cst_id, fixture.book_chapter_id)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["slot_count"] == 10
    assert body["lesson_slot_count"] + body["assessment_slot_count"] == 10
    assert body["lesson_slot_count"] >= 1


async def test_plan_endpoint_already_broken_down_422(fx, monkeypatch):
    fixture, conn = fx
    fake = _FakePlannerLLM(raises=RuntimeError("down"))  # use fallback
    monkeypatch.setattr(cps, "get_planner_llm", lambda *_a, **_k: fake)
    first = await _post_plan(fixture.api_key, fixture.cst_id, fixture.book_chapter_id)
    assert first.status_code == 201
    second = await _post_plan(fixture.api_key, fixture.cst_id, fixture.book_chapter_id)
    assert second.status_code == 422
    assert "already broken down" in second.text


async def test_plan_endpoint_no_dates_422(fx, monkeypatch):
    fixture, conn = fx
    # Strip the chapter's dates -> slot_count 0 -> 422 guard.
    await conn.execute(
        "UPDATE syllabus_chapters SET start_date=NULL, end_date=NULL "
        "WHERE syllabus_breakdown_id=$1",
        fixture.syllabus_id,
    )
    fake = _FakePlannerLLM(raises=RuntimeError("down"))
    monkeypatch.setattr(cps, "get_planner_llm", lambda *_a, **_k: fake)
    resp = await _post_plan(fixture.api_key, fixture.cst_id, fixture.book_chapter_id)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# F-2.5 — multi-topic LP unit -> topic-set-aware class-scope LP request
# ---------------------------------------------------------------------------


async def test_multi_topic_lp_unit_builds_topic_set_request(fx, monkeypatch):
    fixture, conn = fx
    from dars.generated_lps import service as gls
    from dars.generated_lps.service import get_or_generate_class_specific_lp

    # grades.code is an INT in this schema, but _parse_grade_int expects a
    # 'G<n>' string (pre-existing mismatch — see report). Stub it so this test
    # exercises the D-12 topic-set request assembly, not the grade-code path.
    monkeypatch.setattr(gls, "_parse_grade_int", lambda _c: 1)

    inputs = await build_plan_inputs(
        conn, book_chapter_id=fixture.book_chapter_id,
        subject_code=fixture.subject_code, period_count=3,
    )
    t = inputs.topics
    plan = cps.ChapterPlan(
        items=[
            cps.PlanItem(
                kind="lp",
                topic_ids=[t[0].topic_id, t[1].topic_id],
                sub_slo_ids=[t[0].sub_slos[0].sub_slo_id, t[1].sub_slos[0].sub_slo_id],
                lp_type="reading",
            ),
            cps.PlanItem(
                kind="lp", topic_ids=[t[2].topic_id],
                sub_slo_ids=[t[2].sub_slos[0].sub_slo_id], lp_type="reading",
            ),
            cps.PlanItem(
                kind="fa", topic_ids=[t[0].topic_id],
                sub_slo_ids=[t[0].sub_slos[0].sub_slo_id],
            ),
        ],
        source="llm",
    )
    await persist_chapter_plan(
        conn, cst_id=fixture.cst_id, org_id=fixture.org_id,
        book_chapter_id=fixture.book_chapter_id, plan=plan,
    )
    merged_slot_id = await conn.fetchval(
        "SELECT id FROM class_lesson_slots WHERE cst_id=$1 ORDER BY position LIMIT 1",
        fixture.cst_id,
    )

    captured = {}

    async def fake_dispatch(req):
        captured["page_content"] = req.page_content
        captured["sub_slo_statements"] = list(req.sub_slo_statements or [])
        return "job-123"

    await get_or_generate_class_specific_lp(
        conn, merged_slot_id, dispatcher=fake_dispatch,
    )
    # page_content concatenates both topics' text in order.
    assert "topic text body 1" in captured["page_content"]
    assert "topic text body 2" in captured["page_content"]
    assert captured["page_content"].index("topic text body 1") < captured["page_content"].index("topic text body 2")
    # sub_slo_statements covers both topics' sub-SLOs.
    assert any("sub-slo 0." in s for s in captured["sub_slo_statements"])
    assert any("sub-slo 1." in s for s in captured["sub_slo_statements"])
