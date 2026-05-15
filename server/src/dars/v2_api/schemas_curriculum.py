"""Pydantic response schemas for v2 curriculum entities (F1.7)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GradeRead(BaseModel):
    id: UUID
    code: int
    display_name: str


class GradeListResponse(BaseModel):
    items: list[GradeRead]


class SubjectRead(BaseModel):
    id: UUID
    code: str
    display_name: str


class SubjectListResponse(BaseModel):
    items: list[SubjectRead]


class CurriculumRead(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    is_active: bool


class CurriculumListResponse(BaseModel):
    items: list[CurriculumRead]


class SubSLORead(BaseModel):
    id: UUID
    slo_id: UUID
    code: str
    statement: str
    position: int
    source: str


class SLORead(BaseModel):
    id: UUID
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    code: str
    statement: str
    domain: str | None
    position: int
    recommended_lp_type: str | None
    sub_slos: list[SubSLORead] = []
    created_at: datetime
    updated_at: datetime


class SLOListResponse(BaseModel):
    items: list[SLORead]


class SubSLOListResponse(BaseModel):
    items: list[SubSLORead]
