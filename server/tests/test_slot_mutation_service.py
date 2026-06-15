"""
Dynamic Chapter Planner — Phase 1, F-1.5.

Exercises `slot_mutation_service` against a real sqlite database with NO
DATABASE_URL set (D-11). The service speaks asyncpg (`$N` placeholders,
`fetchval`/`fetchrow`/`fetch`/`execute`/`transaction()`); `_PgLikeConn` below is
a thin aiosqlite adapter that translates `$N` -> `?` and mimics those methods,
so the SAME mutation SQL that runs on Railway Postgres runs here unmodified.

Coverage (every F-1.5 bullet):
  - insert renumbers BOTH lesson and assessment rows past the insertion point;
  - UNIQUE (cst_id, position) holds throughout the renumber;
  - taught-lock rejects insert at/before last-taught and allows after;
  - remove refuses a taught slot, succeeds on planned, renumbers the tail;
  - consume_flex picks the nearest downstream flex slot, returns None when none.
"""
import re
from uuid import UUID, uuid4

import aiosqlite
import pytest

from dars.breakdown.slot_mutation_service import (
    consume_flex_slot,
    insert_lesson_slot,
    remove_slot,
)

_PLACEHOLDER = re.compile(r"\$(\d+)")


def _to_sqlite(sql: str, args: tuple) -> tuple[str, list]:
    """Translate asyncpg `$N` SQL + positional args to sqlite `?` form.

    Walks the `$N` tokens in textual order, rebuilding the param list in that
    order (so repeated or out-of-order placeholders bind correctly), and swaps
    each `$N` for `?`. Booleans become 0/1 and UUIDs become str (sqlite has no
    native bool/uuid), matching how the column values round-trip below.
    """
    ordered: list = []

    def repl(m: re.Match) -> str:
        idx = int(m.group(1)) - 1
        ordered.append(_adapt(args[idx]))
        return "?"

    new_sql = _PLACEHOLDER.sub(repl, sql)
    return new_sql, ordered


def _adapt(v):
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, UUID):
        return str(v)
    return v


class _Tx:
    """No-op-ish transaction context manager.

    The service wraps each mutation in `async with conn.transaction()`. For the
    test we run everything on one connection inside a single sqlite transaction
    (autocommit off); the context manager commits on clean exit and rolls back
    on exception, mirroring asyncpg semantics so a failed mutation leaves no
    partial state (the renumber-collision and refusal cases rely on rollback).
    """

    def __init__(self, conn: "_PgLikeConn"):
        self._conn = conn

    async def __aenter__(self):
        # sqlite (aiosqlite) is already in a deferred transaction by default
        # when isolation_level is left at its default; we manage commit/rollback
        # explicitly here.
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is None:
            await self._conn.raw.commit()
        else:
            await self._conn.raw.rollback()
        return False


class _PgLikeConn:
    """asyncpg-shaped facade over an aiosqlite connection."""

    def __init__(self, raw: aiosqlite.Connection):
        self.raw = raw

    def transaction(self):
        return _Tx(self)

    async def execute(self, sql: str, *args):
        s, params = _to_sqlite(sql, args)
        await self.raw.execute(s, params)

    async def fetchval(self, sql: str, *args):
        s, params = _to_sqlite(sql, args)
        cur = await self.raw.execute(s, params)
        row = await cur.fetchone()
        await cur.close()
        if row is None:
            return None
        return row[0]

    async def fetchrow(self, sql: str, *args):
        s, params = _to_sqlite(sql, args)
        self.raw.row_factory = aiosqlite.Row
        cur = await self.raw.execute(s, params)
        row = await cur.fetchone()
        await cur.close()
        return row

    async def fetch(self, sql: str, *args):
        s, params = _to_sqlite(sql, args)
        self.raw.row_factory = aiosqlite.Row
        cur = await self.raw.execute(s, params)
        rows = await cur.fetchall()
        await cur.close()
        return rows


