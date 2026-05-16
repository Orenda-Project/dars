"""
F2.5 — Auto-build tests.

Unit: pure helper math, no DB.
Integration: DB-gated, runs auto-build against the seeded
Dars Curriculum English G1 book and asserts the shape of the draft.
"""
import os

import pytest
from httpx import AsyncClient

from dars.breakdown.auto_build_service import compute_chapter_day_budget

ADMIN_TOKEN = "test-admin-token-f24"
os.environ.setdefault("DARS_ADMIN_TOKEN", ADMIN_TOKEN)
from dars.config import settings  # noqa: E402

if settings.admin_secret != ADMIN_TOKEN:
    object.__setattr__(settings, "admin_secret", ADMIN_TOKEN)


def admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": ADMIN_TOKEN}


# ---------------------------------------------------------------------------
# Unit
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
            # Seed has 10 chapters / 31 topics.
            assert result["chapter_count"] == 10
            assert result["lesson_slot_count"] == 31
            # FA: one wrap-up FA per chapter (since 31 topics across 10 chapters
            # rarely hits exactly fa_cadence=5; the trailing FA always fires).
            assert result["fa_slot_count"] >= 10
            assert result["sa_slot_count"] == 10  # sa_per_chapter=1 × 10 chapters
            assert result["revision_slot_count"] == 10
            # Total: lessons (31) + FAs (≥10) + SAs (10) + revisions (10).
            assert result["total_slot_count"] >= 61

            # Fetch the breakdown and validate slot integrity.
            r = await client.get(
                f"/api/v2/breakdowns/{bd_id}", headers=admin_headers()
            )
            assert r.status_code == 200
            bd = r.json()
            assert bd["status"] == "draft"
            slots = bd["slots"]
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

    async def test_auto_build_requires_admin(self, client: AsyncClient):
        body = {
            "curriculum_id": "00000000-0000-0000-0000-000000000000",
            "grade_id": "00000000-0000-0000-0000-000000000000",
            "subject_id": "00000000-0000-0000-0000-000000000000",
            "book_id": "00000000-0000-0000-0000-000000000000",
        }
        r = await client.post("/api/v2/breakdowns/auto-build", json=body)
        assert r.status_code == 403

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
