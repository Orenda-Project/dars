"""
F3.4 — tests for generated_lps cache lookup/insert service.

Two layers:
  - Unit: cache-key + grade-int helpers (pure).
  - DB-gated: end-to-end against the seeded demo CST. Uses an injected
    dispatcher to avoid hitting LP Assistant.
"""
import os
from uuid import UUID, uuid4

import asyncpg
import pytest

from dars.config import settings
from dars.generated_lps.service import (
    _build_cache_key_class,
    _build_cache_key_global,
    _parse_grade_int,
    get_or_generate_lp,
    get_or_generate_class_specific_lp,
)


# ---------------------------------------------------------------------------
# Unit — cache key shape + grade parsing
# ---------------------------------------------------------------------------


def test_cache_key_global_shape():
    cur = UUID("11111111-1111-1111-1111-111111111111")
    topic = UUID("22222222-2222-2222-2222-222222222222")
    assert _build_cache_key_global(cur, topic, "reading") == (
        f"{cur}:{topic}:reading"
    )


def test_cache_key_class_includes_cst():
    cur = UUID("11111111-1111-1111-1111-111111111111")
    cst = UUID("33333333-3333-3333-3333-333333333333")
    topic = UUID("22222222-2222-2222-2222-222222222222")
    key = _build_cache_key_class(cur, cst, topic, "grammar")
    assert key == f"{cur}:{cst}:{topic}:grammar"
    # And it differs from the global key
    assert key != _build_cache_key_global(cur, topic, "grammar")


@pytest.mark.parametrize("code,expected", [("G1", 1), ("G2", 2), ("G5", 5)])
def test_parse_grade_int(code, expected):
    assert _parse_grade_int(code) == expected


@pytest.mark.parametrize("bad", ["", "Grade1", "1", "X1", None])
def test_parse_grade_int_bad(bad):
    with pytest.raises(ValueError):
        _parse_grade_int(bad)


