"""
Pydantic contracts for the Chapter Planner (ported from chapter-planner-app/models.py).

Frozen I/O contract — see
docs/features/chapter-planner-in-dars/05-reference-planner-contract.md.
Pydantic v2 style.

`VALID_LP_TYPES` is ported verbatim from the reference doc (originally from
UG_LessonPlan/config.py). It is intentionally the single source of truth for the
planner: the existing v2_api constants (`lp_types.LP_TYPES_BY_SUBJECT`,
`lp_type_classifier.VALID_LP_TYPES`) have a different shape/coverage and do not
carry all seven subjects with ordered lists that the frozen planner contract
(D-5) requires. See docs/features/chapter-planner-in-dars/03-phase-1-port-planner.md.
"""
from typing import List

from pydantic import BaseModel, Field, field_validator, model_validator

# ============================================================================
# Valid lp_type values per subject (D-5)
# Copied VERBATIM from UG_LessonPlan/config.py::VALID_LP_TYPES via the frozen
# reference doc. The LLM picks lp_type only from the list for the request's
# subject; ordering is load-bearing for the stub planner (first allowed type).
# ============================================================================
VALID_LP_TYPES: dict[str, list[str]] = {
    "Eng":      ["reading", "comprehension_word_meanings", "comprehension_qa", "grammar", "creative_writing", "revision"],
    "Urdu":     ["reading", "comprehension_word_meanings", "comprehension_qa", "grammar", "creative_writing", "revision"],
    "Maths":    ["concrete", "pictorial_and_abstract", "word_problems", "revision"],
    "Science":  ["revision"],
    "GK":       ["revision"],
    "Islamiat": ["revision"],
    "SST":      ["revision"],
}

VALID_SUBJECTS = list(VALID_LP_TYPES.keys())


# ============================================================================
# Input — POST /plan
# ============================================================================
class SLO(BaseModel):
    id: str = Field(..., description="Stable within request; LLM references these")
    statement: str = Field(..., description="The SLO statement")


class Topic(BaseModel):
    id: str = Field(..., description="Stable within request; LLM references these")
    topic_text: str = Field(..., description="Source text for the topic")
    slos: List[SLO] = Field(..., description="≥1 SLO per topic")

    @field_validator("slos")
    @classmethod
    def _at_least_one_slo(cls, v: List[SLO]) -> List[SLO]:
        if len(v) < 1:
            raise ValueError("each topic must have at least 1 SLO")
        return v


class Chapter(BaseModel):
    title: str
    topics: List[Topic] = Field(..., description="≥1 topic")

    @field_validator("topics")
    @classmethod
    def _at_least_one_topic(cls, v: List[Topic]) -> List[Topic]:
        if len(v) < 1:
            raise ValueError("chapter must have at least 1 topic")
        return v

    @model_validator(mode="after")
    def _unique_ids(self) -> "Chapter":
        topic_ids = [t.id for t in self.topics]
        if len(topic_ids) != len(set(topic_ids)):
            raise ValueError("topic ids must be unique within the chapter")
        # A sub-SLO (SLO id) MAY appear on more than one topic — the same skill
        # is often taught across several topics. That's a valid shape, not a
        # duplicate: it maps to one chapter-wide SLO that the planner must cover
        # once. We only reject the same id carrying a DIFFERENT statement
        # (genuinely inconsistent data); identical repeats are fine.
        statement_by_id: dict[str, str] = {}
        for t in self.topics:
            for s in t.slos:
                prior = statement_by_id.get(s.id)
                if prior is not None and prior != s.statement:
                    raise ValueError(
                        f"SLO id {s.id!r} appears with two different statements"
                    )
                statement_by_id[s.id] = s.statement
        return self


class PlanRequest(BaseModel):
    subject: str = Field(..., description="∈ VALID_LP_TYPES keys; drives allowed lp_types")
    grade: int = Field(..., description="1..5")
    curriculum: str = Field(default="ICT", description="passed through to UG_LP")
    period_count: int = Field(..., description="> 0; number of Plan Units to produce")
    chapter: Chapter

    @field_validator("period_count")
    @classmethod
    def _period_count_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("period_count must be > 0")
        return v

    @field_validator("grade")
    @classmethod
    def _grade_in_range(cls, v: int) -> int:
        if not (1 <= v <= 5):
            raise ValueError("grade must be between 1 and 5")
        return v

    @field_validator("subject")
    @classmethod
    def _subject_valid(cls, v: str) -> str:
        if v not in VALID_LP_TYPES:
            raise ValueError(f"subject must be one of {list(VALID_LP_TYPES.keys())}")
        return v


# ============================================================================
# Output — 200 ChapterPlan
# ============================================================================

# Allowed slot_type values for a PlanUnit (exam-periods-and-formative-assessments
# D-6, D-12, D-13). Summative is deliberately NOT allowed here (D-12/D-16).
VALID_SLOT_TYPES: set[str] = {"lesson", "formative_assessment"}


class PlanUnit(BaseModel):
    sequence: int = Field(..., description="1..period_count, a permutation (D-8e)")
    slot_type: str = Field(
        default="lesson",
        description="'lesson' | 'formative_assessment' (D-6, D-12, D-13). "
        "Omitted ⇒ 'lesson' for back-compat (D-13).",
    )
    lp_type: str | None = Field(
        default=None,
        description="∈ VALID_LP_TYPES[subject] for lessons (D-5); None for FA units (D-7)",
    )
    topic_ids: List[str] = Field(..., description="ordered, ≥1 (D-4)")
    slo_ids: List[str] = Field(..., description="≥1, ⊆ chapter SLOs (D-8b,d)")
    topic_text: str = Field(..., description="member topics' text, joined in topic_ids order (D-4)")
    rationale: str

    @field_validator("slot_type")
    @classmethod
    def _slot_type_allowed(cls, v: str) -> str:
        if v not in VALID_SLOT_TYPES:
            raise ValueError(
                f"slot_type must be one of {sorted(VALID_SLOT_TYPES)} (D-6, D-12)"
            )
        return v

    @model_validator(mode="after")
    def _lp_type_matches_slot_type(self) -> "PlanUnit":
        # D-7: a lesson MUST carry an lp_type; an FA MUST NOT. The subject-
        # membership check (lp_type ∈ VALID_LP_TYPES[subject]) stays in
        # validate_plan, where the request (and thus the subject) is available.
        if self.slot_type == "lesson":
            if not self.lp_type:
                raise ValueError("lesson unit requires an lp_type (D-7)")
        elif self.slot_type == "formative_assessment":
            if self.lp_type is not None:
                raise ValueError(
                    "formative_assessment unit must not carry an lp_type (D-7)"
                )
        return self


class ChapterPlan(BaseModel):
    subject: str
    grade: int
    curriculum: str
    period_count: int
    units: List[PlanUnit]
