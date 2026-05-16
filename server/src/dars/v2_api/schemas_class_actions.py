"""Pydantic schemas for teacher-facing class slot actions (F2.12, F2.13)."""
from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Mark-taught family (F2.12)
# ---------------------------------------------------------------------------


class MarkTaughtBody(BaseModel):
    taught_on: date | None = None  # default: today (server-side)
    notes: str | None = None


class SkipBody(BaseModel):
    occurred_on: date | None = None
    reason: str | None = None


class CompleteAssessmentBody(BaseModel):
    taught_on: date | None = None
    notes: str | None = None


class MarkActionResponse(BaseModel):
    cst_id: UUID
    slot_id: UUID
    slot_kind: str
    action: str
    occurred_on: date
    new_sequence_position: int
    sub_slo_coverage_updates: int = 0


# ---------------------------------------------------------------------------
# Onboarding (F2.13)
# ---------------------------------------------------------------------------


class OnboardBody(BaseModel):
    chapter_position: int = Field(ge=1)
    chapter_day: int = Field(ge=1)


class OnboardResponse(BaseModel):
    cst_id: UUID
    breakdown_id: UUID
    resolved_position: int
    joined_at_position: int


# ---------------------------------------------------------------------------
# Sub-SLO coverage report (F2.12)
# ---------------------------------------------------------------------------


class SubSLOCoverageEntry(BaseModel):
    sub_slo_id: UUID
    sub_slo_code: str
    status: str  # 'taught' | 'not_taught' | 'unknown'


class SubSLOCoverageResponse(BaseModel):
    cst_id: UUID
    joined_at_position: int
    items: list[SubSLOCoverageEntry]
