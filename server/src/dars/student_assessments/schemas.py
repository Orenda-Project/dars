import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class StudentAssessmentResponse(BaseModel):
    id: uuid.UUID
    lesson_plan_id: uuid.UUID
    status: str
    content_json: list[Any] | None = None
    answers_json: list[Any] | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
