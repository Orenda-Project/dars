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
    breakdown_chapter_id: UUID | None = None
    breakdown_chapter_position: int | None = None
    breakdown_chapter_title: str | None = None


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
    breakdown_chapter_id: UUID | None = None
    breakdown_chapter_position: int | None = None
    breakdown_chapter_title: str | None = None


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
    breakdown_chapter_id: UUID | None = None
    breakdown_chapter_position: int | None = None
    breakdown_chapter_title: str | None = None


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
    breakdown_chapter_id: UUID | None = None
    breakdown_chapter_position: int | None = None
    breakdown_chapter_title: str | None = None


TimelineItem = Annotated[
    Union[TimelineLessonItem, TimelineAssessmentItem],
    Field(discriminator="kind"),
]


class CstTimelineResponse(BaseModel):
    cst_id: UUID
    items: list[TimelineItem]
    # F-1.4 (dynamic-chapter-planner): count of tail slots the projector could
    # not land on a teaching day (ProjectedSlot.is_overflow). 0 when the plan
    # fits the academic year; > 0 means the class is genuinely behind and a
    # human alert should fire. Surfaced here so Case-1 (holidays push slots past
    # year-end) is visible before reteach exists. No new projection logic — the
    # projector already sets the flag per item.
    overflow_count: int = 0


# ---------------------------------------------------------------------------
# Teacher Chapter Plan — syllabus view + break-it-down (Phase 3)
# ---------------------------------------------------------------------------


# Teacher-adjustable syllabus (Phase 1): the class's own teaching path
# (`class_chapters`), not the advisory global. Each entry is a chapter the
# teacher picked, in teaching order, with teacher-set dates + derived status.


class ClassPathChapter(BaseModel):
    book_chapter_id: UUID
    chapter_number: int
    title: str
    position: int  # teaching order within the class path (1..N)
    start_date: date | None  # teacher-set (D-7); None until dated
    end_date: date | None
    # D-9/D-14: real teaching periods in the range for THIS class (0 if no dates).
    # This is CAPACITY (non-zero as soon as dates are set), NOT a sign the
    # chapter is generated — use `is_generated` for that.
    slot_count: int
    # True once the chapter has actually been broken down (has generated class
    # slots). Distinct from slot_count; drives "Broken down ✓" + the button.
    is_generated: bool = False
    # D-4: derived from the chapter's class slots.
    status: str  # 'yet_to_start' | 'in_progress' | 'done'


class SyllabusForCstResponse(BaseModel):
    cst_id: UUID
    syllabus_breakdown_id: UUID | None  # the org breakdown the path mirrors; None if none published
    periods_per_week: int
    chapters: list[ClassPathChapter]  # the read-only class path, ordered by position


class GenerateChapterPlanResponse(BaseModel):
    cst_id: UUID
    book_chapter_id: UUID
    slot_count: int
    lesson_slot_count: int
    assessment_slot_count: int
    # dynamic-chapter-planner F-2.3: how many lesson slots are droppable flex
    # (revision) buffer (subset of lesson_slot_count). 0 for short chapters.
    flex_slot_count: int = 0
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# Reteach trigger (dynamic-chapter-planner Phase 3, F-3.1/F-3.2/F-3.3)
#
# A graded formative-assessment slot whose per-sub-SLO mastery is below
# RETEACH_MASTERY_THRESHOLD surfaces a suggestion (read); the teacher then
# confirms an explicit lightweight|heavy action (D-9 — never auto-applied).
# ---------------------------------------------------------------------------


class ReteachSuggestionItem(BaseModel):
    sub_slo_id: UUID
    sub_slo_code: str
    statement: str
    mastery_percent: float  # below the threshold


class ReteachSuggestionResponse(BaseModel):
    class_assessment_slot_id: UUID
    threshold: float
    # Empty when nothing is below threshold (no badge shown).
    items: list[ReteachSuggestionItem]


class ReteachActionBody(BaseModel):
    sub_slo_id: UUID
    # Explicit teacher choice (D-9). 'lightweight' (default) flips coverage to
    # needs-rework; 'heavy' consumes a flex slot (no shift) or inserts one.
    mode: Literal["lightweight", "heavy"] = "lightweight"


class OverflowConsequencePayload(BaseModel):
    """Year-end consequence of an insert (D-17). Present only when the heavy
    path had to INSERT (no downstream flex); null otherwise."""
    overflow_before: int
    overflow_after: int
    newly_overflowed_positions: list[int]
    first_overflow_position: int | None


class ReteachActionResponse(BaseModel):
    class_assessment_slot_id: UUID
    sub_slo_id: UUID
    # 'lightweight' | 'consume_flex' | 'insert'
    path: str
    # The reteach lesson slot for the heavy paths; null for lightweight.
    reteach_slot_id: UUID | None = None
    # Populated only for the 'insert' path (the only one that can overflow).
    consequence: OverflowConsequencePayload | None = None
