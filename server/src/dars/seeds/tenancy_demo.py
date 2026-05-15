"""
F1.5 — Demo tenancy seed.

Seeds one full demo tenancy stack so Phase 2+ can target it:
- 1 Organization ("Dars Demo Org") with a deterministic API key
- 1 OrgAdmin (email + password) for dashboard login (Phase 5)
- 1 School ("Dars Demo School") under the org
- 1 Teacher ("Aisha Khan") under the school; org.default_teacher_id → her
- 1 AcademicYear ("2026-2027") under the school
- 1 SchoolClass ("Grade 1 - A")
- 1 ClassSubjectTeacher (Aisha teaches English to G1-A; book = Dars English G1 Reader)
- Timetable: Mon-Fri for the CST (D-27)
- cst_state row at sequence position 1

🧊 SEED FREEZE: Once this lands, the demo org's API key and IDs are
frozen. Phase 2+ tests reference these via deterministic UUIDs.

The demo API key is hardcoded here (D-65 — staging-only; production
never sees this seed). Anyone with repo access can use it against the
staging API; that's acceptable for v1.
"""
import hashlib
import logging
import uuid

import asyncpg
import bcrypt

from dars.seeds.lookups import seed_uuid

log = logging.getLogger("v2_seed.tenancy_demo")


# ---------------------------------------------------------------------------
# Demo tenancy constants (FROZEN once F1.5 lands on staging)
# ---------------------------------------------------------------------------

DEMO_ORG_NAME = "Dars Demo Org"
DEMO_ORG_API_KEY_RAW = "dk_demo_dars_eng_g1_2dc7e0b8408142fa"  # staging only; deterministic
DEMO_ORG_API_KEY_PREFIX = DEMO_ORG_API_KEY_RAW[:8]

DEMO_ADMIN_EMAIL = "admin@dars-demo.local"
DEMO_ADMIN_PASSWORD = "darsdemo2026"  # staging only; backend doesn't even use it yet
DEMO_ADMIN_NAME = "Demo Admin"

DEMO_SCHOOL_NAME = "Dars Demo School"

DEMO_TEACHER_NAME = "Aisha Khan"
DEMO_TEACHER_EMAIL: str | None = None  # auth-free per D-9

DEMO_ACADEMIC_YEAR_NAME = "2026-2027"
DEMO_ACADEMIC_YEAR_START = "2026-04-01"
DEMO_ACADEMIC_YEAR_END = "2027-03-31"

DEMO_CLASS_GRADE_CODE = 1
DEMO_CLASS_SECTION = "A"
DEMO_CLASS_NAME = "Grade 1 - A"

DEMO_CST_SUBJECT_CODE = "Eng"

# Timetable: Mon-Fri (0..4). D-27.
DEMO_TIMETABLE_DAYS = [0, 1, 2, 3, 4]


def _hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


