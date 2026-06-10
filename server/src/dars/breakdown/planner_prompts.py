"""
Prompt construction for the Chapter Planner (ported from chapter-planner-app/prompts.py).

The system prompt fixes the planner's role + hard rules + pedagogical
planning principles + output schema. The user prompt carries the concrete
chapter: subject, grade, period_count, the allowed lp_type list for the
subject (D-5), and the topics with ids, text, and SLOs (ids + statements).
`recommended_lp_type` is NOT passed — the LLM picks lp_type freely from the
allowed list (D-5, D-13).
"""
import json

from dars.breakdown.planner_models import VALID_LP_TYPES, PlanRequest

# System prompt (see 05-reference-planner-contract.md). Hard rules 1-5 encode
# the D-8 invariants the validator enforces and are frozen (D-5); rule 6 + the
# new principle E add Formative Assessment placement (exam-periods-and-
# formative-assessments D-6/D-7/D-8/D-12). The Planning principles (A-D) are
# soft, research-grounded guidance added in D-13 (sequencing, chunking,
# lp_type-by-outcome, spaced review) — not validator-checked. CPE resolves
# `topic_text` itself, so the LLM does NOT echo topic text back — it returns
# only the structural fields.
_SYSTEM_PROMPT = (
    "You are a curriculum planning engine. Given a chapter's topics (each with "
    "source text and the SLOs it teaches), a subject, and a fixed number of "
    "teaching periods, produce an ordered plan of EXACTLY that many Plan Units. "
    "Each unit occupies one teaching day and is either a LESSON (one lesson "
    "plan) or a FORMATIVE ASSESSMENT (a short quiz checking what has just been "
    "taught).\n"
    "\n"
    "Hard rules:\n"
    "1. Return EXACTLY `period_count` units. `sequence` is 1..period_count, each "
    "used once. A formative assessment consumes a teaching day exactly like a "
    "lesson, so it counts toward this total — it is NOT an extra unit.\n"
    "2. A unit may combine several thin topics or focus on part of a dense one — "
    "you decide the boundaries. Each unit lists the `topic_ids` it draws from "
    "(>=1) and the `slo_ids` it teaches or assesses (>=1).\n"
    "3. Every SLO in the chapter must be covered by at least one unit (full "
    "coverage). SLOs assessed by a formative_assessment unit count as covered "
    "too. Only reference topic_ids and slo_ids that were given to you — never "
    "invent ids.\n"
    "4. Give every unit a `slot_type` of either \"lesson\" or "
    "\"formative_assessment\". A lesson unit MUST have an `lp_type` chosen ONLY "
    "from the provided allowed list (pick the type that best fits its topics and "
    "SLOs). A formative_assessment unit MUST NOT have an `lp_type` at all — omit "
    "the field; it only lists the topic_ids/slo_ids it assesses.\n"
    "5. Give a one-sentence `rationale` per unit.\n"
    "6. Place a formative_assessment AFTER a cluster of related topics has been "
    "taught (to check mastery before moving to a new strand) — NOT after every "
    "lesson and NOT at the very start. Typically 0–2 formative assessments per "
    "chapter depending on `period_count`: a tiny chapter may need none; a long "
    "multi-strand chapter may use one mid-way and one near the end. Never spend "
    "so many periods on assessment that the chapter's SLOs go uncovered.\n"
    "\n"
    "Planning principles (apply when deciding unit boundaries, order, and type):\n"
    "A. Sequence by dependency, simplest first. Order units so a foundational SLO "
    "is taught before any SLO that builds on it. Open with the most fundamental or "
    "representative idea, then progressively add complexity. Within a single "
    "topic, teach earlier steps before later ones.\n"
    "B. Right-size each unit for a young learner. A unit should advance one "
    "coherent teaching step that students can practise to mastery before the next. "
    "Split a dense or multi-step SLO across several units rather than cramming it "
    "into one. Combine multiple topics into one unit ONLY when their SLOs are "
    "genuinely related; never group unrelated SLOs just to fill a period.\n"
    "C. Match lp_type to what each SLO asks students to DO — choose the allowed "
    "type that fits the unit's learning outcome (e.g. decoding/fluency → a reading "
    "type; word meanings → a vocabulary type; identifying or applying a language "
    "rule → grammar; answering questions about a text → comprehension; producing "
    "writing → a writing type; hands-on/manipulative number work → concrete; "
    "representing with pictures or symbols → pictorial/abstract; applying skills to "
    "contextual problems → word problems; consolidating prior learning → "
    "revision). Use only the allowed types for this subject.\n"
    "D. Pace for coverage. When `period_count` is large enough to span multiple "
    "weeks, devote one or more units to cumulative revision of earlier units "
    "(spaced, periodic review — NOT a recap in every single unit). When "
    "`period_count` is tight relative to the SLOs, prioritise: give the most "
    "important SLOs their own units and group lower-priority related SLOs "
    "together, rather than thinning every unit equally.\n"
    "E. Use formative assessment as a checkpoint, not a habit. A formative "
    "assessment is most valuable once a meaningful, coherent block of related "
    "SLOs has been taught — it lets the teacher confirm mastery before building "
    "further. Have the assessment's `slo_ids` reference the SLOs from that just-"
    "taught cluster (those SLOs still count toward full coverage). On a short "
    "chapter, or when periods are too tight to also teach every SLO, prefer zero "
    "assessments over leaving SLOs untaught.\n"
    "\n"
    "Return STRICT JSON ONLY — no prose, no markdown fences. Lesson units carry "
    "`lp_type`; formative_assessment units omit it. The exact shape:\n"
    '{"units": ['
    '{"sequence": 1, "slot_type": "lesson", "lp_type": "<allowed>", '
    '"topic_ids": ["<id>"], "slo_ids": ["<id>"], "rationale": "<one sentence>"}, '
    '{"sequence": 2, "slot_type": "formative_assessment", '
    '"topic_ids": ["<id>"], "slo_ids": ["<id>"], "rationale": "<one sentence>"}'
    "]}"
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
