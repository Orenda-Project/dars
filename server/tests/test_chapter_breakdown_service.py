"""
F2.2 — tests for the chapter breakdown service.

Pure-Python tests cover the JSON extractor and topic-section slicer.
DB-backed tests are gated on DATABASE_URL (matches test_v2_smoke.py).
"""
import json
import os
import uuid as _uuid
from textwrap import dedent

import asyncpg
import pytest

from dars.breakdown.chapter_breakdown_service import (
    _add_line_numbers,
    _extract_topic_sections,
    _flatten_chapter_text,
    extract_topics_from_chapter,
    map_topics_to_sub_slos,
    parse_topic_breakdown_response,
)
from dars.config import settings


# ---------------------------------------------------------------------------
# Unit: JSON extractor
# ---------------------------------------------------------------------------


def test_parse_topic_breakdown_response_fenced_block():
    raw = dedent(
        """
        Here is the response:
        ```json
        {
          "chapter_number": "1",
          "topic_sections": [
            {"section_title": "Intro", "starting_line_number": 1},
            {"section_title": "Animals", "starting_line_number": 10}
          ],
          "exercise": {"starting_line_number": 30}
        }
        ```
        """
    ).strip()
    parsed = parse_topic_breakdown_response(raw)
    assert parsed["chapter_number"] == "1"
    assert len(parsed["topic_sections"]) == 2
    assert parsed["exercise"]["starting_line_number"] == 30


def test_parse_topic_breakdown_response_bare_json():
    raw = '{"chapter_number": "2", "topic_sections": [], "exercise": {}}'
    parsed = parse_topic_breakdown_response(raw)
    assert parsed["chapter_number"] == "2"


def test_parse_topic_breakdown_response_no_json_returns_empty():
    assert parse_topic_breakdown_response("just prose, no braces") == {}
    assert parse_topic_breakdown_response("") == {}


# ---------------------------------------------------------------------------
# Unit: line slicer
# ---------------------------------------------------------------------------


def test_add_line_numbers():
    text = "alpha\nbeta\ngamma"
    numbered = _add_line_numbers(text)
    assert numbered.splitlines() == [
        "Line: 1 - alpha",
        "Line: 2 - beta",
        "Line: 3 - gamma",
    ]


def test_extract_topic_sections_three_topics_with_exercise():
    chapter_text = "\n".join(f"line {i}" for i in range(1, 21))  # 20 lines
    parsed = {
        "topic_sections": [
            {"section_title": "Topic A", "starting_line_number": 1},
            {"section_title": "Chapter 1: Topic B", "starting_line_number": 7},
            {"section_title": "Topic C", "starting_line_number": 13},
        ],
        "exercise": {"starting_line_number": 18},
    }
    topics, exercise = _extract_topic_sections(chapter_text, parsed)
    assert [t["title"] for t in topics] == ["Topic A", "Topic B", "Topic C"]
    assert topics[0]["start_line"] == 1 and topics[0]["end_line"] == 7
    assert topics[1]["start_line"] == 7 and topics[1]["end_line"] == 13
    assert topics[2]["start_line"] == 13 and topics[2]["end_line"] == 18
    # The slicer is end-inclusive (mirrors Schema's behavior). The final-exercise
    # slice starts at the same line, so the boundary is shared between the last
    # topic and the exercise — admins can trim later if it matters.
    assert "line 17" in topics[2]["topic_text"]
    assert exercise.startswith("line 18")


def test_extract_topic_sections_no_exercise_falls_through_to_end():
    chapter_text = "\n".join(f"line {i}" for i in range(1, 11))
    parsed = {
        "topic_sections": [{"section_title": "Solo", "starting_line_number": 3}],
        # no exercise key
    }
    topics, exercise = _extract_topic_sections(chapter_text, parsed)
    assert len(topics) == 1
    assert topics[0]["end_line"] == 10
    assert exercise == ""


# ---------------------------------------------------------------------------
# Unit: chapter_text flattener
# ---------------------------------------------------------------------------


def test_flatten_chapter_text_jsonb_list():
    pages = [
        {"pdf_page_no": 1, "text": "page one"},
        {"pdf_page_no": 2, "text": "page two"},
    ]
    assert _flatten_chapter_text(pages) == "page one\n\npage two"


def test_flatten_chapter_text_string_json():
    pages = [{"pdf_page_no": 1, "text": "hello"}]
    assert _flatten_chapter_text(json.dumps(pages)) == "hello"


def test_flatten_chapter_text_handles_none_and_garbage():
    assert _flatten_chapter_text(None) == ""
    assert _flatten_chapter_text("not json at all") == "not json at all"


