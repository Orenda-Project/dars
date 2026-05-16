"""
F2.2 — Async port of Schema's chapter_plan service (topic extraction +
topic → sub-SLO mapping).

Public surface:
    - extract_topics_from_chapter(conn, book_chapter_id, *, llm) -> dict
    - map_topics_to_sub_slos(conn, topic_ids, sub_slo_ids, *, llm) -> dict
    - parse_topic_breakdown_response(text) -> dict (raw JSON parser)

The topic-breakdown LLM is expected to return a JSON object (possibly
wrapped in a ```json``` code fence) with:
    {
      "chapter_number": str,
      "chapter_name": str,
      "slos": str,             # not persisted in F2.2; used by F2.5
      "topic_sections": [
        {"section_title": str, "starting_line_number": int}
      ],
      "exercise": {"starting_line_number": int}
    }

Topics are inserted with `status='draft'`. F2.2 will not overwrite
existing topics on the chapter (returns a `skipped` flag); a future
admin publish endpoint flips draft → published.
"""
import json
import logging
import re
from typing import Awaitable, Callable
from uuid import UUID

import asyncpg

from dars.breakdown.llm_client import call_llm as default_call_llm
from dars.breakdown.prompt_store import get_prompt

log = logging.getLogger("breakdown.chapter")

LLMCallable = Callable[[str, str], Awaitable[str]]

DEFAULT_TOPIC_MAX_TOKENS = 8000
DEFAULT_MAPPING_MAX_TOKENS = 2000


# ---------------------------------------------------------------------------
# JSON extraction (ported from Schema's _extract_json_from_response)
# ---------------------------------------------------------------------------

def parse_topic_breakdown_response(response: str) -> dict:
    """
    Extract a JSON object from an LLM response. Tries:
      1. ```json``` fenced block
      2. Non-greedy {...} match
      3. Greedy {...} match (last resort)

    Returns {} if nothing parses.
    """
    if not response:
        return {}

    fence = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", response)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            log.debug("topic_breakdown: fenced JSON failed to parse")

    non_greedy = re.search(r"\{(?:[^{}]|(?:\{[^{}]*\}))*?\}", response)
    if non_greedy:
        try:
            return json.loads(non_greedy.group())
        except json.JSONDecodeError:
            log.debug("topic_breakdown: non-greedy JSON failed to parse")

    greedy = re.search(r"\{[\s\S]*\}", response)
    if greedy:
        try:
            return json.loads(greedy.group())
        except json.JSONDecodeError:
            log.debug("topic_breakdown: greedy JSON failed to parse")

    return {}


# ---------------------------------------------------------------------------
# Line-numbered text helpers (ported from Schema)
# ---------------------------------------------------------------------------

def _add_line_numbers(text: str) -> str:
    return "\n".join(f"Line: {i + 1} - {line}" for i, line in enumerate(text.split("\n")))


def _clean_topic_title(title: str) -> str:
    if not title or ":" not in title:
        return title
    return title.split(":", 1)[1].strip()


def _slice_lines(text: str, start: int, end: int) -> str:
    lines = text.split("\n")
    start_idx = max(0, start - 1)
    end_idx = min(len(lines), end)
    return "\n".join(lines[start_idx:end_idx]).strip()


def _extract_topic_sections(chapter_text: str, parsed: dict) -> tuple[list[dict], str]:
    """
    Return ([{title, topic_text, start_line, end_line}], final_exercise_text).
    Mirrors Schema's format_topic_for_extraction but uses our column names.
    """
    sections = parsed.get("topic_sections", [])
    exercise = parsed.get("exercise") or {}
    chapter_lines = chapter_text.split("\n")
    total_lines = len(chapter_lines)

    def _safe_int(v, default):
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    exercise_start = _safe_int(exercise.get("starting_line_number"), None) if exercise else None

    topics: list[dict] = []
    for idx, section in enumerate(sections):
        title = _clean_topic_title(section.get("section_title", "Unknown Topic"))
        start_line = _safe_int(section.get("starting_line_number"), 1)
        if idx + 1 < len(sections):
            end_line = _safe_int(sections[idx + 1].get("starting_line_number"), total_lines)
        else:
            end_line = exercise_start if exercise_start else total_lines
        topic_text = _slice_lines(chapter_text, start_line, end_line)
        topics.append({
            "title": title,
            "topic_text": topic_text,
            "start_line": start_line,
            "end_line": end_line,
        })

    final_exercise = _slice_lines(chapter_text, exercise_start, total_lines) if exercise_start else ""
    return topics, final_exercise


