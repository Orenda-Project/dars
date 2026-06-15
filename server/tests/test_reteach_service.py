"""
Dynamic Chapter Planner — Phase 3, F-3.4.

Exercises `reteach_service` against a real sqlite database with NO DATABASE_URL
set (D-11), reusing the asyncpg-shaped `_PgLikeConn` adapter pattern from
`test_slot_mutation_service.py` so the SAME mutation SQL that runs on Railway
Postgres runs here unmodified.

Coverage (every F-3.4 bullet):
  - suggest_reteach returns the below-threshold sub-SLOs (and nothing when all
    are at/above threshold; rejects a non-FA slot);
  - lightweight reteach flips cst_sub_slo_coverage to 'not_taught', no slot/shift;
  - heavy reteach CONSUMES a downstream flex slot when one exists (no shift,
    consequence=None);
  - heavy reteach INSERTS when no flex exists, shifting the tail, and reports the
    overflow consequence (flags overflow when the insert pushes past year-end).
"""
import re
from uuid import UUID, uuid4

import aiosqlite
import pytest

from dars.breakdown.reteach_service import (
    RETEACH_MASTERY_THRESHOLD,
    reteach,
    suggest_reteach,
)

_PLACEHOLDER = re.compile(r"\$(\d+)")


def _adapt(v):
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, UUID):
        return str(v)
    return v


def _to_sqlite(sql: str, args: tuple) -> tuple[str, list]:
    # sqlite has no now(); map it to a portable literal timestamp expression.
    sql = sql.replace("now()", "CURRENT_TIMESTAMP")
    ordered: list = []

    def repl(m: re.Match) -> str:
        idx = int(m.group(1)) - 1
        ordered.append(_adapt(args[idx]))
        return "?"

    return _PLACEHOLDER.sub(repl, sql), ordered


class _Tx:
    def __init__(self, conn: "_PgLikeConn"):
        self._conn = conn

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is None:
            await self._conn.raw.commit()
        else:
            await self._conn.raw.rollback()
        return False


