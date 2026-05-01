"""
Curriculum breakdown service — two-step AI pipeline ported from the Schema repo.

Step 1: Topic breakdown  — given a chapter text, extract topics with page ranges.
Step 2: Day plan         — given topics, produce a day-by-day lesson schedule.

Both steps call the Anthropic API using claude-sonnet-4-6.
"""
import json
import logging
import re

import anthropic

from dars.config import settings

log = logging.getLogger("curriculum.breakdown")

# ---------------------------------------------------------------------------
# Prompts (copied verbatim from Schema repo)
# ---------------------------------------------------------------------------

TOPIC_BREAKDOWN_PROMPT = """Perform the following tasks on text of a Maths Chapter: test
- Find the chapter number and chapter name from the text. Chapter info is usually at the start of the chapter.
- Find the SLOs(Students' Learning Outcomes) of the chapter. SLOs are usually at the start of the chapter after the chapter title. Maintain the formatting of the SLOs, don't change it, e.g., newlines, indentation, etc. DO NOT add the line prefix "Line: x - " to the SLOs, just maintain the formatting of the SLOs as it is in the chapter text.

- Find the topic sections of the chapter (CONTENT ONLY - DO NOT include practice questions/exercises).
    > Topics are the main content/teaching material in the chapter, identified by EXPLICIT TOPIC HEADINGS in the text.
    > A new topic section should ONLY be created when there is a CLEAR, EXPLICIT TOPIC HEADING in the chapter text (e.g., "Topic 1:", "Topic:", "Unit 1:", or similar clear heading markers).
    > Do NOT split content into new topics based on sub-concepts, examples, or explanations - these belong to the topic they are part of.
    > Do NOT create implied topics from headings that are not explicitly marked as topic headings.
    > Each topic section contains instructional content, examples, and explanations under that explicit topic heading.
    > DO NOT include the practice questions or exercises that come after each topic - those are separate and should NOT be included in the topic section line ranges.
    > A topic section should contain ONLY the teaching content from where the EXPLICIT TOPIC HEADING starts until where the practice/exercise questions BEGIN.
    > For each section, extract only the TITLE TEXT from the topic heading (without the "Topic 1:", "Topic:", "Unit 1:" prefix). For example, if the heading is "Topic 1: Basic Numbers", the title should be "Basic Numbers". If the heading is just "Topic 1", use "Topic 1".

- Find the final exercise section at the end of the chapter.
    > The final exercise is the comprehensive exercise section that covers the entire chapter.
    > It is located at the very end of the chapter after all topic sections.
    > It may be called "Review Exercise", "Chapter Review", "End-of-Chapter Exercise", "Chapter Test", "Mastery Challenge", "Exercise", or any other name indicating it's the final chapter-wide assessment.
    > This is the ONLY exercise section you need to identify - NOT the topic-specific practice questions that come after each topic.

- Find the starting line numbers: For each topic section (content only), identify where it starts by finding the line number where the EXPLICIT TOPIC HEADING appears. For the review exercise, identify where it starts. You can find the line numbers at the start of each line in this format: "Line: x - " where x is the line number. Make sure to correctly identify the starting line numbers, the ending line numbers will be determined by the starting line numbers of the next topic section or the review exercise, so it is important to correctly identify the starting line numbers.

CRITICAL RULES:
- ONLY create a topic section when you find an EXPLICIT topic heading (e.g., "Topic 1", "Topic:", "Unit 1", etc.)
- If content continues without a new topic heading, it belongs to the PREVIOUS topic - do NOT create a new topic
- Do NOT invent or generate topic titles - extract only the TITLE TEXT from the heading
  * Example: "Topic 1: Basic Numbers" → section_title should be "Basic Numbers"
  * Example: "Unit 2: Place Value" → section_title should be "Place Value"
  * Example: "Topic 3" → section_title should be "Topic 3"
- Do NOT include the "Topic", "Unit", or numbering prefix in the title
- Do NOT split topics based on sub-sections, concepts, or examples within the same topic
- Count the actual number of topics by counting explicit topic headings in the chapter
- If the chapter has 3 explicit topic headings, return exactly 3 topic sections - no more, no less

Return the response in the following JSON format:
```
{{
    "chapter_number": "1",
    "chapter_name": "chapter 1",
    "slos": "all the SLOs of the chapter",
    "topic_sections": [
        {{
            "section_title": "Topic Title",
            "starting_line_number": 5
        }},
        {{
            "section_title": "Another Topic",
            "starting_line_number": 20
        }},
        ...
    ],
    "exercise": {{
        "starting_line_number": 90
    }}
}}
```

IMPORTANT:
- topic_sections contains ONLY the starting line numbers of the topic content (without practice questions)
- The line range for each topic ends just BEFORE the practice questions start
- exercise is the ONLY exercise section - the comprehensive one at the end of the chapter (regardless of what it's called in the text)"""

