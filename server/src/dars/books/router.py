from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_admin_client
from dars.books.schemas import BookListResponse, BookResponse, SyncResult
from dars.books.service import list_books, sync_books

router = APIRouter(prefix="/api/admin/books", tags=["admin-books"])


@router.post("/sync", response_model=SyncResult)
async def sync_books_endpoint(
    _client: Client = Depends(get_admin_client),
    db: AsyncSession = Depends(get_db),
) -> SyncResult:
    result = await sync_books(db)
    return SyncResult(**result)


@router.get("", response_model=BookListResponse)
async def list_books_endpoint(
    board: str | None = Query(default=None),
    grade: int | None = Query(default=None),
    subject: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _client: Client = Depends(get_admin_client),
    db: AsyncSession = Depends(get_db),
) -> BookListResponse:
    books, total = await list_books(db, board=board, grade=grade, subject=subject, limit=limit, offset=offset)
    return BookListResponse(
        items=[BookResponse.model_validate(b) for b in books],
        total=total,
    )
