from datetime import datetime

from pydantic import BaseModel, EmailStr


class TeacherRegisterRequest(BaseModel):
    name: str
    email: EmailStr | None = None
    phone: str | None = None
    school: str | None = None


class TeacherUpdateRequest(BaseModel):
    name: str | None = None
    phone: str | None = None
    school: str | None = None
    is_active: bool | None = None


class TeacherResponse(BaseModel):
    id: int
    client_id: int
    name: str
    email: str | None
    phone: str | None
    school: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeacherListResponse(BaseModel):
    items: list[TeacherResponse]
    total: int
