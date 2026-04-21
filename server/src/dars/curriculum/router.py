import logging
import uuid as _uuid_module
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dars.books.models import Book, BookChapter
from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_admin_client, get_current_client

logger = logging.getLogger(__name__)

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
    CurriculumCreateRequest,
    CurriculumDetailResponse,
    CurriculumGenerateRequest,
    CurriculumListItem,
    CurriculumSetTopicsRequest,
    CurriculumTopicDetail,
    CurriculumUpdateRequest,
    GradeResponse,
    LpStubResponse,
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
    result = await db.execute(
        select(Book)
        .where(Book.id == book_id)
        .options(selectinload(Book.chapters))
    )
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found.")

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
    _client: Client = Depends(get_current_client),
) -> list[CurriculumListItem]:
    """Returns all active master curriculums."""
    query = (
        select(Curriculum, Book.title, SloProvider.name)
        .join(Book, Curriculum.book_id == Book.id)
        .join(SloProvider, Curriculum.provider_id == SloProvider.id)
        .where(Curriculum.is_active == True)  # noqa: E712
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
            is_active=curriculum.is_active,
        ))
    return out


@router.get("/api/v1/curriculums/{curriculum_id}", response_model=CurriculumDetailResponse)
async def get_curriculum_detail(
    curriculum_id: str,
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_current_client),
) -> CurriculumDetailResponse:
    """Full curriculum: ordered topics + LP stubs per topic."""
    import uuid as _uuid
    try:
        cid = _uuid.UUID(curriculum_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Curriculum not found.")

    result = await db.execute(
        select(Curriculum, Book.title, SloProvider.name)
        .join(Book, Curriculum.book_id == Book.id)
        .join(SloProvider, Curriculum.provider_id == SloProvider.id)
        .where(
            Curriculum.id == cid,
            Curriculum.is_active == True,  # noqa: E712
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Curriculum not found.")

    curriculum, book_title, provider_name = row

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
            lp_stubs=stubs_out,
        ))

    return CurriculumDetailResponse(
        id=curriculum.id,
        name=curriculum.name,
        book_id=curriculum.book_id,
        book_title=book_title,
        provider_name=provider_name,
        is_active=curriculum.is_active,
        created_at=curriculum.created_at,
        topics=topics_out,
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
            "is_active": curriculum.is_active,
        }
        for curriculum, book_title, provider_name in rows
    ]


# ---------------------------------------------------------------------------
# Admin CRUD — Phase 2
# ---------------------------------------------------------------------------

async def _build_curriculum_detail(db: AsyncSession, curriculum_id: _uuid_module.UUID) -> CurriculumDetailResponse:
    """Load a curriculum with all topics + stubs and return the full detail response."""
    row = (await db.execute(
        select(Curriculum, Book.title, SloProvider.name)
        .join(Book, Curriculum.book_id == Book.id)
        .join(SloProvider, Curriculum.provider_id == SloProvider.id)
        .where(Curriculum.id == curriculum_id)
    )).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Curriculum not found.")
    curriculum, book_title, provider_name = row

    ct_result = await db.execute(
        select(CurriculumTopic)
        .where(CurriculumTopic.curriculum_id == curriculum_id)
        .options(selectinload(CurriculumTopic.stubs))
        .order_by(CurriculumTopic.sequence)
    )
    curriculum_topics = ct_result.scalars().all()

    topic_ids = [ct.topic_id for ct in curriculum_topics]
    topic_map: dict = {}
    if topic_ids:
        topics_result = await db.execute(select(Topic).where(Topic.id.in_(topic_ids)))
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
            lp_stubs=stubs_out,
        ))

    return CurriculumDetailResponse(
        id=curriculum.id,
        name=curriculum.name,
        book_id=curriculum.book_id,
        book_title=book_title,
        provider_name=provider_name,
        is_active=curriculum.is_active,
        created_at=curriculum.created_at,
        topics=topics_out,
    )


@router.post("/api/admin/curriculums", response_model=CurriculumListItem, status_code=201)
async def create_curriculum(
    body: CurriculumCreateRequest,
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_admin_client),
) -> CurriculumListItem:
    """Create a new master curriculum."""
    book = (await db.execute(select(Book).where(Book.id == body.book_id))).scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=422, detail="book_id does not exist.")

    provider = (await db.execute(
        select(SloProvider).where(SloProvider.id == body.provider_id)
    )).scalar_one_or_none()
    if provider is None:
        raise HTTPException(status_code=422, detail="provider_id does not exist.")

    curriculum = Curriculum(
        id=_uuid_module.uuid4(),
        name=body.name,
        book_id=body.book_id,
        provider_id=body.provider_id,
        is_active=True,
    )
    db.add(curriculum)
    await db.commit()
    await db.refresh(curriculum)

    return CurriculumListItem(
        id=curriculum.id,
        name=curriculum.name,
        book_id=curriculum.book_id,
        book_title=book.title,
        provider_name=provider.name,
        is_active=curriculum.is_active,
    )


