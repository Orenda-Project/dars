"""
F2.7 + F2.9 + F2.10 — end-to-end against the seed.

Walks the full flow:
    auto-build global → publish → fork-org → publish org →
    fork-class → publish class (auto-realizes into per-CST slots)
Then verifies:
    - class_lesson_slots + class_assessment_slots populated for the demo CST
    - re-realize is idempotent
    - org holiday → CST sees it via /csts/{id}/holidays
    - projector turns the realized slots into dates

DB-gated.
"""
import os

import asyncpg
import pytest
from httpx import AsyncClient

ADMIN_TOKEN = "test-admin-token-f24"
os.environ.setdefault("DARS_ADMIN_TOKEN", ADMIN_TOKEN)
from dars.config import settings  # noqa: E402

if settings.admin_secret != ADMIN_TOKEN:
    object.__setattr__(settings, "admin_secret", ADMIN_TOKEN)


def admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": ADMIN_TOKEN}


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DB-backed test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestForkRealizeHolidaysE2E:
    async def _refs(self, client: AsyncClient) -> dict:
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
        # Pull the demo org + cst directly from DB (read API for these is
        # surfaced under tenancy but resolving by code is simpler).
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
            ay_row = await conn.fetchrow(
                "SELECT id, start_date, end_date FROM academic_years LIMIT 1"
            )
        finally:
            await conn.close()
        return {
            "curriculum_id": cur["DARS"],
            "grade_id": gr[1],
            "subject_id_eng": subj["Eng"],
            "book_id": book_id,
            "org_id": str(org_row["id"]),
            "cst_id": str(cst_row["id"]),
            "ay_id": str(ay_row["id"]),
            "ay_start": ay_row["start_date"],
            "ay_end": ay_row["end_date"],
        }

    async def test_global_to_org_to_class_realize_and_holidays(
        self, client: AsyncClient
    ):
        refs = await self._refs(client)

        created_breakdowns: list[str] = []
        try:
            # 1. Auto-build a global draft.
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
            assert r.status_code == 201, r.text
            global_id = r.json()["breakdown_id"]
            created_breakdowns.append(global_id)

            # 2. Publish global.
            r = await client.post(
                f"/api/v2/breakdowns/{global_id}/publish", headers=admin_headers()
            )
            assert r.status_code == 200

            # 3. Fork to org.
            r = await client.post(
                f"/api/v2/breakdowns/{global_id}/fork-org",
                json={"org_id": refs["org_id"]},
                headers=admin_headers(),
            )
            assert r.status_code == 201, r.text
            org_fork = r.json()
            org_id = org_fork["new_breakdown_id"]
            created_breakdowns.append(org_id)
            assert org_fork["copied_chapter_count"] == 10
            assert org_fork["copied_slot_count"] >= 61

            # 4. Fork-org duplicate → 409.
            r = await client.post(
                f"/api/v2/breakdowns/{global_id}/fork-org",
                json={"org_id": refs["org_id"]},
                headers=admin_headers(),
            )
            assert r.status_code == 409, r.text

            # 5. Publish org breakdown.
            r = await client.post(
                f"/api/v2/breakdowns/{org_id}/publish", headers=admin_headers()
            )
            assert r.status_code == 200

            # 6. Fork to class for demo CST.
            r = await client.post(
                f"/api/v2/breakdowns/{org_id}/fork-class",
                json={"cst_id": refs["cst_id"]},
                headers=admin_headers(),
            )
            assert r.status_code == 201, r.text
            class_id = r.json()["new_breakdown_id"]
            created_breakdowns.append(class_id)

            # 7. Publish class → auto-realize.
            r = await client.post(
                f"/api/v2/breakdowns/{class_id}/publish", headers=admin_headers()
            )
            assert r.status_code == 200, r.text

            # 8. Verify class_lesson_slots + class_assessment_slots exist.
            conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
            try:
                lesson_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM class_lesson_slots WHERE cst_id = $1",
                    refs["cst_id"],
                )
                assess_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM class_assessment_slots WHERE cst_id = $1",
                    refs["cst_id"],
                )
                assert lesson_count >= 41  # 31 lessons + 10 revisions per F2.5 seed
                assert assess_count >= 20  # ≥10 FAs + 10 SAs

                # 9. Re-realize → still idempotent (no row count change).
                r = await client.post(
                    f"/api/v2/breakdowns/{class_id}/realize",
                    headers=admin_headers(),
                )
                assert r.status_code == 200
                lesson_count2 = await conn.fetchval(
                    "SELECT COUNT(*) FROM class_lesson_slots WHERE cst_id = $1",
                    refs["cst_id"],
                )
                assert lesson_count2 == lesson_count
            finally:
                await conn.close()

            # 10. Add an org holiday and verify CST sees it.
            r = await client.post(
                f"/api/v2/orgs/{refs['org_id']}/holidays",
                json={
                    "academic_year_id": refs["ay_id"],
                    "date": "2026-12-25",
                    "name": "Christmas",
                },
                headers=admin_headers(),
            )
            assert r.status_code == 201, r.text

            r = await client.get(
                f"/api/v2/csts/{refs['cst_id']}/holidays", headers=admin_headers()
            )
            assert r.status_code == 200
            body = r.json()
            assert "2026-12-25" in body["effective_dates"]

            # 11. CST sick-day override.
            r = await client.post(
                f"/api/v2/csts/{refs['cst_id']}/holiday-overrides",
                json={"date": "2026-11-15", "name": "Sick day", "action": "add"},
                headers=admin_headers(),
            )
            assert r.status_code == 201

            r = await client.get(
                f"/api/v2/csts/{refs['cst_id']}/holidays", headers=admin_headers()
            )
            effective = set(r.json()["effective_dates"])
            assert "2026-11-15" in effective
            assert "2026-12-25" in effective

            # 12. Project the CST's schedule via the service directly.
            from dars.breakdown.projector import project_cst_schedule
            conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
            try:
                from uuid import UUID
                projected = await project_cst_schedule(conn, UUID(refs["cst_id"]))
                # We should have a projection for every realized slot.
                total_realized = lesson_count + assess_count
                assert len(projected) == total_realized
                # 25 Dec (org) and 15 Nov (CST add) should not be in
                # the assigned dates of any non-anchor slot.
                projected_dates = {p.projected_date for p in projected if p.projected_date}
                assert "2026-12-25" not in {str(d) for d in projected_dates}
                assert "2026-11-15" not in {str(d) for d in projected_dates}
            finally:
                await conn.close()

        finally:
            # Cleanup — delete drafts (newest first), revert created
            # holidays/overrides for hygiene on reruns.
            conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
            try:
                # Force-delete all created breakdowns regardless of status,
                # since some are published by now.
                for bd_id in reversed(created_breakdowns):
                    await conn.execute(
                        "DELETE FROM breakdowns WHERE id = $1", bd_id
                    )
                await conn.execute(
                    """
                    DELETE FROM org_holidays
                    WHERE academic_year_id = $1 AND date = '2026-12-25'
                    """,
                    refs["ay_id"],
                )
                await conn.execute(
                    """
                    DELETE FROM cst_holiday_overrides
                    WHERE cst_id = $1 AND date = '2026-11-15'
                    """,
                    refs["cst_id"],
                )
                # Class-realized slots are FK'd to breakdown_slots which
                # CASCADE on breakdown delete; no manual cleanup needed.
            finally:
                await conn.close()
