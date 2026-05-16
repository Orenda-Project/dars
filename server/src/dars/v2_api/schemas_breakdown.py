"""Pydantic schemas for v2 breakdown CRUD (F2.4)."""
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Read models
# ---------------------------------------------------------------------------


class BreakdownSlotTopicRead(BaseModel):
    topic_id: UUID
    position: int


class BreakdownSlotRead(BaseModel):
    id: UUID
    breakdown_id: UUID
    breakdown_chapter_id: UUID
    position: int
    chapter_position: int
    slot_type: str
    lp_type: str | None
    topic_id: UUID | None
    anchor_date: date | None
    extra_topics: list[BreakdownSlotTopicRead] = []
    created_at: datetime
    updated_at: datetime


class BreakdownChapterRead(BaseModel):
    id: UUID
    breakdown_id: UUID
    book_chapter_id: UUID
    position: int
    teaching_days: int


class BreakdownRead(BaseModel):
    id: UUID
    scope: str
    scope_ref_id: UUID | None
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    book_id: UUID | None
    parent_breakdown_id: UUID | None
    previous_version_id: UUID | None
    status: str
    total_teaching_days: int | None
    created_at: datetime
    updated_at: datetime
    chapters: list[BreakdownChapterRead] = []
    slots: list[BreakdownSlotRead] = []


class BreakdownListItem(BaseModel):
    id: UUID
    scope: str
    scope_ref_id: UUID | None
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    book_id: UUID | None
    status: str
    total_teaching_days: int | None
    created_at: datetime
    updated_at: datetime


class BreakdownListResponse(BaseModel):
    items: list[BreakdownListItem]


# ---------------------------------------------------------------------------
# Write models
# ---------------------------------------------------------------------------


class BreakdownCreate(BaseModel):
    scope: str = Field(description="'global' | 'org' | 'class'")
    scope_ref_id: UUID | None = None
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    book_id: UUID
    total_teaching_days: int | None = None


class BreakdownUpdate(BaseModel):
    total_teaching_days: int | None = None
    book_id: UUID | None = None


class BreakdownChapterCreate(BaseModel):
    book_chapter_id: UUID
    position: int
    teaching_days: int


class BreakdownChapterUpdate(BaseModel):
    position: int | None = None
    teaching_days: int | None = None


class BreakdownSlotCreate(BaseModel):
    breakdown_chapter_id: UUID
    position: int
    chapter_position: int
    slot_type: str
    lp_type: str | None = None
    topic_id: UUID | None = None
    anchor_date: date | None = None
    extra_topic_ids: list[UUID] = Field(
        default_factory=list,
        description="Additional topics covered (e.g. for assessment slots). The primary topic_id is recorded separately.",
    )


class BreakdownSlotUpdate(BaseModel):
    position: int | None = None
    chapter_position: int | None = None
    slot_type: str | None = None
    lp_type: str | None = None
    topic_id: UUID | None = None
    anchor_date: date | None = None


# ---------------------------------------------------------------------------
# Auto-build (F2.5)
# ---------------------------------------------------------------------------


class AutoBuildBody(BaseModel):
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    book_id: UUID
    total_teaching_days: int = 180
    fa_cadence: int = Field(default=5, ge=1)
    sa_per_chapter: int = Field(default=1, ge=0)
    scope: str = "global"
    scope_ref_id: UUID | None = None


class AutoBuildResponse(BaseModel):
    breakdown_id: UUID
    chapter_count: int
    lesson_slot_count: int
    fa_slot_count: int
    sa_slot_count: int
    revision_slot_count: int
    total_slot_count: int
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# Sub-SLO breakdown trigger (F2.6)
# ---------------------------------------------------------------------------


class SubSLOBreakdownResponse(BaseModel):
    slo_id: UUID
    subject_key: str
    inserted_sub_slo_count: int
    skipped: bool
    raw_response_chars: int


class SubSLOBulkRequest(BaseModel):
    slo_ids: list[UUID] = Field(min_length=1)
    force: bool = False


class SubSLOBulkAccepted(BaseModel):
    accepted_slo_count: int
    skipped_slo_count: int
    grouped_by_subject: dict[str, int]
    # When sync=False (default), the work runs in BackgroundTasks; this list
    # is the SLOs that were queued. With sync=true, this is just the input.
    queued_slo_ids: list[UUID]


# ---------------------------------------------------------------------------
# Fork + realize (F2.7, F2.9)
# ---------------------------------------------------------------------------


class ForkOrgBody(BaseModel):
    org_id: UUID


class ForkClassBody(BaseModel):
    cst_id: UUID


class ForkResponse(BaseModel):
    new_breakdown_id: UUID
    parent_breakdown_id: UUID
    new_scope: str
    scope_ref_id: UUID
    copied_chapter_count: int
    copied_slot_count: int


class RealizeResponse(BaseModel):
    breakdown_id: UUID
    cst_id: UUID
    lesson_slots_upserted: int
    assessment_slots_upserted: int
    assessment_topics_inserted: int
    skipped: list[str] = []


# ---------------------------------------------------------------------------
# Anchor (F2.11)
# ---------------------------------------------------------------------------


class AnchorUpdate(BaseModel):
    # null clears the anchor.
    anchor_date: date | None = None
