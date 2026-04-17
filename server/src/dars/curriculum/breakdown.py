"""
AI breakdown pipeline for curriculum generation.

Step A: Chapter planner — allocates teaching days across chapters.
Step B: Topic/LP planner — produces LP stubs for each chapter.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import anthropic

from dars.config import settings

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Teaching-day helpers
# ---------------------------------------------------------------------------

def _allowed_weekdays(days_per_week: int) -> set[int]:
    """Return the set of ISO weekday numbers (1=Mon…7=Sun) that are teaching days."""
    # days_per_week=5 → Mon–Fri (1–5)
    # days_per_week=4 → Mon–Thu (1–4)
    # etc.
    return set(range(1, days_per_week + 1))


def compute_teaching_days(start: date, end: date, days_per_week: int) -> list[date]:
    """Return an ordered list of teaching-day dates between start and end (inclusive)."""
    allowed = _allowed_weekdays(days_per_week)
    result: list[date] = []
    current = start
    while current <= end:
        if current.isoweekday() in allowed:
            result.append(current)
        current += timedelta(days=1)
    return result


# ---------------------------------------------------------------------------
# Dataclasses for inter-step communication
# ---------------------------------------------------------------------------

@dataclass
class ChapterAllocation:
    chapter_id: int
    days: int


@dataclass
class LpStub:
    topic_id: str  # UUID as string
    planned_date: date
    skill_type: str
    cpa_phase: str
    blooms_level: str
    sequence: int


# ---------------------------------------------------------------------------
# Step A — Chapter planner
# ---------------------------------------------------------------------------

_STEP_A_TOOL = {
    "name": "allocate_chapter_days",
    "description": "Allocate teaching days to chapters proportionally.",
    "input_schema": {
        "type": "object",
        "properties": {
            "allocations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "chapter_id": {"type": "integer"},
                        "days": {"type": "integer", "minimum": 1},
                    },
                    "required": ["chapter_id", "days"],
                },
            }
        },
        "required": ["allocations"],
    },
}

_STEP_A_SYSTEM = (
    "You are a curriculum planner. Given a list of chapters and a total number of "
    "teaching days, allocate days to each chapter proportionally based on the number "
    "of topics in each chapter. Every chapter must get at least 1 day. "
    "The total must equal exactly the number of available teaching days. "
    "Call the allocate_chapter_days tool with your answer."
)


def _build_step_a_user(chapters: list[dict[str, Any]], total_days: int) -> str:
    lines = [f"Total teaching days available: {total_days}", "", "Chapters:"]
    for ch in chapters:
        lines.append(f"- Chapter {ch['chapter_number']}: {ch['title']} ({ch['topic_count']} topics, id={ch['id']})")
    return "\n".join(lines)


async def plan_chapter_days(
    chapters: list[dict[str, Any]],
    total_days: int,
    anthropic_client: anthropic.AsyncAnthropic,
) -> list[ChapterAllocation]:
    """
    Step A: call Claude to allocate teaching days across chapters.

    chapters: list of dicts with keys: id, chapter_number, title, topic_count
    Returns a list of ChapterAllocation objects whose days sum to total_days.
    """
    user_msg = _build_step_a_user(chapters, total_days)

    response = await anthropic_client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": _STEP_A_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[_STEP_A_TOOL],
        tool_choice={"type": "tool", "name": "allocate_chapter_days"},
        messages=[{"role": "user", "content": user_msg}],
    )

    # Extract tool input
    tool_use_block = next(
        (b for b in response.content if b.type == "tool_use"),
        None,
    )
    if tool_use_block is None:
        raise ValueError("Step A: Claude did not call the allocation tool")

    raw: dict = tool_use_block.input
    allocations_raw: list[dict] = raw.get("allocations", [])

    allocations = [
        ChapterAllocation(chapter_id=a["chapter_id"], days=a["days"])
        for a in allocations_raw
    ]

    # Validate total
    actual_total = sum(a.days for a in allocations)
    if actual_total != total_days:
        logger.warning(
            "Step A allocation total mismatch: got %d, expected %d. Adjusting.",
            actual_total,
            total_days,
        )
        # Adjust the last allocation to make totals match
        diff = total_days - actual_total
        if allocations:
            allocations[-1].days = max(1, allocations[-1].days + diff)

    return allocations


# ---------------------------------------------------------------------------
# Step B — Topic/LP planner
# ---------------------------------------------------------------------------

_STEP_B_TOOL = {
    "name": "plan_lp_stubs",
    "description": "Plan lesson plan stubs for a chapter, one LP per teaching day.",
    "input_schema": {
        "type": "object",
        "properties": {
            "stubs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic_id": {"type": "string"},
                        "planned_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                        "skill_type": {
                            "type": "string",
                            "enum": ["reading", "writing", "speaking", "listening", "comprehension", "revision"],
                        },
                        "cpa_phase": {
                            "type": "string",
                            "enum": ["concrete", "pictorial", "abstract"],
                        },
                        "blooms_level": {
                            "type": "string",
                            "enum": ["remember", "understand", "apply", "analyze", "evaluate", "create"],
                        },
                        "sequence": {"type": "integer", "minimum": 1},
                    },
                    "required": ["topic_id", "planned_date", "skill_type", "cpa_phase", "blooms_level", "sequence"],
                },
            }
        },
        "required": ["stubs"],
    },
}

_STEP_B_SYSTEM = (
    "You are a curriculum planner. Given a chapter's topics and allocated teaching days, "
    "create a lesson plan schedule. Assign exactly one LP per day. "
    "For each topic, decide what skill types to cover (reading, writing, speaking, listening, "
    "comprehension, revision) and the appropriate CPA phase (concrete, pictorial, abstract) "
    "and Bloom's level (remember, understand, apply, analyze, evaluate, create). "
    "Topics should be covered in sequence. Include a revision LP at the end if days allow. "
    "Call the plan_lp_stubs tool with your answer."
)


def _build_step_b_user(
    chapter_title: str,
    topics: list[dict[str, Any]],
    days: int,
    teaching_dates: list[date],
) -> str:
    dates_str = ", ".join(d.isoformat() for d in teaching_dates[:days])
    lines = [
        f"Chapter: {chapter_title}",
        f"Teaching days: {days}",
        f"Dates: {dates_str}",
        "",
        "Topics:",
    ]
    for t in topics:
        sub_slos = t.get("sub_slos", [])
        sub_slo_str = "; ".join(s for s in sub_slos if s) if sub_slos else "none"
        lines.append(f"- id={t['id']} | {t['title']} | sub-SLOs: {sub_slo_str}")
    return "\n".join(lines)


async def plan_topic_stubs(
    chapter_title: str,
    topics: list[dict[str, Any]],
    days: int,
    teaching_dates: list[date],
    anthropic_client: anthropic.AsyncAnthropic,
) -> list[LpStub]:
    """
    Step B: call Claude to produce LP stubs for a chapter.

    topics: list of dicts with keys: id (UUID str), title, sub_slos (list of statements)
    teaching_dates: ordered list of all remaining teaching days (we use the first `days` of them)
    Returns list of LpStub objects.
    """
    chapter_dates = teaching_dates[:days]
    user_msg = _build_step_b_user(chapter_title, topics, days, chapter_dates)

    response = await anthropic_client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": _STEP_B_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[_STEP_B_TOOL],
        tool_choice={"type": "tool", "name": "plan_lp_stubs"},
        messages=[{"role": "user", "content": user_msg}],
    )

    tool_use_block = next(
        (b for b in response.content if b.type == "tool_use"),
        None,
    )
    if tool_use_block is None:
        raise ValueError(f"Step B: Claude did not call plan_lp_stubs for chapter '{chapter_title}'")

    raw: dict = tool_use_block.input
    stubs_raw: list[dict] = raw.get("stubs", [])

    stubs: list[LpStub] = []
    for s in stubs_raw:
        try:
            planned_date = date.fromisoformat(s["planned_date"])
        except (KeyError, ValueError):
            # Fallback: use the first available date
            planned_date = chapter_dates[0] if chapter_dates else date.today()

        stubs.append(LpStub(
            topic_id=s["topic_id"],
            planned_date=planned_date,
            skill_type=s.get("skill_type", "reading"),
            cpa_phase=s.get("cpa_phase", "abstract"),
            blooms_level=s.get("blooms_level", "understand"),
            sequence=s.get("sequence", len(stubs) + 1),
        ))

    return stubs