@router.post("/api/admin/curriculums/{curriculum_id}/topics", response_model=CurriculumDetailResponse)
async def set_curriculum_topics(
    curriculum_id: str,
    body: CurriculumSetTopicsRequest,
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_admin_client),
) -> CurriculumDetailResponse:
    """Replace the full ordered topic list for a curriculum."""
    try:
        cid = _uuid_module.UUID(curriculum_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Curriculum not found.")

    curriculum = (await db.execute(
        select(Curriculum).where(Curriculum.id == cid)
    )).scalar_one_or_none()
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found.")

    if body.topics:
        requested_ids = [e.topic_id for e in body.topics]
        found = (await db.execute(
            select(Topic.id).where(Topic.id.in_(requested_ids))
        )).scalars().all()
        found_set = set(found)
        missing = [str(tid) for tid in requested_ids if tid not in found_set]
        if missing:
            raise HTTPException(status_code=422, detail=f"Unknown topic_ids: {missing}")

    await db.execute(delete(CurriculumTopic).where(CurriculumTopic.curriculum_id == cid))

    for seq, entry in enumerate(body.topics, start=1):
        ct = CurriculumTopic(
            id=_uuid_module.uuid4(),
            curriculum_id=cid,
            topic_id=entry.topic_id,
            sequence=seq,
            planned_date=entry.planned_date,
        )
        db.add(ct)

    await db.commit()
    return await _build_curriculum_detail(db, cid)


@router.patch("/api/admin/curriculums/{curriculum_id}", response_model=CurriculumListItem)
async def update_curriculum(
    curriculum_id: str,
    body: CurriculumUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_admin_client),
) -> CurriculumListItem:
    """Update curriculum metadata (name, is_active)."""
    try:
        cid = _uuid_module.UUID(curriculum_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Curriculum not found.")

    row = (await db.execute(
        select(Curriculum, Book.title, SloProvider.name)
        .join(Book, Curriculum.book_id == Book.id)
        .join(SloProvider, Curriculum.provider_id == SloProvider.id)
        .where(Curriculum.id == cid)
    )).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Curriculum not found.")
    curriculum, book_title, provider_name = row

    if body.name is not None:
        curriculum.name = body.name
    if body.is_active is not None:
        curriculum.is_active = body.is_active

    await db.commit()
    await db.refresh(curriculum)

    return CurriculumListItem(
        id=curriculum.id,
        name=curriculum.name,
        book_id=curriculum.book_id,
        book_title=book_title,
        provider_name=provider_name,
        is_active=curriculum.is_active,
    )


@router.delete("/api/admin/curriculums/{curriculum_id}/topics/{ct_id}", status_code=204)
async def delete_curriculum_topic(
    curriculum_id: str,
    ct_id: str,
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_admin_client),
) -> Response:
    """Remove a single topic from a curriculum and re-sequence the remaining topics."""
    try:
        cid = _uuid_module.UUID(curriculum_id)
        ctid = _uuid_module.UUID(ct_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found.")

    ct = (await db.execute(
        select(CurriculumTopic).where(
            CurriculumTopic.id == ctid,
            CurriculumTopic.curriculum_id == cid,
        )
    )).scalar_one_or_none()
    if ct is None:
        raise HTTPException(status_code=404, detail="Curriculum topic not found.")

    await db.delete(ct)
    await db.flush()

    remaining = (await db.execute(
        select(CurriculumTopic)
        .where(CurriculumTopic.curriculum_id == cid)
        .order_by(CurriculumTopic.sequence)
    )).scalars().all()
    for new_seq, remaining_ct in enumerate(remaining, start=1):
        remaining_ct.sequence = new_seq

    await db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Phase 4 — AI breakdown pipeline (now also generates LPs inline)
# ---------------------------------------------------------------------------

@router.post("/api/admin/curriculums/generate", response_model=CurriculumDetailResponse, status_code=201)
async def generate_curriculum(
    body: CurriculumGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_admin_client),
) -> CurriculumDetailResponse:
    """
    Run the two-step AI pipeline, persist a fully scheduled curriculum, and
    generate LPs for every stub inline (synchronous).

    Step A: Allocate teaching days across chapters (one LLM call).
    Step B: For each chapter, generate ordered LP stubs with dates (one LLM call per chapter).
    Step C: For each stub, call LP Assistant and create a LessonPlan record.
    """
    import anthropic as _anthropic
    from dars.config import settings as _settings
    from dars.lesson_plans.models import LessonPlan
    from dars.lesson_plans.schemas import LessonPlanCreateRequest
    from dars.lesson_plans.service import _call_lp_assistant
    from .breakdown import (
        ChapterAllocation,
        LpStub,
        compute_teaching_days,
        plan_chapter_days,
        plan_topic_stubs,
    )

    # --- validate book + provider ----------------------------------------
    book = (await db.execute(select(Book).where(Book.id == body.book_id))).scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=422, detail="book_id does not exist.")

    provider = (await db.execute(
        select(SloProvider).where(SloProvider.id == body.provider_id)
    )).scalar_one_or_none()
    if provider is None:
        raise HTTPException(status_code=422, detail="provider_id does not exist.")

    # --- fetch chapters + topics ------------------------------------------
    chapters_result = await db.execute(
        select(BookChapter)
        .where(BookChapter.book_id == body.book_id)
        .order_by(BookChapter.chapter_number)
    )
    chapters = chapters_result.scalars().all()
    if not chapters:
        raise HTTPException(status_code=422, detail="Book has no chapters.")

    chapter_ids = [c.id for c in chapters]
    topics_result = await db.execute(
        select(Topic)
        .where(Topic.chapter_id.in_(chapter_ids))
        .options(
            selectinload(Topic.sub_slos).selectinload(TopicSubSlo.sub_slo)
        )
        .order_by(Topic.chapter_id, Topic.sequence)
    )
    topics_by_chapter: dict[int, list[Topic]] = {}
    for topic in topics_result.scalars().all():
        topics_by_chapter.setdefault(topic.chapter_id, []).append(topic)

    # --- compute teaching days -------------------------------------------
    teaching_days = compute_teaching_days(body.start_date, body.end_date, body.days_per_week)
    total_days = len(teaching_days)
    if total_days == 0:
        raise HTTPException(status_code=422, detail="No teaching days in the given date range.")
    if total_days < len(chapters):
        raise HTTPException(
            status_code=422,
            detail=f"Only {total_days} teaching days for {len(chapters)} chapters — need at least one day per chapter.",
        )

    chapter_summaries = [
        {
            "id": ch.id,
            "chapter_number": ch.chapter_number,
            "title": ch.title,
            "topic_count": len(topics_by_chapter.get(ch.id, [])),
        }
        for ch in chapters
    ]

    # --- LLM client -------------------------------------------------------
    if not _settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not configured.")

    anthropic_client = _anthropic.AsyncAnthropic(api_key=_settings.anthropic_api_key)

    # --- Step A: chapter day allocation -----------------------------------
    try:
        allocations: list[ChapterAllocation] = await plan_chapter_days(
            chapter_summaries, total_days, anthropic_client
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Step A (chapter planner) failed: {exc}",
        ) from exc

    alloc_map: dict[int, int] = {a.chapter_id: a.days for a in allocations}

    # --- Step B: per-chapter topic/LP planner ----------------------------
    all_stubs: list[tuple[Topic, LpStub]] = []
    day_pointer = 0

    for chapter in chapters:
        allocated_days = alloc_map.get(chapter.id, 1)
        chapter_topics = topics_by_chapter.get(chapter.id, [])

        if not chapter_topics:
            day_pointer += allocated_days
            continue

        topics_for_llm = [
            {
                "id": str(t.id),
                "title": t.title,
                "sub_slos": [
                    tslo.sub_slo.statement
                    for tslo in t.sub_slos
                    if tslo.sub_slo and tslo.sub_slo.statement
                ],
            }
            for t in chapter_topics
        ]

        remaining_dates = teaching_days[day_pointer:]

        try:
            stubs = await plan_topic_stubs(
                chapter_title=chapter.title,
                topics=topics_for_llm,
                days=allocated_days,
                teaching_dates=remaining_dates,
                anthropic_client=anthropic_client,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Step B (topic planner) failed for chapter '{chapter.title}': {exc}",
            ) from exc

        topic_map_local = {str(t.id): t for t in chapter_topics}
        for stub in stubs:
            topic_orm = topic_map_local.get(stub.topic_id)
            if topic_orm is None:
                continue
            all_stubs.append((topic_orm, stub))

        day_pointer += allocated_days

    # --- Step C: persist curriculum + generate LPs inline ----------------
    new_curriculum = Curriculum(
        id=_uuid_module.uuid4(),
        name=body.name,
        book_id=body.book_id,
        provider_id=body.provider_id,
        is_active=True,
    )
    db.add(new_curriculum)
    await db.flush()

    # Group stubs by topic_id preserving order of first appearance
    topic_ct_map: dict[str, CurriculumTopic] = {}
    global_seq = 0

    for topic_orm, stub in all_stubs:
        topic_id_str = str(topic_orm.id)
        if topic_id_str not in topic_ct_map:
            global_seq += 1
            ct = CurriculumTopic(
                id=_uuid_module.uuid4(),
                curriculum_id=new_curriculum.id,
                topic_id=topic_orm.id,
                sequence=global_seq,
                planned_date=stub.planned_date,
            )
            db.add(ct)
            await db.flush()
            topic_ct_map[topic_id_str] = ct

    topic_stub_seq: dict[str, int] = {}
    for topic_orm, stub in all_stubs:
        topic_id_str = str(topic_orm.id)
        ct = topic_ct_map.get(topic_id_str)
        if ct is None:
            continue
        topic_stub_seq[topic_id_str] = topic_stub_seq.get(topic_id_str, 0) + 1

        lp_stub_orm = CurriculumLpStub(
            id=_uuid_module.uuid4(),
            curriculum_topic_id=ct.id,
            skill_type=stub.skill_type,
            cpa_phase=stub.cpa_phase,
            blooms_level=stub.blooms_level,
            sequence=topic_stub_seq[topic_id_str],
            planned_date=stub.planned_date,
            lesson_plan_id=None,
        )
        db.add(lp_stub_orm)
        await db.flush()  # populate lp_stub_orm.id

        # Build custom_prompt
        sub_slo_statements = [
            tslo.sub_slo.statement
            for tslo in topic_orm.sub_slos
            if tslo.sub_slo and tslo.sub_slo.statement
        ]
        parts = [f"Topic: {topic_orm.title}"]
        if sub_slo_statements:
            parts.append(f"Sub-SLOs: {', '.join(sub_slo_statements)}")
        if stub.skill_type:
            parts.append(f"Skill type: {stub.skill_type}")
        if stub.cpa_phase:
            parts.append(f"CPA phase: {stub.cpa_phase}")
        if stub.blooms_level:
            parts.append(f"Bloom's level: {stub.blooms_level}")
        custom_prompt = "\n".join(parts)

        lp_request = LessonPlanCreateRequest(
            grade=str(book.grade),
            subject=book.subject,
            page_number="1",
            curriculum=book.board,
            class_strength=30,
            topic=topic_orm.title,
            custom_prompt=custom_prompt,
            generate_bilingual=False,
        )

        try:
            result_data = await _call_lp_assistant(lp_request)
            lp = LessonPlan(
                grade=str(book.grade),
                subject=book.subject,
                topic=topic_orm.title,
                page_number="1",
                class_strength=30,
                status="READY",
                content=result_data.get("lesson_plan"),
                content_bilingual=result_data.get("lesson_plan_bilingual"),
                tags=result_data.get("tags") or {},
                metadata_=result_data.get("metadata") or {},
                updated_at=datetime.now(timezone.utc),
            )
            db.add(lp)
            await db.flush()
            lp_stub_orm.lesson_plan_id = lp.id
        except Exception as exc:
            logger.error(
                "generate_curriculum: LP generation failed for stub %s topic=%s: %s",
                lp_stub_orm.id,
                topic_orm.title,
                exc,
            )

    await db.commit()
    return await _build_curriculum_detail(db, new_curriculum.id)


