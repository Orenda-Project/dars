"""
Chapter Planner — the LLM-driven planning brain (Phase 1, pure, no DB).

Turns (chapter material, SLOs/sub-SLOs, period count) into a validated
`ChapterPlan`: an ordered sequence of LP units and Formative Assessments whose
count equals the period count (D-74: 1 item = 1 period). The LLM is the primary
path (D-1); the existing deterministic planners are the fallback when the LLM is
unavailable or returns output that fails validation (D-3).

No DB, no endpoint changes — Phase 1 ships behind tests only and is exercised by
Phase 2. See docs/features/intelligent-chapter-planner/03-phase-1-planner-core.md.

Decision references: D-1 (LLM primary + deterministic fallback), D-2 (LP units
are LLM-defined, not 1:1 with topics), D-3 (PlanValidator gates every LLM plan),
D-5 (LLM decides FA count/placement), D-6 (no summative this round —
sa_per_chapter=0), D-10 (PlannerLLM interface with two swappable backends).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable
from uuid import UUID

from dars.breakdown.chapter_plan_service import (
    allocate_chapter_days,
    plan_chapter_slots,
)

if TYPE_CHECKING:
    import asyncpg
from dars.breakdown.lp_type_heuristics import pick_lp_type
from dars.config import Settings, settings as default_settings
from dars.v2_api.lp_types import is_valid_lp_type, valid_lp_types_for_subject

logger = logging.getLogger(__name__)

# Deterministic-fallback constants (D-6).
_FALLBACK_FA_CADENCE = 5
_FALLBACK_SA_PER_CHAPTER = 0

# Char budget per topic_text when building the LLM prompt (note any truncation).
_TOPIC_TEXT_BUDGET = 4000


# ---------------------------------------------------------------------------
# F-1.1 — Plan data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubSloInput:
    sub_slo_id: UUID
    code: str
    statement: str


@dataclass(frozen=True)
class SloInput:
    code: str
    statement: str
    recommended_lp_type: str | None = None


@dataclass(frozen=True)
class TopicInput:
    topic_id: UUID
    title: str
    topic_text: str
    sub_slos: list[SubSloInput] = field(default_factory=list)


@dataclass(frozen=True)
class PlanInputs:
    """Pure inputs to the planner. Phase 2 builds this from DB rows."""

    subject_code: str
    period_count: int
    topics: list[TopicInput] = field(default_factory=list)
    chapter_slos: list[SloInput] = field(default_factory=list)


@dataclass(frozen=True)
class PlanItem:
    """One element of a ChapterPlan; occupies exactly one teaching period.

    Discriminated by `kind`:
      - 'lp': topic_ids (>=1, ordered), lp_type, sub_slo_ids (>=1).
      - 'fa': topic_ids, sub_slo_ids (the sets it assesses).
    """

    kind: Literal["lp", "fa"]
    topic_ids: list[UUID]
    sub_slo_ids: list[UUID]
    lp_type: str | None = None

    def __post_init__(self) -> None:
        if self.kind == "lp":
            if not self.topic_ids:
                raise ValueError("LP item requires >= 1 topic_id")
            if not self.sub_slo_ids:
                raise ValueError("LP item requires >= 1 sub_slo_id")
            if not self.lp_type:
                raise ValueError("LP item requires an lp_type")
        elif self.kind == "fa":
            pass
        else:  # pragma: no cover - guarded by typing
            raise ValueError(f"unknown PlanItem kind: {self.kind!r}")

    def to_json(self) -> dict:
        if self.kind == "lp":
            return {
                "kind": "lp",
                "topic_ids": [str(t) for t in self.topic_ids],
                "lp_type": self.lp_type,
                "sub_slo_ids": [str(s) for s in self.sub_slo_ids],
            }
        return {
            "kind": "fa",
            "topic_ids": [str(t) for t in self.topic_ids],
            "sub_slo_ids": [str(s) for s in self.sub_slo_ids],
        }

    @classmethod
    def from_json(cls, raw: dict) -> "PlanItem":
        kind = raw.get("kind")
        if kind not in ("lp", "fa"):
            raise ValueError(f"PlanItem.kind must be 'lp' or 'fa', got {kind!r}")
        topic_ids = [UUID(str(t)) for t in raw.get("topic_ids", [])]
        sub_slo_ids = [UUID(str(s)) for s in raw.get("sub_slo_ids", [])]
        lp_type = raw.get("lp_type") if kind == "lp" else None
        return cls(
            kind=kind,
            topic_ids=topic_ids,
            sub_slo_ids=sub_slo_ids,
            lp_type=lp_type,
        )


@dataclass(frozen=True)
class ChapterPlan:
    """The planner's structured output: ordered PlanItems + provenance."""

    items: list[PlanItem]
    source: Literal["llm", "fallback"]

    def to_json(self) -> dict:
        return {"items": [it.to_json() for it in self.items]}

    @classmethod
    def from_json(cls, raw: dict, *, source: Literal["llm", "fallback"]) -> "ChapterPlan":
        items_raw = raw.get("items")
        if not isinstance(items_raw, list):
            raise ValueError("ChapterPlan JSON must have an 'items' list")
        items = [PlanItem.from_json(it) for it in items_raw]
        return cls(items=items, source=source)


