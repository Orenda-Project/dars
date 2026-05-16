"""Pydantic schemas for v2 holiday endpoints (F2.10)."""
from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class HolidayRead(BaseModel):
    date: date
    name: str | None = None
    source: str  # 'org' | 'school' | 'cst'
    action: str | None = None  # 'add' | 'remove' (for overrides only)


class HolidayListResponse(BaseModel):
    items: list[HolidayRead]
    effective_dates: list[date]  # final resolved set, sorted ascending


class OrgHolidayCreate(BaseModel):
    academic_year_id: UUID
    date: date
    name: str = Field(min_length=1)


class SchoolOverrideCreate(BaseModel):
    date: date
    name: str | None = None
    action: str = Field(description="'add' | 'remove'")


class CstOverrideCreate(BaseModel):
    date: date
    name: str | None = None
    action: str = Field(description="'add' | 'remove'")


class HolidayCreated(BaseModel):
    id: UUID
    date: date