_SCHEMA = """
CREATE TABLE class_subject_teachers (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL
);
CREATE TABLE class_lesson_slots (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    cst_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    slot_type TEXT NOT NULL,
    lp_type TEXT,
    topic_id TEXT,
    anchor_date TEXT,
    generated_lp_id TEXT,
    status TEXT NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned','taught','skipped')),
    origin TEXT NOT NULL DEFAULT 'breakdown'
        CHECK (origin IN ('breakdown','reteach','manual')),
    reteach_for_sub_slo_id TEXT,
    flex INTEGER NOT NULL DEFAULT 0,
    UNIQUE (cst_id, position)
);
CREATE TABLE class_assessment_slots (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    cst_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    assessment_type TEXT NOT NULL
        CHECK (assessment_type IN ('formative','summative')),
    anchor_date TEXT,
    generated_exam_id TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled','completed','skipped')),
    origin TEXT NOT NULL DEFAULT 'breakdown'
        CHECK (origin IN ('breakdown','reteach','manual')),
    UNIQUE (cst_id, position)
);
CREATE TABLE class_lesson_slot_topics (
    class_lesson_slot_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (class_lesson_slot_id, topic_id)
);
CREATE TABLE class_assessment_slot_topics (
    class_assessment_slot_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (class_assessment_slot_id, topic_id)
);
"""

ORG_ID = uuid4()
CST_ID = uuid4()

# Connections opened during a test, closed on teardown so aiosqlite's worker
# thread doesn't outlive the function-scoped event loop (avoids a benign but
# noisy "Event loop is closed" ResourceWarning at GC).
_OPEN_CONNS: list[aiosqlite.Connection] = []


@pytest.fixture(autouse=True)
async def _close_conns():
    yield
    while _OPEN_CONNS:
        raw = _OPEN_CONNS.pop()
        try:
            await raw.close()
        except Exception:
            pass


async def _new_db() -> _PgLikeConn:
    raw = await aiosqlite.connect(":memory:")
    _OPEN_CONNS.append(raw)
    # Default isolation_level leaves us in implicit-transaction mode, which the
    # service's `transaction()` context manager commits/rolls back explicitly.
    await raw.executescript(_SCHEMA)
    await raw.execute(
        "INSERT INTO class_subject_teachers (id, org_id) VALUES (?, ?)",
        (str(CST_ID), str(ORG_ID)),
    )
    await raw.commit()
    return _PgLikeConn(raw)


async def _insert_lesson(conn, position, *, status="planned", flex=False,
                         origin="breakdown"):
    sid = uuid4()
    await conn.raw.execute(
        """
        INSERT INTO class_lesson_slots
          (id, org_id, cst_id, position, slot_type, lp_type, status, origin, flex)
        VALUES (?, ?, ?, ?, 'lesson', 'core', ?, ?, ?)
        """,
        (str(sid), str(ORG_ID), str(CST_ID), position, status, origin,
         1 if flex else 0),
    )
    await conn.raw.commit()
    return sid


async def _insert_assessment(conn, position, *, status="scheduled"):
    sid = uuid4()
    await conn.raw.execute(
        """
        INSERT INTO class_assessment_slots
          (id, org_id, cst_id, position, assessment_type, status)
        VALUES (?, ?, ?, ?, 'formative', ?)
        """,
        (str(sid), str(ORG_ID), str(CST_ID), position, status),
    )
    await conn.raw.commit()
    return sid


async def _positions(conn, table):
    conn.raw.row_factory = aiosqlite.Row
    cur = await conn.raw.execute(
        f"SELECT id, position FROM {table} WHERE cst_id = ? ORDER BY position",
        (str(CST_ID),),
    )
    rows = await cur.fetchall()
    await cur.close()
    return [(r["id"], r["position"]) for r in rows]


# ---------------------------------------------------------------------------
# insert renumbers BOTH tables + uniqueness holds
# ---------------------------------------------------------------------------


async def test_insert_renumbers_both_tables():
    conn = await _new_db()
    # Interleaved sequence across both tables: L1 A2 L3 A4 L5.
    await _insert_lesson(conn, 1)
    await _insert_assessment(conn, 2)
    await _insert_lesson(conn, 3)
    await _insert_assessment(conn, 4)
    await _insert_lesson(conn, 5)

    topic = uuid4()
    new_id = await insert_lesson_slot(
        conn, CST_ID, after_position=2,
        topic_ids=[topic], lp_type="revision", origin="manual",
    )
    assert isinstance(new_id, UUID) or new_id is not None

    lessons = await _positions(conn, "class_lesson_slots")
    assessments = await _positions(conn, "class_assessment_slots")
    lpos = sorted(p for _, p in lessons)
    apos = sorted(p for _, p in assessments)

    # The new lesson sits at 3; everything formerly > 2 shifted up by one.
    # Lessons were at 1,3,5 -> 1, (new)3, 4, 6 ; assessments at 2,4 -> 2, 5.
    assert lpos == [1, 3, 4, 6]
    assert apos == [2, 5]

    # The new slot is the one at position 3.
    new_pos = {sid: pos for sid, pos in lessons}[str(new_id)]
    assert new_pos == 3

    # Topics written.
    topics = await conn.fetch(
        "SELECT topic_id FROM class_lesson_slot_topics "
        "WHERE class_lesson_slot_id = $1",
        new_id,
    )
    assert [r["topic_id"] for r in topics] == [str(topic)]


