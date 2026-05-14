import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from dars.mapping import canonical_curriculum, canonical_grade, canonical_subject


class LessonPlanCreateRequest(BaseModel):
    grade: int
    subject: str
    page_number: str = ""
    curriculum: str = "ICT"
    class_strength: int | None = None
    topic: str | None = None
    external_ref: str | None = None
    exercise_page_number: str = ""
    custom_prompt: str = ""
    generate_bilingual: bool = False
    webhook_url: str | None = None

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


class LessonPlanResponse(BaseModel):
    id: uuid.UUID
    status: str
    grade: str
    subject: str
    curriculum: str = "ICT"
    topic: str | None = None
    page_number: str | None = None
    class_strength: int | None = None
    webhook_url: str | None = None
    content: str | None = None
    content_bilingual: str | None = None
    tags: dict = {}
    metadata_: dict = {}
    external_ref: str | None = None
    topic_text: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LessonPlanListResponse(BaseModel):
    items: list[LessonPlanResponse]
    total: int
