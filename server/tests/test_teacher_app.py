"""
Tests for Step 7 — Teacher App endpoint:
  GET /api/v1/me/classes
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import dars.clients.models  # noqa
import dars.curriculum.models  # noqa
import dars.curriculum_data.models  # noqa
import dars.generated_exams.models  # noqa
import dars.generated_lps.models  # noqa
import dars.lookup.models  # noqa
import dars.school.models  # noqa
import dars.teachers.models  # noqa
import dars.webhooks.models  # noqa

from dars.clients.models import Client
from dars.curriculum_data.models import CurriculumData
from dars.database import Base, get_db
from dars.lookup.models import Grade, Subject
from dars.main import app

TEST_DB = "sqlite+aiosqlite:///:memory:"

# Seeded IDs (assigned after first commit)
_GRADE_5_CODE = 5
_GRADE_6_CODE = 6
_SUBJECT_ENG = "english"
_SUBJECT_MATHS = "maths"


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
        session.add(CurriculumData(code="NCP", name="National Curriculum of Pakistan"))
        session.add(CurriculumData(code="SNC", name="Single National Curriculum"))
        session.add(Grade(code=5, display_name="Grade 5"))
        session.add(Grade(code=6, display_name="Grade 6"))
        session.add(Subject(code="english", display_name="English"))
        session.add(Subject(code="maths", display_name="Maths"))
        await session.commit()
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def http_client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def headers(key: str) -> dict:
    return {"X-API-Key": key}


async def _signup(http_client, email: str, name: str = "School") -> str:
    """Sign up and return API key. Signup auto-creates a default teacher."""
    resp = await http_client.post(
        "/auth/signup",
        json={"email": email, "password": "pass123", "name": name, "curriculum": "NCP"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["api_key"]


async def _get_me(http_client, key: str) -> dict:
    resp = await http_client.get("/api/v1/me", headers=headers(key))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _make_academic_year(http_client, key: str) -> dict:
    resp = await http_client.post(
        "/api/v1/academic-years",
        json={"name": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31"},
        headers=headers(key),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _get_grade_id(db_session: AsyncSession, code: int) -> int:
    result = await db_session.execute(select(Grade).where(Grade.code == code))
    return result.scalar_one().id


async def _get_subject_id(db_session: AsyncSession, code: str) -> int:
    result = await db_session.execute(select(Subject).where(Subject.code == code))
    return result.scalar_one().id


async def _make_class(http_client, key: str, year_id: str, grade_id: int) -> dict:
    resp = await http_client.post(
        "/api/v1/classes",
        json={
            "academic_year_id": year_id,
            "grade_id": grade_id,
            "section": "A",
            "name": f"Class A",
        },
        headers=headers(key),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _assign_subject(
    http_client, key: str, class_id: str, subject_id: int, teacher_id: str | None = None
) -> dict:
    body: dict = {"subject_id": subject_id}
    if teacher_id:
        body["teacher_id"] = teacher_id
    resp = await http_client.post(
        f"/api/v1/classes/{class_id}/subjects",
        json=body,
        headers=headers(key),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_my_classes_returns_teacher_csts(http_client, db_session):
    """
    GET /api/v1/me/classes returns CSTs assigned to the default_teacher_id.
    Signup auto-creates a default teacher; assign a class subject to that teacher.
    """
    grade_id = await _get_grade_id(db_session, 5)
    subject_id = await _get_subject_id(db_session, "english")

    key = await _signup(http_client, "teacher1@school.com", "School A")
    me = await _get_me(http_client, key)
    default_teacher_id = me["default_teacher_id"]
    assert default_teacher_id is not None, "signup should auto-create a default teacher"

    year = await _make_academic_year(http_client, key)
    school_class = await _make_class(http_client, key, year["id"], grade_id)
    cst = await _assign_subject(http_client, key, school_class["id"], subject_id, default_teacher_id)

    resp = await http_client.get("/api/v1/me/classes", headers=headers(key))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["cst_id"] == cst["id"]
    assert item["class_id"] == school_class["id"]
    assert item["subject"] == "English"
    assert item["grade"] == 5
    assert item["class_name"] == "Class A"
    assert item["chapter_count"] == 0
    assert item["taught_count"] == 0
    assert item["timetable_days"] == []
    assert item["next_slot"] is None


@pytest.mark.asyncio
async def test_my_classes_returns_empty_when_default_teacher_has_no_csts(http_client, db_session):
    """
    GET /api/v1/me/classes returns empty list when no CSTs are assigned to
    the default_teacher_id (or when default_teacher_id is explicitly None).
    """
    key = await _signup(http_client, "noteacher@school.com", "School B")

    # Clear default_teacher_id directly in the DB
    result = await db_session.execute(select(Client).where(Client.email == "noteacher@school.com"))
    client = result.scalar_one()
    client.default_teacher_id = None
    await db_session.commit()

    resp = await http_client.get("/api/v1/me/classes", headers=headers(key))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["items"] == []


@pytest.mark.asyncio
async def test_my_classes_client_isolation(http_client, db_session):
    """Client A cannot see Client B's classes via GET /api/v1/me/classes."""
    grade5_id = await _get_grade_id(db_session, 5)
    grade6_id = await _get_grade_id(db_session, 6)
    eng_id = await _get_subject_id(db_session, "english")
    maths_id = await _get_subject_id(db_session, "maths")

    key_a = await _signup(http_client, "clientA@school.com", "School A")
    key_b = await _signup(http_client, "clientB@school.com", "School B")

    # Client B: get default teacher, set up class + subject
    me_b = await _get_me(http_client, key_b)
    teacher_b_id = me_b["default_teacher_id"]

    year_b = await _make_academic_year(http_client, key_b)
    class_b = await _make_class(http_client, key_b, year_b["id"], grade6_id)
    await _assign_subject(http_client, key_b, class_b["id"], maths_id, teacher_b_id)

    # Client A: no CSTs assigned to their default teacher
    resp_a = await http_client.get("/api/v1/me/classes", headers=headers(key_a))
    assert resp_a.status_code == 200, resp_a.text
    data_a = resp_a.json()
    assert data_a["items"] == []

    # Client B sees their own data only
    resp_b = await http_client.get("/api/v1/me/classes", headers=headers(key_b))
    assert resp_b.status_code == 200, resp_b.text
    data_b = resp_b.json()
    assert len(data_b["items"]) == 1
    assert data_b["items"][0]["subject"] == "Maths"
    assert data_b["items"][0]["grade"] == 6


