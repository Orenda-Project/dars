"""
Import NCP SLOs from taleemabad-core into dars.

Reads from the taleemabad-core PostgreSQL DB (slo_ncpslo, slo_grade, slo_subject,
slo_gradesubject) and upserts into dars' grades, subjects, slo_providers, and slos tables.

Usage:
    cd dars
    uv run python scripts/import_ncp_slos.py [--dry-run]

Required env vars (add to .env):
    CORE_STAGING_DB_HOST, CORE_STAGING_DB_PORT, CORE_STAGING_DB_NAME, CORE_STAGING_DB_USER, CORE_STAGING_DB_PASSWORD
    DATABASE_URL  (the dars Supabase connection string)
"""

import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg
import psycopg2
import psycopg2.extras

# Make dars importable
sys.path.insert(0, str(Path(__file__).parent.parent / "server" / "src"))

from dars.config import settings  # noqa: E402

# ---------------------------------------------------------------------------
# NCP provider metadata
# ---------------------------------------------------------------------------
NCP_PROVIDER = {
    "slug": "ncp",
    "name": "National Curriculum of Pakistan (NCP)",
    "issuing_body": "Federal Government of Pakistan",
    "description": (
        "SLOs defined by the National Curriculum of Pakistan (NCP), "
        "issued by the Federal Ministry of Education."
    ),
}

# Grade label → short_code + order_index (covers what's in taleemabad-core)
GRADE_META: dict[str, tuple[str, int]] = {
    "KG": ("KG", 0),
    "Grade 1": ("G1", 1),
    "Grade 2": ("G2", 2),
    "Grade 3": ("G3", 3),
    "Grade 4": ("G4", 4),
    "Grade 5": ("G5", 5),
    "Grade 6": ("G6", 6),
    "Grade 7": ("G7", 7),
    "Grade 8": ("G8", 8),
    "Grade 9": ("G9", 9),
    "Grade 10": ("G10", 10),
}

