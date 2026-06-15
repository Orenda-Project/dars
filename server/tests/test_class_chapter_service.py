"""
Class-chapter path tests.

Pure-logic: status derivation (D-4) and the reorder lock (D-6, `validate_reorder`).
The class path is auto-seeded from the org breakdown by
`seed_class_chapters_from_breakdown` (D-10) and then teacher-editable on top —
pick / set-dates / reorder / remove (Phase 3 Revival, D-9). The reorder-lock
tests below were restored verbatim from PR #109.

DB-gated: `seed_class_chapters_from_breakdown` (copy rule, idempotency,
no-op cases) and `remove_chapter`'s D-11 guard (a chapter with any generated
slot can't be removed) — follow the DATABASE_URL gating pattern from
`test_chapter_plan_service.py`.
"""
import os
import uuid as _uuid
from datetime import date
from uuid import uuid4

import asyncpg
import pytest

from dars.breakdown.class_chapter_service import (
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    STATUS_YET_TO_START,
    derive_chapter_status,
    remove_chapter,
    seed_class_chapters_from_breakdown,
    validate_reorder,
)
from dars.config import settings


# ---------------------------------------------------------------------------
# Status derivation (D-4)
# ---------------------------------------------------------------------------


def test_status_no_slots_is_yet_to_start():
    # Picked but not broken down → no slots → yet_to_start.
    assert derive_chapter_status([]) == STATUS_YET_TO_START


def test_status_all_planned_is_yet_to_start():
    # Broken down but nothing taught yet → all non-terminal → yet_to_start.
    assert derive_chapter_status(["planned", "planned", "scheduled"]) == STATUS_YET_TO_START


def test_status_some_terminal_is_in_progress():
    assert derive_chapter_status(["taught", "planned", "scheduled"]) == STATUS_IN_PROGRESS


def test_status_one_terminal_among_many_is_in_progress():
    assert derive_chapter_status(["planned", "planned", "completed"]) == STATUS_IN_PROGRESS


def test_status_all_terminal_is_done():
    # Mix of terminal kinds across lesson + assessment slots.
    assert derive_chapter_status(["taught", "completed", "skipped"]) == STATUS_DONE


def test_status_single_terminal_slot_is_done():
    # >= 1 slot, all terminal → done.
    assert derive_chapter_status(["taught"]) == STATUS_DONE


def test_status_skipped_counts_as_terminal():
    # A fully-skipped chapter is 'done' for status purposes (a decision was made).
    assert derive_chapter_status(["skipped", "skipped"]) == STATUS_DONE


def test_status_skipped_partial_is_in_progress():
    assert derive_chapter_status(["skipped", "planned"]) == STATUS_IN_PROGRESS


# ---------------------------------------------------------------------------
# Reorder lock (D-6) — restored verbatim from PR #109 (F3.1).
# ---------------------------------------------------------------------------


def _ids(n: int):
    return [uuid4() for _ in range(n)]


def test_reorder_all_yet_to_start_freely_reorders():
    a, b, c = _ids(3)
    statuses = {a: STATUS_YET_TO_START, b: STATUS_YET_TO_START, c: STATUS_YET_TO_START}
    # Any permutation of the full set is allowed.
    validate_reorder([a, b, c], statuses, [c, a, b])
    validate_reorder([a, b, c], statuses, [b, c, a])


def test_reorder_rejects_missing_chapter():
    a, b, c = _ids(3)
    statuses = {a: STATUS_YET_TO_START, b: STATUS_YET_TO_START, c: STATUS_YET_TO_START}
    with pytest.raises(ValueError, match="exactly the chapters"):
        validate_reorder([a, b, c], statuses, [a, b])


def test_reorder_rejects_extra_chapter():
    a, b, c = _ids(3)
    d = uuid4()
    statuses = {a: STATUS_YET_TO_START, b: STATUS_YET_TO_START, c: STATUS_YET_TO_START}
    with pytest.raises(ValueError, match="exactly the chapters"):
        validate_reorder([a, b, c], statuses, [a, b, c, d])


def test_reorder_rejects_duplicates():
    a, b, c = _ids(3)
    statuses = {a: STATUS_YET_TO_START, b: STATUS_YET_TO_START, c: STATUS_YET_TO_START}
    with pytest.raises(ValueError, match="duplicate"):
        validate_reorder([a, b, c], statuses, [a, b, b])


def test_reorder_started_chapter_must_stay_at_front():
    # a is in_progress (started) and leads; moving it back is rejected (D-6).
    a, b, c = _ids(3)
    statuses = {a: STATUS_IN_PROGRESS, b: STATUS_YET_TO_START, c: STATUS_YET_TO_START}
    with pytest.raises(ValueError, match="locked"):
        validate_reorder([a, b, c], statuses, [b, a, c])


def test_reorder_upcoming_after_started_reorders_freely():
    # a started and stays first; b and c (upcoming) may swap behind it.
    a, b, c = _ids(3)
    statuses = {a: STATUS_IN_PROGRESS, b: STATUS_YET_TO_START, c: STATUS_YET_TO_START}
    validate_reorder([a, b, c], statuses, [a, c, b])


