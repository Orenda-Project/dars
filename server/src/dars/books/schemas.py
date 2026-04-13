from datetime import datetime

from pydantic import BaseModel


class BookChapterResponse(BaseModel):
    id: int
    book_id: int
    title: str
    chapter_number: int
    start_page: int | None
    end_page: int | None

    model_config = {"from_attributes": True}


class BookResponse(BaseModel):
    id: int
    title: str
    grade: int
    subject: str
    curriculum: str
    cover_image: str | None
    total_chapters: int | None
    synced_at: datetime

    model_config = {"from_attributes": True}


class BookListResponse(BaseModel):
    items: list[BookResponse]
    total: int


class SyncResult(BaseModel):
    ict_books: int
    punjab_books: int
    chapters: int
