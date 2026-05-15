"""
F1.2 — Lookup table seed: grades, subjects, curriculums.

Idempotent: ON CONFLICT DO NOTHING keyed on the unique columns.
IDs are deterministic UUID v5 so test fixtures and downstream code can
hard-reference them.

See: docs/plans/2026-05-15-dars-v2-rebuild/03-phase-1-foundation.md#f12
"""
import logging
import uuid

import asyncpg

log = logging.getLogger("v2_seed.lookups")

# Stable namespace for deriving deterministic UUIDs in the dars v2 seed.
# DO NOT change this value — it's the anchor for every seed-row ID.
SEED_NAMESPACE = uuid.UUID("00000000-0000-5da7-5000-000000000001")


def seed_uuid(key: str) -> uuid.UUID:
    """Deterministic UUID v5 derived from SEED_NAMESPACE + key."""
    return uuid.uuid5(SEED_NAMESPACE, key)


# ---------------------------------------------------------------------------
# Data definitions
# ---------------------------------------------------------------------------

GRADES = [(n, f"Grade {n}") for n in range(1, 13)]  # 1..12

# Subjects must align with LP Assistant + UG_EG support enums (08-, 09-reference docs).
# LP Assistant supports: Eng, Urdu, Maths, Science, GK.
# UG_EG supports: Eng, Maths, Urdu, Islamiat, GenSci, GenK, SST. (8 total seeded.)
SUBJECTS = [
    ("Eng", "English"),
    ("Urdu", "Urdu"),
    ("Maths", "Mathematics"),
    ("Science", "Science"),
    ("GK", "General Knowledge"),
    ("Islamiat", "Islamiat"),
    ("GenSci", "General Science"),
    ("SST", "Social Studies"),
]

# Curriculums. DARS is the v1 working curriculum (D-15); NCP and SNC are
# placeholders for future seed (D-61: NCP→ICT, SNC→Punjab for LP Assistant).
CURRICULUMS = [
    ("DARS", "Dars Curriculum", "Dars-authored canonical curriculum for v1 development.", True),
    ("NCP", "National Curriculum of Pakistan", "Government-published K-5 curriculum (placeholder).", False),
    ("SNC", "Single National Curriculum", "Punjab provincial curriculum (placeholder).", False),
]


# ---------------------------------------------------------------------------
# Insert helpers
# ---------------------------------------------------------------------------


async def _seed_grades(conn: asyncpg.Connection) -> int:
    count = 0
    for code, display_name in GRADES:
        uid = seed_uuid(f"grade:{code}")
        result = await conn.execute(
            """
            INSERT INTO grades (id, code, display_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (code) DO NOTHING
            """,
            uid, code, display_name,
        )
        if result.endswith(" 1"):
            count += 1
    return count


async def _seed_subjects(conn: asyncpg.Connection) -> int:
    count = 0
    for code, display_name in SUBJECTS:
        uid = seed_uuid(f"subject:{code}")
        result = await conn.execute(
            """
            INSERT INTO subjects (id, code, display_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (code) DO NOTHING
            """,
            uid, code, display_name,
        )
        if result.endswith(" 1"):
            count += 1
    return count


async def _seed_curriculums(conn: asyncpg.Connection) -> int:
    count = 0
    for code, name, description, is_active in CURRICULUMS:
        uid = seed_uuid(f"curriculum:{code}")
        result = await conn.execute(
            """
            INSERT INTO curriculums (id, code, name, description, is_active)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (code) DO NOTHING
            """,
            uid, code, name, description, is_active,
        )
        if result.endswith(" 1"):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def seed_lookups(conn: asyncpg.Connection) -> None:
    log.info("seed_lookups: starting")
    grades_inserted = await _seed_grades(conn)
    subjects_inserted = await _seed_subjects(conn)
    curriculums_inserted = await _seed_curriculums(conn)
    log.info(
        "seed_lookups: done — grades=%d (inserted=%d), subjects=%d (inserted=%d), curriculums=%d (inserted=%d)",
        len(GRADES), grades_inserted,
        len(SUBJECTS), subjects_inserted,
        len(CURRICULUMS), curriculums_inserted,
    )
