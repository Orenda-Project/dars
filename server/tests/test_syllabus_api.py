"""
Phase 2 — Syllabus-breakdown CRUD endpoint tests (global-only).

DB-gated (mirrors test_v2_smoke.py): only runs when DATABASE_URL points
at a migrated + seeded Postgres. The AsyncClient fixture triggers
lifespan which migrates + seeds.

Auth: these endpoints use get_current_org (per-org); we send the seeded
demo org's API key.
"""
import os

import pytest
from httpx import AsyncClient

DEMO_API_KEY = "dk_demo_dars_eng_g1_2dc7e0b8408142fa"


def admin_headers() -> dict[str, str]:
    return {"X-API-Key": DEMO_API_KEY}


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="Syllabus API tests require DATABASE_URL pointing at a seeded Postgres",
)
class TestSyllabusAPI:
    async def _seed_refs(self, client: AsyncClient) -> dict:
        """Resolve seeded curriculum/grade/subject/book ids from the read API."""
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
        r = await client.get(f"/api/v2/books/{book_id}/chapters")
        chapter_ids_by_num = {c["chapter_number"]: c["id"] for c in r.json()["items"]}
        return {
            "curriculum_id": curriculums["DARS"],
            "grade_id": grades[1],
            "subject_id_eng": subjects["Eng"],
            "subject_id_maths": subjects["Maths"],
            "book_id": book_id,
            "book_chapter_id_1": chapter_ids_by_num[1],
        }

    async def test_auth_required(self, client: AsyncClient):
        r = await client.get("/api/v2/syllabus-breakdowns")
        assert r.status_code == 401, r.text

        r = await client.get(
            "/api/v2/syllabus-breakdowns",
            headers={"X-API-Key": "wrong-key"},
        )
        assert r.status_code == 401, r.text

    async def test_create_list_get_breakdown(self, client: AsyncClient):
        refs = await self._seed_refs(client)
        body = {
            "curriculum_id": refs["curriculum_id"],
            "grade_id": refs["grade_id"],
            "subject_id": refs["subject_id_eng"],
            "book_id": refs["book_id"],
        }
        r = await client.post(
            "/api/v2/syllabus-breakdowns", json=body, headers=admin_headers()
        )
        assert r.status_code == 201, r.text
        breakdown = r.json()
        assert breakdown["status"] == "draft"
        assert "scope" not in breakdown
        assert "total_teaching_days" not in breakdown
        bd_id = breakdown["id"]

        r = await client.get(
            "/api/v2/syllabus-breakdowns", headers=admin_headers()
        )
        assert r.status_code == 200
        ids = {item["id"] for item in r.json()["items"]}
        assert bd_id in ids

        r = await client.get(
            f"/api/v2/syllabus-breakdowns/{bd_id}", headers=admin_headers()
        )
        assert r.status_code == 200
        assert r.json()["chapters"] == []
        assert "slots" not in r.json()

        # Cleanup: soft-delete.
        r = await client.delete(
            f"/api/v2/syllabus-breakdowns/{bd_id}", headers=admin_headers()
        )
        assert r.status_code == 204

    async def test_chapter_and_publish_flow(self, client: AsyncClient):
        refs = await self._seed_refs(client)
        # 1. Create draft
        r = await client.post(
            "/api/v2/syllabus-breakdowns",
            json={
                "curriculum_id": refs["curriculum_id"],
                "grade_id": refs["grade_id"],
                "subject_id": refs["subject_id_eng"],
                "book_id": refs["book_id"],
            },
            headers=admin_headers(),
        )
        assert r.status_code == 201, r.text
        bd_id = r.json()["id"]

        # 2. Add chapter with a date range
        r = await client.post(
            f"/api/v2/syllabus-breakdowns/{bd_id}/chapters",
            json={
                "book_chapter_id": refs["book_chapter_id_1"],
                "position": 1,
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
            },
            headers=admin_headers(),
        )
        assert r.status_code == 201, r.text
        chapter_id = r.json()["id"]
        assert "teaching_days" not in r.json()

        # 3. Duplicate position → 409
        r = await client.post(
            f"/api/v2/syllabus-breakdowns/{bd_id}/chapters",
            json={
                "book_chapter_id": refs["book_chapter_id_1"],
                "position": 1,
            },
            headers=admin_headers(),
        )
        assert r.status_code == 409, r.text

        # 4. derived_teaching_days computed (Mon-Fri, no holidays): Sep 1-11 2026
        r = await client.get(
            f"/api/v2/syllabus-breakdowns/{bd_id}", headers=admin_headers()
        )
        assert r.status_code == 200
        ch = r.json()["chapters"][0]
        assert ch["derived_teaching_days"] is not None

        # 5. Publish
        r = await client.post(
            f"/api/v2/syllabus-breakdowns/{bd_id}/publish", headers=admin_headers()
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "published"

        # 6. Chapter mutation on a published breakdown → 409
        r = await client.delete(
            f"/api/v2/syllabus-breakdowns/{bd_id}/chapters/{chapter_id}",
            headers=admin_headers(),
        )
        assert r.status_code == 409, r.text

        # 7. PATCH on a published breakdown → 409 (no versioning anymore)
        r = await client.patch(
            f"/api/v2/syllabus-breakdowns/{bd_id}",
            json={"book_id": refs["book_id"]},
            headers=admin_headers(),
        )
        assert r.status_code == 409, r.text

        # 8. Delete the published breakdown → 409
        r = await client.delete(
            f"/api/v2/syllabus-breakdowns/{bd_id}", headers=admin_headers()
        )
        assert r.status_code == 409, r.text
