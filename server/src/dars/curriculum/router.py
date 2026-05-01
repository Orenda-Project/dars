import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.curriculum.models import Book
from dars.curriculum.schemas import BookChapterListResponse, BookChapterResponse, BookListResponse, BookResponse
from dars.curriculum.service import list_book_chapters, list_books
from dars.database import get_db
from dars.deps import get_current_client

router = APIRouter(prefix="/api/v1/books", tags=["books"])


@router.get("", response_model=BookListResponse)
async def list_books_endpoint(
    curriculum: str | None = Query(default=None),
    grade: int | None = Query(default=None),
    subject: str | None = Query(default=None),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> BookListResponse:
    items, total = await list_books(db, curriculum=curriculum, grade=grade, subject=subject)
    return BookListResponse(
        items=[BookResponse.model_validate(b) for b in items],
        total=total,
    )


@router.get("/{book_id}/chapters", response_model=BookChapterListResponse)
async def list_book_chapters_endpoint(
    book_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> BookChapterListResponse:
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    chapters = await list_book_chapters(db, book_id=book_id)
    return BookChapterListResponse(
        items=[BookChapterResponse.model_validate(c) for c in chapters],
    )
