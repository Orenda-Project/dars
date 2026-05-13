import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_current_client
from dars.generated_lps.schemas import GeneratedLPCreate, GeneratedLPListResponse, GeneratedLPResponse
from dars.generated_lps.service import create_generated_lp, get_generated_lp, generate_lp_task, list_generated_lps

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lesson-plans", tags=["lesson-plans"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GeneratedLPResponse,
)
async def create_lp_endpoint(
    body: GeneratedLPCreate,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GeneratedLPResponse:
    """
    Queue a lesson plan for async generation.

    Curriculum is taken from the authenticated client's profile.
    Returns immediately with status=PENDING and a lesson plan id.
    Poll GET /api/v1/lesson-plans/{id} to check status.
    """
    logger.info(
        "create_lp_endpoint: client_id=%s grade=%s subject=%s",
        current_client.id, body.grade, body.subject,
    )
    if not current_client.curriculum:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client has no curriculum configured.",
        )

    lp = await create_generated_lp(
        db,
        client_id=current_client.id,
        data=body,
        curriculum=current_client.curriculum,
    )
    background_tasks.add_task(
        generate_lp_task,
        lp_id=lp.id,
        client_id=current_client.id,
        curriculum=current_client.curriculum,
        request=body,
    )
    logger.info("create_lp_endpoint: queued lp_id=%s client_id=%s", lp.id, current_client.id)
    return GeneratedLPResponse.model_validate(lp)


@router.get(
    "",
    response_model=GeneratedLPListResponse,
)
async def list_lps_endpoint(
    external_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GeneratedLPListResponse:
    """List all generated lesson plans for the authenticated client."""
    logger.info("list_lps_endpoint: client_id=%s", current_client.id)
    items, total = await list_generated_lps(
        db,
        client_id=current_client.id,
        external_id=external_id,
        skip=offset,
        limit=limit,
    )
    logger.info("list_lps_endpoint: client_id=%s total=%d", current_client.id, total)
    return GeneratedLPListResponse(
        items=[GeneratedLPResponse.model_validate(lp) for lp in items],
        total=total,
    )


@router.get(
    "/{lp_id}",
    response_model=GeneratedLPResponse,
)
async def get_lp_endpoint(
    lp_id: int,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GeneratedLPResponse:
    """Get a single generated lesson plan by id. Only accessible to the owning client."""
    logger.info("get_lp_endpoint: lp_id=%s client_id=%s", lp_id, current_client.id)
    lp = await get_generated_lp(db, lp_id=lp_id, client_id=current_client.id)
    if lp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson plan not found",
        )
    return GeneratedLPResponse.model_validate(lp)
