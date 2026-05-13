import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import dars.clients.models  # noqa
import dars.curriculum.models  # noqa
import dars.curriculum_data.models  # noqa
import dars.generated_lps.models  # noqa
import dars.lookup.models  # noqa
from dars.clients.service import create_client
from dars.curriculum.models import Book, BookChapter
from dars.curriculum_data.models import CurriculumData
from dars.database import Base, get_db
from dars.lookup.models import Grade, Subject
from dars.main import app

TEST_DB = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add(CurriculumData(code="ICT", name="ICT Curriculum"))
        session.add(CurriculumData(code="AKU", name="AKU Curriculum"))
        session.add(Grade(code=5, display_name="Grade 5"))
        session.add(Grade(code=6, display_name="Grade 6"))
        session.add(Subject(code="Math", display_name="Mathematics"))
        session.add(Subject(code="Science", display_name="Science"))
        await session.commit()
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def authed_client(db_session):
    client_obj, raw_key = await create_client(db_session, name="Test Client")
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, raw_key, client_obj
    app.dependency_overrides.clear()


async def _lookup(db_session: AsyncSession, model, code_attr, code_val):
    result = await db_session.execute(select(model).where(getattr(model, code_attr) == code_val))
    return result.scalar_one()


async def _make_book(db: AsyncSession, curriculum: str = "ICT", grade: int = 5,
                     subject: str = "Math", title: str = "Math Book Grade 5",
                     core_id: int | None = 1) -> Book:
    curr = await _lookup(db, CurriculumData, "code", curriculum)
    grade_obj = await _lookup(db, Grade, "code", grade)
    subj = await _lookup(db, Subject, "code", subject)
    book = Book(
        core_id=core_id,
        curriculum_id=curr.id,
        grade_id=grade_obj.id,
        subject_id=subj.id,
        title=title,
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def _make_chapter(db: AsyncSession, book_id: int, **kwargs) -> BookChapter:
    defaults = {
        "core_id": 1,
        "book_id": book_id,
        "title": "Chapter 1",
        "chapter_number": 1,
    }
    defaults.update(kwargs)
    chapter = BookChapter(**defaults)
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return chapter


# ---------------------------------------------------------------------------
# GET /api/v1/books
# ---------------------------------------------------------------------------


async def test_list_books_empty(authed_client):
    http, api_key, _ = authed_client
    response = await http.get("/api/v1/books", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_list_books_requires_auth(authed_client):
    http, _, _ = authed_client
    response = await http.get("/api/v1/books")
    assert response.status_code == 401


async def test_list_books_returns_all(authed_client, db_session):
    http, api_key, _ = authed_client
    await _make_book(db_session, curriculum="ICT", grade=5, subject="Math", title="Math 5", core_id=1)
    await _make_book(db_session, curriculum="AKU", grade=6, subject="Science", title="Science 6", core_id=2)

    response = await http.get("/api/v1/books", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


async def test_list_books_filter_curriculum(authed_client, db_session):
    # client has no curriculum → sees all books
    http, api_key, _ = authed_client
    await _make_book(db_session, curriculum="ICT", grade=5, subject="Math", title="Math 5 ICT", core_id=1)
    await _make_book(db_session, curriculum="AKU", grade=5, subject="Math", title="Math 5 AKU", core_id=2)

    response = await http.get("/api/v1/books", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


async def test_list_books_filter_grade(authed_client, db_session):
    http, api_key, _ = authed_client
    await _make_book(db_session, curriculum="ICT", grade=5, subject="Math", title="Math 5", core_id=1)
    await _make_book(db_session, curriculum="ICT", grade=6, subject="Math", title="Math 6", core_id=2)

    response = await http.get("/api/v1/books?grade=5", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "grade_id" in data["items"][0]


async def test_list_books_filter_subject(authed_client, db_session):
    http, api_key, _ = authed_client
    await _make_book(db_session, curriculum="ICT", grade=5, subject="Math", title="Math 5", core_id=1)
    await _make_book(db_session, curriculum="ICT", grade=5, subject="Science", title="Science 5", core_id=2)

    response = await http.get("/api/v1/books?subject=Math", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "subject_id" in data["items"][0]


async def test_list_books_filter_combined(authed_client, db_session):
    http, api_key, _ = authed_client
    await _make_book(db_session, curriculum="ICT", grade=5, subject="Math", title="Match", core_id=1)
    await _make_book(db_session, curriculum="ICT", grade=5, subject="Science", title="No match subject", core_id=2)
    await _make_book(db_session, curriculum="AKU", grade=6, subject="Math", title="No match grade", core_id=3)

    response = await http.get(
        "/api/v1/books?grade=5&subject=Math",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Match"


# ---------------------------------------------------------------------------
# GET /api/v1/books/{book_id}/chapters
# ---------------------------------------------------------------------------


async def test_list_chapters_requires_auth(authed_client, db_session):
    http, _, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    response = await http.get(f"/api/v1/books/{book.id}/chapters")
    assert response.status_code == 401


async def test_list_chapters_book_not_found(authed_client):
    http, api_key, _ = authed_client
    fake_id = 99999
    response = await http.get(f"/api/v1/books/{fake_id}/chapters", headers={"X-API-Key": api_key})
    assert response.status_code == 404


async def test_list_chapters_empty(authed_client, db_session):
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    response = await http.get(f"/api/v1/books/{book.id}/chapters", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []


async def test_list_chapters_ordered_by_chapter_number(authed_client, db_session):
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    await _make_chapter(db_session, book_id=book.id, core_id=3, title="Chapter 3", chapter_number=3)
    await _make_chapter(db_session, book_id=book.id, core_id=1, title="Chapter 1", chapter_number=1)
    await _make_chapter(db_session, book_id=book.id, core_id=2, title="Chapter 2", chapter_number=2)

    response = await http.get(f"/api/v1/books/{book.id}/chapters", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    numbers = [item["chapter_number"] for item in data["items"]]
    assert numbers == [1, 2, 3]


async def test_list_chapters_only_for_requested_book(authed_client, db_session):
    http, api_key, _ = authed_client
    book_a = await _make_book(db_session, core_id=1, title="Book A")
    book_b = await _make_book(db_session, core_id=2, title="Book B")
    await _make_chapter(db_session, book_id=book_a.id, core_id=1, title="A Ch1", chapter_number=1)
    await _make_chapter(db_session, book_id=book_b.id, core_id=2, title="B Ch1", chapter_number=1)

    response = await http.get(f"/api/v1/books/{book_a.id}/chapters", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "A Ch1"


async def test_list_chapters_response_fields(authed_client, db_session):
    http, api_key, _ = authed_client
    book = await _make_book(db_session, core_id=1)
    await _make_chapter(
        db_session,
        book_id=book.id,
        core_id=10,
        title="Intro",
        chapter_number=1,
        start_page=1,
        end_page=20,
    )

    response = await http.get(f"/api/v1/books/{book.id}/chapters", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert "id" in item
    assert item["core_id"] == 10
    assert item["book_id"] == book.id
    assert item["title"] == "Intro"
    assert item["chapter_number"] == 1
    assert item["start_page"] == 1
    assert item["end_page"] == 20
    assert "created_at" in item