async def seed_demo_tenancy(conn: asyncpg.Connection) -> None:
    log.info("seed_demo_tenancy: starting")

    curriculum_id = seed_uuid("curriculum:DARS")
    grade_id = seed_uuid("grade:1")
    subject_id = seed_uuid("subject:Eng")

    org_id = seed_uuid("org:dars-demo-org")
    org_admin_id = seed_uuid("org_admin:dars-demo:admin")
    school_id = seed_uuid("school:dars-demo-school")
    teacher_id = seed_uuid("teacher:dars-demo:aisha-khan")
    academic_year_id = seed_uuid("academic_year:dars-demo:2026-2027")
    school_class_id = seed_uuid("school_class:dars-demo:g1-a")
    cst_id = seed_uuid("cst:dars-demo:g1-a:eng")

    # Resolve book FK (seeded in F1.4).
    book_id_row = await conn.fetchrow(
        """
        SELECT id FROM books
        WHERE curriculum_id=$1 AND grade_id=$2 AND subject_id=$3
        ORDER BY created_at ASC LIMIT 1
        """,
        curriculum_id, grade_id, subject_id,
    )
    if book_id_row is None:
        log.warning("seed_demo_tenancy: no book found for DARS×G1×Eng — F1.4 not seeded yet; skipping")
        return
    book_id = book_id_row["id"]

    # Fast-path: skip everything if the CST already exists with the right shape.
    existing_cst = await conn.fetchrow("SELECT id FROM class_subject_teachers WHERE id=$1", cst_id)
    if existing_cst is not None:
        log.info("seed_demo_tenancy: already complete — skipping")
        return

    # 1) Organization (deferred FK to default_teacher_id; we'll set it after teacher exists)
    await conn.execute(
        """
        INSERT INTO organizations (id, name, curriculum_id, api_key_hash, api_key_prefix)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (id) DO NOTHING
        """,
        org_id, DEMO_ORG_NAME, curriculum_id,
        _hash_api_key(DEMO_ORG_API_KEY_RAW), DEMO_ORG_API_KEY_PREFIX,
    )

    # 2) Org admin
    await conn.execute(
        """
        INSERT INTO org_admins (id, org_id, email, password_hash, name)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (id) DO NOTHING
        """,
        org_admin_id, org_id, DEMO_ADMIN_EMAIL, _hash_password(DEMO_ADMIN_PASSWORD), DEMO_ADMIN_NAME,
    )

    # 3) School
    await conn.execute(
        """
        INSERT INTO schools (id, org_id, name) VALUES ($1, $2, $3)
        ON CONFLICT (id) DO NOTHING
        """,
        school_id, org_id, DEMO_SCHOOL_NAME,
    )

    # 4) Teacher
    await conn.execute(
        """
        INSERT INTO teachers (id, org_id, school_id, name, email) VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (id) DO NOTHING
        """,
        teacher_id, org_id, school_id, DEMO_TEACHER_NAME, DEMO_TEACHER_EMAIL,
    )

    # 5) Org.default_teacher_id → Aisha
    await conn.execute(
        """
        UPDATE organizations SET default_teacher_id=$1 WHERE id=$2 AND default_teacher_id IS NULL
        """,
        teacher_id, org_id,
    )

    # 6) Academic year
    await conn.execute(
        """
        INSERT INTO academic_years (id, org_id, school_id, name, start_date, end_date)
        VALUES ($1, $2, $3, $4, $5::date, $6::date)
        ON CONFLICT (id) DO NOTHING
        """,
        academic_year_id, org_id, school_id, DEMO_ACADEMIC_YEAR_NAME,
        DEMO_ACADEMIC_YEAR_START, DEMO_ACADEMIC_YEAR_END,
    )

    # 7) School class
    await conn.execute(
        """
        INSERT INTO school_classes (id, org_id, school_id, academic_year_id, grade_id, section, name)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (id) DO NOTHING
        """,
        school_class_id, org_id, school_id, academic_year_id, grade_id,
        DEMO_CLASS_SECTION, DEMO_CLASS_NAME,
    )

    # 8) ClassSubjectTeacher
    await conn.execute(
        """
        INSERT INTO class_subject_teachers (id, org_id, school_class_id, subject_id, teacher_id, book_id)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (id) DO NOTHING
        """,
        cst_id, org_id, school_class_id, subject_id, teacher_id, book_id,
    )

    # 9) cst_state at position 1
    await conn.execute(
        """
        INSERT INTO cst_state (cst_id, current_sequence_position, joined_at_position)
        VALUES ($1, 1, 1)
        ON CONFLICT (cst_id) DO NOTHING
        """,
        cst_id,
    )

    # 10) Timetable: Mon-Fri
    for dow in DEMO_TIMETABLE_DAYS:
        tt_id = seed_uuid(f"timetable:dars-demo:g1-a:eng:dow{dow}")
        await conn.execute(
            """
            INSERT INTO timetables (id, cst_id, day_of_week) VALUES ($1, $2, $3)
            ON CONFLICT (cst_id, day_of_week) DO NOTHING
            """,
            tt_id, cst_id, dow,
        )

    log.info(
        "seed_demo_tenancy: done — org='%s' api_key_prefix='%s' (raw key: see seed file), "
        "school='%s', teacher='%s', class='%s', timetable_days=%s",
        DEMO_ORG_NAME, DEMO_ORG_API_KEY_PREFIX, DEMO_SCHOOL_NAME,
        DEMO_TEACHER_NAME, DEMO_CLASS_NAME, DEMO_TIMETABLE_DAYS,
    )
