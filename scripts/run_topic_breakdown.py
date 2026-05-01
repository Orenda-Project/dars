"""
Run AI topic breakdown for all book chapters in Dars.

Calls POST /api/v1/admin/chapters/{chapter_id}/breakdown for each chapter
that does not yet have topics. Uses the Dars HTTP API so the AI logic
stays in one place (breakdown_service.py).

Usage:
    uv run python scripts/run_topic_breakdown.py \
        --dars-url  http://localhost:8000 \
        --admin-secret <ADMIN_SECRET> \
        [--book-id <uuid>]          # limit to one book
        [--chapter-id <uuid>]       # limit to one chapter
        [--force]                   # re-run even if topics already exist
        [--dry-run]                 # print what would run, no API calls
"""

import argparse
import sys
import time
import requests

def client_headers(api_key: str) -> dict:
    return {"X-API-Key": api_key}


def admin_headers(secret: str) -> dict:
    return {"X-Admin-Secret": secret}


def get_books(base: str, api_key: str, book_id: str | None) -> list[dict]:
    if book_id:
        return [{"id": book_id, "title": "(specified)", "curriculum": "", "grade": "", "subject": ""}]
    r = requests.get(
        f"{base}/api/v1/books",
        headers=client_headers(api_key),
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("items", [])


def get_chapters(base: str, api_key: str, book_id: str) -> list[dict]:
    r = requests.get(
        f"{base}/api/v1/books/{book_id}/chapters",
        headers=client_headers(api_key),
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("items", [])


def has_topics(base: str, api_key: str, book_id: str, chapter_id: str) -> bool:
    r = requests.get(
        f"{base}/api/v1/books/{book_id}/chapters/{chapter_id}/topics",
        headers=client_headers(api_key),
        timeout=30,
    )
    if not r.ok:
        return False
    return r.json().get("total", 0) > 0


def run_breakdown(base: str, secret: str, chapter_id: str) -> dict:
    r = requests.post(
        f"{base}/admin/chapters/{chapter_id}/breakdown",
        headers={"X-Admin-Secret": secret},
        timeout=300,  # AI call can take a while
    )
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="Run AI topic breakdown for Dars chapters")
    parser.add_argument("--dars-url", default="http://localhost:8000", help="Dars API base URL")
    parser.add_argument("--admin-secret", required=True, help="ADMIN_SECRET value")
    parser.add_argument("--api-key", required=True, help="Client API key (for listing books/chapters)")
    parser.add_argument("--book-id", help="Limit to a single book UUID")
    parser.add_argument("--chapter-id", help="Limit to a single chapter UUID (requires --book-id)")
    parser.add_argument("--force", action="store_true", help="Re-run even if topics already exist")
    parser.add_argument("--dry-run", action="store_true", help="Print what would run, no API calls")
    args = parser.parse_args()

    base = args.dars_url.rstrip("/")
    print(f"Dars: {base}")

    if args.chapter_id:
        if not args.book_id:
            print("ERROR: --book-id is required when --chapter-id is specified", file=sys.stderr)
            sys.exit(1)
        chapters_to_process = [(args.book_id, args.chapter_id, "(specified)")]
    else:
        books = get_books(base, args.api_key, args.book_id)
        print(f"Found {len(books)} book(s)")

        chapters_to_process = []
        for book in books:
            bid = book["id"]
            label = f"[{book.get('curriculum','')} G{book.get('grade','')} {book.get('subject','')}] {book.get('title','')}"
            try:
                chapters = get_chapters(base, args.api_key, bid)
            except Exception as e:
                print(f"  SKIP book {bid} — could not fetch chapters: {e}")
                continue
            for ch in chapters:
                chapters_to_process.append((bid, ch["id"], f"{label} / Ch{ch['chapter_number']} {ch['title']}"))

    print(f"Total chapters: {len(chapters_to_process)}")

    ok = skipped = failed = 0

    for book_id, chapter_id, label in chapters_to_process:
        if not args.force:
            try:
                if has_topics(base, args.api_key, book_id, chapter_id):
                    print(f"  SKIP  {label}")
                    skipped += 1
                    continue
            except Exception:
                pass

        if args.dry_run:
            print(f"  DRY   {label}")
            ok += 1
            continue

        print(f"  RUN   {label} ... ", end="", flush=True)
        try:
            result = run_breakdown(base, args.admin_secret, chapter_id)
            print(f"topics={result.get('topics_count',0)} slots={result.get('slots_count',0)}")
            ok += 1
        except requests.HTTPError as e:
            print(f"FAILED ({e.response.status_code}: {e.response.text[:200]})")
            failed += 1
        except Exception as e:
            print(f"FAILED ({e})")
            failed += 1

        # Brief pause between chapters to avoid overwhelming the AI API
        time.sleep(1)

    print(f"\nDone. ok={ok} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