@pytest.mark.asyncio
async def test_my_classes_timetable_days(http_client, db_session):
    """timetable_days in MyClassEntry reflects saved timetable slots."""
    grade_id = await _get_grade_id(db_session, 5)
    subject_id = await _get_subject_id(db_session, "english")

    key = await _signup(http_client, "timetable@school.com", "School T")
    me = await _get_me(http_client, key)
    default_teacher_id = me["default_teacher_id"]

    year = await _make_academic_year(http_client, key)
    school_class = await _make_class(http_client, key, year["id"], grade_id)
    cst = await _assign_subject(http_client, key, school_class["id"], subject_id, default_teacher_id)

    # Set timetable: Mon (0) and Wed (2)
    tt_resp = await http_client.post(
        f"/api/v1/classes/{school_class['id']}/subjects/{cst['id']}/timetable",
        json={"slots": [{"day_of_week": 0}, {"day_of_week": 2}]},
        headers=headers(key),
    )
    assert tt_resp.status_code == 200, tt_resp.text

    resp = await http_client.get("/api/v1/me/classes", headers=headers(key))
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["timetable_days"] == [0, 2]


# ---------------------------------------------------------------------------
# Calendar tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calendar_week_empty_without_teacher(http_client, db_session):
    """Client with no default_teacher_id gets empty calendar."""
    key = await _signup(http_client, "nocalteacher@school.com", "School NC")

    result = await db_session.execute(select(Client).where(Client.email == "nocalteacher@school.com"))
    client = result.scalar_one()
    client.default_teacher_id = None
    await db_session.commit()

    resp = await http_client.get("/api/v1/me/calendar?week_start=2026-05-12", headers=headers(key))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["week_start"] == "2026-05-12"
    assert data["week_end"] == "2026-05-18"
    assert len(data["items"]) == 7
    for day in data["items"]:
        assert day["lessons"] == []
        assert day["assessments"] == []


