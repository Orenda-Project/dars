import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class LessonPlanEditRequest(BaseModel):
    edit_prompt: str
    grade: str
    subject: str
    page_number: str
    curriculum: str = "ICT"
    class_strength: int | None = None


class LessonPlanCreateRequest(BaseModel):
    grade: str
    subject: str
    page_number: str
    curriculum: str = "ICT"
    class_strength: int | None = None
    topic: str | None = None
    external_ref: str | None = None
    exercise_page_number: str = ""
    custom_prompt: str = ""
    generate_bilingual: bool = False


class LessonPlanResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    external_ref: str | None
    grade: str
    subject: str
    topic: str | None
    page_number: str | None
    class_strength: int | None
    content: str | None
    content_bilingual: str | None
    status: str
    metadata_: dict[str, Any]
    tags: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LessonPlanListResponse(BaseModel):
    items: list[LessonPlanResponse]
    total: int