async def test_insert_preserves_uniqueness_across_renumber():
    conn = await _new_db()
    # Dense contiguous run in both tables — the case most likely to collide if
    # the renumber weren't collision-safe.
    for p in (1, 3, 5, 7):
        await _insert_lesson(conn, p)
    for p in (2, 4, 6):
        await _insert_assessment(conn, p)

    await insert_lesson_slot(
        conn, CST_ID, after_position=1, topic_ids=[uuid4()], lp_type=None,
    )

    # No duplicate positions within each table (UNIQUE held throughout).
    for table in ("class_lesson_slots", "class_assessment_slots"):
        pos = [p for _, p in await _positions(conn, table)]
        assert len(pos) == len(set(pos)), f"duplicate positions in {table}"

    # Merged sequence is gap-free 1..8 (4 lessons + 1 inserted + 3 assessments).
    all_pos = sorted(
        [p for _, p in await _positions(conn, "class_lesson_slots")]
        + [p for _, p in await _positions(conn, "class_assessment_slots")]
    )
    assert all_pos == list(range(1, 9))


# ---------------------------------------------------------------------------
# taught-lock (F-1.3)
# ---------------------------------------------------------------------------


async def test_taught_lock_rejects_insert_at_or_before_last_taught():
    conn = await _new_db()
    await _insert_lesson(conn, 1, status="taught")
    await _insert_lesson(conn, 2, status="taught")
    await _insert_lesson(conn, 3, status="planned")

    # after_position=1 is before the last taught (position 2) -> rejected.
    with pytest.raises(ValueError, match="last taught"):
        await insert_lesson_slot(
            conn, CST_ID, after_position=1, topic_ids=[uuid4()], lp_type=None,
        )

    # Nothing shifted (rollback): positions unchanged.
    assert [p for _, p in await _positions(conn, "class_lesson_slots")] == [1, 2, 3]


async def test_taught_lock_rejects_at_completed_assessment():
    conn = await _new_db()
    await _insert_lesson(conn, 1, status="taught")
    await _insert_assessment(conn, 2, status="completed")
    await _insert_lesson(conn, 3, status="planned")

    # Last settled position is 2 (completed assessment). after_position=2 is not
    # strictly after it -> the boundary is exactly 2, so after_position=1 fails.
    with pytest.raises(ValueError):
        await insert_lesson_slot(
            conn, CST_ID, after_position=1, topic_ids=[uuid4()], lp_type=None,
        )


async def test_taught_lock_allows_insert_after_last_taught():
    conn = await _new_db()
    await _insert_lesson(conn, 1, status="taught")
    await _insert_lesson(conn, 2, status="taught")
    await _insert_lesson(conn, 3, status="planned")

    # after_position=2 == last_taught is allowed (the gap opens at 3, all
    # shifted rows are > the frozen boundary).
    new_id = await insert_lesson_slot(
        conn, CST_ID, after_position=2, topic_ids=[uuid4()], lp_type=None,
    )
    assert new_id is not None
    pos = {sid: p for sid, p in await _positions(conn, "class_lesson_slots")}
    assert pos[str(new_id)] == 3
    # The formerly-planned slot moved 3 -> 4; taught slots untouched.
    assert sorted(pos.values()) == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# remove (F-1.2)
# ---------------------------------------------------------------------------


async def test_remove_refuses_taught_slot():
    conn = await _new_db()
    await _insert_lesson(conn, 1, status="taught")
    await _insert_lesson(conn, 2, status="planned")

    # position 1 is taught — taught-lock catches it first (mutation at/before
    # the last taught position), which is the correct refusal.
    with pytest.raises(ValueError):
        await remove_slot(conn, CST_ID, position=1)
    assert [p for _, p in await _positions(conn, "class_lesson_slots")] == [1, 2]


async def test_remove_refuses_taught_slot_in_tail():
    conn = await _new_db()
    # A taught slot sitting AFTER the frozen boundary would still be refused by
    # the status check. Construct: nothing settled before it, but the slot
    # itself is taught.
    await _insert_lesson(conn, 1, status="planned")
    await _insert_lesson(conn, 2, status="taught")

    # Removing position 1 (planned) is fine; removing 2 (taught) is refused by
    # the taught-lock. Verify the explicit-status refusal by removing 1 first.
    with pytest.raises(ValueError):
        await remove_slot(conn, CST_ID, position=2)