def test_reorder_keeps_relative_order_of_multiple_started():
    # a (done) then b (in_progress) lead and must keep that relative order;
    # c is upcoming. Submitting them in the same leading order is fine.
    a, b, c = _ids(3)
    statuses = {a: STATUS_DONE, b: STATUS_IN_PROGRESS, c: STATUS_YET_TO_START}
    validate_reorder([a, b, c], statuses, [a, b, c])


def test_reorder_rejects_reordering_two_started_chapters():
    # Swapping the two locked chapters' relative order is rejected.
    a, b, c = _ids(3)
    statuses = {a: STATUS_DONE, b: STATUS_IN_PROGRESS, c: STATUS_YET_TO_START}
    with pytest.raises(ValueError, match="locked"):
        validate_reorder([a, b, c], statuses, [b, a, c])


def test_reorder_done_chapter_locked_at_front():
    a, b = _ids(2)
    statuses = {a: STATUS_DONE, b: STATUS_YET_TO_START}
    with pytest.raises(ValueError, match="locked"):
        validate_reorder([a, b], statuses, [b, a])


def test_reorder_single_chapter_noop():
    (a,) = _ids(1)
    validate_reorder([a], {a: STATUS_YET_TO_START}, [a])


def test_reorder_empty_path_noop():
    validate_reorder([], {}, [])