SUBJECT_SHORT_CODES: dict[str, str] = {
    "English": "Eng",
    "Urdu": "Urdu",
    "Maths": "Maths",
    "Mathematics": "Maths",
    "Science": "Science",
    "Social Studies": "SocStudies",
    "Islamic Studies": "IslamicStudies",
    "General Knowledge": "GK",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def core_conn():
    return psycopg2.connect(
        host=settings.core_staging_db_host,
        port=settings.core_staging_db_port,
        dbname=settings.core_staging_db_name,
        user=settings.core_staging_db_user,
        password=settings.core_staging_db_password,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def pg_dsn(url: str) -> str:
    """Convert asyncpg-style DSN (postgresql+asyncpg://...) to plain psycopg2 DSN."""
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )


def dars_conn():
    return psycopg2.connect(
        dsn=pg_dsn(settings.database_url),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(dry_run: bool) -> None:
    print("Connecting to taleemabad-core DB...")
    src = core_conn()
    src_cur = src.cursor()

    print("Connecting to dars DB...")
    dst = dars_conn()
    # Use autocommit so we control the transaction boundary explicitly with BEGIN.
    dst.autocommit = False
    dst_cur = dst.cursor()

    print("Starting transaction...")

    try:
        # ----------------------------------------------------------------
        # 1. Fetch grades from core
        # ----------------------------------------------------------------
        src_cur.execute(
            """
            SELECT g.id, g.label, g.short_code, g.grade_order
            FROM slo_grade g
            WHERE g.deleted_at IS NULL
            ORDER BY g.grade_order
            """
        )
        core_grades = src_cur.fetchall()
        print(f"Found {len(core_grades)} grades in core")

        # ----------------------------------------------------------------
        # 2. Fetch subjects from core
        # ----------------------------------------------------------------
        src_cur.execute(
            """
            SELECT s.id, s.label, s.short_code
            FROM slo_subject s
            WHERE s.deleted_at IS NULL
            ORDER BY s.label
            """
        )
        core_subjects = src_cur.fetchall()
        print(f"Found {len(core_subjects)} subjects in core")

        # ----------------------------------------------------------------
        # 3. Fetch NCP SLOs (active only) with grade+subject via gradesubject
        # ----------------------------------------------------------------
        src_cur.execute(
            """
            SELECT
                n.id          AS source_id,
                n.ncp_slo_id  AS code,
                n.slo_statement AS statement,
                n.domain,
                n.language_skills,
                n.sub_strand,
                g.id          AS core_grade_id,
                g.label       AS grade_label,
                g.short_code  AS grade_short_code,
                g.grade_order,
                s.id          AS core_subject_id,
                s.label       AS subject_label,
                s.short_code  AS subject_short_code
            FROM slo_ncpslo n
            JOIN slo_gradesubject gs ON gs.id = n.grade_subject_id AND gs.deleted_at IS NULL
            JOIN slo_grade g         ON g.id  = gs.grade_id         AND g.deleted_at IS NULL
            JOIN slo_subject s       ON s.id  = gs.subject_id       AND s.deleted_at IS NULL
            WHERE n.is_active = true
            ORDER BY g.grade_order, s.label, n.ncp_slo_id
            """
        )
        ncp_slos = src_cur.fetchall()
        print(f"Found {len(ncp_slos)} active NCP SLOs in core")

        if not ncp_slos:
            print("No NCP SLOs found — check CORE_STAGING_DB_* connection vars and that data exists.")
            return

        if dry_run:
            print("\n[DRY RUN] Would import:")
            grades_seen = {r["grade_label"] for r in ncp_slos}
            subjects_seen = {r["subject_label"] for r in ncp_slos}
            print(f"  Grades: {sorted(grades_seen)}")
            print(f"  Subjects: {sorted(subjects_seen)}")
            print(f"  SLOs: {len(ncp_slos)}")
            return

        # ----------------------------------------------------------------
        # 4. Upsert grades into dars
        #    Match by short_code; fall back to deriving from label.
        # ----------------------------------------------------------------
        grade_map: dict[int, str] = {}  # core_grade_id → dars grade uuid

        unique_grades = {r["core_grade_id"]: r for r in ncp_slos}.values()
        for g in unique_grades:
            label = g["grade_label"]
            short_code = g["grade_short_code"] or GRADE_META.get(label, (label[:10], 99))[0]
            order_index = g["grade_order"] or GRADE_META.get(label, (None, 99))[1]

            dst_cur.execute(
                """
                INSERT INTO grades (label, short_code, order_index)
                VALUES (%s, %s, %s)
                ON CONFLICT (short_code) DO UPDATE
                    SET label = EXCLUDED.label,
                        order_index = EXCLUDED.order_index
                RETURNING id
                """,
                (label, short_code, order_index),
            )
            row = dst_cur.fetchone()
            grade_map[g["core_grade_id"]] = row["id"]

        print(f"Upserted {len(grade_map)} grades")

        # ----------------------------------------------------------------
        # 5. Upsert subjects into dars
        # ----------------------------------------------------------------
        subject_map: dict[int, str] = {}  # core_subject_id → dars subject uuid

        unique_subjects = {r["core_subject_id"]: r for r in ncp_slos}.values()
        for s in unique_subjects:
            label = s["subject_label"]
            short_code = SUBJECT_SHORT_CODES.get(label, s["subject_short_code"] or label[:20])

            dst_cur.execute(
                """
                INSERT INTO subjects (label, short_code)
                VALUES (%s, %s)
                ON CONFLICT (short_code) DO UPDATE
                    SET label = EXCLUDED.label
                RETURNING id
                """,
                (label, short_code),
            )
            row = dst_cur.fetchone()
            subject_map[s["core_subject_id"]] = row["id"]

        print(f"Upserted {len(subject_map)} subjects")

        # ----------------------------------------------------------------
        # 6. Upsert NCP provider
        # ----------------------------------------------------------------
        dst_cur.execute(
            """
            INSERT INTO slo_providers (slug, name, issuing_body, description)
            VALUES (%(slug)s, %(name)s, %(issuing_body)s, %(description)s)
            ON CONFLICT (slug) DO UPDATE
                SET name         = EXCLUDED.name,
                    issuing_body = EXCLUDED.issuing_body,
                    description  = EXCLUDED.description
            RETURNING id
            """,
            NCP_PROVIDER,
        )
        provider_id = dst_cur.fetchone()["id"]
        print(f"Upserted NCP provider (id={provider_id})")

        # ----------------------------------------------------------------
        # 7. Upsert SLOs (batched)
        # ----------------------------------------------------------------
        total_slos = len(ncp_slos)
        print(f"Upserting {total_slos} SLOs in batches of 500...")

        BATCH_SIZE = 500
        SLO_SQL = """
            INSERT INTO slos
                (provider_id, code, statement, grade_id, subject_id,
                 domain, language_skills, sub_strand, source_id, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true)
            ON CONFLICT (provider_id, code, grade_id, subject_id) DO UPDATE
                SET statement       = EXCLUDED.statement,
                    domain          = EXCLUDED.domain,
                    language_skills = EXCLUDED.language_skills,
                    sub_strand      = EXCLUDED.sub_strand,
                    source_id       = EXCLUDED.source_id,
                    is_active       = true
        """

        inserted = 0
        skipped = 0
        batch: list[tuple] = []

        def flush_batch(cur, rows: list[tuple]) -> None:
            if rows:
                psycopg2.extras.execute_batch(cur, SLO_SQL, rows, page_size=BATCH_SIZE)

        for row in ncp_slos:
            grade_uuid = grade_map.get(row["core_grade_id"])
            subject_uuid = subject_map.get(row["core_subject_id"])
            if not grade_uuid or not subject_uuid:
                skipped += 1
                continue

            batch.append((
                provider_id,
                row["code"],
                row["statement"],
                grade_uuid,
                subject_uuid,
                row["domain"],
                row["language_skills"],   # psycopg2 passes list as PG array
                row["sub_strand"],
                row["source_id"],
            ))
            inserted += 1

            if len(batch) >= BATCH_SIZE:
                flush_batch(dst_cur, batch)
                batch.clear()
                if inserted % 100 == 0:
                    print(f"  [{inserted}/{total_slos}] SLOs upserted...")

        # Flush any remaining rows
        flush_batch(dst_cur, batch)

        # Final progress line if last batch didn't land on a 100-boundary
        if inserted % 100 != 0 or inserted == 0:
            print(f"  [{inserted}/{total_slos}] SLOs upserted...")

        dst.commit()
        print(f"Done. Upserted {inserted} SLOs ({skipped} skipped due to missing grade/subject).")

    except Exception:
        dst.rollback()
        raise
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import NCP SLOs from taleemabad-core into dars")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be imported without writing")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