# ---------------------------------------------------------------------------
# Stub status endpoint (Phase 5, kept)
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/curriculums/{curriculum_id}/stubs/{stub_id}",
    response_model=LpStubResponse,
)
async def get_stub(
    curriculum_id: str,
    stub_id: str,
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_current_client),
) -> LpStubResponse:
    """Get a single stub's current status + lesson_plan_id."""
    try:
        cid = _uuid_module.UUID(curriculum_id)
        sid = _uuid_module.UUID(stub_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found.")

    # Verify curriculum exists and is accessible
    curriculum = (await db.execute(
        select(Curriculum)
        .where(Curriculum.id == cid, Curriculum.is_active == True)  # noqa: E712
    )).scalar_one_or_none()
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found.")

    result = await db.execute(
        select(CurriculumLpStub)
        .join(CurriculumTopic, CurriculumLpStub.curriculum_topic_id == CurriculumTopic.id)
        .where(
            CurriculumLpStub.id == sid,
            CurriculumTopic.curriculum_id == curriculum.id,
        )
    )
    stub = result.scalar_one_or_none()
    if stub is None:
        raise HTTPException(status_code=404, detail="Stub not found.")

    return LpStubResponse(
        id=stub.id,
        curriculum_topic_id=stub.curriculum_topic_id,
        skill_type=stub.skill_type,
        cpa_phase=stub.cpa_phase,
        blooms_level=stub.blooms_level,
        planned_date=stub.planned_date,
        lesson_plan_id=stub.lesson_plan_id,
        sequence=stub.sequence,
    )
