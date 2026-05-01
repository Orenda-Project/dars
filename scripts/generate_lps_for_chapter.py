"""
Generate lesson plans for all slots in a chapter by calling UG LP with topic_text as page_content.
Persists each LP into the Dars lesson_plans table and links it back to the slot.

Usage:
    uv run --with psycopg2-binary --with requests python scripts/generate_lps_for_chapter.py \
        --dars-db postgresql://... \
        --lp-url https://lp-assistant.taleemabad.com \
        --lp-key <api_key> \
        --client-id <dars_client_uuid> \
        --chapter-id <uuid> \
        [--force]   # re-generate even if slot already has an LP
        [--dry-run]
"""

import argparse
import json
import sys
import time
import uuid

import psycopg2
import psycopg2.extras
import requests


def get_chapter_slots(conn, chapter_id: str) -> list[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT
            ls.id            AS slot_id,
            ls.day_number,
            ls.topic_subtopic,
            ls.lesson_plan_id,
            t.id             AS topic_id,
            t.title          AS topic_title,
            t.page_number,
            t.topic_text,
            bc.title         AS chapter_title,
            b.grade,
            b.subject,
            b.curriculum
        FROM lesson_slots ls
        JOIN topics t ON t.id = ls.topic_id
        JOIN book_chapters bc ON bc.id = t.chapter_id
        JOIN books b ON b.id = bc.book_id
        WHERE t.chapter_id = %s
        ORDER BY ls.day_number
    """, (chapter_id,))
    return cur.fetchall()


def generate_lp(lp_url: str, lp_key: str, slot: dict) -> dict:
    # Values in the DB are already canonical after the lookup-table migration;
    # pass them through directly — no ICT-specific remapping needed.
    payload = {
        "grade": slot["grade"],
        "curriculum": slot["curriculum"],
        "subject": slot["subject"],
        "topic": slot["topic_subtopic"],
        "page_content": slot["topic_text"] or "",
    }

    r = requests.post(
        f"{lp_url}/api/generate-lp",
        headers={"api-key": lp_key, "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def persist_lp(conn, client_id: str, slot: dict, result: dict) -> str:
    """Insert LP into lesson_plans, update slot.lesson_plan_id, return lp_id."""
    lp_id = str(uuid.uuid4())
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO lesson_plans
            (id, client_id, curriculum, grade, subject, topic, page_number, status,
             content, content_bilingual, tags, metadata_, created_at, updated_at)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, 'READY', %s, %s, %s, %s, NOW(), NOW())
    """, (
        lp_id,
        client_id,
        slot["curriculum"],
        str(slot["grade"]),
        slot["subject"],
        slot["topic_subtopic"],
        slot["page_number"],
        result.get("lesson_plan") or "",
        result.get("lesson_plan_bilingual") or "",
        json.dumps(result.get("tags") or {}),
        json.dumps(result.get("metadata") or {}),
    ))
    cur.execute("""
        UPDATE lesson_slots SET lesson_plan_id = %s WHERE id = %s
    """, (lp_id, str(slot["slot_id"])))
    conn.commit()
    return lp_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dars-db", required=True)
    parser.add_argument("--lp-url", required=True)
    parser.add_argument("--lp-key", required=True)
    parser.add_argument("--client-id", required=True, help="Dars client UUID to own the LPs")
    parser.add_argument("--chapter-id", required=True)
    parser.add_argument("--force", action="store_true", help="Re-generate even if LP already exists")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N slots")
    args = parser.parse_args()

    conn = psycopg2.connect(args.dars_db, cursor_factory=psycopg2.extras.RealDictCursor)
    slots = get_chapter_slots(conn, args.chapter_id)
    if args.limit:
        slots = slots[: args.limit]

    if not slots:
        print("No slots found for this chapter.")
        sys.exit(1)

    print(f"Found {len(slots)} slots for chapter")
    ok = skipped = failed = 0

    for slot in slots:
        label = f"Day {slot['day_number']}: {slot['topic_subtopic']}"

        if not slot["topic_text"]:
            print(f"  SKIP  {label} — no topic_text")
            skipped += 1
            continue

        if slot["lesson_plan_id"] and not args.force:
            print(f"  SKIP  {label} — LP already exists")
            skipped += 1
            continue

        if args.dry_run:
            print(f"  DRY   {label}")
            ok += 1
            continue

        print(f"  GEN   {label} ... ", end="", flush=True)
        try:
            result = generate_lp(args.lp_url, args.lp_key, slot)
            lp_id = persist_lp(conn, args.client_id, slot, result)
            print(f"OK lp_id={lp_id}")
            ok += 1
        except requests.HTTPError as e:
            print(f"FAILED ({e.response.status_code}: {e.response.text[:200]})")
            failed += 1
        except Exception as e:
            print(f"FAILED ({e})")
            failed += 1

        time.sleep(0.5)

    print(f"\nDone. ok={ok} skipped={skipped} failed={failed}")
    conn.close()


if __name__ == "__main__":
    main()
