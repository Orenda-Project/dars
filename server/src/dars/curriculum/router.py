from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dars.books.models import Book, BookChapter
from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_admin_client, get_current_client

from .models import (
    Curriculum,
    CurriculumLpStub,
    CurriculumTopic,
    Grade,
    Subject,
    SloProvider,
    SubSlo,
    Slo,
    Topic,
    TopicSubSlo,
)
from .schemas import (
    BookDetailResponse,
    BookListItem,
    ChapterDetail,
    CurriculumDetailResponse,
    CurriculumListItem,
    CurriculumProgressResponse,
    CurriculumResponse,
    CurriculumTopicDetail,
    GradeResponse,
    LpStubSummary,
    SubjectResponse,
    SubSloSummary,
    TopicDetail,
)

router = APIRouter(tags=["curriculum"])


# ---------------------------------------------------------------------------
# Grades + Subjects (catalog)
# ---------------------------------------------------------------------------

@router.get("/api/v1/grades", response_model=list[GradeResponse])
async def list_grades(
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_current_client),
) -> list[GradeResponse]:
    result = await db.execute(select(Grade).order_by(Grade.order_index))
    return list(result.scalars().all())


@router.get("/api/v1/subjects", response_model=list[SubjectResponse])
async def list_subjects(
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_current_client),
) -> list[SubjectResponse]:
    result = await db.execute(select(Subject).order_by(Subject.label))
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Books — client-accessible
# ---------------------------------------------------------------------------

@router.get("/api/v1/books", response_model=list[BookListItem])
async def list_books_client(
    board: str | None = Query(default=None),
    grade: int | None = Query(default=None),
    subject: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_current_client),
) -> list[BookListItem]:
    """Browse books. Filters: board, grade, subject."""
    query = select(Book)
    if board:
        query = query.where(Book.board == board)
    if grade is not None:
        query = query.where(Book.grade == grade)
    if subject:
        query = query.where(Book.subject == subject)
    query = query.order_by(Book.board, Book.grade, Book.subject)

    result = await db.execute(query)
    books = result.scalars().all()
    return [BookListItem.model_validate(b) for b in books]


@router.get("/api/v1/books/{book_id}", response_model=BookDetailResponse)
async def get_book_detail(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_current_client),
) -> BookDetailResponse:
    """Book detail: book + chapters + topics + sub-SLOs per topic."""
    # Load book with chapters
    result = await db.execute(
        select(Book)
        .where(Book.id == book_id)
        .options(selectinload(Book.chapters))
    )
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found.")

    # Load topics for all chapters (with sub-SLO join)
    chapter_ids = [c.id for c in book.chapters]
    topics_result = await db.execute(
        select(Topic)
        .where(Topic.chapter_id.in_(chapter_ids))
        .options(
            selectinload(Topic.sub_slos).selectinload(TopicSubSlo.sub_slo).selectinload(SubSlo.slo)
        )
        .order_by(Topic.chapter_id, Topic.sequence)
    )
    topics_by_chapter: dict[int, list[Topic]] = {}
    for topic in topics_result.scalars().all():
        topics_by_chapter.setdefault(topic.chapter_id, []).append(topic)

    chapters_out = []
    for chapter in sorted(book.chapters, key=lambda c: c.chapter_number):
        topics_out = []
        for topic in topics_by_chapter.get(chapter.id, []):
            sub_slos_out = []
            for tslo in topic.sub_slos:
                sub_slos_out.append(SubSloSummary(
                    id=tslo.sub_slo.id,
                    code=tslo.sub_slo.code,
                    statement=tslo.sub_slo.statement,
                    slo_code=tslo.sub_slo.slo.code,
                ))
            topics_out.append(TopicDetail(
                id=topic.id,
                title=topic.title,
                text=topic.text,
                sequence=topic.sequence,
                sub_slos=sub_slos_out,
            ))
        chapters_out.append(ChapterDetail(
            id=chapter.id,
            chapter_number=chapter.chapter_number,
            title=chapter.title,
            start_page=chapter.start_page,
            end_page=chapter.end_page,
            topics=topics_out,
        ))

    return BookDetailResponse(
        id=book.id,
        title=book.title,
        grade=book.grade,
        subject=book.subject,
        board=book.board,
        cover_image=book.cover_image,
        total_chapters=book.total_chapters,
        chapters=chapters_out,
    )


# ---------------------------------------------------------------------------
# Curriculums — client-accessible
# ---------------------------------------------------------------------------

@router.get("/api/v1/curriculums", response_model=list[CurriculumListItem])
async def list_curriculums(
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
) -> list[CurriculumListItem]:
    """
    Returns:
    - Admin defaults (is_default=True) for all books
    - Teacher's own curriculums (client_id = current client)
    """
    query = (
        select(Curriculum, Book.title, SloProvider.name)
        .join(Book, Curriculum.book_id == Book.id)
        .join(SloProvider, Curriculum.provider_id == SloProvider.id)
        .where(
            Curriculum.is_active == True,  # noqa: E712
            (Curriculum.is_default == True) | (Curriculum.client_id == client.id),  # noqa: E712
        )
        .order_by(Curriculum.name)
    )
    result = await db.execute(query)
    rows = result.all()

    out = []
    for curriculum, book_title, provider_name in rows:
        out.append(CurriculumListItem(
            id=curriculum.id,
            name=curriculum.name,
            book_id=curriculum.book_id,
            book_title=book_title,
            provider_name=provider_name,
            is_default=curriculum.is_default,
            teacher_id=curriculum.teacher_id,
            is_active=curriculum.is_active,
        ))
    return out


