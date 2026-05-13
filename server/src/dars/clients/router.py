import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.clients.schemas import (
    ClientAdminResponse,
    ClientCreateRequest,
    ClientCreateResponse,
    ClientListResponse,
    ClientPublicResponse,
    ClientSelfUpdateRequest,
    ClientUpdateRequest,
)
from dars.clients.service import create_client, rotate_api_key, update_client
from dars.database import get_db
from dars.deps import get_admin_client, get_current_client, require_admin_secret

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/admin", tags=["admin"])
client_router = APIRouter(prefix="/api/v1", tags=["clients"])

CURRICULUM_NAMES = {
    "NCP": "National Curriculum of Pakistan",
    "SNC": "Single National Curriculum",
}


@admin_router.post(
    "/clients",
    status_code=status.HTTP_201_CREATED,
    response_model=ClientCreateResponse,
    dependencies=[Depends(require_admin_secret)],
)
async def create_client_endpoint(
    body: ClientCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ClientCreateResponse:
    logger.info("create_client_endpoint: name=%s", body.name)
    client, raw_key = await create_client(db, name=body.name)
    logger.info("create_client_endpoint: done client_id=%s", client.id)
    return ClientCreateResponse(
        id=client.id,
        name=client.name,
        is_active=client.is_active,
        created_at=client.created_at,
        api_key=raw_key,
    )


@admin_router.patch(
    "/clients/{client_id}",
    response_model=ClientPublicResponse,
    dependencies=[Depends(require_admin_secret)],
)
async def update_client_endpoint(
    client_id: int,
    body: ClientUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ClientPublicResponse:
    logger.info("update_client_endpoint: client_id=%s", client_id)
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    client = await update_client(db, client, webhook_url=body.webhook_url)
    logger.info("update_client_endpoint: done client_id=%s", client_id)
    return ClientPublicResponse.model_validate(client)


@admin_router.get(
    "/clients",
    response_model=ClientListResponse,
    dependencies=[Depends(get_admin_client)],
)
async def list_clients_endpoint(db: AsyncSession = Depends(get_db)) -> ClientListResponse:
    result = await db.execute(select(Client).order_by(Client.created_at.desc()))
    clients = result.scalars().all()
    logger.info("list_clients_endpoint: returning count=%d", len(clients))
    return ClientListResponse(items=[ClientAdminResponse.model_validate(c) for c in clients])


@client_router.get("/me")
async def get_me(
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> dict:
    logger.info("get_me: client_id=%s", current_client.id)
    curriculum_obj = None
    if current_client.curriculum_id:
        from dars.lookup.service import get_curriculum_code
        code = await get_curriculum_code(db, current_client.curriculum_id)
        if code:
            curriculum_obj = {
                "code": code,
                "name": CURRICULUM_NAMES.get(code, code),
            }
    return {
        "id": str(current_client.id),
        "name": current_client.name,
        "is_active": current_client.is_active,
        "webhook_url": current_client.webhook_url,
        "curriculum": curriculum_obj,
        "default_teacher_id": str(current_client.default_teacher_id) if current_client.default_teacher_id else None,
        "created_at": current_client.created_at.isoformat(),
    }


@client_router.patch("/me")
async def update_me(
    body: ClientSelfUpdateRequest,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> dict:
    logger.info("update_me: client_id=%s", current_client.id)
    if body.curriculum is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="curriculum is immutable and cannot be changed after signup.",
        )
    if body.webhook_url is not None:
        current_client.webhook_url = body.webhook_url
    await db.commit()
    await db.refresh(current_client)
    logger.info("update_me: done client_id=%s", current_client.id)
    curriculum_obj = None
    if current_client.curriculum_id:
        from dars.lookup.service import get_curriculum_code
        code = await get_curriculum_code(db, current_client.curriculum_id)
        if code:
            curriculum_obj = {
                "code": code,
                "name": CURRICULUM_NAMES.get(code, code),
            }
    return {
        "id": str(current_client.id),
        "name": current_client.name,
        "is_active": current_client.is_active,
        "webhook_url": current_client.webhook_url,
        "curriculum": curriculum_obj,
        "default_teacher_id": str(current_client.default_teacher_id) if current_client.default_teacher_id else None,
        "created_at": current_client.created_at.isoformat(),
    }


class RotateKeyResponse(BaseModel):
    api_key: str


@client_router.post("/me/rotate-key", response_model=RotateKeyResponse)
async def rotate_my_key(
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> RotateKeyResponse:
    logger.info("rotate_my_key: client_id=%s", current_client.id)
    raw_key = await rotate_api_key(db, current_client)
    logger.info("rotate_my_key: done client_id=%s", current_client.id)
    return RotateKeyResponse(api_key=raw_key)
