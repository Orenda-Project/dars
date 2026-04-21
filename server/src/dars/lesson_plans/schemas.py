import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, model_validator


class LessonPlanEditRequest(BaseModel):
    edit_prompt: str


class LessonPlanReviewRequest(BaseModel):
    lesson_plan_id: uuid.UUID | None = None
    lesson_plan_html: str | None = None
    subject: str | None = None
    grade: int | None = None

    @model_validator(mode="after")
    def validate_source_and_fields(self) -> "LessonPlanReviewRequest":
        has_id = self.lesson_plan_id is not None
        has_html = self.lesson_plan_html is not None
        if has_id == has_html:
            raise ValueError(
                "Provide exactly one of 'lesson_plan_id' or 'lesson_plan_html'."
            )
        if has_html:
            if self.subject is None or self.grade is None:
                raise ValueError(
                    "'subject' and 'grade' are required when 'lesson_plan_html' is provided."
                )
        return self


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
    review: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LessonPlanReviewResponse(BaseModel):
    review: dict[str, Any]


class LessonPlanListResponse(BaseModel):
    items: list[LessonPlanResponse]
    total: int
