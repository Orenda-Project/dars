import uuid
from datetime import date, datetime

from pydantic import BaseModel


class GradeResponse(BaseModel):
    id: uuid.UUID
    label: str
    short_code: str
    order_index: int

    model_config = {"from_attributes": True}


class SubjectResponse(BaseModel):
    id: uuid.UUID
    label: str
    short_code: str

    model_config = {"from_attributes": True}


class CurriculumResponse(BaseModel):
    id: uuid.UUID
    name: str
    book_id: int
    provider_id: uuid.UUID
    is_default: bool
    teacher_id: uuid.UUID | None
    client_id: uuid.UUID | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