DAY_PLAN_PROMPT = """Role: You are an experienced curriculum planner specializing in designing effective, time-bound instructional plans for teachers.
Task: Create a teacher-oriented, topic-wise breakdown of the given chapter(s). The plan should be divided into daily teaching segments, ensuring full coverage.
Purpose: To help teachers plan and manage classroom time efficiently, allowing them to cover the entire chapter systematically while maintaining student engagement and comprehension.
Input: You will be provided with a list of topics covering the chapters.
Output: You have to provide a unit plan.
Guidelines:
* Each topic should be manageable within a day or maximum 2 days.
* You can decide the number of teaching day(s) for a topic depending upon the length of the topic.
* Arrange topics in a logical progression that builds conceptual understanding.
* Make the plan clear, actionable, and classroom-ready.
* If a Start Date is provided, use it as Day 1 and increment each subsequent day by 1 calendar day (e.g. Start Date: 2026-03-12 → Day 1: 2026-03-12, Day 2: 2026-03-13, etc.).

Rules for giving the sub-topics:
*If a topic cannot be divided into further sub-topics. For example: Addition word problems then please do not provide any sub-topic.
*Subtopics MUST be extremely short — ideally 3 words maximum. Use concise labels only, like a heading or title.
*Examples of good subtopics: "With regrouping", "Without regrouping", "Using number line", "Properties of addition", "Word problems".
*Examples of bad subtopics (too long): "Understanding how to subtract two 3-digit numbers with regrouping across place values", "Learning the concept of carrying over in addition".
*Never write subtopics as sentences or explanations. They should read like brief labels or tags.
*No descriptions, no elaboration, no instructional details in the subtopic text.

Output Format: Respond with ONLY a valid JSON object — no markdown, no explanation, no code fences.

Schema:
{
  "plan": [
    {
      "day": 1,
      "date": "YYYY-MM-DD or Day 1 if no date given",
      "topic_subtopic": "Topic — Subtopic"
    }
  ]
}"""

# ---------------------------------------------------------------------------
# Helpers (ported from Schema/services/chapter_plan.py)
# ---------------------------------------------------------------------------


def add_line_numbers(text: str) -> str:
    """Add 'Line: N - ' prefix to each line."""
    lines = text.split("\n")
    return "\n".join(f"Line: {i + 1} - {line}" for i, line in enumerate(lines))


def clean_topic_title(title: str) -> str:
    """Strip 'Topic 1:' style prefix from a section title."""
    if not title or ":" not in title:
        return title
    return title.split(":", 1)[1].strip()


def _extract_topic_text(chapter_text: str, start_line: int, end_line: int) -> str:
    """Extract lines [start_line, end_line) from chapter_text (1-indexed)."""
    lines = chapter_text.split("\n")
    start_idx = max(0, start_line - 1)
    end_idx = min(len(lines), end_line)
    return "\n".join(lines[start_idx:end_idx]).strip()


def _extract_json_from_response(response: str) -> dict:
    """Extract JSON from LLM response using three fallback strategies."""
    if not response or not isinstance(response, str):
        return {}

    # Strategy 1: ```json ... ``` code block
    code_block = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", response)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError as exc:
            log.debug("code-block JSON parse failed — %s", exc)

    # Strategy 2: non-greedy brace match
    non_greedy = re.search(r"\{(?:[^{}]|(?:\{[^{}]*\}))*?\}", response)
    if non_greedy:
        try:
            return json.loads(non_greedy.group())
        except json.JSONDecodeError as exc:
            log.debug("non-greedy JSON parse failed — %s", exc)

    # Strategy 3: greedy brace match (last resort)
    greedy = re.search(r"\{[\s\S]*\}", response)
    if greedy:
        try:
            return json.loads(greedy.group())
        except json.JSONDecodeError as exc:
            log.debug("greedy JSON parse failed — %s", exc)

    return {}


