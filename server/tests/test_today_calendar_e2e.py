"""
F2.14 + F2.15 + F2.16 — end-to-end.

Relies on the v2_seed (lifespan) having already produced a realized
class breakdown for the demo CST. Verifies:
    - /today returns one entry for the demo CST at as_of=AY start
    - /me/calendar returns the same slot at the same date
    - Both go through the same projector → consistency by construction
"""
import os
from datetime import date, timedelta

import asyncpg
import pytest
from httpx import AsyncClient

from dars.config import settings

DEMO_API_KEY = "dk_demo_dars_eng_g1_2dc7e0b8408142fa"
AY_START = date(2026, 4, 1)  # mirrors tenancy_demo.DEMO_ACADEMIC_YEAR_START


def org_headers() -> dict[str, str]:
    return {"X-API-Key": DEMO_API_KEY}


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DB-backed test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestTodayCalendarE2E:
    async def test_seed_produced_realized_slots(self) -> None:
        """F2.14 acceptance: the demo CST has realized slots after seed."""
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            row = await conn.fetchrow(
                """
                SELECT cst.id
                FROM class_subject_teachers cst
                JOIN school_classes sc ON sc.id = cst.school_class_id
                WHERE sc.section = 'A'
                LIMIT 1
                """
            )
            cst_id = row["id"]
            lesson_count = await conn.fetchval(
                "SELECT COUNT(*) FROM class_lesson_slots WHERE cst_id = $1", cst_id
            )
            assess_count = await conn.fetchval(
                "SELECT COUNT(*) FROM class_assessment_slots WHERE cst_id = $1", cst_id
            )
            assert lesson_count >= 41, f"expected ≥41 realized lesson slots, got {lesson_count}"
            assert assess_count >= 20, f"expected ≥20 realized assessment slots, got {assess_count}"

            # Positions are contiguous 1..N across both tables.
            all_positions = await conn.fetch(
                """
                SELECT position FROM class_lesson_slots WHERE cst_id = $1
                UNION ALL
                SELECT position FROM class_assessment_slots WHERE cst_id = $1
                ORDER BY 1
                """,
                cst_id,
            )
            positions = [r["position"] for r in all_positions]
            assert positions[0] == 1
            assert positions[-1] == len(positions)
        finally:
            await conn.close()

    async def test_today_returns_position_1_at_ay_start(
        self, client: AsyncClient
    ) -> None:
        """At as_of=AY start, the demo CST's day_number should be 1."""
        r = await client.get(
            f"/api/v2/today?as_of={AY_START.isoformat()}",
            headers=org_headers(),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["as_of"] == AY_START.isoformat()
        # The demo teacher has exactly one CST (G1-A Eng), so we expect one
        # entry — unless 2026-04-01 happens to be a non-teaching day.
        if not body["items"]:
            # Tolerate Mon-Fri timetable: April 1 2026 is a Wednesday — should
            # be a teaching day, so an empty list is a real failure.
            pytest.fail("expected /today to return an entry at AY start (Wed)")
        entry = body["items"][0]
        assert entry["day_number"] == 1
        assert entry["subject_code"] == "Eng"
        assert entry["grade_code"] == 1
        # Position 1 is a lesson slot per the auto-build algorithm.
        assert entry["lesson_slot"] is not None
        assert entry["assessment_slot"] is None
        # lp-context-header F-1.1: the lesson slot carries its topic title so
        # the teacher app can show "what topic" without a second fetch. The
        # demo seed's first lesson is topic-backed.
        assert "topic_title" in entry["lesson_slot"]
        assert isinstance(entry["lesson_slot"]["topic_title"], str)
        assert entry["lesson_slot"]["topic_title"]
        # No previous taught records.
        assert entry["previous_taught"] is None

    async def test_today_non_teaching_day_still_anchors_the_class(
        self, client: AsyncClient
    ) -> None:
        """
        today-prev-current-next: a CST with a planned path always yields an
        entry, even on a non-teaching day. The demo CST is broken down, so on a
        Sunday (no slot lands) we still get current_chapter + next_up with no
        lesson_slot — "no class today, here's where you are / what's next" —
        rather than the old empty list.
        """
        # 2026-04-05 is a Sunday — outside the demo Mon-Fri timetable.
        sunday = date(2026, 4, 5)
        assert sunday.weekday() == 6
        r = await client.get(
            f"/api/v2/today?as_of={sunday.isoformat()}",
            headers=org_headers(),
        )
        assert r.status_code == 200
        items = r.json()["items"]
        # The demo teacher's one CST has a planned path → exactly one entry,
        # anchored to the chapter even though Sunday is non-teaching.
        assert len(items) == 1
        entry = items[0]
        assert entry["subject_code"] == "Eng"
        # No slot lands on a non-teaching day.
        assert entry["day_number"] is None
        assert entry["lesson_slot"] is None
        assert entry["assessment_slot"] is None
        # But the chapter the class is on + what's coming up are still set.
        assert entry["current_chapter"] is not None
        assert entry["next_up"] is not None
        # next_up is a future slot — early in the demo course, after AY start.
        assert entry["next_up"]["position"] >= 1

    async def test_calendar_week_matches_today_entry(
        self, client: AsyncClient
    ) -> None:
        """
        F2.16 — calendar uses the same projector; for the AY-start week,
        the date of the projected position-1 slot must appear in the
        calendar with the same slot id as /today returns.
        """
        # 2026-03-30 is the Monday of the AY-start week.
        monday = date(2026, 3, 30)
        assert monday.weekday() == 0
        r = await client.get(
            f"/api/v2/me/calendar?week_start={monday.isoformat()}",
            headers=org_headers(),
        )
        assert r.status_code == 200, r.text
        cal = r.json()
        assert cal["week_start"] == monday.isoformat()
        assert cal["week_end"] == (monday + timedelta(days=6)).isoformat()
        assert len(cal["csts"]) == 1
        sched = cal["csts"][0]
        # AY starts on Wed 2026-04-01 — that's the day where position 1 lands.
        wed_idx = (date(2026, 4, 1) - monday).days
        wed = sched["days"][wed_idx]
        assert wed["day"] == "2026-04-01"
        assert len(wed["lesson_slots"]) == 1
        wed_slot_id = wed["lesson_slots"][0]["slot_id"]

        # /today on Wed should return the same slot id.
        r = await client.get(
            "/api/v2/today?as_of=2026-04-01", headers=org_headers()
        )
        today_body = r.json()
        assert today_body["items"][0]["lesson_slot"]["slot_id"] == wed_slot_id

    async def test_today_and_calendar_require_api_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/v2/today")
        assert r.status_code == 401
        r = await client.get("/api/v2/me/calendar?week_start=2026-04-01")
        assert r.status_code == 401