# ---------------------------------------------------------------------------
# DB-gated — end-to-end cache hit / miss against the seeded CST
# ---------------------------------------------------------------------------


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DB-backed test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestGeneratedLPCache:
    async def _seed_lesson_slot(self, conn: asyncpg.Connection):
        """Pick a real lesson slot off the demo CST + clean prior gen_lps.

        Returns (lesson_slot_id, curriculum_id, topic_id, lp_type).
        """
        row = await conn.fetchrow(
            """
            SELECT cls.id AS slot_id, cst.curriculum_id, cls.topic_id, cls.lp_type, cls.cst_id
            FROM class_lesson_slots cls
            JOIN class_subject_teachers cst ON cst.id = cls.cst_id
            JOIN organizations o ON o.id = cst.org_id
            WHERE o.api_key_prefix = 'dk_demo'
              AND cls.slot_type = 'lesson'
              AND cls.topic_id IS NOT NULL
              AND cls.lp_type IS NOT NULL
            ORDER BY cls.position
            LIMIT 1
            """
        )
        assert row is not None, "demo CST has no eligible lesson slot"
        await conn.execute(
            "DELETE FROM generated_lps "
            "WHERE curriculum_id = $1 AND topic_id = $2 AND lp_type = $3",
            row["curriculum_id"], row["topic_id"], row["lp_type"],
        )
        await conn.execute(
            "UPDATE class_lesson_slots SET generated_lp_id = NULL WHERE id = $1",
            row["slot_id"],
        )
        return row

    async def test_cache_miss_then_hit(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            slot = await self._seed_lesson_slot(conn)
            calls: list[str] = []

            async def fake_dispatcher(req) -> str:
                calls.append(req.callback_url)
                return f"fake-job-{uuid4()}"

            # First call: cache miss → insert + dispatch
            lp1 = await get_or_generate_lp(
                conn, slot["slot_id"], dispatcher=fake_dispatcher
            )
            assert lp1.status == "IN_FLIGHT"
            assert lp1.job_id and lp1.job_id.startswith("fake-job-")
            assert lp1.scope == "global"
            assert lp1.cache_key == _build_cache_key_global(
                slot["curriculum_id"], slot["topic_id"], slot["lp_type"],
            )
            assert len(calls) == 1
            assert f"/api/v1/webhooks/lp/{lp1.id}" in calls[0]

            # Slot got linked
            linked = await conn.fetchval(
                "SELECT generated_lp_id FROM class_lesson_slots WHERE id = $1",
                slot["slot_id"],
            )
            assert linked == lp1.id

            # Second call: cache hit → no new dispatch, same row
            lp2 = await get_or_generate_lp(
                conn, slot["slot_id"], dispatcher=fake_dispatcher
            )
            assert lp2.id == lp1.id
            assert len(calls) == 1, "dispatcher must not be called on cache hit"

            # Cleanup so reruns are deterministic
            await conn.execute(
                "UPDATE class_lesson_slots SET generated_lp_id = NULL WHERE id = $1",
                slot["slot_id"],
            )
            await conn.execute("DELETE FROM generated_lps WHERE id = $1", lp1.id)
        finally:
            await conn.close()

    async def test_class_specific_creates_separate_row(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            slot = await self._seed_lesson_slot(conn)
            calls: list[str] = []

            async def fake_dispatcher(req) -> str:
                calls.append(req.callback_url)
                return f"fake-job-{uuid4()}"

            # Pre-populate a global row so we can prove the class-scope
            # path doesn't reuse it.
            global_lp = await get_or_generate_lp(
                conn, slot["slot_id"], dispatcher=fake_dispatcher
            )
            assert global_lp.scope == "global"
            assert len(calls) == 1

            # Class-specific should insert a NEW row regardless of the
            # global one
            class_lp = await get_or_generate_class_specific_lp(
                conn, slot["slot_id"], dispatcher=fake_dispatcher
            )
            assert class_lp.id != global_lp.id
            assert class_lp.scope == "class"
            assert class_lp.scope_ref_id == slot["cst_id"]
            assert str(slot["cst_id"]) in class_lp.cache_key
            assert len(calls) == 2

            # And the slot points at the latest (class-specific) one
            linked = await conn.fetchval(
                "SELECT generated_lp_id FROM class_lesson_slots WHERE id = $1",
                slot["slot_id"],
            )
            assert linked == class_lp.id

            # Cleanup
            await conn.execute(
                "UPDATE class_lesson_slots SET generated_lp_id = NULL WHERE id = $1",
                slot["slot_id"],
            )
            await conn.execute(
                "DELETE FROM generated_lps WHERE id = ANY($1)",
                [global_lp.id, class_lp.id],
            )
        finally:
            await conn.close()

    async def test_requested_sub_slo_ids_populated_and_dispatched(self):
        """D-1..D-5: requested_sub_slo_ids on the row matches the topic's
        topic_sub_slos join, and the dispatcher receives the same set as
        sub_slo_statements (statements only, ordered by sub_slo.code)."""
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            slot = await self._seed_lesson_slot(conn)
            expected = await conn.fetch(
                """
                SELECT ss.id, ss.statement
                FROM topic_sub_slos tss
                JOIN sub_slos ss ON ss.id = tss.sub_slo_id
                WHERE tss.topic_id = $1
                ORDER BY ss.code
                """,
                slot["topic_id"],
            )
            expected_ids = [r["id"] for r in expected]
            expected_statements = [r["statement"] for r in expected]

            captured: list = []

            async def capturing_dispatcher(req) -> str:
                captured.append(req)
                return f"fake-job-{uuid4()}"

            lp = await get_or_generate_lp(
                conn, slot["slot_id"], dispatcher=capturing_dispatcher
            )

            persisted = await conn.fetchval(
                "SELECT requested_sub_slo_ids FROM generated_lps WHERE id = $1",
                lp.id,
            )
            assert persisted == expected_ids, (
                f"persisted requested_sub_slo_ids mismatch: "
                f"got {persisted}, expected {expected_ids}"
            )

            assert len(captured) == 1
            sent = captured[0].sub_slo_statements or []
            if expected_statements:
                assert sent == expected_statements
            else:
                # D-4: empty topic → no statements sent → no custom_prompt
                assert sent == [] or sent is None

            # Cleanup
            await conn.execute(
                "UPDATE class_lesson_slots SET generated_lp_id = NULL WHERE id = $1",
                slot["slot_id"],
            )
            await conn.execute("DELETE FROM generated_lps WHERE id = $1", lp.id)
        finally:
            await conn.close()

    async def test_error_state_re_requests(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            slot = await self._seed_lesson_slot(conn)
            calls = []

            async def failing_dispatcher(req) -> str:
                calls.append(1)
                raise RuntimeError("simulated dispatch failure")

            lp1 = await get_or_generate_lp(
                conn, slot["slot_id"], dispatcher=failing_dispatcher
            )
            assert lp1.status == "ERROR"
            assert len(calls) == 1

            async def ok_dispatcher(req) -> str:
                calls.append(2)
                return "fake-job-retry"

            lp2 = await get_or_generate_lp(
                conn, slot["slot_id"], dispatcher=ok_dispatcher
            )
            # Re-request on ERROR creates a new PENDING row
            assert lp2.id != lp1.id
            assert lp2.status == "IN_FLIGHT"
            assert lp2.job_id == "fake-job-retry"
            assert len(calls) == 2

            # Cleanup
            await conn.execute(
                "UPDATE class_lesson_slots SET generated_lp_id = NULL WHERE id = $1",
                slot["slot_id"],
            )
            await conn.execute(
                "DELETE FROM generated_lps WHERE id = ANY($1)",
                [lp1.id, lp2.id],
            )
        finally:
            await conn.close()
