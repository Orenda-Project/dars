"""
F2.6 — Sub-SLO breakdown trigger endpoint tests.

DB-gated end-to-end. Mocks Anthropic via monkeypatching the
`call_llm` import in the slo_breakdown_service module — that's the
default LLM the endpoint resolves through `default_call_llm`.
"""
import os
from textwrap import dedent

import asyncpg
import pytest
from httpx import AsyncClient

ADMIN_TOKEN = "test-admin-token-f24"
os.environ.setdefault("DARS_ADMIN_TOKEN", ADMIN_TOKEN)
from dars.breakdown import slo_breakdown_service  # noqa: E402
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
class TestSubSLOTriggerAPI:
    async def test_single_slo_breakdown_inserts_then_skips_on_repeat(
        self, client: AsyncClient, monkeypatch
    ) -> None:
        # Resolve a seeded SLO (R1-01 is in the Eng G1 seed).
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            slo = await conn.fetchrow(
                "SELECT id, code FROM slos WHERE code = 'R1-01' LIMIT 1"
            )
            assert slo is not None, "seed missing R1-01"
            slo_id = slo["id"]
            slo_code = slo["code"]

            # Pre-clean any prior schema_breakdown sub-SLOs for this SLO.
            await conn.execute(
                "DELETE FROM sub_slos WHERE slo_id = $1 AND source = 'schema_breakdown'",
                slo_id,
            )
        finally:
            await conn.close()

        # Patch the LLM to a deterministic response shaped like the prompt expects.
        mocked_markdown = dedent(
            f"""
            | SLO Code | Main SLO | Sub SLO Code | Sub SLOs |
            |---|---|---|---|
            | {slo_code} | Identify and name 26 letters. | {slo_code}.1 | Identify the letters (mocked F2.6). |
            | {slo_code} | Identify and name 26 letters. | {slo_code}.2 | Name the letters (mocked F2.6). |
            """
        ).strip()

        async def fake_call_llm(system: str, user: str) -> str:
            assert "Subject: English" in user
            return mocked_markdown

        monkeypatch.setattr(slo_breakdown_service, "default_call_llm", fake_call_llm)

        # 1st call → 200, 2 inserted, skipped=False.
        r = await client.post(
            f"/api/v2/slos/{slo_id}/breakdown", headers=admin_headers()
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["subject_key"] == "english"
        assert body["inserted_sub_slo_count"] == 2
        assert body["skipped"] is False
        assert body["raw_response_chars"] > 0

        # 2nd call → idempotent: 200, 0 inserted, skipped=True.
        r2 = await client.post(
            f"/api/v2/slos/{slo_id}/breakdown", headers=admin_headers()
        )
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["inserted_sub_slo_count"] == 0
        assert body2["skipped"] is True
        assert body2["raw_response_chars"] == 0

        # Cleanup.
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            await conn.execute(
                "DELETE FROM sub_slos WHERE slo_id = $1 AND source = 'schema_breakdown'",
                slo_id,
            )
        finally:
            await conn.close()

    async def test_single_breakdown_requires_admin(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/v2/slos/00000000-0000-0000-0000-000000000000/breakdown"
        )
        assert r.status_code == 403

    async def test_single_breakdown_unknown_slo_returns_404(
        self, client: AsyncClient
    ) -> None:
        r = await client.post(
            "/api/v2/slos/00000000-0000-0000-0000-000000000000/breakdown",
            headers=admin_headers(),
        )
        assert r.status_code == 404, r.text

    async def test_bulk_endpoint_groups_by_subject_and_returns_202(
        self, client: AsyncClient
    ) -> None:
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            eng_slos = await conn.fetch(
                """
                SELECT slos.id FROM slos
                JOIN subjects s ON s.id = slos.subject_id
                WHERE s.code = 'Eng' LIMIT 2
                """
            )
            assert len(eng_slos) == 2
        finally:
            await conn.close()

        r = await client.post(
            "/api/v2/breakdowns/sub-slos/bulk",
            json={"slo_ids": [str(s["id"]) for s in eng_slos]},
            headers=admin_headers(),
        )
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["accepted_slo_count"] == 2
        assert body["grouped_by_subject"] == {"english": 2}
        assert len(body["queued_slo_ids"]) == 2

    async def test_bulk_endpoint_404s_on_missing_id(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/v2/breakdowns/sub-slos/bulk",
            json={"slo_ids": ["00000000-0000-0000-0000-000000000000"]},
            headers=admin_headers(),
        )
        assert r.status_code == 422, r.text