@router.get("/api/v1/curriculums/{curriculum_id}", response_model=CurriculumDetailResponse)
async def get_curriculum_detail(
    curriculum_id: str,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
) -> CurriculumDetailResponse:
    """Full curriculum: ordered topics + LP stubs per topic."""
    import uuid as _uuid
    try:
        cid = _uuid.UUID(curriculum_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Curriculum not found.")

    # Fetch curriculum with book + provider
    result = await db.execute(
        select(Curriculum, Book.title, SloProvider.name)
        .join(Book, Curriculum.book_id == Book.id)
        .join(SloProvider, Curriculum.provider_id == SloProvider.id)
        .where(
            Curriculum.id == cid,
            Curriculum.is_active == True,  # noqa: E712
            (Curriculum.is_default == True) | (Curriculum.client_id == client.id),  # noqa: E712
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Curriculum not found.")

    curriculum, book_title, provider_name = row

    # Load curriculum_topics with their stubs and the linked topic
    ct_result = await db.execute(
        select(CurriculumTopic)
        .where(CurriculumTopic.curriculum_id == cid)
        .options(
            selectinload(CurriculumTopic.stubs),
            selectinload(CurriculumTopic.curriculum),
        )
        .order_by(CurriculumTopic.sequence)
    )
    curriculum_topics = ct_result.scalars().all()

    # Bulk-load topics
    topic_ids = [ct.topic_id for ct in curriculum_topics]
    topic_map: dict = {}
    if topic_ids:
        topics_result = await db.execute(
            select(Topic).where(Topic.id.in_(topic_ids))
        )
        topic_map = {t.id: t for t in topics_result.scalars().all()}

    topics_out = []
    for ct in curriculum_topics:
        topic = topic_map.get(ct.topic_id)
        stubs_out = [
            LpStubSummary(
                id=stub.id,
                sequence=stub.sequence,
                skill_type=stub.skill_type,
                cpa_phase=stub.cpa_phase,
                blooms_level=stub.blooms_level,
                planned_date=stub.planned_date,
                status=stub.status,
                lesson_plan_id=stub.lesson_plan_id,
            )
            for stub in ct.stubs
        ]
        topics_out.append(CurriculumTopicDetail(
            id=ct.id,
            sequence=ct.sequence,
            topic_id=ct.topic_id,
            topic_title=topic.title if topic else "",
            topic_text=topic.text if topic else None,
            planned_date=ct.planned_date,
            completed_date=ct.completed_date,
            lp_stubs=stubs_out,
        ))

    return CurriculumDetailResponse(
        id=curriculum.id,
        name=curriculum.name,
        book_id=curriculum.book_id,
        book_title=book_title,
        provider_name=provider_name,
        is_default=curriculum.is_default,
        teacher_id=curriculum.teacher_id,
        is_active=curriculum.is_active,
        created_at=curriculum.created_at,
        topics=topics_out,
    )


@router.get("/api/v1/curriculums/{curriculum_id}/progress", response_model=CurriculumProgressResponse)
async def get_curriculum_progress(
    curriculum_id: str,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
) -> CurriculumProgressResponse:
    """Progress summary: total, completed, behind (past planned_date, not done), on_track."""
    import uuid as _uuid
    try:
        cid = _uuid.UUID(curriculum_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Curriculum not found.")

    # Verify access
    result = await db.execute(
        select(Curriculum)
        .where(
            Curriculum.id == cid,
            Curriculum.is_active == True,  # noqa: E712
            (Curriculum.is_default == True) | (Curriculum.client_id == client.id),  # noqa: E712
        )
    )
    curriculum = result.scalar_one_or_none()
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found.")

    ct_result = await db.execute(
        select(CurriculumTopic).where(CurriculumTopic.curriculum_id == cid)
    )
    topics = ct_result.scalars().all()

    today = date.today()
    total = len(topics)
    completed = sum(1 for t in topics if t.completed_date is not None)
    behind = sum(
        1 for t in topics
        if t.completed_date is None and t.planned_date is not None and t.planned_date < today
    )
    on_track = total - completed - behind

    return CurriculumProgressResponse(
        total_topics=total,
        completed=completed,
        behind=behind,
        on_track=on_track,
    )


# ---------------------------------------------------------------------------
# Legacy endpoints (kept for backward compatibility — remove in a later phase)
# ---------------------------------------------------------------------------

@router.get("/api/v1/curriculum/books")
async def list_curriculum_books_legacy(
    _client: Client = Depends(get_current_client),
) -> list:
    """Deprecated: use GET /api/v1/books instead."""
    return []


@router.get("/api/v1/curriculum/curriculums")
async def list_curriculums_legacy(
    _client: Client = Depends(get_current_client),
) -> list:
    """Deprecated: use GET /api/v1/curriculums instead."""
    return []


@router.get("/api/v1/curriculum/curriculums/{curriculum_id}")
async def get_curriculum_detail_legacy(
    curriculum_id: str,
    _client: Client = Depends(get_current_client),
) -> dict:
    """Deprecated: use GET /api/v1/curriculums/{id} instead."""
    raise HTTPException(status_code=410, detail="Use GET /api/v1/curriculums/{id}.")


@router.get("/api/admin/curriculums")
async def list_all_curriculums(
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_admin_client),
) -> list:
    result = await db.execute(
        select(Curriculum, Book.title, SloProvider.name)
        .join(Book, Curriculum.book_id == Book.id)
        .join(SloProvider, Curriculum.provider_id == SloProvider.id)
        .order_by(Curriculum.name)
    )
    rows = result.all()
    return [
        {
            "id": str(curriculum.id),
            "name": curriculum.name,
            "book_id": curriculum.book_id,
            "book_title": book_title,
            "provider_name": provider_name,
            "is_default": curriculum.is_default,
            "is_active": curriculum.is_active,
        }
        for curriculum, book_title, provider_name in rows
    ]
