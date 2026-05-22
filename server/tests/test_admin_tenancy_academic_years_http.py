"""
HTTP regression for POST/PATCH /api/v1/academic-years.

Locks the fix for the asyncpg DataError that fired when the request body
arrived as a JSON ISO date string. asyncpg requires `datetime.date` for
date params — Pydantic v2 now parses the strings to date for us, and
the SQL no longer carries a redundant `::date` cast.

DB-gated (mirrors the other tenancy/breakdown HTTP suites): the demo
tenancy seed runs on lifespan startup and provides the admin we log in
as. Skips when DATABASE_URL is unset.

All assertions live inside a single test method on purpose. The v2 API
uses a process-global asyncpg pool (see deps.get_db_pool); spreading
the assertions across multiple test methods spawns a fresh AsyncClient
per method, each on a new event loop, while the pool's connections are
still bound to the first loop — that combination raises
``InterfaceError: another operation is in progress`` on the second
test. The rest of the suite avoids this by keeping each DB-touching
class to one method.
"""
import os

import pytest
from httpx import AsyncClient


DEMO_ADMIN_EMAIL = "admin@dars-demo.example"
DEMO_ADMIN_PASSWORD = "darsdemo2026"
DEMO_API_KEY = "dk_demo_dars_eng_g1_2dc7e0b8408142fa"


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="HTTP test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestAcademicYearsHTTP:
    async def test_create_and_update_with_iso_date_strings(
        self, client: AsyncClient
    ) -> None:
        """Regression for the asyncpg DataError on str dates.

        Sends raw JSON ISO strings (NOT pre-parsed date objects) for
        start_date / end_date and asserts:
          - POST returns 201 with strings round-tripped via to_char
          - PATCH on the same row returns 200 with the updated strings
          - POST with a malformed date returns 422 (Pydantic-validated,
            never reaches asyncpg)
        """
        # 1. Login → admin session.
        login = await client.post(
            "/api/v1/admin/login",
            json={"email": DEMO_ADMIN_EMAIL, "password": DEMO_ADMIN_PASSWORD},
        )
        assert login.status_code == 200, login.text
        session = login.json()["session_token"]
        admin_headers = {"X-Admin-Session": session}

        # 2. Resolve the demo school via the read API (seeded by lifespan).
        schools = await client.get(
            "/api/v2/schools", headers={"X-API-Key": DEMO_API_KEY}
        )
        assert schools.status_code == 200, schools.text
        school_id = schools.json()["items"][0]["id"]

        # 3. POST /academic-years with raw ISO strings — pre-fix this 500'd.
        created = await client.post(
            "/api/v1/academic-years",
            headers=admin_headers,
            json={
                "school_id": school_id,
                "name": "AY-regression-create",
                "start_date": "2026-08-01",
                "end_date": "2027-05-31",
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["school_id"] == school_id
        assert body["name"] == "AY-regression-create"
        # to_char in the SQL keeps the response shape contractual.
        assert body["start_date"] == "2026-08-01"
        assert body["end_date"] == "2027-05-31"
        ay_id = body["id"]

        # 4. PATCH /academic-years/{id} — same bug applied here.
        updated = await client.patch(
            f"/api/v1/academic-years/{ay_id}",
            headers=admin_headers,
            json={
                "start_date": "2026-09-01",
                "end_date": "2027-06-30",
            },
        )
        assert updated.status_code == 200, updated.text
        ubody = updated.json()
        assert ubody["id"] == ay_id
        assert ubody["start_date"] == "2026-09-01"
        assert ubody["end_date"] == "2027-06-30"

        # 5. Malformed date → 422 at Pydantic, never reaches asyncpg.
        bad = await client.post(
            "/api/v1/academic-years",
            headers=admin_headers,
            json={
                "school_id": school_id,
                "name": "AY-bad-date",
                "start_date": "not-a-date",
                "end_date": "2027-05-31",
            },
        )
        assert bad.status_code == 422, bad.text
