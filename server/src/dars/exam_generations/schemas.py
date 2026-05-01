import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from dars.mapping import canonical_curriculum, canonical_grade, canonical_subject


class ExamGenerationCreateRequest(BaseModel):
    generation_type: str = "exam"
    curriculum: str = "ICT"
    grade: int
    subject: str

    @field_validator("subject", mode="before")
    @classmethod
    def normalise_subject(cls, v: str) -> str:
        return canonical_subject(v)

    @field_validator("curriculum", mode="before")
    @classmethod
    def normalise_curriculum(cls, v: str) -> str:
        return canonical_curriculum(v)

    @field_validator("grade", mode="before")
    @classmethod
    def normalise_grade(cls, v: int | str) -> int:
        return canonical_grade(v)
    page_ranges: str
    custom_system_prompt: Optional[str] = None
    question_types: list[str]
    seen_categories: Optional[list[str]] = None
    unseen_categories: Optional[list[str]] = None
    unseen_objective_types: Optional[list[str]] = None
    unseen_subjective_types: Optional[list[str]] = None
    unseen_objective_counts: Optional[dict] = None
    unseen_subjective_counts: Optional[dict] = None
    long_question_sub_types: Optional[list[str]] = None
    image_generation_enabled: bool = False
    include_answer_key: bool = False
    enable_review: bool = False
    webhook_url: Optional[str] = None
    external_ref: Optional[str] = None


class ExamGenerationResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    curriculum: str
    grade: int
    subject: str
    page_ranges: str
    generation_type: str
    status: str
    result: Optional[dict] = None
    error_detail: Optional[str] = None
    external_ref: Optional[str] = None
    webhook_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExamGenerationListResponse(BaseModel):
    items: list[ExamGenerationResponse]
    total: int
