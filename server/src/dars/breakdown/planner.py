"""
Chapter planner core (ported from chapter-planner-app/planner.py).

Call the LLM, parse strict JSON, validate against the D-8 invariants, build the
ChapterPlan. No repair, no retry, no fallback (D-5) — a bad plan fails loudly.

PlanParseError / PlanValidationError / PlannerLLMError are preserved.
"""
import json
import logging
from typing import Optional

from dars.breakdown.planner_llm import PlannerLLM, PlannerLLMError  # noqa: F401  (re-exported)
from dars.breakdown.planner_models import (
    VALID_LP_TYPES,
    ChapterPlan,
    PlanRequest,
    PlanUnit,
)

logger = logging.getLogger(__name__)


class PlanParseError(ValueError):
    """Raised when the LLM response can't be parsed into units."""


class PlanValidationError(ValueError):
    """Raised when a parsed plan violates a D-8 invariant. Message = first violation."""


def _extract_json(raw: str) -> str:
    """Return the JSON object substring from a model response.

    Strips ``` fences and any prose around the object. This is parsing, not
    repair/retry (D-5): we read what the model returned, we don't ask again or
    synthesise a plan. A brace-scan recovers JSON wrapped in a sentence or fence.
    """
    s = raw.strip()
    if s.startswith("```"):
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1:]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
        s = s.strip()
    # Fall back to the first '{' .. matching last '}' if there's leading prose.
    if not s.startswith("{"):
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            s = s[start: end + 1]
    return s


