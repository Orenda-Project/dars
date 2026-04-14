import uuid
from datetime import datetime

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
    academic_year: str | None
    is_active: bool

    model_config = {"from_attributes": True}