def _flatten_chapter_text(chapter_text_jsonb) -> str:
    """
    book_chapters.chapter_text is JSONB [{pdf_page_no, text}, ...].
    Concatenate the text fields preserving order.
    Tolerates raw strings too (in case future seeds use a plain string).
    """
    if chapter_text_jsonb is None:
        return ""
    if isinstance(chapter_text_jsonb, str):
        # asyncpg may surface JSONB as a string if no type codec is registered.
        try:
            chapter_text_jsonb = json.loads(chapter_text_jsonb)
        except json.JSONDecodeError:
            return chapter_text_jsonb
    if isinstance(chapter_text_jsonb, list):
        return "\n\n".join(p.get("text", "") for p in chapter_text_jsonb if isinstance(p, dict))
    return ""


# ---------------------------------------------------------------------------
# extract_topics_from_chapter
# ---------------------------------------------------------------------------

async def extract_topics_from_chapter(
    conn: asyncpg.Connection,
    book_chapter_id: UUID,
    *,
    llm: LLMCallable | None = None,
    force: bool = False,
) -> dict:
    """
    Run the topic-extraction LLM against a chapter and insert draft topics.

    Idempotency: if the chapter already has any topics (draft or published),
    returns `skipped=True` and inserts nothing unless `force=True`.

    Returns:
        {
          "book_chapter_id": UUID,
          "skipped": bool,
          "inserted_topic_count": int,
          "topics": [{topic_id, topic_number, title, topic_text, start_line, end_line}],
          "raw_response": str,
        }
    """
    log.info("extract_topics_from_chapter: entry chapter_id=%s force=%s", book_chapter_id, force)

    row = await conn.fetchrow(
        """
        SELECT id, title, chapter_text, start_page
        FROM book_chapters
        WHERE id = $1
        """,
        book_chapter_id,
    )
    if row is None:
        raise ValueError(f"book_chapter not found: {book_chapter_id}")

    existing_count = await conn.fetchval(
        "SELECT COUNT(*) FROM topics WHERE book_chapter_id = $1",
        book_chapter_id,
    )
    if existing_count and not force:
        log.info(
            "extract_topics_from_chapter: chapter_id=%s already has %d topics — skipping",
            book_chapter_id, existing_count,
        )
        return {
            "book_chapter_id": book_chapter_id,
            "skipped": True,
            "inserted_topic_count": 0,
            "topics": [],
            "raw_response": "",
        }

    chapter_text = _flatten_chapter_text(row["chapter_text"])
    if not chapter_text.strip():
        raise ValueError(f"book_chapter {book_chapter_id} has no chapter_text to break down")

    numbered = _add_line_numbers(chapter_text)
    user_message = (
        f"Chapter Title: {row['title']}\n"
        f"Start Page: {row['start_page'] or 1}\n\n"
        f"Chapter Text:\n{numbered}"
    )
    system_prompt = get_prompt("topic_breakdown")

    llm_call = llm or default_call_llm
    raw = await llm_call(system_prompt, user_message)
    if not raw:
        raise ValueError("LLM returned empty response for topic breakdown")

    parsed = parse_topic_breakdown_response(raw)
    if not parsed:
        raise ValueError("topic breakdown LLM response did not contain parseable JSON")

    topic_sections, _final_exercise = _extract_topic_sections(chapter_text, parsed)
    if not topic_sections:
        raise ValueError("topic breakdown produced no topic_sections")

    inserted = []
    async with conn.transaction():
        for idx, t in enumerate(topic_sections, start=1):
            topic_id = await conn.fetchval(
                """
                INSERT INTO topics (book_chapter_id, topic_number, title, topic_text,
                                    start_line, end_line, status)
                VALUES ($1, $2, $3, $4, $5, $6, 'draft')
                ON CONFLICT (book_chapter_id, topic_number) DO NOTHING
                RETURNING id
                """,
                book_chapter_id, idx, t["title"], t["topic_text"],
                t["start_line"], t["end_line"],
            )
            if topic_id is not None:
                inserted.append({
                    "topic_id": topic_id,
                    "topic_number": idx,
                    "title": t["title"],
                    "topic_text": t["topic_text"],
                    "start_line": t["start_line"],
                    "end_line": t["end_line"],
                })

    log.info(
        "extract_topics_from_chapter: exit chapter_id=%s inserted=%d (of %d)",
        book_chapter_id, len(inserted), len(topic_sections),
    )
    return {
        "book_chapter_id": book_chapter_id,
        "skipped": False,
        "inserted_topic_count": len(inserted),
        "topics": inserted,
        "raw_response": raw,
    }


# ---------------------------------------------------------------------------
# map_topics_to_sub_slos
# ---------------------------------------------------------------------------