def parse_plan_units(raw: str) -> list[dict]:
    """Parse the LLM response into a list of raw unit dicts."""
    try:
        data = json.loads(_extract_json(raw))
    except json.JSONDecodeError as exc:
        raise PlanParseError(f"response is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or "units" not in data or not isinstance(data["units"], list):
        raise PlanParseError("response missing a 'units' array")
    return data["units"]


def validate_plan(units: list[PlanUnit], request: PlanRequest) -> Optional[str]:
    """D-8 invariants (a)-(e). Returns the first violation message, or None if valid.

    Formative-assessment support (exam-periods-and-formative-assessments
    D-7/D-8): a plan now mixes 'lesson' and 'formative_assessment' units. The
    count (a) and sequence-permutation (e) invariants are over ALL units
    (lessons + FAs); SLO coverage (b) counts BOTH kinds; the lp_type-allowed
    check (c) applies ONLY to lesson units (an FA carries no lp_type, D-7).
    """
    chapter_topic_ids = {t.id for t in request.chapter.topics}
    chapter_slo_ids = {s.id for t in request.chapter.topics for s in t.slos}
    allowed_lp = set(VALID_LP_TYPES[request.subject])

    # (a) exactly period_count units total (lessons + FAs combined, D-8)
    if len(units) != request.period_count:
        return f"expected {request.period_count} units, got {len(units)}"

    # (e) sequence is a permutation of 1..period_count
    seqs = sorted(u.sequence for u in units)
    if seqs != list(range(1, request.period_count + 1)):
        return f"sequence values must be a permutation of 1..{request.period_count}, got {seqs}"

    covered_slos: set[str] = set()
    for u in units:
        # (d) >=1 topic, >=1 slo, all real
        if not u.topic_ids:
            return f"unit {u.sequence} has no topic_ids"
        if not u.slo_ids:
            return f"unit {u.sequence} has no slo_ids"
        bad_topics = [t for t in u.topic_ids if t not in chapter_topic_ids]
        if bad_topics:
            return f"unit {u.sequence} references unknown topic_ids: {bad_topics}"
        bad_slos = [s for s in u.slo_ids if s not in chapter_slo_ids]
        if bad_slos:
            return f"unit {u.sequence} references unknown slo_ids: {bad_slos}"
        # (c) lp_type allowed for subject — lessons only (D-7). An FA must not
        # carry an lp_type at all; the PlanUnit model already enforces that, so
        # a non-null lp_type on an FA is caught here too (defence in depth).
        if u.slot_type == "lesson":
            if u.lp_type not in allowed_lp:
                return (
                    f"unit {u.sequence} lp_type '{u.lp_type}' not allowed for "
                    f"subject {request.subject}"
                )
        elif u.lp_type is not None:
            return (
                f"unit {u.sequence} is a formative_assessment but carries an "
                f"lp_type '{u.lp_type}' (FA units must not, D-7)"
            )
        # (b) coverage counts both lesson and FA units (D-7)
        covered_slos.update(u.slo_ids)

    # (b) every chapter SLO covered by ≥1 unit (lesson or FA)
    missing = chapter_slo_ids - covered_slos
    if missing:
        return f"SLOs not covered by any unit: {sorted(missing)}"

    return None


def _resolve_topic_text(topic_ids: list[str], request: PlanRequest) -> str:
    """Concatenate member topics' text in topic_ids order (D-4)."""
    by_id = {t.id: t.topic_text for t in request.chapter.topics}
    return "\n\n".join(by_id[t] for t in topic_ids if t in by_id)


def _build_unit(ru: dict, request: PlanRequest) -> PlanUnit:
    """Build one PlanUnit from a raw LLM unit dict.

    `slot_type` defaults to 'lesson' when absent (back-compat, D-13). An FA unit
    carries NO lp_type (D-7): even if the model echoes one, we drop it so the
    PlanUnit model validator is satisfied and the persisted slot is a clean FA.
    A lesson keeps whatever lp_type the model returned (validated downstream).

    `flex` (dynamic-chapter-planner D-15): a droppable revision/consolidation
    lesson. A flex unit is always a lesson with lp_type='revision' — if the model
    sets `flex: true` we coerce both (overriding any divergent slot_type/lp_type
    it echoed) so the persisted slot is a clean flex revision slot the buffer
    planner (F-2.3) and reteach (Phase 3) rely on. A non-flex unit is unchanged.
    """
    flex = bool(ru.get("flex", False))
    if flex:
        slot_type = "lesson"
        lp_type: str | None = "revision"
    else:
        slot_type = str(ru.get("slot_type", "lesson"))
        raw_lp = ru.get("lp_type")
        lp_type = None if slot_type == "formative_assessment" else (
            str(raw_lp) if raw_lp is not None else None
        )
    topic_ids = list(ru.get("topic_ids", []))
    return PlanUnit(
        sequence=int(ru["sequence"]),
        slot_type=slot_type,
        lp_type=lp_type,
        topic_ids=topic_ids,
        slo_ids=list(ru.get("slo_ids", [])),
        topic_text=_resolve_topic_text(topic_ids, request),
        rationale=str(ru.get("rationale", "")),
        flex=flex,
    )


async def make_chapter_plan(request: PlanRequest, llm: PlannerLLM) -> ChapterPlan:
    """Call the LLM, parse, validate, and build the ChapterPlan.

    Raises PlannerLLMError (LLM transport) / PlanParseError (bad JSON) /
    PlanValidationError (failed invariant). No fallback (D-5).
    """
    logger.info(
        "[PLANNER] entry — subject=%s grade=%s period_count=%s topics=%s",
        request.subject, request.grade, request.period_count, len(request.chapter.topics),
    )
    from dars.breakdown.planner_prompts import build_system_prompt, build_user_prompt

    raw = await llm.complete(build_system_prompt(), build_user_prompt(request))

    raw_units = parse_plan_units(raw)
    units = [_build_unit(ru, request) for ru in raw_units]

    violation = validate_plan(units, request)
    if violation is not None:
        logger.error("[PLANNER] invalid plan — %s", violation)
        raise PlanValidationError(violation)

    units.sort(key=lambda u: u.sequence)
    plan = ChapterPlan(
        subject=request.subject,
        grade=request.grade,
        curriculum=request.curriculum,
        period_count=request.period_count,
        units=units,
    )
    # Distribution by lp_type for lessons; FAs are counted separately (D-7: an
    # FA has no lp_type, so it never appears in lp_dist). flex revision lessons
    # are also tallied separately (dynamic-chapter-planner F-2.3) so the buffer
    # split is visible in the log.
    lp_dist: dict[str, int] = {}
    fa_count = 0
    flex_count = 0
    for u in units:
        if u.slot_type == "formative_assessment":
            fa_count += 1
            continue
        if u.flex:
            flex_count += 1
        lp_dist[u.lp_type] = lp_dist.get(u.lp_type, 0) + 1
    logger.info(
        "[PLANNER] exit — units=%d lessons=%d formative_assessments=%d flex=%d "
        "lp_type_dist=%s",
        len(units), len(units) - fa_count, fa_count, flex_count, lp_dist,
    )
    return plan
