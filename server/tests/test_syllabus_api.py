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


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="Syllabus API tests require DATABASE_URL pointing at a seeded Postgres",
)
class TestCstSyllabusReadOnly:
    """teacher-readonly-syllabus Phase 1 — the CST syllabus GET is now a
    read-only, auto-seeded mirror of the org breakdown (D-2, D-5)."""

    async def _first_cst_id(self, client: AsyncClient) -> str | None:
        r = await client.get("/api/v2/csts", headers=admin_headers())
        assert r.status_code == 200, r.text
        items = r.json().get("items", [])
        return items[0]["id"] if items else None

    async def test_syllabus_get_is_readonly_and_drops_recommended_next(
        self, client: AsyncClient
    ):
        cst_id = await self._first_cst_id(client)
        if cst_id is None:
            pytest.skip("no CST seeded for the demo org")

        r = await client.get(
            f"/api/v2/csts/{cst_id}/syllabus", headers=admin_headers()
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # D-5: recommended_next was dropped from the response entirely.
        assert "recommended_next" not in body
        # The read-only path shape is intact.
        assert "chapters" in body
        assert "syllabus_breakdown_id" in body
        assert "periods_per_week" in body

        # D-2: auto-seed-on-GET is idempotent — a second read is stable.
        r2 = await client.get(
            f"/api/v2/csts/{cst_id}/syllabus", headers=admin_headers()
        )
        assert r2.status_code == 200, r2.text
        assert len(r2.json()["chapters"]) == len(body["chapters"])

    async def test_mutation_endpoints_are_gone(self, client: AsyncClient):
        cst_id = await self._first_cst_id(client)
        if cst_id is None:
            pytest.skip("no CST seeded for the demo org")
        # The four Phase-1-removed routes no longer exist on the router → 405
        # (path matched by other methods) or 404. Either way, never a success.
        r = await client.put(
            f"/api/v2/csts/{cst_id}/chapters/order",
            json={"book_chapter_ids": []},
            headers=admin_headers(),
        )
        assert r.status_code in (404, 405), r.text