# ---------------------------------------------------------------------------
# Auto-seed (F1.1, D-2) — DB-gated like the other DB-backed tests.
# ---------------------------------------------------------------------------


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DB-backed test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestSeedClassChaptersAgainstDB:
    async def _build_graph(self, conn, *, with_breakdown=True, num_chapters=3):
        """
        Throwaway org → school → AY → class → CST → book → N chapters, and
        (optionally) a published syllabus_breakdown with one dated
        syllabus_chapters row per chapter. Returns ids + a cleanup fn. No
        class_chapters are pre-created (clean install).
        """
        ids = {}
        curriculum = await conn.fetchrow("SELECT id FROM curriculums LIMIT 1")
        grade = await conn.fetchrow("SELECT id FROM grades ORDER BY code LIMIT 1")
        subject = await conn.fetchrow("SELECT id FROM subjects WHERE code = 'Eng'")
        assert subject is not None, "seed must provide an 'Eng' subject"

        org_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO organizations
              (id, name, curriculum_id, api_key_hash, api_key_prefix)
            VALUES ($1, $2, $3, 'x', 'xxxxxxxx')
            """,
            org_id, "seed test org", curriculum["id"],
        )
        ids["org_id"] = org_id

        school_id = _uuid.uuid4()
        await conn.execute(
            "INSERT INTO schools (id, org_id, name) VALUES ($1, $2, 'seed school')",
            school_id, org_id,
        )
        ay_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO academic_years (id, org_id, school_id, name, start_date, end_date)
            VALUES ($1, $2, $3, 'AY', $4, $5)
            """,
            ay_id, org_id, school_id, date(2026, 1, 1), date(2026, 12, 31),
        )
        class_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO school_classes
              (id, org_id, school_id, academic_year_id, grade_id, section, name)
            VALUES ($1, $2, $3, $4, $5, 'A', 'Class A')
            """,
            class_id, org_id, school_id, ay_id, grade["id"],
        )
        cst_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO class_subject_teachers (id, org_id, school_class_id, subject_id)
            VALUES ($1, $2, $3, $4)
            """,
            cst_id, org_id, class_id, subject["id"],
        )
        ids["cst_id"] = cst_id

        book_id = _uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO books (id, curriculum_id, grade_id, subject_id, title)
            VALUES ($1, $2, $3, $4, 'seed book')
            """,
            book_id, curriculum["id"], grade["id"], subject["id"],
        )
        chapter_ids = []
        for n in range(1, num_chapters + 1):
            cid = _uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO book_chapters (id, book_id, chapter_number, title, status)
                VALUES ($1, $2, $3, $4, 'published')
                """,
                cid, book_id, n, f"Chapter {n}",
            )
            chapter_ids.append(cid)
        ids["chapter_ids"] = chapter_ids

        if with_breakdown:
            bd_id = _uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO syllabus_breakdowns
                  (id, curriculum_id, grade_id, subject_id, status)
                VALUES ($1, $2, $3, $4, 'published')
                """,
                bd_id, curriculum["id"], grade["id"], subject["id"],
            )
            ids["breakdown_id"] = bd_id
            base = date(2026, 6, 1)
            for pos, cid in enumerate(chapter_ids, start=1):
                await conn.execute(
                    """
                    INSERT INTO syllabus_chapters
                      (syllabus_breakdown_id, book_chapter_id, position, start_date, end_date)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    bd_id, cid, pos,
                    date(2026, 6, pos), date(2026, 6, pos + 1),
                )

        async def cleanup():
            await conn.execute("DELETE FROM organizations WHERE id=$1", org_id)
            await conn.execute("DELETE FROM books WHERE id=$1", book_id)

        return ids, cleanup

    async def test_seeds_chapters_from_published_breakdown(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn, num_chapters=3)
            try:
                n = await seed_class_chapters_from_breakdown(conn, ids["cst_id"])
                assert n == 3
                rows = await conn.fetch(
                    """
                    SELECT book_chapter_id, position, start_date, end_date, org_id
                      FROM class_chapters WHERE cst_id = $1 ORDER BY position
                    """,
                    ids["cst_id"],
                )
                assert [r["position"] for r in rows] == [1, 2, 3]
                assert [r["book_chapter_id"] for r in rows] == ids["chapter_ids"]
                assert all(r["org_id"] == ids["org_id"] for r in rows)
                # Dates copied verbatim from the breakdown.
                assert rows[0]["start_date"] == date(2026, 6, 1)
                assert rows[0]["end_date"] == date(2026, 6, 2)
            finally:
                await cleanup()
        finally:
            await conn.close()

    async def test_seed_is_idempotent(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn, num_chapters=2)
            try:
                first = await seed_class_chapters_from_breakdown(conn, ids["cst_id"])
                assert first == 2
                second = await seed_class_chapters_from_breakdown(conn, ids["cst_id"])
                assert second == 0
                total = await conn.fetchval(
                    "SELECT count(*) FROM class_chapters WHERE cst_id=$1", ids["cst_id"]
                )
                assert total == 2
            finally:
                await cleanup()
        finally:
            await conn.close()

    async def test_no_op_without_published_breakdown(self):
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn, with_breakdown=False)
            try:
                n = await seed_class_chapters_from_breakdown(conn, ids["cst_id"])
                assert n == 0
                total = await conn.fetchval(
                    "SELECT count(*) FROM class_chapters WHERE cst_id=$1", ids["cst_id"]
                )
                assert total == 0
            finally:
                await cleanup()
        finally:
            await conn.close()

    async def test_no_op_when_path_non_empty(self):
        # Clean-install rule: a CST with any pre-existing class_chapters row is
        # left untouched (avoids (cst_id, position) collisions with legacy paths).
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn, num_chapters=3)
            try:
                # Pre-seed one arbitrary legacy row at a colliding position.
                await conn.execute(
                    """
                    INSERT INTO class_chapters
                      (org_id, cst_id, book_chapter_id, position, start_date, end_date)
                    VALUES ($1, $2, $3, 1, $4, $5)
                    """,
                    ids["org_id"], ids["cst_id"], ids["chapter_ids"][2],
                    date(2026, 9, 1), date(2026, 9, 2),
                )
                n = await seed_class_chapters_from_breakdown(conn, ids["cst_id"])
                assert n == 0
                rows = await conn.fetch(
                    "SELECT book_chapter_id FROM class_chapters WHERE cst_id=$1",
                    ids["cst_id"],
                )
                # Still just the one legacy row — untouched.
                assert len(rows) == 1
                assert rows[0]["book_chapter_id"] == ids["chapter_ids"][2]
            finally:
                await cleanup()
        finally:
            await conn.close()

    async def test_remove_chapter_422s_when_chapter_has_a_generated_slot(self):
        # D-11: a chapter with ANY generated slot (even a non-terminal one)
        # cannot be removed — it would orphan the plan. The slot below is
        # 'planned' (NON-terminal), so the #109 status-lock alone would have
        # allowed removal; the D-11 guard rejects it.
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn, num_chapters=2)
            try:
                # Seed the path from the breakdown so the chapter is in it.
                seeded = await seed_class_chapters_from_breakdown(
                    conn, ids["cst_id"]
                )
                assert seeded == 2
                target = ids["chapter_ids"][0]
                # Generate a single NON-terminal lesson slot for the chapter.
                await conn.execute(
                    """
                    INSERT INTO class_lesson_slots
                      (org_id, cst_id, position, slot_type, book_chapter_id, status)
                    VALUES ($1, $2, 1, 'lesson', $3, 'planned')
                    """,
                    ids["org_id"], ids["cst_id"], target,
                )
                with pytest.raises(ValueError, match="generated plan"):
                    await remove_chapter(conn, ids["cst_id"], target)
                # The path row survives — nothing was deleted.
                still_there = await conn.fetchval(
                    """
                    SELECT 1 FROM class_chapters
                     WHERE cst_id = $1 AND book_chapter_id = $2
                    """,
                    ids["cst_id"], target,
                )
                assert still_there == 1
            finally:
                await cleanup()
        finally:
            await conn.close()

    async def test_remove_chapter_succeeds_when_no_slots(self):
        # Control for the D-11 test: a seeded chapter with no generated slots
        # is yet_to_start and removable.
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            ids, cleanup = await self._build_graph(conn, num_chapters=2)
            try:
                await seed_class_chapters_from_breakdown(conn, ids["cst_id"])
                target = ids["chapter_ids"][1]
                await remove_chapter(conn, ids["cst_id"], target)
                gone = await conn.fetchval(
                    """
                    SELECT 1 FROM class_chapters
                     WHERE cst_id = $1 AND book_chapter_id = $2
                    """,
                    ids["cst_id"], target,
                )
                assert gone is None
            finally:
                await cleanup()
        finally:
            await conn.close()
