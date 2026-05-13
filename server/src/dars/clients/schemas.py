from datetime import datetime

from pydantic import BaseModel


class ClientCreateRequest(BaseModel):
    name: str


class ClientCreateResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    created_at: datetime
    api_key: str  # raw key — shown once only

    model_config = {"from_attributes": True}


class ClientPublicResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    webhook_url: str | None = None
    curriculum_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClientUpdateRequest(BaseModel):
    webhook_url: str | None = None


class ClientSelfUpdateRequest(BaseModel):
    curriculum: str | None = None  # code, resolved to curriculum_id on update
    webhook_url: str | None = None


class ClientAdminResponse(BaseModel):
    id: int
    name: str
    email: str | None = None
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ClientListResponse(BaseModel):
    items: list[ClientAdminResponse]
