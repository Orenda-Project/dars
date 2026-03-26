from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.clients.schemas import ClientCreateRequest, ClientCreateResponse, ClientPublicResponse
from dars.clients.service import create_client
from dars.database import get_db
from dars.deps import get_current_client, require_internal_secret

internal_router = APIRouter(prefix="/internal", tags=["internal"])
client_router = APIRouter(prefix="/api/v1", tags=["clients"])


@internal_router.post(
    "/clients",
    status_code=status.HTTP_201_CREATED,
    response_model=ClientCreateResponse,
    dependencies=[Depends(require_internal_secret)],
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


@client_router.get("/me", response_model=ClientPublicResponse)
async def get_me(current_client: Client = Depends(get_current_client)) -> ClientPublicResponse:
    return ClientPublicResponse.model_validate(current_client)