@pytest.mark.asyncio
async def test_calendar_week_includes_assessments(http_client, db_session):
    """Assessment slots with scheduled_date in the week appear on the correct day."""
    grade_id = await _get_grade_id(db_session, 5)
    subject_id = await _get_subject_id(db_session, "english")

    key = await _signup(http_client, "calassess@school.com", "School CA")
    me = await _get_me(http_client, key)
    default_teacher_id = me["default_teacher_id"]

    year = await _make_academic_year(http_client, key)
    school_class = await _make_class(http_client, key, year["id"], grade_id)
    cst = await _assign_subject(http_client, key, school_class["id"], subject_id, default_teacher_id)

    # Create an assessment on 2026-05-14 (Thursday, weekday index 3 in the 2026-05-12 week)
    aslot_resp = await http_client.post(
        f"/api/v1/classes/{school_class['id']}/subjects/{cst['id']}/assessment-slots",
        json={
            "assessment_type": "formative",
            "scheduled_date": "2026-05-14",
            "title": "Chapter 1 FA",
        },
        headers=headers(key),
    )
    assert aslot_resp.status_code == 201, aslot_resp.text

    resp = await http_client.get("/api/v1/me/calendar?week_start=2026-05-12", headers=headers(key))
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Wednesday is index 2 in the week (Mon=0, Tue=1, Wed=2 …)
    wednesday = data["items"][2]
    assert wednesday["date"] == "2026-05-14"
    assert len(wednesday["assessments"]) == 1
    a = wednesday["assessments"][0]
    assert a["assessment_type"] == "formative"
    assert a["title"] == "Chapter 1 FA"
    assert a["cst_id"] == cst["id"]


@pytest.mark.asyncio
async def test_calendar_week_client_isolation(http_client, db_session):
    """Two clients cannot see each other's calendar events."""
    grade_id = await _get_grade_id(db_session, 5)
    subject_id = await _get_subject_id(db_session, "english")

    key_a = await _signup(http_client, "calA@school.com", "School A")
    key_b = await _signup(http_client, "calB@school.com", "School B")

    me_b = await _get_me(http_client, key_b)
    teacher_b_id = me_b["default_teacher_id"]

    year_b = await _make_academic_year(http_client, key_b)
    class_b = await _make_class(http_client, key_b, year_b["id"], grade_id)
    cst_b = await _assign_subject(http_client, key_b, class_b["id"], subject_id, teacher_b_id)

    await http_client.post(
        f"/api/v1/classes/{class_b['id']}/subjects/{cst_b['id']}/assessment-slots",
        json={"assessment_type": "formative", "scheduled_date": "2026-05-13", "title": "B's FA"},
        headers=headers(key_b),
    )

    # Client A's calendar should be empty
    resp_a = await http_client.get("/api/v1/me/calendar?week_start=2026-05-12", headers=headers(key_a))
    assert resp_a.status_code == 200
    for day in resp_a.json()["items"]:
        assert day["assessments"] == []
        assert day["lessons"] == []

    # Client B sees their own event
    resp_b = await http_client.get("/api/v1/me/calendar?week_start=2026-05-12", headers=headers(key_b))
    assert resp_b.status_code == 200
    all_assessments = [a for day in resp_b.json()["items"] for a in day["assessments"]]
    assert len(all_assessments) == 1
    assert all_assessments[0]["title"] == "B's FA"
