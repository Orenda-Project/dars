"""
F1.4 — Book + chapters + topics + SLO/sub-SLO mappings.

🧊 SEED FREEZE: Once this lands, chapter numbers (1..10) and topic
numbers within each chapter are frozen. Phase 2+ code references topics
by (book, chapter_number, topic_number). Renaming or renumbering requires
explicit user approval per REBUILD.md Step 9.

Authored content lives in dars_english_g1_book/chapter_01.py .. chapter_10.py.
Each chapter module exports a CHAPTER dict with: chapter_number, title,
start_page, end_page, slos (codes mapping to book_chapter_slos), and
topics (each with title, sub_slos, and text).

Topic text doubles as page_content sent to LP Assistant for that topic.
Chapter text (chapter_text JSONB) is materialized as the concatenation
of all topic texts, each wrapped in {pdf_page_no, text} per the OCR
storage format defined in 02-data-model.md.
"""
import logging

import asyncpg

from dars.seeds.dars_english_g1_book import (
    chapter_01,
    chapter_02,
    chapter_03,
    chapter_04,
    chapter_05,
    chapter_06,
    chapter_07,
    chapter_08,
    chapter_09,
    chapter_10,
)
from dars.seeds.lookups import seed_uuid

log = logging.getLogger("v2_seed.book_dars_english_g1")


ALL_CHAPTERS = [
    chapter_01.CHAPTER,
    chapter_02.CHAPTER,
    chapter_03.CHAPTER,
    chapter_04.CHAPTER,
    chapter_05.CHAPTER,
    chapter_06.CHAPTER,
    chapter_07.CHAPTER,
    chapter_08.CHAPTER,
    chapter_09.CHAPTER,
    chapter_10.CHAPTER,
]


BOOK = {
    "title": "Dars English Grade 1 Reader",
    "publisher": "Dars Press",
    "edition": "1st Edition",
    "published_year": 2026,
    "total_chapters": 10,
}


def _build_book_text(chapters: list[dict]) -> list[dict]:
    """
    Compose the book_text JSONB payload.

    Each topic's text becomes one OCR page entry. pdf_page_no is computed
    as the topic's chapter's start_page plus the topic index. This isn't
    exact pagination but is consistent and indexable by chapter.
    """
    pages: list[dict] = []
    for chapter in chapters:
        for i, topic in enumerate(chapter["topics"]):
            pdf_page_no = chapter["start_page"] + i
            pages.append({"pdf_page_no": pdf_page_no, "text": topic["text"]})
    return pages


def _build_chapter_text(chapter: dict) -> list[dict]:
    """Same shape but scoped to one chapter."""
    pages: list[dict] = []
    for i, topic in enumerate(chapter["topics"]):
        pdf_page_no = chapter["start_page"] + i
        pages.append({"pdf_page_no": pdf_page_no, "text": topic["text"]})
    return pages


async def seed_dars_english_g1_book(conn: asyncpg.Connection) -> None:
    import json

    log.info("seed_dars_english_g1_book: starting")

    curriculum_id = seed_uuid("curriculum:DARS")
    grade_id = seed_uuid("grade:1")
    subject_id = seed_uuid("subject:Eng")

    # Fast-path skip if already complete.
    existing_book = await conn.fetchrow(
        """
        SELECT id FROM books
        WHERE curriculum_id=$1 AND grade_id=$2 AND subject_id=$3 AND title=$4
        """,
        curriculum_id, grade_id, subject_id, BOOK["title"],
    )
    if existing_book is not None:
        existing_chapter_count = await conn.fetchval(
            "SELECT COUNT(*) FROM book_chapters WHERE book_id=$1",
            existing_book["id"],
        )
        if existing_chapter_count == len(ALL_CHAPTERS):
            existing_topic_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM topics t
                JOIN book_chapters bc ON bc.id = t.book_chapter_id
                WHERE bc.book_id=$1
                """,
                existing_book["id"],
            )
            expected_topic_count = sum(len(c["topics"]) for c in ALL_CHAPTERS)
            if existing_topic_count == expected_topic_count:
                log.info(
                    "seed_dars_english_g1_book: already complete (chapters=%d, topics=%d) — skipping",
                    existing_chapter_count, existing_topic_count,
                )
                return

    # 1) Book row
    book_id = seed_uuid("book:DARS:1:Eng:dars-eng-g1-reader")
    book_text_json = json.dumps(_build_book_text(ALL_CHAPTERS))
    await conn.execute(
        """
        INSERT INTO books (id, curriculum_id, grade_id, subject_id, title, publisher, edition,
                           published_year, total_chapters, book_text)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
        ON CONFLICT DO NOTHING
        """,
        book_id, curriculum_id, grade_id, subject_id,
        BOOK["title"], BOOK["publisher"], BOOK["edition"],
        BOOK["published_year"], BOOK["total_chapters"], book_text_json,
    )

    chapters_inserted = 0
    topics_inserted = 0
    chapter_slo_links_inserted = 0
    topic_sub_slo_links_inserted = 0

    for chapter in ALL_CHAPTERS:
        ch_num = chapter["chapter_number"]
        chapter_id = seed_uuid(f"book_chapter:DARS:1:Eng:{ch_num}")
        chapter_text_json = json.dumps(_build_chapter_text(chapter))
        result = await conn.execute(
            """
            INSERT INTO book_chapters (id, book_id, chapter_number, title, start_page, end_page,
                                        chapter_text, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, 'published')
            ON CONFLICT (book_id, chapter_number) DO NOTHING
            """,
            chapter_id, book_id, ch_num, chapter["title"],
            chapter["start_page"], chapter["end_page"], chapter_text_json,
        )
        if result.endswith(" 1"):
            chapters_inserted += 1

        # Link chapter → SLOs
        for slo_code in chapter["slos"]:
            slo_id = seed_uuid(f"slo:DARS:1:Eng:{slo_code}")
            result = await conn.execute(
                """
                INSERT INTO book_chapter_slos (book_chapter_id, slo_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                chapter_id, slo_id,
            )
            if result.endswith(" 1"):
                chapter_slo_links_inserted += 1

        # Topics + sub-SLO links
        for topic in chapter["topics"]:
            t_num = topic["topic_number"]
            topic_id = seed_uuid(f"topic:DARS:1:Eng:{ch_num}:{t_num}")
            # start_line/end_line: not used in this hand-authored seed; topic_text is provided directly.
            result = await conn.execute(
                """
                INSERT INTO topics (id, book_chapter_id, topic_number, title, topic_text, status)
                VALUES ($1, $2, $3, $4, $5, 'published')
                ON CONFLICT (book_chapter_id, topic_number) DO NOTHING
                """,
                topic_id, chapter_id, t_num, topic["title"], topic["text"],
            )
            if result.endswith(" 1"):
                topics_inserted += 1

            for sub_slo_code in topic["sub_slos"]:
                sub_slo_id = seed_uuid(f"sub_slo:DARS:1:Eng:{sub_slo_code}")
                result = await conn.execute(
                    """
                    INSERT INTO topic_sub_slos (topic_id, sub_slo_id)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                    """,
                    topic_id, sub_slo_id,
                )
                if result.endswith(" 1"):
                    topic_sub_slo_links_inserted += 1

    log.info(
        "seed_dars_english_g1_book: done — chapters_inserted=%d, topics_inserted=%d, "
        "chapter_slo_links=%d, topic_sub_slo_links=%d",
        chapters_inserted, topics_inserted, chapter_slo_links_inserted, topic_sub_slo_links_inserted,
    )