class _PgLikeConn:
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
        return None if row is None else row[0]

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
    book_chapter_id TEXT,
    generated_lp_id TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    origin TEXT NOT NULL DEFAULT 'breakdown',
    reteach_for_sub_slo_id TEXT,
    flex INTEGER NOT NULL DEFAULT 0,
    UNIQUE (cst_id, position)
);
CREATE TABLE class_assessment_slots (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    cst_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    assessment_type TEXT NOT NULL,
    anchor_date TEXT,
    book_chapter_id TEXT,
    generated_exam_id TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled',
    origin TEXT NOT NULL DEFAULT 'breakdown',
    UNIQUE (cst_id, position)
);
CREATE TABLE class_lesson_slot_topics (
    class_lesson_slot_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (class_lesson_slot_id, topic_id)
);
CREATE TABLE sub_slos (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    statement TEXT NOT NULL
);
CREATE TABLE topics (
    id TEXT PRIMARY KEY,
    book_chapter_id TEXT,
    topic_number INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE topic_sub_slos (
    topic_id TEXT NOT NULL,
    sub_slo_id TEXT NOT NULL,
    PRIMARY KEY (topic_id, sub_slo_id)
);
CREATE TABLE sub_slo_mastery (
    id TEXT PRIMARY KEY,
    cst_id TEXT NOT NULL,
    sub_slo_id TEXT NOT NULL,
    class_assessment_slot_id TEXT NOT NULL,
    mastery_percent NUMERIC NOT NULL,
    assessed_on TEXT NOT NULL
);
CREATE TABLE cst_sub_slo_coverage (
    cst_id TEXT NOT NULL,
    sub_slo_id TEXT NOT NULL,
    status TEXT NOT NULL,
    marked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (cst_id, sub_slo_id)
);
"""

ORG_ID = uuid4()
CST_ID = uuid4()
CHAPTER_ID = uuid4()

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
    await raw.executescript(_SCHEMA)
    await raw.execute(
        "INSERT INTO class_subject_teachers (id, org_id) VALUES (?, ?)",
        (str(CST_ID), str(ORG_ID)),
    )
    await raw.commit()
    return _PgLikeConn(raw)


async def _add_lesson(conn, position, *, flex=False, status="planned"):
    sid = uuid4()
    await conn.raw.execute(
        """
        INSERT INTO class_lesson_slots
          (id, org_id, cst_id, position, slot_type, lp_type, book_chapter_id,
           status, origin, flex)
        VALUES (?, ?, ?, ?, 'lesson', 'reading', ?, ?, 'breakdown', ?)
        """,
        (str(sid), str(ORG_ID), str(CST_ID), position, str(CHAPTER_ID),
         status, 1 if flex else 0),
    )
    await conn.raw.commit()
    return sid


async def _add_fa(conn, position, *, status="completed"):
    sid = uuid4()
    await conn.raw.execute(
        """
        INSERT INTO class_assessment_slots
          (id, org_id, cst_id, position, assessment_type, book_chapter_id, status)
        VALUES (?, ?, ?, ?, 'formative', ?, ?)
        """,
        (str(sid), str(ORG_ID), str(CST_ID), position, str(CHAPTER_ID), status),
    )
    await conn.raw.commit()
    return sid


async def _add_sub_slo(conn, code, *, topic_number=1) -> tuple[UUID, UUID]:
    """Create a sub_slo + a topic on the FA chapter that carries it. Returns
    (sub_slo_id, topic_id)."""
    ssid = uuid4()
    tid = uuid4()
    await conn.raw.execute(
        "INSERT INTO sub_slos (id, code, statement) VALUES (?, ?, ?)",
        (str(ssid), code, f"statement for {code}"),
    )
    await conn.raw.execute(
        "INSERT INTO topics (id, book_chapter_id, topic_number) VALUES (?, ?, ?)",
        (str(tid), str(CHAPTER_ID), topic_number),
    )
    await conn.raw.execute(
        "INSERT INTO topic_sub_slos (topic_id, sub_slo_id) VALUES (?, ?)",
        (str(tid), str(ssid)),
    )
    await conn.raw.commit()
    return ssid, tid


async def _add_mastery(conn, fa_id, sub_slo_id, percent):
    await conn.raw.execute(
        """
        INSERT INTO sub_slo_mastery
          (id, cst_id, sub_slo_id, class_assessment_slot_id, mastery_percent,
           assessed_on)
        VALUES (?, ?, ?, ?, ?, '2026-06-15')
        """,
        (str(uuid4()), str(CST_ID), str(sub_slo_id), str(fa_id), percent),
    )
    await conn.raw.commit()


async def _positions(conn, table):
    conn.raw.row_factory = aiosqlite.Row
    cur = await conn.raw.execute(
        f"SELECT position FROM {table} WHERE cst_id = ? ORDER BY position",
        (str(CST_ID),),
    )
    rows = await cur.fetchall()
    await cur.close()
    return [r["position"] for r in rows]


class _ProjSlot:
    def __init__(self, position, is_overflow):
        self.position = position
        self.is_overflow = is_overflow


def _projector_with_capacity(capacity: int):
    """A fake projector: the first `capacity` positions fit; the rest overflow.
    Reads the live class_lesson_slots + class_assessment_slots so it reflects the
    post-mutation positions (mirrors the real projector's merge-by-position)."""

    async def _proj(conn, cst_id):
        lpos = await _positions(conn, "class_lesson_slots")
        apos = await _positions(conn, "class_assessment_slots")
        allpos = sorted(lpos + apos)
        return [_ProjSlot(p, p > capacity) for p in allpos]

    return _proj


async def _noop_lp(conn, slot_id):
    """Stub for get_or_generate_lp so tests don't dispatch to LP Assistant."""
    return None


# ---------------------------------------------------------------------------
# F-3.1 — suggestion read
# ---------------------------------------------------------------------------


async def test_suggest_returns_below_threshold_subslos():
    conn = await _new_db()
    fa = await _add_fa(conn, 3)
    low, _ = await _add_sub_slo(conn, "1.1")
    high, _ = await _add_sub_slo(conn, "1.2", topic_number=2)
    await _add_mastery(conn, fa, low, 40.0)    # below 60 -> suggested
    await _add_mastery(conn, fa, high, 90.0)   # above -> not suggested

    out = await suggest_reteach(conn, fa)
    assert [s.sub_slo_id for s in out] == [str(low)]
    assert out[0].mastery_percent == 40.0
    assert out[0].sub_slo_code == "1.1"


async def test_suggest_empty_when_all_above_threshold():
    conn = await _new_db()
    fa = await _add_fa(conn, 1)
    ss, _ = await _add_sub_slo(conn, "2.1")
    await _add_mastery(conn, fa, ss, 85.0)
    assert await suggest_reteach(conn, fa) == []


async def test_suggest_boundary_at_threshold_not_suggested():
    # Exactly at the threshold is NOT below it (strict <).
    conn = await _new_db()
    fa = await _add_fa(conn, 1)
    ss, _ = await _add_sub_slo(conn, "2.2")
    await _add_mastery(conn, fa, ss, RETEACH_MASTERY_THRESHOLD)
    assert await suggest_reteach(conn, fa) == []


async def test_suggest_rejects_non_fa_slot():
    conn = await _new_db()
    # Forge a summative slot.
    sid = uuid4()
    await conn.raw.execute(
        """
        INSERT INTO class_assessment_slots
          (id, org_id, cst_id, position, assessment_type, book_chapter_id, status)
        VALUES (?, ?, ?, 1, 'summative', ?, 'completed')
        """,
        (str(sid), str(ORG_ID), str(CST_ID), str(CHAPTER_ID)),
    )
    await conn.raw.commit()
    with pytest.raises(ValueError, match="not a formative"):
        await suggest_reteach(conn, sid)


# ---------------------------------------------------------------------------
# F-3.2 — lightweight
# ---------------------------------------------------------------------------


async def test_lightweight_flips_coverage_no_slot():
    conn = await _new_db()
    await _add_lesson(conn, 1)
    fa = await _add_fa(conn, 2)
    ss, _ = await _add_sub_slo(conn, "3.1")

    result = await reteach(
        conn, class_assessment_slot_id=fa, sub_slo_id=ss, mode="lightweight",
    )
    assert result.path == "lightweight"
    assert result.slot_id is None
    assert result.consequence is None

    # Coverage flipped to needs-rework.
    row = await conn.fetchrow(
        "SELECT status FROM cst_sub_slo_coverage WHERE cst_id = $1 AND sub_slo_id = $2",
        CST_ID, ss,
    )
    assert row["status"] == "not_taught"
    # No new slot, positions unchanged (1 lesson + 1 FA).
    assert await _positions(conn, "class_lesson_slots") == [1]
    assert await _positions(conn, "class_assessment_slots") == [2]


# ---------------------------------------------------------------------------
# F-3.2 — heavy: consume vs insert branch picks correctly
# ---------------------------------------------------------------------------


async def test_heavy_consumes_downstream_flex_no_shift():
    conn = await _new_db()
    await _add_lesson(conn, 1)
    fa = await _add_fa(conn, 2)
    await _add_lesson(conn, 3, flex=True)   # downstream flex to consume
    await _add_lesson(conn, 4)
    ss, topic = await _add_sub_slo(conn, "4.1")

    result = await reteach(
        conn, class_assessment_slot_id=fa, sub_slo_id=ss, mode="heavy",
        lp_generator=_noop_lp, projector=_projector_with_capacity(100),
    )
    assert result.path == "consume_flex"
    assert result.slot_id is not None
    assert result.consequence is None  # consume never shifts -> no consequence

    # The flex slot at position 3 was repurposed in place — no position shift.
    assert await _positions(conn, "class_lesson_slots") == [1, 3, 4]
    row = await conn.fetchrow(
        "SELECT origin, flex, reteach_for_sub_slo_id, lp_type, topic_id "
        "FROM class_lesson_slots WHERE position = 3 AND cst_id = $1",
        CST_ID,
    )
    assert row["origin"] == "reteach"
    assert row["flex"] == 0
    assert row["reteach_for_sub_slo_id"] == str(ss)
    assert row["lp_type"] == "revision"
    assert row["topic_id"] == str(topic)


async def test_heavy_inserts_when_no_flex_and_reports_no_overflow():
    conn = await _new_db()
    await _add_lesson(conn, 1)
    fa = await _add_fa(conn, 2)
    await _add_lesson(conn, 3)   # NOT flex
    ss, topic = await _add_sub_slo(conn, "5.1")

    # Capacity 100 >> slots, so the inserted slot still fits — no overflow.
    result = await reteach(
        conn, class_assessment_slot_id=fa, sub_slo_id=ss, mode="heavy",
        lp_generator=_noop_lp, projector=_projector_with_capacity(100),
    )
    assert result.path == "insert"
    assert result.slot_id is not None
    assert result.consequence is not None
    assert result.consequence.overflow_before == 0
    assert result.consequence.overflow_after == 0
    assert result.consequence.newly_overflowed_positions == []
    assert result.consequence.first_overflow_position is None

    # The inserted reteach slot sits at position 3; the old position-3 lesson
    # shifted to 4.
    lpos = await _positions(conn, "class_lesson_slots")
    assert lpos == [1, 3, 4]
    row = await conn.fetchrow(
        "SELECT origin, flex, reteach_for_sub_slo_id, lp_type, topic_id "
        "FROM class_lesson_slots WHERE position = 3 AND cst_id = $1",
        CST_ID,
    )
    assert row["origin"] == "reteach"
    assert row["flex"] == 0
    assert row["reteach_for_sub_slo_id"] == str(ss)
    assert row["topic_id"] == str(topic)


# ---------------------------------------------------------------------------
# F-3.4 — consequence reporting flags overflow when insert pushes past year-end
# ---------------------------------------------------------------------------


async def test_heavy_insert_overflow_consequence_flags_pushed_tail():
    conn = await _new_db()
    # Plan fills the year exactly: 4 slots, capacity 4. No flex anywhere.
    await _add_lesson(conn, 1)
    fa = await _add_fa(conn, 2)
    await _add_lesson(conn, 3)
    await _add_lesson(conn, 4)   # the last slot that fits
    ss, _ = await _add_sub_slo(conn, "6.1")

    # Capacity 4 — inserting a 5th slot pushes the tail past year-end.
    result = await reteach(
        conn, class_assessment_slot_id=fa, sub_slo_id=ss, mode="heavy",
        lp_generator=_noop_lp, projector=_projector_with_capacity(4),
    )
    assert result.path == "insert"
    cons = result.consequence
    assert cons is not None
    assert cons.overflow_before == 0          # fit exactly before
    assert cons.overflow_after == 1           # one slot now overflows
    assert cons.newly_overflowed_positions == [5]
    assert cons.first_overflow_position == 5

    # Tail shifted: 5 slots now, the last at position 5 (the overflowed one).
    allpos = sorted(
        await _positions(conn, "class_lesson_slots")
        + await _positions(conn, "class_assessment_slots")
    )
    assert allpos == [1, 2, 3, 4, 5]


async def test_heavy_rejects_bad_mode():
    conn = await _new_db()
    fa = await _add_fa(conn, 1)
    ss, _ = await _add_sub_slo(conn, "7.1")
    with pytest.raises(ValueError, match="mode must be"):
        await reteach(
            conn, class_assessment_slot_id=fa, sub_slo_id=ss, mode="bogus",
        )
