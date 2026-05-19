"""
F2.5 — Auto-build tests.

Unit: pure helper math, no DB.
Integration: DB-gated, runs auto-build against the seeded
Dars Curriculum English G1 book and asserts the shape of the draft.
"""
import os
from uuid import uuid4

import pytest
from httpx import AsyncClient

from dars.breakdown.auto_build_service import (
    allocate_chapter_days,
    compute_chapter_day_budget,
    plan_chapter_slots,
)

DEMO_API_KEY = "dk_demo_dars_eng_g1_2dc7e0b8408142fa"


def admin_headers() -> dict[str, str]:
    return {"X-API-Key": DEMO_API_KEY}


# ---------------------------------------------------------------------------
# Unit: chapter day budget
# ---------------------------------------------------------------------------


def test_chapter_day_budget_proportional():
    # 4 chapters, equal topic counts, 100 days → each gets ~25.
    budget = compute_chapter_day_budget([3, 3, 3, 3], 100)
    assert sum(budget) == 100
    assert all(b >= 1 for b in budget)
    # Difference between min/max ≤ 1 for equal weights.
    assert max(budget) - min(budget) <= 1


def test_chapter_day_budget_weighted():
    # 10 + 5 + 5 topics over 100 days → ~50/25/25.
    budget = compute_chapter_day_budget([10, 5, 5], 100)
    assert sum(budget) == 100
    assert budget[0] >= budget[1]
    assert budget[0] >= budget[2]


def test_chapter_day_budget_no_topics_gives_one_each():
    budget = compute_chapter_day_budget([0, 0, 0], 50)
    assert budget == [1, 1, 1]


def test_chapter_day_budget_each_chapter_has_at_least_one():
    # 100 chapters, 50 days → can't give each ≥1 fairly, but we must give
    # at least 1; sum may exceed total_teaching_days in that case.
    budget = compute_chapter_day_budget([1] * 100, 50)
    assert all(b >= 1 for b in budget)


# ---------------------------------------------------------------------------
# Unit: per-chapter allocation (1 slot = 1 day, D-74)
# ---------------------------------------------------------------------------


def test_allocation_invariant_typical():
    # 27 days, 5 topics, cadence 5, SA=1.
    a = allocate_chapter_days(chapter_days=27, topic_count=5, fa_cadence=5, sa_per_chapter=1)
    assert a.lesson_days + a.fa_count + a.sa_count + a.revision_count == 27
    assert sum(a.days_per_topic) == a.lesson_days
    assert len(a.days_per_topic) == 5
    # Uniform within ±1.
    assert max(a.days_per_topic) - min(a.days_per_topic) <= 1


def test_allocation_tiny_chapter_drops_revision_before_sa():
    # 1 day, 2 topics. Only enough for one SA (priority).
    a = allocate_chapter_days(chapter_days=1, topic_count=2, fa_cadence=5, sa_per_chapter=1)
    assert a.lesson_days + a.fa_count + a.sa_count + a.revision_count == 1
    assert a.sa_count == 1
    assert a.revision_count == 0
    assert a.lesson_days == 0


def test_allocation_zero_topics():
    # Edge case: chapter with no topics. All days become extra SAs to
    # preserve the count invariant.
    a = allocate_chapter_days(chapter_days=5, topic_count=0, fa_cadence=5, sa_per_chapter=1)
    assert a.lesson_days + a.fa_count + a.sa_count + a.revision_count == 5
    assert a.lesson_days == 0
    assert a.days_per_topic == []


def test_allocation_plan_count_equals_chapter_days():
    # The plan output must be exactly chapter_days items.
    for days in (1, 3, 7, 27, 100, 365):
        for topics in (1, 3, 10):
            a = allocate_chapter_days(
                chapter_days=days, topic_count=topics, fa_cadence=5, sa_per_chapter=1,
            )
            assert a.lesson_days + a.fa_count + a.sa_count + a.revision_count == days, (
                f"invariant failed for days={days} topics={topics}: "
                f"{a.lesson_days}+{a.fa_count}+{a.sa_count}+{a.revision_count}"
            )
            tids = [uuid4() for _ in range(topics)]
            slots = plan_chapter_slots(tids, ["reading"] * topics, a, fa_cadence=5)
            assert len(slots) == days, (
                f"plan_chapter_slots produced {len(slots)} slots for chapter_days={days}"
            )


def test_planned_slots_consecutive_same_topic_share_lp_type():
    # 9 days, 3 topics, cadence 5, sa=1 → 6 lesson days (2 per topic).
    a = allocate_chapter_days(chapter_days=9, topic_count=3, fa_cadence=5, sa_per_chapter=1)
    tids = [uuid4() for _ in range(3)]
    lp_types = ["reading", "grammar", "comprehension_qa"]
    slots = plan_chapter_slots(tids, lp_types, a, fa_cadence=5)
    # All lesson slots for topic 0 should have lp_type="reading", etc.
    by_topic: dict = {}
    for s in slots:
        if s.slot_type == "lesson":
            by_topic.setdefault(s.topic_id, []).append(s.lp_type)
    for tid, types in by_topic.items():
        assert len(set(types)) == 1, f"topic {tid} got mixed lp_types: {types}"