# ---------------------------------------------------------------------------
# F-1.2 — PlanValidator (D-3)
# ---------------------------------------------------------------------------


def validate_plan(plan: ChapterPlan, inputs: PlanInputs) -> list[str]:
    """Check an LLM ChapterPlan against the D-3 hard invariants.

    Returns a list of violation strings; empty == valid. Pure, no DB.
    Invariants (a)-(f):
      (a) item count == period_count
      (b) every input topic appears in >= 1 LP unit's topic_ids
      (c) every LP unit's lp_type passes is_valid_lp_type(subject, lp_type)
      (d) every LP unit has >= 1 topic and >= 1 sub-SLO
      (e) every FA item's topic_ids / sub_slo_ids subset of the chapter's
      (f) >= 1 LP unit, and >= 1 FA item when period_count leaves room
    """
    violations: list[str] = []

    chapter_topic_ids = {t.topic_id for t in inputs.topics}
    chapter_sub_slo_ids = {
        ss.sub_slo_id for t in inputs.topics for ss in t.sub_slos
    }

    lp_items = [it for it in plan.items if it.kind == "lp"]
    fa_items = [it for it in plan.items if it.kind == "fa"]

    # (a) item count == period_count
    if len(plan.items) != inputs.period_count:
        violations.append(
            f"item count {len(plan.items)} != period_count {inputs.period_count}"
        )

    # (b) every input topic taught by >= 1 LP unit
    taught_topics = {t for it in lp_items for t in it.topic_ids}
    uncovered = chapter_topic_ids - taught_topics
    if uncovered:
        violations.append(
            f"topics not taught by any LP unit: {sorted(str(t) for t in uncovered)}"
        )

    # (c) + (d) per-LP-unit checks
    for idx, it in enumerate(lp_items):
        if not it.topic_ids:
            violations.append(f"LP unit #{idx} has no topics")
        if not it.sub_slo_ids:
            violations.append(f"LP unit #{idx} has no sub-SLOs")
        if not is_valid_lp_type(inputs.subject_code, it.lp_type):
            violations.append(
                f"LP unit #{idx} lp_type {it.lp_type!r} invalid for subject "
                f"{inputs.subject_code!r}"
            )
        # LP topic/sub-SLO ids must be ones supplied in the input (no invention).
        bad_topics = [t for t in it.topic_ids if t not in chapter_topic_ids]
        if bad_topics:
            violations.append(
                f"LP unit #{idx} references unknown topic_ids: "
                f"{sorted(str(t) for t in bad_topics)}"
            )
        bad_subs = [s for s in it.sub_slo_ids if s not in chapter_sub_slo_ids]
        if bad_subs:
            violations.append(
                f"LP unit #{idx} references unknown sub_slo_ids: "
                f"{sorted(str(s) for s in bad_subs)}"
            )

    # (e) FA coverage subset of chapter
    for idx, it in enumerate(fa_items):
        bad_topics = [t for t in it.topic_ids if t not in chapter_topic_ids]
        if bad_topics:
            violations.append(
                f"FA item #{idx} references out-of-chapter topic_ids: "
                f"{sorted(str(t) for t in bad_topics)}"
            )
        bad_subs = [s for s in it.sub_slo_ids if s not in chapter_sub_slo_ids]
        if bad_subs:
            violations.append(
                f"FA item #{idx} references out-of-chapter sub_slo_ids: "
                f"{sorted(str(s) for s in bad_subs)}"
            )

    # (f) >= 1 LP unit; >= 1 FA when period_count leaves room for one.
    # "room" is defined to agree with the deterministic fallback (F-1.4 self-
    # consistency): the allocator only emits an FA once there are at least
    # _FALLBACK_FA_CADENCE lesson periods (fa_count = lesson_days // cadence).
    # Below that threshold a chapter is too short to carry an FA, so the
    # absence of one is not a violation. (D-3 (f): "if periods permit".)
    if not lp_items:
        violations.append("plan has no LP units")
    if inputs.period_count > _FALLBACK_FA_CADENCE and chapter_topic_ids and not fa_items:
        violations.append("plan has room for an FA but contains none")

    return violations


