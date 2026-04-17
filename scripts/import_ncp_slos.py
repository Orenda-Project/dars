"""
Import NCP SLOs from taleemabad-core into dars.

SLOs are tied to a specific book (not grade/subject). This script imports
NCP SLOs from taleemabad-core and links them to the correct book in dars.

It joins slo_ncpslo → slo_gradesubject → book_library_book to find the book
each SLO belongs to. Only SLOs for books that already exist in dars (synced
via POST /api/admin/books/sync) are imported.

Usage:
    cd dars
    uv run python scripts/import_ncp_slos.py [--dry-run]

Required env vars (add to .env):
    CORE_STAGING_DB_HOST, CORE_STAGING_DB_PORT, CORE_STAGING_DB_NAME,
    CORE_STAGING_DB_USER, CORE_STAGING_DB_PASSWORD
    DATABASE_URL  (the dars Supabase connection string)
"""

import argparse
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent.parent / "server" / "src"))

from dars.config import settings  # noqa: E402

NCP_PROVIDER = {
    "slug": "ncp",
    "name": "National Curriculum of Pakistan (NCP)",
    "issuing_body": "Federal Government of Pakistan",
    "description": (
        "SLOs defined by the National Curriculum of Pakistan (NCP), "
        "issued by the Federal Ministry of Education."
    ),
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
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )


def dars_conn():
    return psycopg2.connect(
        dsn=pg_dsn(settings.database_url),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def run(dry_run: bool) -> None:
    print("Connecting to taleemabad-core DB...")
    src = core_conn()
    src_cur = src.cursor()

    print("Connecting to dars DB...")
    dst = dars_conn()
    dst.autocommit = False
    dst_cur = dst.cursor()

    try:
        # ----------------------------------------------------------------
        # 1. Fetch NCP SLOs joined to books from core
        #    book_library_book is the source of book IDs (synced into dars)
        # ----------------------------------------------------------------
        src_cur.execute(
            """
            SELECT
                n.id            AS source_id,
                n.ncp_slo_id    AS code,
                n.slo_statement AS statement,
                n.domain,
                n.language_skills,
                n.sub_strand,
                g.label         AS grade_label,
                g.short_code    AS grade_short_code,
                g.grade_order,
                s.label         AS subject_label,
                s.short_code    AS subject_short_code,
                b.id            AS book_id
            FROM slo_ncpslo n
            JOIN slo_gradesubject gs ON gs.id = n.grade_subject_id AND gs.deleted_at IS NULL
            JOIN slo_grade g         ON g.id  = gs.grade_id         AND g.deleted_at IS NULL
            JOIN slo_subject s       ON s.id  = gs.subject_id       AND s.deleted_at IS NULL
            JOIN book_library_book b ON b.grade_subject_id = gs.id  AND b.is_active = true
            WHERE n.is_active = true
            ORDER BY b.id, g.grade_order, s.label, n.ncp_slo_id
            """
        )
        ncp_slos = src_cur.fetchall()
        print(f"Found {len(ncp_slos)} active NCP SLOs with book links in core")

        if not ncp_slos:
            print("No NCP SLOs with book links found — check that books exist in core and are active.")
            return

        # ----------------------------------------------------------------
        # 2. Filter to books that exist in dars (already synced)
        # ----------------------------------------------------------------
        dst_cur.execute("SELECT id FROM books")
        dars_book_ids = {row["id"] for row in dst_cur.fetchall()}

        filtered_slos = [r for r in ncp_slos if r["book_id"] in dars_book_ids]
        skipped_book = len(ncp_slos) - len(filtered_slos)
        print(f"  {len(filtered_slos)} SLOs match books in dars ({skipped_book} skipped — book not synced yet)")

        if dry_run:
            books_seen = {r["book_id"] for r in filtered_slos}
            grades_seen = {r["grade_label"] for r in filtered_slos}
            subjects_seen = {r["subject_label"] for r in filtered_slos}
            print(f"\n[DRY RUN] Would import:")
            print(f"  Books: {sorted(books_seen)}")
            print(f"  Grades: {sorted(grades_seen)}")
            print(f"  Subjects: {sorted(subjects_seen)}")
            print(f"  SLOs: {len(filtered_slos)}")
            return

        if not filtered_slos:
            print("Nothing to import. Run POST /api/admin/books/sync first.")
            return

        # ----------------------------------------------------------------
        # 3. Upsert grades (catalog — for UI use)
        # ----------------------------------------------------------------
        unique_grades = {r["grade_label"]: r for r in filtered_slos}.values()
        for g in unique_grades:
            label = g["grade_label"]
            short_code = g["grade_short_code"] or GRADE_META.get(label, (label[:10], 99))[0]
            order_index = g["grade_order"] or GRADE_META.get(label, (None, 99))[1]
            dst_cur.execute(
                """
                INSERT INTO grades (label, short_code, order_index)
                VALUES (%s, %s, %s)
                ON CONFLICT (short_code) DO UPDATE
                    SET label = EXCLUDED.label, order_index = EXCLUDED.order_index
                """,
                (label, short_code, order_index),
            )
        print(f"Upserted grades catalog")

        # ----------------------------------------------------------------
        # 4. Upsert subjects (catalog — for UI use)
        # ----------------------------------------------------------------
        unique_subjects = {r["subject_label"]: r for r in filtered_slos}.values()
        for s in unique_subjects:
            label = s["subject_label"]
            short_code = SUBJECT_SHORT_CODES.get(label, s["subject_short_code"] or label[:20])
            dst_cur.execute(
                """
                INSERT INTO subjects (label, short_code)
                VALUES (%s, %s)
                ON CONFLICT (short_code) DO UPDATE SET label = EXCLUDED.label
                """,
                (label, short_code),
            )
        print(f"Upserted subjects catalog")

        # ----------------------------------------------------------------
        # 5. Upsert NCP provider
        # ----------------------------------------------------------------
        dst_cur.execute(
            """
            INSERT INTO slo_providers (slug, name, issuing_body, description)
            VALUES (%(slug)s, %(name)s, %(issuing_body)s, %(description)s)
            ON CONFLICT (slug) DO UPDATE
                SET name = EXCLUDED.name, issuing_body = EXCLUDED.issuing_body,
                    description = EXCLUDED.description
            RETURNING id
            """,
            NCP_PROVIDER,
        )
        provider_id = dst_cur.fetchone()["id"]
        print(f"Upserted NCP provider (id={provider_id})")

        # ----------------------------------------------------------------
        # 6. Upsert SLOs with book_id (batched)
        # ----------------------------------------------------------------
        total = len(filtered_slos)
        print(f"Upserting {total} SLOs...")

        BATCH_SIZE = 500
        SLO_SQL = """
            INSERT INTO slos
                (provider_id, book_id, code, statement,
                 domain, language_skills, sub_strand, source_id, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true)
            ON CONFLICT (provider_id, book_id, code) DO UPDATE
                SET statement       = EXCLUDED.statement,
                    domain          = EXCLUDED.domain,
                    language_skills = EXCLUDED.language_skills,
                    sub_strand      = EXCLUDED.sub_strand,
                    source_id       = EXCLUDED.source_id,
                    is_active       = true
        """

        batch: list[tuple] = []

        def flush(cur, rows):
            if rows:
                psycopg2.extras.execute_batch(cur, SLO_SQL, rows, page_size=BATCH_SIZE)

        for i, row in enumerate(filtered_slos, 1):
            batch.append((
                provider_id,
                row["book_id"],
                row["code"],
                row["statement"],
                row["domain"],
                row["language_skills"],
                row["sub_strand"],
                row["source_id"],
            ))
            if len(batch) >= BATCH_SIZE:
                flush(dst_cur, batch)
                batch.clear()
                print(f"  [{i}/{total}] SLOs upserted...")

        flush(dst_cur, batch)
        print(f"  [{total}/{total}] Done.")

        dst.commit()
        print(f"\nImport complete. {total} SLOs upserted.")

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