_MAPPING_SYSTEM_TEMPLATE = """You are an expert educator. Map the given topic content to the most relevant sub-SLOs from the provided list.

Available sub-SLOs:
{slos_list}

Return a JSON object with this exact shape:
{{"matched_sub_slo_codes": ["CODE1", "CODE2", ...]}}

Rules:
- Pick at most {max_match} sub-SLOs.
- Use only codes from the list above. Do not invent new codes.
- Return an empty array if no sub-SLO is a good match."""


def _build_mapping_prompt(sub_slos: list[asyncpg.Record], max_match: int) -> str:
    slos_list = "\n".join(
        f"- {r['code']}: {r['statement']}" for r in sub_slos
    )
    return _MAPPING_SYSTEM_TEMPLATE.format(slos_list=slos_list, max_match=max_match)


def _parse_mapping_response(raw: str, valid_codes: set[str]) -> list[str]:
    parsed = parse_topic_breakdown_response(raw)  # same JSON extractor
    if not isinstance(parsed, dict):
        return []
    matched = parsed.get("matched_sub_slo_codes") or []
    if not isinstance(matched, list):
        return []
    result: list[str] = []
    for code in matched:
        if isinstance(code, str) and code in valid_codes:
            result.append(code)
    return result


async def map_topics_to_sub_slos(
    conn: asyncpg.Connection,
    topic_ids: list[UUID],
    sub_slo_ids: list[UUID],
    *,
    max_match: int = 5,
    llm: LLMCallable | None = None,
    replace: bool = False,
) -> dict:
    """
    Use the LLM to map each topic to relevant sub-SLOs, inserting rows
    into `topic_sub_slos`.

    Args:
        topic_ids:   topics.id list. Every id must exist.
        sub_slo_ids: candidate sub-SLO universe. Mapping picks from here.
        max_match:   cap on sub-SLOs assigned per topic.
        replace:     if True, delete existing topic_sub_slos rows for these
                     topics before re-inserting. Default False (additive).

    Returns:
        {
          "topic_count": int,
          "sub_slo_candidate_count": int,
          "inserted_pair_count": int,
          "mappings": [{topic_id, sub_slo_codes: [...]}],
        }
    """
    log.info(
        "map_topics_to_sub_slos: entry topics=%d sub_slos=%d max_match=%d replace=%s",
        len(topic_ids), len(sub_slo_ids), max_match, replace,
    )
    if not topic_ids:
        raise ValueError("topic_ids is empty")
    if not sub_slo_ids:
        raise ValueError("sub_slo_ids is empty")

    topics = await conn.fetch(
        """
        SELECT id, title, topic_text
        FROM topics
        WHERE id = ANY($1::uuid[])
        ORDER BY topic_number
        """,
        topic_ids,
    )
    if len(topics) != len(topic_ids):
        missing = set(topic_ids) - {t["id"] for t in topics}
        raise ValueError(f"topics not found: {sorted(str(m) for m in missing)}")

    sub_slos = await conn.fetch(
        """
        SELECT id, code, statement
        FROM sub_slos
        WHERE id = ANY($1::uuid[])
        ORDER BY code
        """,
        sub_slo_ids,
    )
    if len(sub_slos) != len(sub_slo_ids):
        missing = set(sub_slo_ids) - {s["id"] for s in sub_slos}
        raise ValueError(f"sub_slos not found: {sorted(str(m) for m in missing)}")

    sub_slo_by_code = {s["code"]: s["id"] for s in sub_slos}
    valid_codes = set(sub_slo_by_code.keys())
    system_prompt = _build_mapping_prompt(sub_slos, max_match)
    llm_call = llm or default_call_llm

    mappings: list[dict] = []
    pair_count = 0
    async with conn.transaction():
        if replace:
            await conn.execute(
                "DELETE FROM topic_sub_slos WHERE topic_id = ANY($1::uuid[])",
                topic_ids,
            )

        for t in topics:
            user_message = (
                f"Topic Title: {t['title']}\n\n"
                f"Topic Content:\n{t['topic_text'] or ''}\n"
            )
            raw = await llm_call(system_prompt, user_message)
            picked = _parse_mapping_response(raw, valid_codes)
            mappings.append({"topic_id": t["id"], "sub_slo_codes": picked})
            for code in picked:
                result = await conn.execute(
                    """
                    INSERT INTO topic_sub_slos (topic_id, sub_slo_id)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                    """,
                    t["id"], sub_slo_by_code[code],
                )
                if result.endswith(" 1"):
                    pair_count += 1
            log.info(
                "map_topics_to_sub_slos: topic_id=%s matched=%d",
                t["id"], len(picked),
            )

    log.info(
        "map_topics_to_sub_slos: exit inserted_pairs=%d across %d topics",
        pair_count, len(topics),
    )
    return {
        "topic_count": len(topics),
        "sub_slo_candidate_count": len(sub_slos),
        "inserted_pair_count": pair_count,
        "mappings": mappings,
    }