def format_topic_for_extraction(
    chapter_text: str,
    parsed: dict,
    start_page: int | None,
) -> list[dict]:
    """
    Given the LLM-parsed JSON from the topic-breakdown step and the raw chapter
    text, return a list of dicts:
        {topic_number, title, page_number, topic_text}
    """
    topics: list[dict] = []

    if not isinstance(parsed, dict) or "topic_sections" not in parsed:
        return topics

    topic_sections = parsed.get("topic_sections", [])
    final_exercise = parsed.get("exercise", {})
    chapter_lines = chapter_text.split("\n")
    total_lines = len(chapter_lines)

    # Parse final exercise start line
    final_exercise_start: int | None = None
    if final_exercise:
        try:
            raw = final_exercise.get("starting_line_number")
            final_exercise_start = int(raw) if raw is not None else None
        except (ValueError, TypeError):
            log.warning("Invalid exercise starting_line_number — value=%r", final_exercise.get("starting_line_number"))

    for idx, section in enumerate(topic_sections):
        raw_title = section.get("section_title", "Unknown Topic")
        title = clean_topic_title(raw_title)

        try:
            section_start = int(section.get("starting_line_number", 1))
        except (ValueError, TypeError):
            log.warning("Invalid section starting_line_number — idx=%d", idx)
            section_start = 1

        # End line = next section start, or final exercise start, or chapter end
        if idx + 1 < len(topic_sections):
            try:
                section_end = int(topic_sections[idx + 1].get("starting_line_number", total_lines))
            except (ValueError, TypeError):
                section_end = total_lines
        else:
            section_end = final_exercise_start if final_exercise_start else total_lines

        topic_text = _extract_topic_text(chapter_text, section_start, section_end)
        page_number = section.get("page_number")
        if page_number is not None:
            page_number = str(page_number)

        topics.append(
            {
                "topic_number": idx + 1,
                "title": title,
                "page_number": page_number,
                "topic_text": topic_text,
            }
        )

    return topics


# ---------------------------------------------------------------------------
# Public AI functions
# ---------------------------------------------------------------------------


async def run_topic_breakdown(
    chapter_title: str,
    chapter_text: str,
    start_page: int | None,
) -> list[dict]:
    """
    Step 1: Break a chapter into topics.

    Returns list of dicts: {topic_number, title, page_number, topic_text}
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    page_hint = f"Start Page: {start_page}\n" if start_page else ""
    numbered_text = add_line_numbers(chapter_text)
    user_message = f"Chapter Title: {chapter_title}\n{page_hint}\nChapter Text:\n{numbered_text}"

    log.info("Topic breakdown — chapter=%r chars=%d", chapter_title, len(chapter_text))

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=TOPIC_BREAKDOWN_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text
    log.info("Topic breakdown done — chapter=%r response_chars=%d", chapter_title, len(raw))

    parsed = _extract_json_from_response(raw)
    if not parsed:
        log.warning("No JSON found in topic breakdown response — chapter=%r", chapter_title)
        return []

    topics = format_topic_for_extraction(chapter_text, parsed, start_page=start_page)
    log.info("Extracted %d topics — chapter=%r", len(topics), chapter_title)
    return topics


async def run_day_plan(topics: list[dict]) -> list[dict]:
    """
    Step 2: Generate a day-by-day lesson schedule from the extracted topics.

    Returns list of dicts: {day_number, scheduled_date, topic_subtopic}
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Simplify topics for day-plan prompt (title + page_number only — no large text)
    topics_for_prompt = [
        {"topic_number": t["topic_number"], "title": t["title"], "page_number": t.get("page_number")}
        for t in topics
    ]
    user_message = json.dumps({"topics": topics_for_prompt}, ensure_ascii=False)

    log.info("Day plan — topics=%d", len(topics))

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=DAY_PLAN_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text
    log.info("Day plan done — response_chars=%d", len(raw))

    parsed = _extract_json_from_response(raw)
    if not parsed:
        log.warning("No JSON found in day plan response")
        return []

    plan_items = parsed.get("plan", parsed) if isinstance(parsed, dict) else []
    if not isinstance(plan_items, list):
        log.warning("Unexpected day plan format — type=%s", type(plan_items))
        return []

    slots: list[dict] = []
    for item in plan_items:
        day_number = item.get("day")
        raw_date = item.get("date", "")
        topic_subtopic = item.get("topic_subtopic", "")

        if not day_number or not topic_subtopic:
            continue

        # scheduled_date is None if the value looks like "Day N" (no real date given)
        scheduled_date: str | None = None
        if raw_date and not str(raw_date).lower().startswith("day"):
            scheduled_date = str(raw_date)

        slots.append(
            {
                "day_number": int(day_number),
                "scheduled_date": scheduled_date,
                "topic_subtopic": topic_subtopic,
            }
        )

    return slots
