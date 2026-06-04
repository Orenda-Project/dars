"""
Pydantic contracts for the Chapter Planning Engine (CPE).

Schemas match docs/features/chapter-planner-engine/02-data-model.md exactly
(ground truth, precedence #2). Pydantic v2 style.
"""
from typing import List
from pydantic import BaseModel, Field, field_validator, model_validator

from config import VALID_LP_TYPES


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
class PlanUnit(BaseModel):
    sequence: int = Field(..., description="1..period_count, a permutation (D-8e)")
    lp_type: str = Field(..., description="∈ VALID_LP_TYPES[subject] (D-5)")
    topic_ids: List[str] = Field(..., description="ordered, ≥1 (D-4)")
    slo_ids: List[str] = Field(..., description="≥1, ⊆ chapter SLOs (D-8b,d)")
    topic_text: str = Field(..., description="member topics' text, joined in topic_ids order (D-4)")
    rationale: str


class ChapterPlan(BaseModel):
    subject: str
    grade: int
    curriculum: str
    period_count: int
    units: List[PlanUnit]