# ---------------------------------------------------------------------------
# F-1.3 — PlannerLLM interface + two backends (D-5, D-10)
# ---------------------------------------------------------------------------


class PlannerLLMError(Exception):
    """Transport or parse failure in the LLM planning path (caller -> fallback)."""


@runtime_checkable
class PlannerLLM(Protocol):
    async def complete(self, system: str, user: str) -> str:
        """Return the model's raw text response to (system, user)."""
        ...


class ApiKeyPlannerLLM:
    """Production backend (D-10): wraps breakdown/llm_client.call_llm (ANTHROPIC_API_KEY)."""

    async def complete(self, system: str, user: str) -> str:
        from dars.breakdown.llm_client import call_llm

        return await call_llm(system, user)


class AgentSdkPlannerLLM:
    """Development-only backend (D-10): wraps claude-agent-sdk against the dev's
    Claude Code OAuth session. The SDK is a dev/optional dependency and is
    imported lazily so production never requires it installed.
    """

    async def complete(self, system: str, user: str) -> str:
        try:
            from claude_agent_sdk import (  # type: ignore[import-not-found]
                ClaudeAgentOptions,
                query,
            )
        except ImportError as exc:  # pragma: no cover - exercised only in dev
            raise PlannerLLMError(
                "claude-agent-sdk is not installed; install the dev extra or use "
                "the api_key backend (PLANNER_LLM_BACKEND=api_key)"
            ) from exc

        chunks: list[str] = []
        try:
            async for message in query(
                prompt=user,
                options=ClaudeAgentOptions(system_prompt=system),
            ):
                # Assistant text lives in content blocks (TextBlock.text), not a
                # top-level .text attribute. Collect text from every block that
                # exposes a string `.text`.
                for block in getattr(message, "content", None) or []:
                    text = getattr(block, "text", None)
                    if isinstance(text, str):
                        chunks.append(text)
        except Exception as exc:  # pragma: no cover - dev path
            raise PlannerLLMError(f"agent-sdk query failed: {exc}") from exc
        return "".join(chunks)


def get_planner_llm(settings: Settings | None = None) -> PlannerLLM:
    """Factory selecting a backend by `settings.planner_llm_backend`.

    Default = api_key (production); the SDK backend is only returned when the
    dev flag explicitly sets `agent_sdk`.
    """
    settings = settings or default_settings
    backend = (getattr(settings, "planner_llm_backend", "api_key") or "api_key").lower()
    if backend == "agent_sdk":
        logger.info("get_planner_llm: selecting agent_sdk backend (development)")
        return AgentSdkPlannerLLM()
    logger.info("get_planner_llm: selecting api_key backend (production)")
    return ApiKeyPlannerLLM()


