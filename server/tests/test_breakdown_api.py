"""
F2.4 — Breakdown CRUD endpoint tests.

DB-gated (mirrors test_v2_smoke.py): only runs when DATABASE_URL points
at a migrated + seeded Postgres. The AsyncClient fixture triggers
lifespan which migrates + seeds.

We set DARS_ADMIN_TOKEN here for the test process; the require_admin
dep reads it via settings.admin_secret.
"""
import os
import uuid

import pytest
from httpx import AsyncClient

ADMIN_TOKEN = "test-admin-token-f24"
os.environ.setdefault("DARS_ADMIN_TOKEN", ADMIN_TOKEN)
# Re-import settings to pick up the env override before app routes resolve
# their dependency. pydantic-settings reads env at instantiation time, so we
# clear the cached singleton if needed.
from dars.config import settings  # noqa: E402

if settings.admin_secret != ADMIN_TOKEN:
    # Settings was already instantiated before this test module loaded.
    # Patch the field directly for the test run.
    object.__setattr__(settings, "admin_secret", ADMIN_TOKEN)


def admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": ADMIN_TOKEN}


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="Breakdown API tests require DATABASE_URL pointing at a seeded Postgres",
)
class TestBreakdownAPI:
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
        # Pick chapter 1 + a topic for slot tests.
        r = await client.get(f"/api/v2/books/{book_id}/chapters")
        chapter_ids_by_num = {c["chapter_number"]: c["id"] for c in r.json()["items"]}
        r = await client.get(f"/api/v2/book-chapters/{chapter_ids_by_num[1]}/topics")
        topic_id = r.json()["items"][0]["id"]
        return {
            "curriculum_id": curriculums["DARS"],
            "grade_id": grades[1],
            "subject_id_eng": subjects["Eng"],
            "subject_id_maths": subjects["Maths"],
            "book_id": book_id,
            "book_chapter_id_1": chapter_ids_by_num[1],
            "topic_id_1": topic_id,
        }

    async def test_admin_token_required(self, client: AsyncClient):
        r = await client.get("/api/v2/breakdowns")
        assert r.status_code == 403, r.text

        r = await client.get(
            "/api/v2/breakdowns",
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert r.status_code == 403, r.text

    async def test_create_list_get_breakdown(self, client: AsyncClient):
        refs = await self._seed_refs(client)
        body = {
            "scope": "global",
            "scope_ref_id": None,
            "curriculum_id": refs["curriculum_id"],
            "grade_id": refs["grade_id"],
            "subject_id": refs["subject_id_eng"],
            "book_id": refs["book_id"],
            "total_teaching_days": 180,
        }
        r = await client.post("/api/v2/breakdowns", json=body, headers=admin_headers())
        assert r.status_code == 201, r.text
        breakdown = r.json()
        assert breakdown["status"] == "draft"
        bd_id = breakdown["id"]

        r = await client.get("/api/v2/breakdowns?scope=global", headers=admin_headers())
        assert r.status_code == 200
        ids = {item["id"] for item in r.json()["items"]}
        assert bd_id in ids

        r = await client.get(f"/api/v2/breakdowns/{bd_id}", headers=admin_headers())
        assert r.status_code == 200
        assert r.json()["chapters"] == []
        assert r.json()["slots"] == []

        # Cleanup: soft-delete.
        r = await client.delete(f"/api/v2/breakdowns/{bd_id}", headers=admin_headers())
        assert r.status_code == 204

    async def test_global_scope_rejects_scope_ref_id(self, client: AsyncClient):
        refs = await self._seed_refs(client)
        body = {
            "scope": "global",
            "scope_ref_id": str(uuid.uuid4()),
            "curriculum_id": refs["curriculum_id"],
            "grade_id": refs["grade_id"],
            "subject_id": refs["subject_id_eng"],
            "book_id": refs["book_id"],
        }
        r = await client.post("/api/v2/breakdowns", json=body, headers=admin_headers())
        assert r.status_code == 422, r.text

    async def test_full_chapter_slot_publish_flow(self, client: AsyncClient):
        refs = await self._seed_refs(client)
        # 1. Create draft
        r = await client.post(
            "/api/v2/breakdowns",
            json={
                "scope": "global",
                "scope_ref_id": None,
                "curriculum_id": refs["curriculum_id"],
                "grade_id": refs["grade_id"],
                "subject_id": refs["subject_id_eng"],
                "book_id": refs["book_id"],
                "total_teaching_days": 100,
            },
            headers=admin_headers(),
        )
        assert r.status_code == 201, r.text
        bd_id = r.json()["id"]

        # 2. Add chapter
        r = await client.post(
            f"/api/v2/breakdowns/{bd_id}/chapters",
            json={
                "book_chapter_id": refs["book_chapter_id_1"],
                "position": 1,
                "teaching_days": 12,
            },
            headers=admin_headers(),
        )
        assert r.status_code == 201, r.text
        chapter_id = r.json()["id"]

        # 3. Add a valid English lesson slot
        r = await client.post(
            f"/api/v2/breakdowns/{bd_id}/slots",
            json={
                "breakdown_chapter_id": chapter_id,
                "position": 1,
                "chapter_position": 1,
                "slot_type": "lesson",
                "lp_type": "reading",
                "topic_id": refs["topic_id_1"],
            },
            headers=admin_headers(),
        )
        assert r.status_code == 201, r.text
        slot_id = r.json()["id"]

        # 4. lp_type validation: 'concrete' is Maths-only
        r = await client.post(
            f"/api/v2/breakdowns/{bd_id}/slots",
            json={
                "breakdown_chapter_id": chapter_id,
                "position": 2,
                "chapter_position": 2,
                "slot_type": "lesson",
                "lp_type": "concrete",
                "topic_id": refs["topic_id_1"],
            },
            headers=admin_headers(),
        )
        assert r.status_code == 422, r.text

        # 5. Duplicate position → 409
        r = await client.post(
            f"/api/v2/breakdowns/{bd_id}/slots",
            json={
                "breakdown_chapter_id": chapter_id,
                "position": 1,
                "chapter_position": 5,
                "slot_type": "revision",
                "lp_type": "revision",
                "topic_id": refs["topic_id_1"],
            },
            headers=admin_headers(),
        )
        assert r.status_code == 409, r.text

        # 6. Publish
        r = await client.post(
            f"/api/v2/breakdowns/{bd_id}/publish", headers=admin_headers()
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "published"

        # 7. PATCH on published → new draft version
        r = await client.patch(
            f"/api/v2/breakdowns/{bd_id}",
            json={"total_teaching_days": 110},
            headers=admin_headers(),
        )
        assert r.status_code == 200, r.text
        new_version = r.json()
        assert new_version["id"] != bd_id
        assert new_version["status"] == "draft"
        assert new_version["previous_version_id"] == bd_id

        # 8. Slot/chapter mutations on the published breakdown → 409
        r = await client.delete(
            f"/api/v2/breakdowns/{bd_id}/slots/{slot_id}", headers=admin_headers()
        )
        assert r.status_code == 409, r.text

        # 9. Delete the published parent → 409
        r = await client.delete(f"/api/v2/breakdowns/{bd_id}", headers=admin_headers())
        assert r.status_code == 409, r.text

        # 10. Soft-delete the new draft version for cleanup
        r = await client.delete(
            f"/api/v2/breakdowns/{new_version['id']}", headers=admin_headers()
        )
        assert r.status_code == 204