# ---------------------------------------------------------------------------
# Integration: hit POST /api/v2/breakdowns/auto-build against the seed.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="auto-build test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestAutoBuildAPI:
    async def _seed_refs(self, client: AsyncClient) -> dict:
        r = await client.get("/api/v2/curriculums")
        curriculums = {c["code"]: c["id"] for c in r.json()["items"]}
        r = await client.get("/api/v2/grades")
        grades = {g["code"]: g["id"] for g in r.json()["items"]}
        r = await client.get("/api/v2/subjects")
        subjects = {s["code"]: s["id"] for s in r.json()["items"]}
        r = await client.get(
            f"/api/v2/books?curriculum_id={curriculums['DARS']}&grade_id={grades[1]}&subject_id={subjects['Eng']}"
        )
        book_id = r.json()["items"][0]["id"]
        return {
            "curriculum_id": curriculums["DARS"],
            "grade_id": grades[1],
            "subject_id_eng": subjects["Eng"],
            "book_id": book_id,
        }

    async def test_auto_build_against_seed_dars_eng_g1(self, client: AsyncClient):
        refs = await self._seed_refs(client)
        body = {
            "curriculum_id": refs["curriculum_id"],
            "grade_id": refs["grade_id"],
            "subject_id": refs["subject_id_eng"],
            "book_id": refs["book_id"],
            "total_teaching_days": 180,
            "fa_cadence": 5,
            "sa_per_chapter": 1,
        }
        r = await client.post(
            "/api/v2/breakdowns/auto-build",
            json=body,
            headers=admin_headers(),
        )
        assert r.status_code == 201, r.text
        result = r.json()
        bd_id = result["breakdown_id"]
        try:
            # D-74 invariant: total slot count == total_teaching_days.
            assert result["total_slot_count"] == 180
            # Seed has 10 chapters; each contributes 1 revision + sa_per_chapter SAs.
            assert result["chapter_count"] == 10
            assert result["sa_slot_count"] == 10
            assert result["revision_slot_count"] == 10
            # The rest splits between lesson and FA slots.
            assert (
                result["lesson_slot_count"] + result["fa_slot_count"]
                == 180 - 10 - 10
            )

            # Fetch the breakdown and validate slot integrity.
            r = await client.get(
                f"/api/v2/breakdowns/{bd_id}", headers=admin_headers()
            )
            assert r.status_code == 200
            bd = r.json()
            assert bd["status"] == "draft"
            slots = bd["slots"]
            assert len(slots) == 180, f"expected 180 slots, got {len(slots)}"
            positions = [s["position"] for s in slots]
            assert positions == sorted(positions)
            assert positions[0] == 1
            assert positions[-1] == len(positions)

            # Every lesson slot has a non-null lp_type valid for Eng.
            VALID_ENG = {
                "reading", "comprehension_word_meanings", "comprehension_qa",
                "grammar", "creative_writing", "revision",
            }
            for s in slots:
                if s["slot_type"] == "lesson":
                    assert s["lp_type"] in VALID_ENG, s
                if s["slot_type"] == "revision":
                    assert s["lp_type"] == "revision"
                if s["slot_type"] in ("formative_assessment", "summative_assessment"):
                    assert s["lp_type"] is None
        finally:
            # Cleanup: soft-delete the draft.
            r = await client.delete(
                f"/api/v2/breakdowns/{bd_id}", headers=admin_headers()
            )
            assert r.status_code == 204

    async def test_auto_build_requires_auth(self, client: AsyncClient):
        body = {
            "curriculum_id": "00000000-0000-0000-0000-000000000000",
            "grade_id": "00000000-0000-0000-0000-000000000000",
            "subject_id": "00000000-0000-0000-0000-000000000000",
            "book_id": "00000000-0000-0000-0000-000000000000",
        }
        r = await client.post("/api/v2/breakdowns/auto-build", json=body)
        assert r.status_code == 401

    async def test_auto_build_rejects_book_mismatch(self, client: AsyncClient):
        refs = await self._seed_refs(client)
        # Wrong subject for this book.
        wrong_subject = await client.get("/api/v2/subjects")
        wrong_subject_id = next(
            s["id"] for s in wrong_subject.json()["items"] if s["code"] == "Maths"
        )
        body = {
            "curriculum_id": refs["curriculum_id"],
            "grade_id": refs["grade_id"],
            "subject_id": wrong_subject_id,
            "book_id": refs["book_id"],
        }
        r = await client.post(
            "/api/v2/breakdowns/auto-build", json=body, headers=admin_headers()
        )
        assert r.status_code == 422, r.text
