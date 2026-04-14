"""
Seed sample curriculum data into the dars DB for development and testing.

Seeds:
  - 10 NCP G1 English SLOs (queried from DB) and one sub-SLO per SLO
  - A sample book (id=9999), chapter (id=99991), and 5 topics
  - topic→sub-SLO mappings (round-robin, 2 per topic)
  - A curriculum linking everything together

Usage:
    cd dars
    uv run --project server python scripts/seed_sample_curriculum.py
    uv run --project server python scripts/seed_sample_curriculum.py --teardown
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent.parent / "server" / "src"))

from dars.config import settings  # noqa: E402

CURRICULUM_NAME = "Grade 1 English NCP Sample 2025-26"

BOOK = {
    "id": 9999,
    "title": "English Grade 1 (Sample)",
    "grade": 1,
    "subject": "English",
    "curriculum": "NCP",
    "total_chapters": 1,
    "synced_at": datetime.utcnow(),
}

CHAPTER = {
    "id": 99991,
    "book_id": 9999,
    "chapter_number": 1,
    "title": "My Family and Me",
    "start_page": 1,
    "end_page": 20,
}

TOPICS = [
    "Naming family members",
    "Describing family roles",
    "Reading family-related words",
    "Writing simple sentences about family",
    "Listening and responding to family stories",
]


def pg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )


def dars_conn():
    return psycopg2.connect(
        dsn=pg_dsn(settings.database_url),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def seed(conn) -> None:
    cur = conn.cursor()

    # ------------------------------------------------------------------
    # 1. Look up grade, subject, provider UUIDs
    # ------------------------------------------------------------------
    cur.execute("SELECT id FROM grades WHERE short_code = 'G1'")
    row = cur.fetchone()
    if not row:
        print("ERROR: grade G1 not found in grades table. Run import_ncp_slos.py first.")
        sys.exit(1)
    grade_id = row["id"]
    print(f"Grade G1 id: {grade_id}")

    cur.execute("SELECT id FROM subjects WHERE short_code = 'Eng'")
    row = cur.fetchone()
    if not row:
        print("ERROR: subject Eng not found in subjects table. Run import_ncp_slos.py first.")
        sys.exit(1)
    subject_id = row["id"]
    print(f"Subject Eng id: {subject_id}")

    cur.execute("SELECT id FROM slo_providers WHERE slug = 'ncp'")
    row = cur.fetchone()
    if not row:
        print("ERROR: provider ncp not found in slo_providers. Run import_ncp_slos.py first.")
        sys.exit(1)
    provider_id = row["id"]
    print(f"Provider ncp id: {provider_id}")

    # ------------------------------------------------------------------
    # 2. Pick 10 NCP G1 English SLOs
    # ------------------------------------------------------------------
    cur.execute(
        """
        SELECT s.id, s.code, s.statement
        FROM slos s
        JOIN slo_providers p ON p.id = s.provider_id
        JOIN grades g         ON g.id = s.grade_id
        JOIN subjects sub     ON sub.id = s.subject_id
        WHERE p.slug = 'ncp'
          AND g.short_code = 'G1'
          AND sub.short_code = 'Eng'
        ORDER BY s.code
        LIMIT 10
        """
    )
    slos = cur.fetchall()
    if not slos:
        print("ERROR: no NCP G1 English SLOs found. Run import_ncp_slos.py first.")
        sys.exit(1)
    print(f"Found {len(slos)} NCP G1 English SLOs (using first 10)")

    # ------------------------------------------------------------------
    # 3. Insert one sub-SLO per SLO
    # ------------------------------------------------------------------
    sub_slo_ids = []
    for slo in slos:
        sub_code = f"{slo['code']}.1"
        cur.execute(
            """
            INSERT INTO sub_slos (slo_id, code, statement, source_id)
            VALUES (%s, %s, %s, NULL)
            ON CONFLICT (slo_id, code) DO NOTHING
            RETURNING id
            """,
            (slo["id"], sub_code, slo["statement"]),
        )
        result = cur.fetchone()
        if result:
            sub_slo_ids.append(result["id"])
            print(f"  Inserted sub-SLO {sub_code}")
        else:
            # Already existed — fetch its id
            cur.execute(
                "SELECT id FROM sub_slos WHERE slo_id = %s AND code = %s",
                (slo["id"], sub_code),
            )
            existing = cur.fetchone()
            sub_slo_ids.append(existing["id"])
            print(f"  Sub-SLO {sub_code} already exists, using existing id")

    # ------------------------------------------------------------------
    # 4. Insert sample book
    # ------------------------------------------------------------------
    cur.execute(
        """
        INSERT INTO books (id, title, grade, subject, curriculum, total_chapters, synced_at)
        VALUES (%(id)s, %(title)s, %(grade)s, %(subject)s, %(curriculum)s, %(total_chapters)s, %(synced_at)s)
        ON CONFLICT (id) DO NOTHING
        """,
        BOOK,
    )
    print(f"Inserted book id={BOOK['id']}: {BOOK['title']}")

    # ------------------------------------------------------------------
    # 5. Insert chapter
    # ------------------------------------------------------------------
    cur.execute(
        """
        INSERT INTO book_chapters (id, book_id, chapter_number, title, start_page, end_page)
        VALUES (%(id)s, %(book_id)s, %(chapter_number)s, %(title)s, %(start_page)s, %(end_page)s)
        ON CONFLICT (id) DO NOTHING
        """,
        CHAPTER,
    )
    print(f"Inserted chapter id={CHAPTER['id']}: {CHAPTER['title']}")

    # ------------------------------------------------------------------
    # 6. Insert 5 topics
    # ------------------------------------------------------------------
    topic_ids = []
    for seq, title in enumerate(TOPICS, start=1):
        cur.execute(
            """
            INSERT INTO topics (chapter_id, title, sequence, source_id)
            VALUES (%s, %s, %s, NULL)
            ON CONFLICT (chapter_id, sequence) DO NOTHING
            RETURNING id
            """,
            (CHAPTER["id"], title, seq),
        )
        result = cur.fetchone()
        if result:
            topic_ids.append(result["id"])
            print(f"  Inserted topic {seq}: {title}")
        else:
            cur.execute(
                "SELECT id FROM topics WHERE chapter_id = %s AND sequence = %s",
                (CHAPTER["id"], seq),
            )
            existing = cur.fetchone()
            topic_ids.append(existing["id"])
            print(f"  Topic {seq} already exists, using existing id")

    # ------------------------------------------------------------------
    # 7. Map each topic to 2 sub-SLOs (round-robin)
    # ------------------------------------------------------------------
    n_sub = len(sub_slo_ids)
    for i, topic_id in enumerate(topic_ids):
        for j in range(2):
            sub_slo_id = sub_slo_ids[(i * 2 + j) % n_sub]
            cur.execute(
                """
                INSERT INTO topic_sub_slos (topic_id, sub_slo_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (topic_id, sub_slo_id),
            )
        print(f"  Mapped topic {i+1} to 2 sub-SLOs (indices {(i*2) % n_sub}, {(i*2+1) % n_sub})")

    # ------------------------------------------------------------------
    # 8. Insert curriculum
    # ------------------------------------------------------------------
    cur.execute(
        """
        INSERT INTO curriculums (name, grade_id, subject_id, book_id, provider_id, academic_year)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        (CURRICULUM_NAME, grade_id, subject_id, BOOK["id"], provider_id, "2025-2026"),
    )
    result = cur.fetchone()
    if result:
        curriculum_id = result["id"]
        print(f"Inserted curriculum: {CURRICULUM_NAME} (id={curriculum_id})")
    else:
        cur.execute("SELECT id FROM curriculums WHERE name = %s", (CURRICULUM_NAME,))
        curriculum_id = cur.fetchone()["id"]
        print(f"Curriculum already exists (id={curriculum_id})")

    # ------------------------------------------------------------------
    # 9. Insert curriculum_topics (sequence 1-5)
    # ------------------------------------------------------------------
    for seq, topic_id in enumerate(topic_ids, start=1):
        cur.execute(
            """
            INSERT INTO curriculum_topics (curriculum_id, topic_id, sequence)
            VALUES (%s, %s, %s)
            ON CONFLICT (curriculum_id, sequence) DO NOTHING
            """,
            (curriculum_id, topic_id, seq),
        )
        print(f"  Linked curriculum topic {seq}")

    conn.commit()
    print("\nSeed complete.")


def teardown(conn) -> None:
    cur = conn.cursor()

    # Find the 10 NCP G1 English SLO ids (same query as seed)
    cur.execute(
        """
        SELECT s.id, s.code
        FROM slos s
        JOIN slo_providers p ON p.id = s.provider_id
        JOIN grades g         ON g.id = s.grade_id
        JOIN subjects sub     ON sub.id = s.subject_id
        WHERE p.slug = 'ncp'
          AND g.short_code = 'G1'
          AND sub.short_code = 'Eng'
        ORDER BY s.code
        LIMIT 10
        """
    )
    slos = cur.fetchall()
    slo_ids = [r["id"] for r in slos]

    # 1. curriculum_topics
    cur.execute(
        """
        DELETE FROM curriculum_topics
        WHERE curriculum_id IN (
            SELECT id FROM curriculums WHERE name = %s
        )
        """,
        (CURRICULUM_NAME,),
    )
    print(f"Deleted curriculum_topics for '{CURRICULUM_NAME}'")

    # 2. curriculums
    cur.execute("DELETE FROM curriculums WHERE name = %s", (CURRICULUM_NAME,))
    print(f"Deleted curriculum '{CURRICULUM_NAME}'")

    # 3. topic_sub_slos for topics under chapter 99991
    cur.execute(
        """
        DELETE FROM topic_sub_slos
        WHERE topic_id IN (
            SELECT id FROM topics WHERE chapter_id = %s
        )
        """,
        (CHAPTER["id"],),
    )
    print(f"Deleted topic_sub_slos for chapter_id={CHAPTER['id']}")

    # 4. topics
    cur.execute("DELETE FROM topics WHERE chapter_id = %s", (CHAPTER["id"],))
    print(f"Deleted topics where chapter_id={CHAPTER['id']}")

    # 5. book_chapters
    cur.execute("DELETE FROM book_chapters WHERE id = %s", (CHAPTER["id"],))
    print(f"Deleted book_chapter id={CHAPTER['id']}")

    # 6. books
    cur.execute("DELETE FROM books WHERE id = %s", (BOOK["id"],))
    print(f"Deleted book id={BOOK['id']}")

    # 7. sub_slos
    if slo_ids:
        cur.execute(
            """
            DELETE FROM sub_slos
            WHERE source_id IS NULL
              AND code LIKE %s
              AND slo_id = ANY(%s)
            """,
            ("%.1", slo_ids),
        )
        print(f"Deleted sub_slos for {len(slo_ids)} NCP G1 Eng SLOs")
    else:
        print("No NCP G1 Eng SLOs found — skipping sub_slos teardown")

    conn.commit()
    print("\nTeardown complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed or teardown sample curriculum data in the dars DB"
    )
    parser.add_argument(
        "--teardown",
        action="store_true",
        help="Delete all seeded sample data instead of inserting it",
    )
    args = parser.parse_args()

    print("Connecting to dars DB...")
    conn = dars_conn()
    conn.autocommit = False

    try:
        if args.teardown:
            print("Running teardown...")
            teardown(conn)
        else:
            print("Running seed...")
            seed(conn)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