_SYSTEM_PROMPT = (
    "You are a curriculum planner. Given a chapter's topics, the sub-SLOs each "
    "topic teaches, and a fixed number of teaching periods, produce an ordered "
    "plan of exactly N periods. Each period is either a lesson (one LP that may "
    "combine several thin topics or focus on part of a dense one) or a formative "
    "assessment (FA) that checks sub-SLOs already taught. Sequence lessons before "
    "the FAs that assess them. Every topic must be taught by at least one lesson. "
    "Choose an lp_type for each lesson only from the allowed list. Cover all the "
    "chapter's sub-SLOs across the lessons. Place FAs where they best consolidate "
    "learning — you decide how many and where. Output strict JSON only, no prose, "
    "no markdown fences. Use only the topic_id and sub_slo_id values supplied; do "
    "not invent UUIDs. The JSON shape is:\n"
    '{"items": [{"kind": "lp", "topic_ids": ["<uuid>"], "lp_type": "<allowed>", '
    '"sub_slo_ids": ["<uuid>"]}, {"kind": "fa", "topic_ids": ["<uuid>"], '
    '"sub_slo_ids": ["<uuid>"]}]}'
)


def _build_user_prompt(inputs: PlanInputs) -> str:
    allowed = sorted(valid_lp_types_for_subject(inputs.subject_code))
    topics_payload = []
    for t in inputs.topics:
        text = t.topic_text or ""
        truncated = len(text) > _TOPIC_TEXT_BUDGET
        topics_payload.append(
            {
                "topic_id": str(t.topic_id),
                "title": t.title,
                "topic_text": text[:_TOPIC_TEXT_BUDGET],
                "topic_text_truncated": truncated,
                "sub_slos": [
                    {
                        "sub_slo_id": str(ss.sub_slo_id),
                        "code": ss.code,
                        "statement": ss.statement,
                    }
                    for ss in t.sub_slos
                ],
            }
        )
    payload = {
        "subject_code": inputs.subject_code,
        "period_count": inputs.period_count,
        "allowed_lp_types": allowed,
        "topics": topics_payload,
        "chapter_slos": [
            {
                "code": s.code,
                "statement": s.statement,
                "recommended_lp_type": s.recommended_lp_type,
            }
            for s in inputs.chapter_slos
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _strip_json_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        # Drop the opening fence line (``` or ```json) and the closing fence.
        first_newline = s.find("\n")
        if first_newline != -1:
            s = s[first_newline + 1 :]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


async def plan_with_llm(inputs: PlanInputs, *, llm: PlannerLLM) -> ChapterPlan:
    """Build the prompt (doc 05), call the LLM, parse JSON -> ChapterPlan(source='llm').

    Raises PlannerLLMError on transport or parse failure; the orchestrator
    catches it and routes to the deterministic fallback.
    """
    backend = type(llm).__name__
    logger.info(
        "plan_with_llm: entry subject=%s period_count=%d topic_count=%d backend=%s",
        inputs.subject_code,
        inputs.period_count,
        len(inputs.topics),
        backend,
    )
    user = _build_user_prompt(inputs)
    try:
        raw = await llm.complete(_SYSTEM_PROMPT, user)
    except PlannerLLMError:
        raise
    except Exception as exc:
        logger.error("plan_with_llm: transport failure backend=%s", backend, exc_info=True)
        raise PlannerLLMError(f"LLM transport failure: {exc}") from exc

    try:
        parsed = json.loads(_strip_json_fences(raw))
        plan = ChapterPlan.from_json(parsed, source="llm")
    except Exception as exc:
        logger.error(
            "plan_with_llm: parse failure backend=%s response_chars=%d",
            backend,
            len(raw or ""),
            exc_info=True,
        )
        raise PlannerLLMError(f"failed to parse LLM plan: {exc}") from exc

    logger.info(
        "plan_with_llm: exit subject=%s item_count=%d backend=%s",
        inputs.subject_code,
        len(plan.items),
        backend,
    )
    return plan


# ---------------------------------------------------------------------------
# F-1.4 — Deterministic fallback adapter
# ---------------------------------------------------------------------------


def plan_deterministic(inputs: PlanInputs) -> ChapterPlan:
    """Reuse the existing pure planners to build a validator-clean ChapterPlan.

    One-topic LP units (D-2: the fallback can't merge), FA items carrying their
    covered topic ids + the sub-SLOs of those topics. sa_per_chapter=0 (D-6);
    summative slots are dropped. Revision slots map to an LP unit of
    lp_type='revision'. source='fallback'.
    """
    logger.info(
        "plan_deterministic: entry subject=%s period_count=%d topic_count=%d",
        inputs.subject_code,
        inputs.period_count,
        len(inputs.topics),
    )
    period_count = inputs.period_count
    topics = inputs.topics
    topic_ids = [t.topic_id for t in topics]
    # sub-SLOs mapped to each topic.
    subs_by_topic: dict[UUID, list[UUID]] = {
        t.topic_id: [ss.sub_slo_id for ss in t.sub_slos] for t in topics
    }
    all_sub_slo_ids = [ss for subs in subs_by_topic.values() for ss in subs]

    allocation = allocate_chapter_days(
        chapter_days=period_count,
        topic_count=len(topics),
        fa_cadence=_FALLBACK_FA_CADENCE,
        sa_per_chapter=_FALLBACK_SA_PER_CHAPTER,
    )
    topic_lp_types = [
        pick_lp_type(
            subject_code=inputs.subject_code,
            topic_title=t.title,
            topic_text=t.topic_text,
            recommended_lp_type=None,
            sub_slo_recommended_lp_type=None,
        )
        for t in topics
    ]
    planned = plan_chapter_slots(
        topic_ids=topic_ids,
        topic_lp_types=topic_lp_types,
        allocation=allocation,
        fa_cadence=_FALLBACK_FA_CADENCE,
    )

    items: list[PlanItem] = []
    for slot in planned:
        if slot.slot_type == "summative_assessment":
            # D-6: no summative in the plan; should not occur with sa_per_chapter=0.
            continue
        if slot.slot_type == "lesson":
            t_subs = subs_by_topic.get(slot.topic_id, [])
            items.append(
                PlanItem(
                    kind="lp",
                    topic_ids=[slot.topic_id],
                    sub_slo_ids=t_subs,
                    lp_type=slot.lp_type,
                )
            )
        elif slot.slot_type == "revision":
            # Revision LP unit covers all topics / all sub-SLOs.
            items.append(
                PlanItem(
                    kind="lp",
                    topic_ids=list(topic_ids),
                    sub_slo_ids=list(all_sub_slo_ids),
                    lp_type=slot.lp_type or "revision",
                )
            )
        elif slot.slot_type == "formative_assessment":
            covered = list(slot.covered_topic_ids)
            fa_subs = [s for t in covered for s in subs_by_topic.get(t, [])]
            items.append(
                PlanItem(
                    kind="fa",
                    topic_ids=covered,
                    sub_slo_ids=fa_subs,
                )
            )

    plan = ChapterPlan(items=items, source="fallback")
    logger.info(
        "plan_deterministic: exit subject=%s item_count=%d",
        inputs.subject_code,
        len(plan.items),
    )
    return plan


# ---------------------------------------------------------------------------
# F-1.5 — Orchestrator: make_chapter_plan
# ---------------------------------------------------------------------------


async def make_chapter_plan(inputs: PlanInputs, *, llm: PlannerLLM) -> ChapterPlan:
    """Primary LLM path with the deterministic fallback (D-1). Never raises.

    1. Try plan_with_llm; on PlannerLLMError -> fallback (WARNING).
    2. validate_plan the LLM plan; on violations -> fallback (WARNING + reasons).
    3. Else return the LLM plan.
    The fallback is validator-clean (F-1.4); if it somehow fails, log ERROR and
    still return it (never block the teacher — D-1).
    """
    logger.info(
        "make_chapter_plan: entry subject=%s period_count=%d topic_count=%d",
        inputs.subject_code,
        inputs.period_count,
        len(inputs.topics),
    )
    try:
        plan = await plan_with_llm(inputs, llm=llm)
    except PlannerLLMError as exc:
        logger.warning(
            "make_chapter_plan: llm unavailable (%s) — falling back to deterministic",
            exc,
        )
        return _fallback(inputs)

    violations = validate_plan(plan, inputs)
    if violations:
        logger.warning(
            "make_chapter_plan: llm plan failed validation (%s) — falling back",
            "; ".join(violations),
        )
        return _fallback(inputs)

    logger.info(
        "make_chapter_plan: exit source=llm subject=%s item_count=%d",
        inputs.subject_code,
        len(plan.items),
    )
    return plan


def _fallback(inputs: PlanInputs) -> ChapterPlan:
    plan = plan_deterministic(inputs)
    residual = validate_plan(plan, inputs)
    if residual:
        logger.error(
            "make_chapter_plan: deterministic fallback itself failed validation "
            "(%s) — returning anyway (D-1, never block the teacher)",
            "; ".join(residual),
        )
    logger.info(
        "make_chapter_plan: exit source=fallback subject=%s item_count=%d",
        inputs.subject_code,
        len(plan.items),
    )
    return plan


# ---------------------------------------------------------------------------
# F-2.2 — Build PlanInputs from DB
# ---------------------------------------------------------------------------


async def build_plan_inputs(
    conn: "asyncpg.Connection",
    *,
    book_chapter_id: UUID,
    subject_code: str,
    period_count: int,
) -> PlanInputs:
    """Load the planner's inputs for one chapter from the v2 schema (F-2.2).

    - topics: `topics` for the chapter, ordered by `topic_number`, each with
      `title` / `topic_text`.
    - sub-SLOs per topic: `topic_sub_slos` → `sub_slos` (id, code, statement),
      ordered by `sub_slos.position` then `code` for stable ordering.
    - chapter SLOs: `book_chapter_slos` → `slos` (code, statement,
      recommended_lp_type), ordered by `slos.position`.

    All rows are scoped to the chapter already resolved upstream by
    `resolve_cst_syllabus_context` (the curriculum/grade/subject triple is
    fixed by `book_chapter_id`). Pure read; no writes.
    """
    logger.info(
        "build_plan_inputs: entry book_chapter_id=%s subject_code=%s period_count=%d",
        book_chapter_id,
        subject_code,
        period_count,
    )

    topic_rows = await conn.fetch(
        """
        SELECT id, title, topic_text
        FROM topics
        WHERE book_chapter_id = $1
        ORDER BY topic_number
        """,
        book_chapter_id,
    )

    sub_slos_by_topic: dict[UUID, list[SubSloInput]] = {}
    if topic_rows:
        sub_rows = await conn.fetch(
            """
            SELECT tss.topic_id AS topic_id,
                   ss.id        AS sub_slo_id,
                   ss.code      AS code,
                   ss.statement AS statement
            FROM topic_sub_slos tss
            JOIN sub_slos ss ON ss.id = tss.sub_slo_id
            WHERE tss.topic_id = ANY($1::uuid[])
            ORDER BY tss.topic_id, ss.position, ss.code
            """,
            [t["id"] for t in topic_rows],
        )
        for r in sub_rows:
            sub_slos_by_topic.setdefault(r["topic_id"], []).append(
                SubSloInput(
                    sub_slo_id=r["sub_slo_id"],
                    code=r["code"],
                    statement=r["statement"],
                )
            )

    topics = [
        TopicInput(
            topic_id=t["id"],
            title=t["title"] or "",
            topic_text=t["topic_text"] or "",
            sub_slos=sub_slos_by_topic.get(t["id"], []),
        )
        for t in topic_rows
    ]

    slo_rows = await conn.fetch(
        """
        SELECT s.code AS code, s.statement AS statement,
               s.recommended_lp_type AS recommended_lp_type
        FROM book_chapter_slos bcs
        JOIN slos s ON s.id = bcs.slo_id
        WHERE bcs.book_chapter_id = $1
        ORDER BY s.position
        """,
        book_chapter_id,
    )
    chapter_slos = [
        SloInput(
            code=r["code"],
            statement=r["statement"],
            recommended_lp_type=r["recommended_lp_type"],
        )
        for r in slo_rows
    ]

    inputs = PlanInputs(
        subject_code=subject_code,
        period_count=period_count,
        topics=topics,
        chapter_slos=chapter_slos,
    )
    logger.info(
        "build_plan_inputs: exit book_chapter_id=%s topic_count=%d "
        "sub_slo_count=%d chapter_slo_count=%d",
        book_chapter_id,
        len(topics),
        sum(len(t.sub_slos) for t in topics),
        len(chapter_slos),
    )
    return inputs


# ---------------------------------------------------------------------------
# F-2.3 — Persist a ChapterPlan (multi-topic aware)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PersistCounts:
    lesson_slot_count: int
    assessment_slot_count: int


async def persist_chapter_plan(
    conn: "asyncpg.Connection",
    *,
    cst_id: UUID,
    org_id: UUID,
    book_chapter_id: UUID,
    plan: ChapterPlan,
) -> PersistCounts:
    """Persist a ChapterPlan into the class slot tables (F-2.3, D-4, D-6).

    One transaction. LP units and FA items share a single per-CST position
    sequence (`greatest(max(class_lesson_slots.position),
    max(class_assessment_slots.position)) + 1` per item — mirrors
    `generate_chapter_plan`).

    Each `PlanItem`, in order:
      - LP unit → one `class_lesson_slots` row (slot_type 'revision' if
        lp_type == 'revision' else 'lesson'; topic_id = primary topic = first
        in topic_ids per D-4; book_chapter_id; status 'planned') THEN one
        `class_lesson_slot_topics` row per topic (position 1..N).
      - FA item → one `class_assessment_slots` row (assessment_type
        'formative', status 'scheduled', book_chapter_id) THEN
        `class_assessment_slot_topics` rows (position 1..N).
    """
    logger.info(
        "persist_chapter_plan: entry cst=%s chapter=%s item_count=%d source=%s",
        cst_id,
        book_chapter_id,
        len(plan.items),
        plan.source,
    )
    lesson_slot_count = 0
    assessment_slot_count = 0

    async with conn.transaction():
        pos = await conn.fetchval(
            """
            SELECT greatest(
              (SELECT coalesce(max(position), 0) FROM class_lesson_slots WHERE cst_id = $1),
              (SELECT coalesce(max(position), 0) FROM class_assessment_slots WHERE cst_id = $1)
            )
            """,
            cst_id,
        )
        for item in plan.items:
            pos += 1
            if item.kind == "lp":
                slot_type = "revision" if item.lp_type == "revision" else "lesson"
                primary_topic_id = item.topic_ids[0]  # D-4: primary topic
                slot_id = await conn.fetchval(
                    """
                    INSERT INTO class_lesson_slots
                      (org_id, cst_id, position, slot_type, lp_type, topic_id,
                       book_chapter_id, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'planned')
                    RETURNING id
                    """,
                    org_id, cst_id, pos, slot_type, item.lp_type,
                    primary_topic_id, book_chapter_id,
                )
                for i, t_id in enumerate(item.topic_ids, start=1):
                    await conn.execute(
                        """
                        INSERT INTO class_lesson_slot_topics
                          (class_lesson_slot_id, topic_id, position)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (class_lesson_slot_id, topic_id) DO NOTHING
                        """,
                        slot_id, t_id, i,
                    )
                lesson_slot_count += 1
            else:  # FA item (D-6: formative only)
                slot_id = await conn.fetchval(
                    """
                    INSERT INTO class_assessment_slots
                      (org_id, cst_id, position, assessment_type, book_chapter_id, status)
                    VALUES ($1, $2, $3, 'formative', $4, 'scheduled')
                    RETURNING id
                    """,
                    org_id, cst_id, pos, book_chapter_id,
                )
                for i, t_id in enumerate(item.topic_ids, start=1):
                    await conn.execute(
                        """
                        INSERT INTO class_assessment_slot_topics
                          (class_assessment_slot_id, topic_id, position)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (class_assessment_slot_id, topic_id) DO NOTHING
                        """,
                        slot_id, t_id, i,
                    )
                assessment_slot_count += 1

    logger.info(
        "persist_chapter_plan: exit cst=%s chapter=%s lessons=%d assessments=%d",
        cst_id,
        book_chapter_id,
        lesson_slot_count,
        assessment_slot_count,
    )
    return PersistCounts(
        lesson_slot_count=lesson_slot_count,
        assessment_slot_count=assessment_slot_count,
    )