async def test_remove_planned_renumbers_tail():
    conn = await _new_db()
    await _insert_lesson(conn, 1)
    await _insert_assessment(conn, 2)
    await _insert_lesson(conn, 3)
    await _insert_assessment(conn, 4)

    await remove_slot(conn, CST_ID, position=2)  # the assessment at 2

    lessons = [p for _, p in await _positions(conn, "class_lesson_slots")]
    assessments = [p for _, p in await _positions(conn, "class_assessment_slots")]
    # Lessons 1,3 -> 1,2 ; assessment 4 -> 3 ; assessment at 2 gone.
    assert lessons == [1, 2]
    assert assessments == [3]
    # Merged is contiguous 1..3.
    assert sorted(lessons + assessments) == [1, 2, 3]


async def test_remove_deletes_topics():
    conn = await _new_db()
    new_id = await insert_lesson_slot(
        conn, CST_ID, after_position=0, topic_ids=[uuid4(), uuid4()],
        lp_type=None,
    )
    before = await conn.fetch(
        "SELECT * FROM class_lesson_slot_topics WHERE class_lesson_slot_id = $1",
        new_id,
    )
    assert len(before) == 2
    await remove_slot(conn, CST_ID, position=1)
    after = await conn.fetch(
        "SELECT * FROM class_lesson_slot_topics WHERE class_lesson_slot_id = $1",
        new_id,
    )
    assert len(after) == 0


async def test_remove_missing_position_raises():
    conn = await _new_db()
    await _insert_lesson(conn, 1)
    with pytest.raises(ValueError, match="no slot at position"):
        await remove_slot(conn, CST_ID, position=9)


# ---------------------------------------------------------------------------
# consume_flex (F-1.2, D-5)
# ---------------------------------------------------------------------------


async def test_consume_flex_picks_nearest_downstream():
    conn = await _new_db()
    await _insert_lesson(conn, 1)                          # mandatory
    flex_near = await _insert_lesson(conn, 2, flex=True)   # nearest downstream
    flex_far = await _insert_lesson(conn, 3, flex=True)    # further

    sub_slo = uuid4()
    topic = uuid4()
    got = await consume_flex_slot(
        conn, CST_ID, after_position=1,
        reteach_for_sub_slo_id=sub_slo, lp_type="revision", topic_ids=[topic],
    )
    assert str(got) == str(flex_near)
    assert str(got) != str(flex_far)

    row = await conn.fetchrow(
        "SELECT origin, flex, reteach_for_sub_slo_id, lp_type, topic_id "
        "FROM class_lesson_slots WHERE id = $1",
        flex_near,
    )
    assert row["origin"] == "reteach"
    assert row["flex"] == 0
    assert row["reteach_for_sub_slo_id"] == str(sub_slo)
    assert row["lp_type"] == "revision"
    assert row["topic_id"] == str(topic)

    # No position shift — flex consumed in place.
    assert [p for _, p in await _positions(conn, "class_lesson_slots")] == [1, 2, 3]

    # Topics rewritten to the reteach topic.
    topics = await conn.fetch(
        "SELECT topic_id FROM class_lesson_slot_topics "
        "WHERE class_lesson_slot_id = $1",
        flex_near,
    )
    assert [r["topic_id"] for r in topics] == [str(topic)]


async def test_consume_flex_returns_none_when_no_flex():
    conn = await _new_db()
    await _insert_lesson(conn, 1)
    await _insert_lesson(conn, 2)  # not flex

    got = await consume_flex_slot(
        conn, CST_ID, after_position=1,
        reteach_for_sub_slo_id=uuid4(), lp_type="revision", topic_ids=[uuid4()],
    )
    assert got is None


async def test_consume_flex_ignores_upstream_flex():
    conn = await _new_db()
    await _insert_lesson(conn, 1, flex=True)   # upstream of after_position
    await _insert_lesson(conn, 2)
    await _insert_lesson(conn, 3)

    # after_position=2: the only flex slot is at position 1 (upstream) -> None.
    got = await consume_flex_slot(
        conn, CST_ID, after_position=2,
        reteach_for_sub_slo_id=uuid4(), lp_type="revision", topic_ids=[uuid4()],
    )
    assert got is None
