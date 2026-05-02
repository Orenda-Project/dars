import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.clients.schemas import (
    ClientAdminResponse,
    ClientCreateRequest,
    ClientCreateResponse,
    ClientListResponse,
    ClientPublicResponse,
    ClientUpdateRequest,
)
from dars.clients.service import create_client, update_client
from dars.database import get_db
from dars.deps import get_admin_client, get_current_client, require_admin_secret

admin_router = APIRouter(prefix="/admin", tags=["admin"])
client_router = APIRouter(prefix="/api/v1", tags=["clients"])


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
    client, raw_key = await create_client(db, name=body.name)
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
    client_id: uuid.UUID,
    body: ClientUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ClientPublicResponse:
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    client = await update_client(db, client, webhook_url=body.webhook_url)
    return ClientPublicResponse.model_validate(client)


@admin_router.get(
    "/clients",
    response_model=ClientListResponse,
    dependencies=[Depends(get_admin_client)],
)
async def list_clients_endpoint(db: AsyncSession = Depends(get_db)) -> ClientListResponse:
    result = await db.execute(select(Client).order_by(Client.created_at.desc()))
    clients = result.scalars().all()
    return ClientListResponse(items=[ClientAdminResponse.model_validate(c) for c in clients])


@client_router.get("/me", response_model=ClientPublicResponse)
async def get_me(current_client: Client = Depends(get_current_client)) -> ClientPublicResponse:
    return ClientPublicResponse.model_validate(current_client)
