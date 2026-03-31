import uuid
from datetime import datetime

from pydantic import BaseModel


class ClientCreateRequest(BaseModel):
    name: str


class ClientCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime
    api_key: str  # raw key — shown once only

    model_config = {"from_attributes": True}


class ClientPublicResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    webhook_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClientUpdateRequest(BaseModel):
    webhook_url: str | None = None
