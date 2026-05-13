import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from dars.mapping import canonical_grade, canonical_subject


class GeneratedLPCreate(BaseModel):
    grade: int
    subject: str
    topic: Optional[str] = None
    page_number: Optional[str] = None
    class_strength: Optional[int] = None
    lp_type: Optional[str] = None
    external_id: Optional[str] = None
    generate_bilingual: bool = False

    @field_validator("subject", mode="before")
    @classmethod
    def normalise_subject(cls, v: str) -> str:
        return canonical_subject(v)

    @field_validator("grade", mode="before")
    @classmethod
    def normalise_grade(cls, v: int | str) -> int:
        return canonical_grade(v)


class GeneratedLPResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    external_id: Optional[str] = None
    status: str
    grade: str
    subject: str
    curriculum: str
    topic: Optional[str] = None
    page_number: Optional[str] = None
    class_strength: Optional[int] = None
    lp_type: Optional[str] = None
    content: Optional[str] = None
    content_bilingual: Optional[str] = None
    tags: dict = {}
    metadata_: dict = {}
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GeneratedLPListResponse(BaseModel):
    items: list[GeneratedLPResponse]
    total: int
