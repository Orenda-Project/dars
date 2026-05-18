"""
F2.11 + F2.12 + F2.13 — end-to-end against the seed.

Walks fork → realize → set anchor → mark-taught → skip → onboard →
coverage. DB-gated.

Uses the demo org's API key for both teacher-facing and breakdown
endpoints (one auth model after the require_admin retirement).
"""
import os

import asyncpg
import pytest
from httpx import AsyncClient

from dars.config import settings

DEMO_API_KEY = "dk_demo_dars_eng_g1_2dc7e0b8408142fa"


def admin_headers() -> dict[str, str]:
    return {"X-API-Key": DEMO_API_KEY}


def org_headers() -> dict[str, str]:
    return {"X-API-Key": DEMO_API_KEY}


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DB-backed test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestClassActionsE2E:
    async def _refs_and_realize_class(self, client: AsyncClient) -> dict:
        """Build the global→org→class pipeline so we have realized slots."""
        r = await client.get("/api/v2/curriculums")
        cur = {c["code"]: c["id"] for c in r.json()["items"]}
        r = await client.get("/api/v2/grades")
        gr = {g["code"]: g["id"] for g in r.json()["items"]}
        r = await client.get("/api/v2/subjects")
        subj = {s["code"]: s["id"] for s in r.json()["items"]}
        r = await client.get(
            f"/api/v2/books?curriculum_id={cur['DARS']}&grade_id={gr[1]}&subject_id={subj['Eng']}"
        )
        book_id = r.json()["items"][0]["id"]

        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            org_row = await conn.fetchrow(
                "SELECT id FROM organizations WHERE api_key_prefix = 'dk_demo' LIMIT 1"
            )
            cst_row = await conn.fetchrow(
                """
                SELECT cst.id FROM class_subject_teachers cst
                JOIN school_classes sc ON sc.id = cst.school_class_id
                WHERE sc.section = 'A' LIMIT 1
                """
            )
        finally:
            await conn.close()
        refs = {
            "curriculum_id": cur["DARS"],
            "grade_id": gr[1],
            "subject_id_eng": subj["Eng"],
            "book_id": book_id,
            "org_id": str(org_row["id"]),
            "cst_id": str(cst_row["id"]),
        }

        # Build chain
        r = await client.post(
            "/api/v2/breakdowns/auto-build",
            json={
                "curriculum_id": refs["curriculum_id"],
                "grade_id": refs["grade_id"],
                "subject_id": refs["subject_id_eng"],
                "book_id": refs["book_id"],
                "total_teaching_days": 180,
                "fa_cadence": 5,
                "sa_per_chapter": 1,
            },
            headers=admin_headers(),
        )
        assert r.status_code == 201
        global_id = r.json()["breakdown_id"]
        refs["global_id"] = global_id

        await client.post(
            f"/api/v2/breakdowns/{global_id}/publish", headers=admin_headers()
        )
        r = await client.post(
            f"/api/v2/breakdowns/{global_id}/fork-org",
            json={"org_id": refs["org_id"]},
            headers=admin_headers(),
        )
        org_id = r.json()["new_breakdown_id"]
        refs["org_breakdown_id"] = org_id
        await client.post(
            f"/api/v2/breakdowns/{org_id}/publish", headers=admin_headers()
        )
        r = await client.post(
            f"/api/v2/breakdowns/{org_id}/fork-class",
            json={"cst_id": refs["cst_id"]},
            headers=admin_headers(),
        )
        class_id = r.json()["new_breakdown_id"]
        refs["class_breakdown_id"] = class_id
        await client.post(
            f"/api/v2/breakdowns/{class_id}/publish", headers=admin_headers()
        )
        return refs

    async def _cleanup(self, refs: dict) -> None:
        if not refs.get("global_id"):
            return
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            for key in ("class_breakdown_id", "org_breakdown_id", "global_id"):
                if refs.get(key):
                    await conn.execute(
                        "DELETE FROM breakdowns WHERE id = $1", refs[key]
                    )
            # class_state was created by mark-taught/onboard; leave it
            # (foreign keys cascade from cst_id which is seeded and not deleted).
            await conn.execute(
                "DELETE FROM cst_sub_slo_coverage WHERE cst_id = $1", refs["cst_id"]
            )
            await conn.execute(
                "DELETE FROM slot_progress WHERE cst_id = $1", refs["cst_id"]
            )
            await conn.execute(
                "DELETE FROM cst_state WHERE cst_id = $1", refs["cst_id"]
            )
        finally:
            await conn.close()

    async def test_anchor_endpoint_admin_only_and_class_forbidden(
        self, client: AsyncClient
    ):
        refs = await self._refs_and_realize_class(client)
        try:
            # Find a slot id on the org breakdown (post-fork it's a draft? no — we
            # published it). To test anchor we need a *draft*, so create a fresh
            # global draft and add a slot to it.
            r = await client.post(
                "/api/v2/breakdowns",
                json={
                    "scope": "global",
                    "scope_ref_id": None,
                    "curriculum_id": refs["curriculum_id"],
                    "grade_id": refs["grade_id"],
                    "subject_id": refs["subject_id_eng"],
                    "book_id": refs["book_id"],
                },
                headers=admin_headers(),
            )
            assert r.status_code == 201, r.text
            new_global_draft = r.json()["id"]
            refs.setdefault("_extra_bd", []).append(new_global_draft)

            # add a chapter + slot
            book_chapter_id = (await client.get(
                f"/api/v2/books/{refs['book_id']}/chapters"
            )).json()["items"][0]["id"]
            r = await client.post(
                f"/api/v2/breakdowns/{new_global_draft}/chapters",
                json={
                    "book_chapter_id": book_chapter_id,
                    "position": 1,
                    "teaching_days": 5,
                },
                headers=admin_headers(),
            )
            assert r.status_code == 201
            chapter_id = r.json()["id"]
            r = await client.post(
                f"/api/v2/breakdowns/{new_global_draft}/slots",
                json={
                    "breakdown_chapter_id": chapter_id,
                    "position": 1,
                    "chapter_position": 1,
                    "slot_type": "lesson",
                    "lp_type": "reading",
                },
                headers=admin_headers(),
            )
            assert r.status_code == 201
            slot_id = r.json()["id"]

            # Set anchor
            r = await client.patch(
                f"/api/v2/breakdowns/{new_global_draft}/slots/{slot_id}/anchor",
                json={"anchor_date": "2026-06-15"},
                headers=admin_headers(),
            )
            assert r.status_code == 200, r.text
            assert r.json()["anchor_date"] == "2026-06-15"

            # Clear anchor
            r = await client.patch(
                f"/api/v2/breakdowns/{new_global_draft}/slots/{slot_id}/anchor",
                json={"anchor_date": None},
                headers=admin_headers(),
            )
            assert r.status_code == 200
            assert r.json()["anchor_date"] is None

            # Class-scope breakdowns are forbidden for anchoring (teachers can't).
            r = await client.patch(
                f"/api/v2/breakdowns/{refs['class_breakdown_id']}/slots/00000000-0000-0000-0000-000000000000/anchor",
                json={"anchor_date": "2026-06-15"},
                headers=admin_headers(),
            )
            assert r.status_code == 403, r.text

            # Missing admin token → 403
            r = await client.patch(
                f"/api/v2/breakdowns/{new_global_draft}/slots/{slot_id}/anchor",
                json={"anchor_date": "2026-06-15"},
            )
            assert r.status_code == 403

            # Cleanup the extra draft.
            await client.delete(
                f"/api/v2/breakdowns/{new_global_draft}", headers=admin_headers()
            )
        finally:
            await self._cleanup(refs)

    async def test_mark_taught_flow_and_sequence_recompute(
        self, client: AsyncClient
    ):
        refs = await self._refs_and_realize_class(client)
        try:
            cst_id = refs["cst_id"]
            # Grab the first 3 lesson slots in order.
            conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
            try:
                slots = await conn.fetch(
                    """
                    SELECT id, position FROM class_lesson_slots
                    WHERE cst_id = $1
                    ORDER BY position LIMIT 3
                    """,
                    cst_id,
                )
                slot_1, slot_2, slot_3 = slots[0], slots[1], slots[2]
            finally:
                await conn.close()

            # Mark slot 3 taught FIRST → position advances to slot_3.position + 1.
            r = await client.post(
                f"/api/v2/class-lesson-slots/{slot_3['id']}/mark-taught",
                json={"taught_on": "2026-09-10"},
                headers=org_headers(),
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["new_sequence_position"] == slot_3["position"] + 1
            assert body["sub_slo_coverage_updates"] >= 1
            assert body["action"] == "taught"

            # Mark slot 2 LATE → position stays at slot_3.position + 1 (max-based).
            r = await client.post(
                f"/api/v2/class-lesson-slots/{slot_2['id']}/mark-taught",
                json={"taught_on": "2026-09-12"},
                headers=org_headers(),
            )
            assert r.status_code == 200
            assert r.json()["new_sequence_position"] == slot_3["position"] + 1

            # Skip slot 1.
            r = await client.post(
                f"/api/v2/class-lesson-slots/{slot_1['id']}/skip",
                json={"reason": "snow day"},
                headers=org_headers(),
            )
            assert r.status_code == 200
            assert r.json()["action"] == "skipped"

            # Verify DB state.
            conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
            try:
                statuses = {
                    r["id"]: r["status"]
                    for r in await conn.fetch(
                        """
                        SELECT id, status FROM class_lesson_slots
                        WHERE id = ANY($1::uuid[])
                        """,
                        [slot_1["id"], slot_2["id"], slot_3["id"]],
                    )
                }
                assert statuses[slot_1["id"]] == "skipped"
                assert statuses[slot_2["id"]] == "taught"
                assert statuses[slot_3["id"]] == "taught"

                # slot_progress has 3 events for this CST (one per slot).
                evt_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM slot_progress WHERE cst_id = $1",
                    cst_id,
                )
                assert evt_count == 3
            finally:
                await conn.close()
        finally:
            await self._cleanup(refs)

    async def test_complete_assessment_advances_sequence(self, client: AsyncClient):
        refs = await self._refs_and_realize_class(client)
        try:
            cst_id = refs["cst_id"]
            conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
            try:
                assess = await conn.fetchrow(
                    """
                    SELECT id, position FROM class_assessment_slots
                    WHERE cst_id = $1 ORDER BY position LIMIT 1
                    """,
                    cst_id,
                )
            finally:
                await conn.close()
            r = await client.post(
                f"/api/v2/class-assessment-slots/{assess['id']}/complete",
                json={"taught_on": "2026-09-15"},
                headers=org_headers(),
            )
            assert r.status_code == 200, r.text
            assert r.json()["new_sequence_position"] == assess["position"] + 1
            assert r.json()["slot_kind"] == "assessment"
        finally:
            await self._cleanup(refs)

    async def test_onboarding_resolves_to_slot_position(self, client: AsyncClient):
        refs = await self._refs_and_realize_class(client)
        try:
            r = await client.post(
                f"/api/v2/csts/{refs['cst_id']}/onboard",
                json={"chapter_position": 3, "chapter_day": 2},
                headers=org_headers(),
            )
            assert r.status_code == 200, r.text
            body = r.json()
            # The exact position depends on chapter sizes; the bare minimum
            # is that it's > 1 (we joined past chapter 1).
            assert body["resolved_position"] > 1
            assert body["joined_at_position"] == body["resolved_position"]

            # Coverage report should mark sub-SLOs from pre-onboarding
            # positions as 'unknown'.
            r = await client.get(
                f"/api/v2/csts/{refs['cst_id']}/sub-slo-coverage",
                headers=org_headers(),
            )
            assert r.status_code == 200
            cov = r.json()
            assert cov["joined_at_position"] == body["resolved_position"]
            statuses = {item["status"] for item in cov["items"]}
            # At least some sub-SLOs should be 'unknown' since we onboarded
            # past chapter 1.
            assert "unknown" in statuses
        finally:
            await self._cleanup(refs)

    async def test_mark_taught_requires_org_auth(self, client: AsyncClient):
        # No header
        r = await client.post(
            "/api/v2/class-lesson-slots/00000000-0000-0000-0000-000000000000/mark-taught",
            json={},
        )
        assert r.status_code == 401, r.text

        # Wrong key
        r = await client.post(
            "/api/v2/class-lesson-slots/00000000-0000-0000-0000-000000000000/mark-taught",
            json={},
            headers={"X-API-Key": "wrong-key"},
        )
        assert r.status_code == 401, r.text
