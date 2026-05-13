import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from dars.mapping import canonical_grade, canonical_subject


class GeneratedExamCreate(BaseModel):
    grade: int
    subject: str
    page_ranges: str
    generation_type: str = "exam"
    question_types: Optional[list[str]] = None
    seen_categories: Optional[list[str]] = None
    unseen_categories: Optional[list[str]] = None
    unseen_objective_types: Optional[list[str]] = None
    unseen_subjective_types: Optional[list[str]] = None
    unseen_objective_counts: Optional[dict[str, int]] = None
    unseen_subjective_counts: Optional[dict[str, int]] = None
    long_question_sub_types: Optional[list[str]] = None
    include_answer_key: bool = False
    image_generation_enabled: bool = False
    enable_review: bool = False
    external_id: Optional[str] = None

    @field_validator("subject", mode="before")
    @classmethod
    def normalise_subject(cls, v: str) -> str:
        return canonical_subject(v)

    @field_validator("grade", mode="before")
    @classmethod
    def normalise_grade(cls, v: int | str) -> int:
        return canonical_grade(v)


class GeneratedExamResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    external_id: Optional[str] = None
    status: str
    curriculum: str
    grade: int
    subject: str
    page_ranges: str
    generation_type: str
    eg_job_id: Optional[str] = None
    result: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GeneratedExamListResponse(BaseModel):
    items: list[GeneratedExamResponse]
    total: int