# ---------------------------------------------------------------------------
# Integration: DB-backed runs with mocked LLM
# ---------------------------------------------------------------------------


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DB-backed test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestChapterBreakdownAgainstDB:
    async def test_extract_topics_skips_seeded_chapter(self):
        """Seeded chapter 1 already has published topics — extract should skip."""
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            chapter = await conn.fetchrow(
                """
                SELECT bc.id FROM book_chapters bc
                JOIN books b ON b.id = bc.book_id
                WHERE bc.chapter_number = 1
                ORDER BY bc.created_at
                LIMIT 1
                """
            )
            assert chapter is not None, "seed did not load chapter 1"

            async def fake_llm(system: str, user: str) -> str:
                raise AssertionError("LLM must not be called when chapter has topics")

            result = await extract_topics_from_chapter(
                conn, chapter["id"], llm=fake_llm
            )
            assert result["skipped"] is True
            assert result["inserted_topic_count"] == 0
        finally:
            await conn.close()

    async def test_extract_topics_inserts_drafts_on_empty_chapter(self):
        """
        Create a throwaway book + book_chapter with chapter_text but no topics,
        then run extract. Verify draft topics land. Cleanup after.
        """
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            curriculum = await conn.fetchrow("SELECT id FROM curriculums LIMIT 1")
            grade = await conn.fetchrow("SELECT id FROM grades LIMIT 1")
            subject = await conn.fetchrow("SELECT id FROM subjects LIMIT 1")

            book_id = _uuid.uuid4()
            chapter_id = _uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO books (id, curriculum_id, grade_id, subject_id, title)
                VALUES ($1, $2, $3, $4, $5)
                """,
                book_id, curriculum["id"], grade["id"], subject["id"],
                "F2.2 test book",
            )
            chapter_text_jsonb = json.dumps([
                {"pdf_page_no": 1, "text": "Introduction to the chapter.\nMore intro lines."},
                {"pdf_page_no": 2, "text": "Section about colors.\nRed, blue, green.\nWe see colors."},
                {"pdf_page_no": 3, "text": "Section about numbers.\nOne, two, three.\n\nExercise: answer the questions."},
            ])
            await conn.execute(
                """
                INSERT INTO book_chapters
                  (id, book_id, chapter_number, title, start_page, end_page, chapter_text, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, 'draft')
                """,
                chapter_id, book_id, 1, "F2.2 test chapter", 1, 3, chapter_text_jsonb,
            )

            mock_response = dedent(
                """
                ```json
                {
                  "chapter_number": "1",
                  "chapter_name": "F2.2 test chapter",
                  "slos": "",
                  "topic_sections": [
                    {"section_title": "Introduction", "starting_line_number": 1},
                    {"section_title": "Colors: Section", "starting_line_number": 4},
                    {"section_title": "Numbers", "starting_line_number": 9}
                  ],
                  "exercise": {"starting_line_number": 12}
                }
                ```
                """
            ).strip()

            captured: dict = {}

            async def fake_llm(system: str, user: str) -> str:
                captured["system"] = system
                captured["user"] = user
                return mock_response

            result = await extract_topics_from_chapter(conn, chapter_id, llm=fake_llm)
            assert result["skipped"] is False
            assert result["inserted_topic_count"] == 3
            titles = [t["title"] for t in result["topics"]]
            assert titles == ["Introduction", "Section", "Numbers"]

            # Verify rows landed with status='draft'
            db_rows = await conn.fetch(
                "SELECT topic_number, title, status FROM topics WHERE book_chapter_id=$1 ORDER BY topic_number",
                chapter_id,
            )
            assert len(db_rows) == 3
            assert all(r["status"] == "draft" for r in db_rows)

            # Idempotency: re-run should skip.
            async def assert_no_call(system: str, user: str) -> str:
                raise AssertionError("LLM must not be called on idempotent re-run")

            result2 = await extract_topics_from_chapter(conn, chapter_id, llm=assert_no_call)
            assert result2["skipped"] is True

            # Cleanup (cascades to topics).
            await conn.execute("DELETE FROM books WHERE id=$1", book_id)
        finally:
            await conn.close()

    async def test_map_topics_to_sub_slos_inserts_pairs(self):
        """
        Use seeded chapter 1 topics + a few seeded sub-SLOs.
        Mock LLM returns codes; assert topic_sub_slos rows inserted.
        Use replace=True so we restore state on cleanup.
        """
        conn = await asyncpg.connect(_asyncpg_url(settings.database_url))
        try:
            topics = await conn.fetch(
                """
                SELECT t.id, t.title FROM topics t
                JOIN book_chapters bc ON bc.id = t.book_chapter_id
                WHERE bc.chapter_number = 1
                ORDER BY t.topic_number
                LIMIT 2
                """
            )
            assert len(topics) == 2, "seed did not load enough topics in chapter 1"
            topic_ids = [t["id"] for t in topics]

            sub_slo_rows = await conn.fetch(
                """
                SELECT id, code FROM sub_slos
                WHERE source='manual' AND code LIKE 'R1-01%'
                ORDER BY code
                LIMIT 2
                """
            )
            assert len(sub_slo_rows) == 2, "expected R1-01-* sub-SLOs from seed"
            sub_slo_ids = [s["id"] for s in sub_slo_rows]
            sub_slo_codes = [s["code"] for s in sub_slo_rows]

            # Snapshot existing topic_sub_slos to restore after.
            existing = await conn.fetch(
                "SELECT topic_id, sub_slo_id FROM topic_sub_slos WHERE topic_id = ANY($1::uuid[])",
                topic_ids,
            )

            async def fake_llm(system: str, user: str) -> str:
                # Pick whichever code matches first by simple title heuristic;
                # for the test it's enough to always return the same two codes.
                payload = {"matched_sub_slo_codes": sub_slo_codes}
                return f"```json\n{json.dumps(payload)}\n```"

            result = await map_topics_to_sub_slos(
                conn, topic_ids, sub_slo_ids, llm=fake_llm, replace=True,
            )
            assert result["topic_count"] == 2
            assert result["sub_slo_candidate_count"] == 2
            # Each topic mapped to both codes → 4 pairs.
            assert result["inserted_pair_count"] == 4

            # Verify in DB.
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM topic_sub_slos
                WHERE topic_id = ANY($1::uuid[]) AND sub_slo_id = ANY($2::uuid[])
                """,
                topic_ids, sub_slo_ids,
            )
            assert count == 4

            # Restore prior state.
            await conn.execute(
                "DELETE FROM topic_sub_slos WHERE topic_id = ANY($1::uuid[])",
                topic_ids,
            )
            for r in existing:
                await conn.execute(
                    "INSERT INTO topic_sub_slos (topic_id, sub_slo_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    r["topic_id"], r["sub_slo_id"],
                )
        finally:
            await conn.close()
