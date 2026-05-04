import json
import logging
import re
import uuid

import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from dars.assessments.models import Assessment
from dars.config import settings

logger = logging.getLogger(__name__)

# These assessments are for the teacher, not the student — the goal is to verify
# the teacher actually understands the material before they deliver the lesson.
# Hence the emphasis on comprehension/application over recall.
ASSESSMENT_SYSTEM_PROMPT = """You are an expert teacher creating a short assessment to test student understanding of a lesson.

Generate exactly 9 multiple-choice questions (MCQs) that are genuinely challenging — testing comprehension and application, not trivial recall. Questions should require students to think critically about the content, not just recognise a memorised fact.

Each MCQ must have:
- A clear, specific question
- Four options labelled a, b, c, d
- The correct answer (single letter: a, b, c, or d)
- A brief explanation of why the answer is correct

Return ONLY a valid JSON array with no markdown, no explanation, no code fences:
[
  {
    "question": "...",
    "options": {"a": "...", "b": "...", "c": "...", "d": "..."},
    "answer": "a",
    "explanation": "..."
  }
]"""


def _extract_json_array(response: str) -> list:
    """Extract a JSON array from LLM response using two fallback strategies."""
    if not response or not isinstance(response, str):
        return []

    code_block = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n?\s*```", response)
    if code_block:
        try:
            result = json.loads(code_block.group(1).strip())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError as exc:
            logger.debug("code-block JSON parse failed — %s", exc)

    greedy = re.search(r"\[[\s\S]*\]", response)
    if greedy:
        try:
            result = json.loads(greedy.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError as exc:
            logger.debug("greedy JSON parse failed — %s", exc)

    return []


def _split_mcqs(mcqs: list) -> tuple[list, list]:
    """Split MCQs into questions-only and answers-only parallel lists."""
    questions = []
    answers = []
    for mcq in mcqs:
        questions.append({
            "question": mcq.get("question", ""),
            "options": mcq.get("options", {}),
        })
        answers.append({
            "answer": mcq.get("answer", ""),
            "explanation": mcq.get("explanation", ""),
        })
    return questions, answers


async def generate_assessment(
    assessment_id: uuid.UUID,
    lesson_plan_id: uuid.UUID,
    db_url: str,
) -> None:
    """Background task: generate MCQs from a lesson plan and update the assessment record."""
    logger.info("generate_assessment: start assessment_id=%s lesson_plan_id=%s", assessment_id, lesson_plan_id)

    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        record = await session.get(Assessment, assessment_id)
        if record is None:
            logger.error("generate_assessment: assessment_id=%s not found in DB", assessment_id)
            await engine.dispose()
            return

        row = await session.execute(
            text("""
                SELECT
                    lp.topic,
                    lp.content,
                    lp.grade,
                    lp.subject,
                    lp.curriculum
                FROM lesson_plans lp
                WHERE lp.id = :lp_id
            """),
            {"lp_id": str(lesson_plan_id)},
        )
        data = row.mappings().one_or_none()

        if data is None:
            logger.error("generate_assessment: lesson_plan_id=%s not found", lesson_plan_id)
            record.status = "ERROR"
            record.error_message = "Lesson plan not found"
            await session.commit()
            await engine.dispose()
            return

        lp_content = data["content"] or ""
        if not lp_content:
            logger.error("generate_assessment: lesson_plan_id=%s has no content", lesson_plan_id)
            record.status = "ERROR"
            record.error_message = "Lesson plan has no content — generate the LP first"
            await session.commit()
            await engine.dispose()
            return

        user_message = (
            f"Grade: {data['grade']}\n"
            f"Subject: {data['subject']}\n"
            f"Curriculum: {data['curriculum']}\n"
            f"Topic: {data['topic']}\n\n"
            f"Lesson Plan Content:\n{lp_content}"
        )

        try:
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            message = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=ASSESSMENT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = message.content[0].text
            logger.info("generate_assessment: LLM responded assessment_id=%s chars=%d", assessment_id, len(raw))

            mcqs = _extract_json_array(raw)
            if not mcqs:
                raise ValueError(f"No JSON array found in LLM response: {raw[:200]}")

            questions, answers = _split_mcqs(mcqs)
            record.content_json = questions
            record.answers_json = answers
            record.content = None
            record.status = "READY"
        except Exception:
            logger.error("generate_assessment: failed assessment_id=%s", assessment_id, exc_info=True)
            record.status = "ERROR"
            record.error_message = "Generation failed — see server logs"

        logger.info("generate_assessment: done assessment_id=%s status=%s", assessment_id, record.status)
        await session.commit()

    await engine.dispose()
