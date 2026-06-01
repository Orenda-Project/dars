"""Pydantic schemas for teacher-facing class slot actions (F2.12, F2.13)."""
from datetime import date
from typing import Annotated, Literal, Union
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


# ---------------------------------------------------------------------------
# Class slot listings (F4.6/F4.7) — used by the teacher app to render
# the full Lessons / Assessments tabs grouped by breakdown chapter.
# ---------------------------------------------------------------------------


class ClassLessonSlotListItem(BaseModel):
    id: UUID
    cst_id: UUID
    position: int
    slot_type: str  # 'lesson' | 'revision'
    lp_type: str | None
    topic_id: UUID | None
    topic_title: str | None
    anchor_date: date | None
    status: str  # 'planned' | 'taught' | 'skipped'
    generated_lp_id: UUID | None
    lp_status: str  # 'not_generated' | 'PENDING' | 'IN_FLIGHT' | 'READY' | 'ERROR'
    # Breakdown chapter context — drives the grouped UI.
    breakdown_chapter_id: UUID
    breakdown_chapter_position: int
    breakdown_chapter_title: str


class ClassLessonSlotListResponse(BaseModel):
    cst_id: UUID
    items: list[ClassLessonSlotListItem]


class ClassAssessmentSlotListItem(BaseModel):
    id: UUID
    cst_id: UUID
    position: int
    assessment_type: str  # 'formative' | 'summative'
    anchor_date: date | None
    status: str  # 'scheduled' | 'completed' | 'skipped'
    generated_exam_id: UUID | None
    exam_status: str
    topic_ids: list[UUID]
    topic_titles: list[str]
    breakdown_chapter_id: UUID
    breakdown_chapter_position: int
    breakdown_chapter_title: str


class ClassAssessmentSlotListResponse(BaseModel):
    cst_id: UUID
    items: list[ClassAssessmentSlotListItem]


# ---------------------------------------------------------------------------
# Unified timeline (class-timeline-view feature; D-3/D-4).
#
# Lessons + assessments interleaved by `position`, each stamped with the
# projector's `projected_date` and conflict/overflow flags. A kind-tagged
# discriminated union so the frontend renders both in one ordered list.
# Field names mirror the per-kind list items above + four projector fields.
# ---------------------------------------------------------------------------


class TimelineLessonItem(BaseModel):
    kind: Literal["lesson"] = "lesson"
    id: UUID
    position: int
    projected_date: date | None
    is_anchor: bool
    is_conflict: bool
    is_overflow: bool
    slot_type: str  # 'lesson' | 'revision'
    lp_type: str | None
    topic_id: UUID | None
    topic_title: str | None
    status: str  # 'planned' | 'taught' | 'skipped'
    generated_lp_id: UUID | None
    lp_status: str
    breakdown_chapter_id: UUID
    breakdown_chapter_position: int
    breakdown_chapter_title: str


class TimelineAssessmentItem(BaseModel):
    kind: Literal["assessment"] = "assessment"
    id: UUID
    position: int
    projected_date: date | None
    is_anchor: bool
    is_conflict: bool
    is_overflow: bool
    assessment_type: str  # 'formative' | 'summative'
    topic_ids: list[UUID]
    topic_titles: list[str]
    status: str  # 'scheduled' | 'completed' | 'skipped'
    generated_exam_id: UUID | None
    exam_status: str
    breakdown_chapter_id: UUID
    breakdown_chapter_position: int
    breakdown_chapter_title: str


TimelineItem = Annotated[
    Union[TimelineLessonItem, TimelineAssessmentItem],
    Field(discriminator="kind"),
]


class CstTimelineResponse(BaseModel):
    cst_id: UUID
    items: list[TimelineItem]
