import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AssessmentResponse(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    status: str
    content: str | None = None
    content_json: list[Any] | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
