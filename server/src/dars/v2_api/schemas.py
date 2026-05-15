"""Pydantic response schemas for v2 endpoints."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class OrgRead(BaseModel):
    id: UUID
    name: str
    curriculum_id: UUID
    api_key_prefix: str
    default_teacher_id: UUID | None
    created_at: datetime
    updated_at: datetime


class SchoolRead(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class SchoolListResponse(BaseModel):
    items: list[SchoolRead]


class TeacherRead(BaseModel):
    id: UUID
    org_id: UUID
    school_id: UUID
    name: str
    email: str | None
    created_at: datetime
    updated_at: datetime


class TeacherListResponse(BaseModel):
    items: list[TeacherRead]


class AcademicYearRead(BaseModel):
    id: UUID
    org_id: UUID
    school_id: UUID
    name: str
    start_date: date
    end_date: date
    created_at: datetime
    updated_at: datetime


class AcademicYearListResponse(BaseModel):
    items: list[AcademicYearRead]


class SchoolClassRead(BaseModel):
    id: UUID
    org_id: UUID
    school_id: UUID
    academic_year_id: UUID
    grade_id: UUID
    section: str
    name: str
    created_at: datetime
    updated_at: datetime


class SchoolClassListResponse(BaseModel):
    items: list[SchoolClassRead]


class CSTRead(BaseModel):
    id: UUID
    org_id: UUID
    school_class_id: UUID
    subject_id: UUID
    teacher_id: UUID | None
    book_id: UUID | None
    created_at: datetime
    updated_at: datetime
    # Computed fields appended in the per-resource GET (not in list response):
    current_sequence_position: int | None = None


class CSTListResponse(BaseModel):
    items: list[CSTRead]
