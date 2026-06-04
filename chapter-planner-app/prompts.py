"""
Prompt construction for the CPE planner (F-2.2).

The system prompt fixes the planner's role + hard rules + output schema.
The user prompt carries the concrete chapter: subject, grade, period_count,
the allowed lp_type list for the subject (D-5), and the topics with ids,
text, and SLOs (ids + statements). `recommended_lp_type` is NOT passed (D-5).
"""
import json

from config import VALID_LP_TYPES
from models import PlanRequest

# Frozen system prompt. Output schema mirrors the `units` array in
# 02-data-model.md; CPE resolves `topic_text` itself, so the LLM does NOT
# echo topic text back — it returns only the structural fields.
_SYSTEM_PROMPT = (
    "You are a curriculum planning engine. Given a chapter's topics (each with "
    "source text and the SLOs it teaches), a subject, and a fixed number of "
    "teaching periods, produce an ordered plan of EXACTLY that many lesson Plan "
    "Units. Each unit is one lesson plan.\n"
    "\n"
    "Hard rules:\n"
    "1. Return EXACTLY `period_count` units. `sequence` is 1..period_count, each "
    "used once.\n"
    "2. A unit may combine several thin topics or focus on part of a dense one — "
    "you decide the boundaries. Each unit lists the `topic_ids` it draws from "
    "(>=1) and the `slo_ids` it teaches (>=1).\n"
    "3. Every SLO in the chapter must be taught by at least one unit (full "
    "coverage). Only reference topic_ids and slo_ids that were given to you — "
    "never invent ids.\n"
    "4. Choose `lp_type` for each unit ONLY from the provided allowed list. Pick "
    "the type that best fits that unit's topics and SLOs.\n"
    "5. Give a one-sentence `rationale` per unit.\n"
    "\n"
    "Return STRICT JSON ONLY — no prose, no markdown fences. The exact shape:\n"
    '{"units": [{"sequence": 1, "lp_type": "<allowed>", "topic_ids": ["<id>"], '
    '"slo_ids": ["<id>"], "rationale": "<one sentence>"}]}'
)


def build_system_prompt() -> str:
    return _SYSTEM_PROMPT


def build_user_prompt(request: PlanRequest) -> str:
    allowed = VALID_LP_TYPES[request.subject]
    payload = {
        "subject": request.subject,
        "grade": request.grade,
        "period_count": request.period_count,
        "allowed_lp_types": allowed,
        "chapter_title": request.chapter.title,
        "topics": [
            {
                "id": t.id,
                "topic_text": t.topic_text,
                "slos": [{"id": s.id, "statement": s.statement} for s in t.slos],
            }
            for t in request.chapter.topics
        ],
    }
    return json.dumps(payload, ensure_ascii=False)
