"""
F2.1 — tests for the SLO breakdown service.

Two layers:
  - Unit: markdown parser is pure, tested without DB/LLM.
  - Integration: DB-backed run with a mocked LLM. Gated on DATABASE_URL so
    it only runs when a real Postgres + seed are reachable, matching
    test_v2_smoke.py's gating.
"""
import os
from textwrap import dedent

import asyncpg
import pytest

from dars.breakdown.slo_breakdown_service import (
    parse_breakdown_markdown,
    run_breakdown_for_slos,
)
from dars.config import settings


# ---------------------------------------------------------------------------
# Unit: markdown parser
# ---------------------------------------------------------------------------


def test_parse_breakdown_markdown_basic():
    md = dedent(
        """
        | SLO Code | Main SLO (verbatim) | Sub SLO Code | Sub SLOs |
        |---|---|---|---|
        | R1-01 | Identify and name all 26 letters of the English alphabet. | R1-01.1 | Identify all 26 letters of the English alphabet. |
        | R1-01 | Identify and name all 26 letters of the English alphabet. | R1-01.2 | Name all 26 letters of the English alphabet. |
        """
    ).strip()
    rows = parse_breakdown_markdown(md)
    assert len(rows) == 2
    assert rows[0]["slo_code"] == "R1-01"
    assert rows[0]["sub_slo_code"] == "R1-01.1"
    assert rows[0]["sub_slo"].startswith("Identify all 26 letters")
    assert rows[1]["sub_slo_code"] == "R1-01.2"


def test_parse_breakdown_markdown_skips_separator_and_prose():
    md = dedent(
        """
        Some preamble the model decided to write.

        | SLO Code | Main SLO | Sub SLO Code | Sub SLOs |
        |---|---|---|---|
        | G1-01 | Use singular and plural nouns. | G1-01.1 | Use singular nouns. |
        | G1-01 | Use singular and plural nouns. | G1-01.2 | Use plural nouns. |

        A trailing paragraph too.
        """
    ).strip()
    rows = parse_breakdown_markdown(md)
    assert [r["sub_slo_code"] for r in rows] == ["G1-01.1", "G1-01.2"]


def test_parse_breakdown_markdown_empty_raises():
    with pytest.raises(ValueError):
        parse_breakdown_markdown("the model returned only prose, no table")


def test_parse_breakdown_markdown_missing_column_raises():
    md = dedent(
        """
        | Foo | Bar |
        |---|---|
        | a | b |
        """
    ).strip()
    with pytest.raises(ValueError):
        parse_breakdown_markdown(md)


# ---------------------------------------------------------------------------
# Integration: DB-backed run with mocked LLM
# ---------------------------------------------------------------------------


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DB-backed test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestRunBreakdownAgainstDB:
    async def test_inserts_schema_breakdown_sub_slos_and_is_idempotent(self):
        # Pick two seeded SLOs that have no schema_breakdown sub-SLOs yet
        # (the seed only creates source='manual' sub-SLOs per F1.3).
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            rows = await conn.fetch(
                """
                SELECT s.id, s.code
                FROM slos s
                WHERE s.code IN ('R1-01', 'R1-02')
                ORDER BY s.code
                """
            )
            assert len(rows) == 2, "seed did not load expected SLO codes"
            slo_ids = [r["id"] for r in rows]
            codes = [r["code"] for r in rows]

            # Mocked LLM emits a valid markdown table for both SLOs.
            mocked_markdown = dedent(
                f"""
                | SLO Code | Main SLO | Sub SLO Code | Sub SLOs |
                |---|---|---|---|
                | {codes[0]} | Identify and name letters. | {codes[0]}.1 | Identify letters of the alphabet (test-generated). |
                | {codes[0]} | Identify and name letters. | {codes[0]}.2 | Name letters of the alphabet (test-generated). |
                | {codes[1]} | Read CVC words. | {codes[1]}.1 | Read CVC words (test-generated). |
                """
            ).strip()

            async def fake_llm(system: str, user: str) -> str:
                assert "Subject: English" in user
                assert codes[0] in user
                return mocked_markdown

            # Clean up any prior test-run schema_breakdown rows.
            await conn.execute(
                """
                DELETE FROM sub_slos
                WHERE slo_id = ANY($1::uuid[]) AND source = 'schema_breakdown'
                """,
                slo_ids,
            )

            result = await run_breakdown_for_slos(
                conn, slo_ids, subject_key="english", llm=fake_llm
            )
            assert result["inserted_sub_slo_count"] == 3
            assert result["skipped_slo_ids"] == []

            # Verify the rows landed with the right source.
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM sub_slos
                WHERE slo_id = ANY($1::uuid[]) AND source = 'schema_breakdown'
                """,
                slo_ids,
            )
            assert count == 3

            # Idempotent: a second run with force=False skips both SLOs.
            result2 = await run_breakdown_for_slos(
                conn, slo_ids, subject_key="english", llm=fake_llm
            )
            assert result2["inserted_sub_slo_count"] == 0
            assert set(result2["skipped_slo_ids"]) == set(slo_ids)
            assert result2["markdown"] == ""

            # Cleanup so reruns of the test stay deterministic.
            await conn.execute(
                """
                DELETE FROM sub_slos
                WHERE slo_id = ANY($1::uuid[]) AND source = 'schema_breakdown'
                """,
                slo_ids,
            )
        finally:
            await conn.close()
