"""
Tests for the school/ teacher-planning module.

Pattern follows test_auth.py / test_clients.py:
  - db_session: in-memory SQLite session
  - http_client: overrides get_db, wires up AsyncClient against the app
  - api_key: obtained via /auth/signup
"""

from datetime import date, timedelta

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
from dars.curriculum.models import Book, BookChapter
from dars.curriculum_data.models import CurriculumData
from dars.database import Base, get_db
from dars.lookup.models import Grade, Subject
from dars.main import app

TEST_DB = "sqlite+aiosqlite:///:memory:"

_GRADE_CODES = list(range(1, 11))
_SUBJECT_CODES = ["Math", "Science", "English", "Urdu", "Art", "Music"]


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
        for code in _GRADE_CODES:
            session.add(Grade(code=code, display_name=f"Grade {code}"))
        for code in _SUBJECT_CODES:
            session.add(Subject(code=code, display_name=code))
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


@pytest.fixture(scope="function")
async def api_key(http_client):
    """Create a client via signup and return the raw API key."""
    resp = await http_client.post(
        "/auth/signup",
        json={"email": "school@test.com", "password": "pass123", "name": "School Test", "curriculum": "NCP"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["api_key"]


@pytest.fixture(scope="function")
async def api_key2(http_client):
    """A second client (different client_id) for isolation tests."""
    resp = await http_client.post(
        "/auth/signup",
        json={"email": "other@test.com", "password": "pass456", "name": "Other Client", "curriculum": "SNC"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["api_key"]


def headers(key: str) -> dict:
    return {"X-API-Key": key}


# Helpers for building fixtures inline ----------------------------------------


async def _make_academic_year(http_client, key: str, *, name="2025-26",
                               start="2025-04-01", end="2026-03-31") -> dict:
    resp = await http_client.post(
        "/api/v1/academic-years",
        json={"name": name, "start_date": start, "end_date": end},
        headers=headers(key),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _make_class(http_client, key: str, year_id: str, db_session: AsyncSession, *,
                      grade: int = 5, section: str = "A") -> dict:
    result = await db_session.execute(select(Grade).where(Grade.code == grade))
    grade_obj = result.scalar_one()
    resp = await http_client.post(
        "/api/v1/classes",
        json={
            "academic_year_id": year_id,
            "grade_id": grade_obj.id,
            "section": section,
            "name": f"Grade {grade}-{section}",
        },
        headers=headers(key),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _assign_subject(http_client, key: str, class_id: str,
                          db_session: AsyncSession, subject: str = "Math") -> dict:
    result = await db_session.execute(select(Subject).where(Subject.code == subject))
    subject_obj = result.scalar_one()
    resp = await http_client.post(
        f"/api/v1/classes/{class_id}/subjects",
        json={"subject_id": subject_obj.id},
        headers=headers(key),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _make_chapter_id(db_session: AsyncSession) -> int:
    """Create a Book + BookChapter and return the chapter's integer id."""
    ncp = (await db_session.execute(select(CurriculumData).where(CurriculumData.code == "NCP"))).scalar_one()
    math = (await db_session.execute(select(Subject).where(Subject.code == "Math"))).scalar_one()
    grade5 = (await db_session.execute(select(Grade).where(Grade.code == 5))).scalar_one()

    book = Book(curriculum_id=ncp.id, grade_id=grade5.id, subject_id=math.id, title="Test Book")
    db_session.add(book)
    await db_session.flush()
    await db_session.refresh(book)
    chapter = BookChapter(book_id=book.id, title="Ch 1", chapter_number=1)
    db_session.add(chapter)
    await db_session.flush()
    await db_session.refresh(chapter)
    await db_session.commit()
    return chapter.id


# ---------------------------------------------------------------------------
# 1. Academic year + holidays
# ---------------------------------------------------------------------------


async def test_create_and_list_academic_year(http_client, api_key):
    year = await _make_academic_year(http_client, api_key)
    assert year["name"] == "2025-26"
    assert "id" in year

    resp = await http_client.get("/api/v1/academic-years", headers=headers(api_key))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == year["id"]


async def test_add_and_list_holidays(http_client, api_key):
    year = await _make_academic_year(http_client, api_key)
    year_id = year["id"]

    resp = await http_client.post(
        f"/api/v1/academic-years/{year_id}/holidays",
        json={"date": "2025-08-14", "name": "Independence Day"},
        headers=headers(api_key),
    )
    assert resp.status_code == 201
    hol = resp.json()
    assert hol["name"] == "Independence Day"

    resp = await http_client.get(
        f"/api/v1/academic-years/{year_id}/holidays",
        headers=headers(api_key),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == hol["id"]


async def test_delete_holiday(http_client, api_key):
    year = await _make_academic_year(http_client, api_key)
    year_id = year["id"]

    resp = await http_client.post(
        f"/api/v1/academic-years/{year_id}/holidays",
        json={"date": "2025-08-14", "name": "Independence Day"},
        headers=headers(api_key),
    )
    hol_id = resp.json()["id"]

    del_resp = await http_client.delete(
        f"/api/v1/academic-years/{year_id}/holidays/{hol_id}",
        headers=headers(api_key),
    )
    assert del_resp.status_code == 204

    resp = await http_client.get(
        f"/api/v1/academic-years/{year_id}/holidays",
        headers=headers(api_key),
    )
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# 2. Create class, assign subject + teacher + book
# ---------------------------------------------------------------------------


async def test_create_class_and_assign_subject(http_client, api_key, db_session):
    year = await _make_academic_year(http_client, api_key)
    cls = await _make_class(http_client, api_key, year["id"], db_session)
    assert "grade_id" in cls

    # Assign subject (no teacher/book)
    cst = await _assign_subject(http_client, api_key, cls["id"], db_session, subject="Science")
    assert "subject_id" in cst
    assert cst["class_id"] == cls["id"]

    # Get class with subjects
    resp = await http_client.get(f"/api/v1/classes/{cls['id']}", headers=headers(api_key))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["subjects"]) == 1
    assert "subject_id" in data["subjects"][0]


# ---------------------------------------------------------------------------
# 3. Timetable and compute_teaching_days
# ---------------------------------------------------------------------------


async def test_set_timetable_and_compute_teaching_days(http_client, api_key, db_session):
    # Short academic year: Mon 2026-05-04 to Fri 2026-05-08  (5 school days)
    year = await _make_academic_year(
        http_client, api_key, start="2026-05-04", end="2026-05-08"
    )
    cls = await _make_class(http_client, api_key, year["id"], db_session)
    cst = await _assign_subject(http_client, api_key, cls["id"], db_session)

    # Set timetable: Mon (0), Wed (2), Fri (4)
    resp = await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/timetable",
        json={"slots": [
            {"day_of_week": 0},
            {"day_of_week": 2},
            {"day_of_week": 4},
        ]},
        headers=headers(api_key),
    )
    assert resp.status_code == 200
    tt = resp.json()
    assert len(tt["items"]) == 3

    # Get timetable
    resp = await http_client.get(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/timetable",
        headers=headers(api_key),
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 3

    # Verify via service
    from dars.school.service import compute_teaching_days
    teaching = await compute_teaching_days(int(cst["id"]), db_session)
    # Mon 05-04, Wed 05-06, Fri 05-08 → 3 days
    assert len(teaching) == 3
    assert teaching[0] == date(2026, 5, 4)
    assert teaching[1] == date(2026, 5, 6)
    assert teaching[2] == date(2026, 5, 8)


async def test_compute_teaching_days_excludes_holidays(http_client, api_key, db_session):
    # Mon 2026-05-04 to Fri 2026-05-08 (Mon/Wed/Fri active)
    year = await _make_academic_year(
        http_client, api_key, name="Y2", start="2026-05-04", end="2026-05-08"
    )
    cls = await _make_class(http_client, api_key, year["id"], db_session, grade=6, section="B")
    cst = await _assign_subject(http_client, api_key, cls["id"], db_session, subject="English")

    await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/timetable",
        json={"slots": [{"day_of_week": 0}, {"day_of_week": 2}, {"day_of_week": 4}]},
        headers=headers(api_key),
    )

    # Add Wednesday as holiday
    await http_client.post(
        f"/api/v1/academic-years/{year['id']}/holidays",
        json={"date": "2026-05-06", "name": "Local Holiday"},
        headers=headers(api_key),
    )

    from dars.school.service import compute_teaching_days
    teaching = await compute_teaching_days(int(cst["id"]), db_session)
    # Should be Mon 05-04 and Fri 05-08 (Wed excluded)
    assert len(teaching) == 2
    assert date(2026, 5, 6) not in teaching


# ---------------------------------------------------------------------------
# 4. Bulk upsert chapter plans
# ---------------------------------------------------------------------------


async def test_bulk_upsert_chapter_plans(http_client, api_key, db_session):
    year = await _make_academic_year(
        http_client, api_key, name="Y3", start="2026-05-04", end="2026-06-30"
    )
    cls = await _make_class(http_client, api_key, year["id"], db_session, grade=7, section="C")
    cst = await _assign_subject(http_client, api_key, cls["id"], db_session, subject="Math")

    # Create real BookChapter records (chapter_id is an int FK)
    ch1 = await _make_chapter_id(db_session)
    ch2 = await _make_chapter_id(db_session)
    ch3 = await _make_chapter_id(db_session)

    resp = await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/chapter-plans",
        json={"plans": [
            {"chapter_id": ch1, "position": 1, "teaching_days": 10},
            {"chapter_id": ch2, "position": 2, "teaching_days": 8},
            {"chapter_id": ch3, "position": 3, "teaching_days": 6},
        ]},
        headers=headers(api_key),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 3
    # Ordered by position
    positions = [item["position"] for item in data["items"]]
    assert positions == sorted(positions)

    # Upsert again with updated teaching_days
    resp2 = await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/chapter-plans",
        json={"plans": [
            {"chapter_id": ch1, "position": 1, "teaching_days": 12},
        ]},
        headers=headers(api_key),
    )
    assert resp2.status_code == 200
    # The updated plan should reflect 12 days
    updated = [i for i in resp2.json()["items"] if i["chapter_id"] == ch1]
    assert updated[0]["teaching_days"] == 12


# ---------------------------------------------------------------------------
# 5. Generate lesson sequence
# ---------------------------------------------------------------------------


async def test_generate_lesson_sequence(http_client, api_key, db_session):
    year = await _make_academic_year(
        http_client, api_key, name="Y4", start="2026-05-04", end="2026-07-31"
    )
    cls = await _make_class(http_client, api_key, year["id"], db_session, grade=8, section="D")
    cst = await _assign_subject(http_client, api_key, cls["id"], db_session, subject="Math")

    ch1 = await _make_chapter_id(db_session)
    plan_resp = await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/chapter-plans",
        json={"plans": [{"chapter_id": ch1, "position": 1, "teaching_days": 6}]},
        headers=headers(api_key),
    )
    plan_id = plan_resp.json()["items"][0]["id"]

    # Generate
    resp = await http_client.post(
        f"/api/v1/chapter-plans/{plan_id}/lesson-slots/generate",
        headers=headers(api_key),
    )
    assert resp.status_code == 200
    slots = resp.json()["items"]
    assert len(slots) == 6

    # Last slot must be "Revision"
    assert slots[-1]["lp_type"] == "Revision"

    # All day numbers present in order
    day_nums = [s["day_number"] for s in slots]
    assert day_nums == list(range(1, 7))


async def test_lesson_sequence_idempotent_regeneration(http_client, api_key, db_session):
    year = await _make_academic_year(
        http_client, api_key, name="Y4b", start="2026-05-04", end="2026-07-31"
    )
    cls = await _make_class(http_client, api_key, year["id"], db_session, grade=9, section="E")
    cst = await _assign_subject(http_client, api_key, cls["id"], db_session, subject="English")

    ch1 = await _make_chapter_id(db_session)
    plan_resp = await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/chapter-plans",
        json={"plans": [{"chapter_id": ch1, "position": 1, "teaching_days": 4}]},
        headers=headers(api_key),
    )
    plan_id = plan_resp.json()["items"][0]["id"]

    await http_client.post(
        f"/api/v1/chapter-plans/{plan_id}/lesson-slots/generate",
        headers=headers(api_key),
    )
    # Regenerate
    resp = await http_client.post(
        f"/api/v1/chapter-plans/{plan_id}/lesson-slots/generate",
        headers=headers(api_key),
    )
    assert resp.status_code == 200
    slots = resp.json()["items"]
    # Should still be exactly 4 (not duplicated)
    assert len(slots) == 4
    assert slots[-1]["lp_type"] == "Revision"


# ---------------------------------------------------------------------------
# 6. Mark slot as taught
# ---------------------------------------------------------------------------


async def test_mark_slot_taught(http_client, api_key, db_session):
    year = await _make_academic_year(
        http_client, api_key, name="Y5", start="2026-05-04", end="2026-07-31"
    )
    cls = await _make_class(http_client, api_key, year["id"], db_session, grade=10, section="F")
    cst = await _assign_subject(http_client, api_key, cls["id"], db_session, subject="Science")

    ch1 = await _make_chapter_id(db_session)
    plan_resp = await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/chapter-plans",
        json={"plans": [{"chapter_id": ch1, "position": 1, "teaching_days": 3}]},
        headers=headers(api_key),
    )
    plan_id = plan_resp.json()["items"][0]["id"]

    gen_resp = await http_client.post(
        f"/api/v1/chapter-plans/{plan_id}/lesson-slots/generate",
        headers=headers(api_key),
    )
    slot_id = gen_resp.json()["items"][0]["id"]
    assert gen_resp.json()["items"][0]["status"] == "planned"

    # Mark taught
    resp = await http_client.patch(
        f"/api/v1/class-lesson-slots/{slot_id}/mark-taught",
        headers=headers(api_key),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "taught"
    assert data["taught_date"] is not None


# ---------------------------------------------------------------------------
# 7. Auto-schedule formative assessments
# ---------------------------------------------------------------------------


async def test_auto_schedule_formative_assessments(http_client, api_key, db_session):
    # Academic year with clear Mon-Fri schedule
    year = await _make_academic_year(
        http_client, api_key, name="Y6", start="2026-05-04", end="2026-06-26"
    )
    cls = await _make_class(http_client, api_key, year["id"], db_session, grade=4, section="G")
    cst = await _assign_subject(http_client, api_key, cls["id"], db_session, subject="Urdu")

    # Mon/Wed/Fri timetable
    await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/timetable",
        json={"slots": [{"day_of_week": 0}, {"day_of_week": 2}, {"day_of_week": 4}]},
        headers=headers(api_key),
    )

    ch1 = await _make_chapter_id(db_session)
    ch2 = await _make_chapter_id(db_session)
    plan_resp = await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/chapter-plans",
        json={"plans": [
            {"chapter_id": ch1, "position": 1, "teaching_days": 3},
            {"chapter_id": ch2, "position": 2, "teaching_days": 3},
        ]},
        headers=headers(api_key),
    )
    assert plan_resp.status_code == 200

    # Auto-schedule
    resp = await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/assessment-slots/auto-schedule",
        headers=headers(api_key),
    )
    assert resp.status_code == 200
    slots = resp.json()["items"]
    # One FA per chapter
    assert len(slots) == 2
    for s in slots:
        assert s["assessment_type"] == "formative"


async def test_auto_schedule_fa_idempotent(http_client, api_key, db_session):
    year = await _make_academic_year(
        http_client, api_key, name="Y7", start="2026-05-04", end="2026-06-26"
    )
    cls = await _make_class(http_client, api_key, year["id"], db_session, grade=3, section="H")
    cst = await _assign_subject(http_client, api_key, cls["id"], db_session, subject="Science")

    await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/timetable",
        json={"slots": [{"day_of_week": 0}, {"day_of_week": 2}, {"day_of_week": 4}]},
        headers=headers(api_key),
    )
    ch1 = await _make_chapter_id(db_session)
    await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/chapter-plans",
        json={"plans": [{"chapter_id": ch1, "position": 1, "teaching_days": 2}]},
        headers=headers(api_key),
    )

    # Schedule twice
    r1 = await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/assessment-slots/auto-schedule",
        headers=headers(api_key),
    )
    r2 = await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/assessment-slots/auto-schedule",
        headers=headers(api_key),
    )
    # Same slot returned both times, no duplicates
    assert r1.json()["items"][0]["id"] == r2.json()["items"][0]["id"]


# ---------------------------------------------------------------------------
# 8. GET /today returns only today's scheduled classes
# ---------------------------------------------------------------------------


async def test_today_endpoint_returns_todays_classes(http_client, api_key, db_session):
    from datetime import datetime, timezone

    today_weekday = datetime.now(timezone.utc).weekday()

    year = await _make_academic_year(
        http_client, api_key, name="Y8",
        start=str(date.today() - timedelta(days=5)),
        end=str(date.today() + timedelta(days=60)),
    )
    cls = await _make_class(http_client, api_key, year["id"], db_session, grade=2, section="I")
    cst = await _assign_subject(http_client, api_key, cls["id"], db_session, subject="Art")

    # Set timetable for today's weekday only
    await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/timetable",
        json={"slots": [{"day_of_week": today_weekday}]},
        headers=headers(api_key),
    )

    resp = await http_client.get("/api/v1/today", headers=headers(api_key))
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) >= 1
    assert all("subject_id" in e for e in entries)


async def test_today_endpoint_excludes_other_weekdays(http_client, api_key, db_session):
    from datetime import datetime, timezone

    today_weekday = datetime.now(timezone.utc).weekday()
    # Schedule on a DIFFERENT weekday
    other_day = (today_weekday + 1) % 7

    year = await _make_academic_year(
        http_client, api_key, name="Y9",
        start=str(date.today() - timedelta(days=5)),
        end=str(date.today() + timedelta(days=60)),
    )
    cls = await _make_class(http_client, api_key, year["id"], db_session, grade=1, section="J")
    music_id = (await db_session.execute(select(Subject).where(Subject.code == "Music"))).scalar_one().id
    cst = await _assign_subject(http_client, api_key, cls["id"], db_session, subject="Music")

    await http_client.post(
        f"/api/v1/classes/{cls['id']}/subjects/{cst['id']}/timetable",
        json={"slots": [{"day_of_week": other_day}]},
        headers=headers(api_key),
    )

    resp = await http_client.get("/api/v1/today", headers=headers(api_key))
    assert resp.status_code == 200
    subject_ids = [e["subject_id"] for e in resp.json()]
    assert music_id not in subject_ids


# ---------------------------------------------------------------------------
# 9. Wrong client_id → 404/empty results
# ---------------------------------------------------------------------------


async def test_wrong_client_cannot_see_other_client_data(http_client, api_key, api_key2):
    year = await _make_academic_year(http_client, api_key, name="Y10")
    year_id = year["id"]

    # Client 2 tries to list client 1's academic years
    resp = await http_client.get("/api/v1/academic-years", headers=headers(api_key2))
    ids = [y["id"] for y in resp.json()["items"]]
    assert year_id not in ids


async def test_wrong_client_cannot_access_holiday_endpoint(http_client, api_key, api_key2):
    year = await _make_academic_year(http_client, api_key, name="Y11")
    year_id = year["id"]

    # Client 2 tries to add a holiday to client 1's year
    resp = await http_client.post(
        f"/api/v1/academic-years/{year_id}/holidays",
        json={"date": "2025-12-25", "name": "Christmas"},
        headers=headers(api_key2),
    )
    assert resp.status_code == 404


async def test_wrong_client_cannot_access_class(http_client, api_key, api_key2, db_session):
    year = await _make_academic_year(http_client, api_key, name="Y12")
    cls = await _make_class(http_client, api_key, year["id"], db_session)

    # Client 2 tries to get client 1's class
    resp = await http_client.get(f"/api/v1/classes/{cls['id']}", headers=headers(api_key2))
    assert resp.status_code == 404


async def test_missing_api_key_returns_401(http_client):
    resp = await http_client.get("/api/v1/academic-years")
    assert resp.status_code == 401


async def test_invalid_api_key_returns_401(http_client):
    resp = await http_client.get(
        "/api/v1/academic-years",
        headers={"X-API-Key": "dars_fake_invalid_key"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 10. Step 3 — Academic Calendar: teaching days + date validation
# ---------------------------------------------------------------------------


async def test_teaching_days_count_no_holidays(http_client, api_key):
    # Sep 1 2025 (Mon) to Sep 12 2025 (Fri) = 10 weekdays
    resp = await http_client.post(
        "/api/v1/academic-years",
        json={"name": "Short Year", "start_date": "2025-09-01", "end_date": "2025-09-12"},
        headers=headers(api_key),
    )
    assert resp.status_code == 201
    year_id = resp.json()["id"]

    resp = await http_client.get(
        f"/api/v1/academic-years/{year_id}/teaching-days",
        headers=headers(api_key),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["academic_year_id"] == year_id
    assert data["teaching_days"] == 10


async def test_teaching_days_excludes_holidays(http_client, api_key):
    # Sep 1–12 2025 = 10 weekdays; add 2 holidays on Mon and Tue → 8 teaching days
    resp = await http_client.post(
        "/api/v1/academic-years",
        json={"name": "Holiday Year", "start_date": "2025-09-01", "end_date": "2025-09-12"},
        headers=headers(api_key),
    )
    assert resp.status_code == 201
    year_id = resp.json()["id"]

    await http_client.post(
        f"/api/v1/academic-years/{year_id}/holidays",
        json={"date": "2025-09-01", "name": "H1"},
        headers=headers(api_key),
    )
    await http_client.post(
        f"/api/v1/academic-years/{year_id}/holidays",
        json={"date": "2025-09-02", "name": "H2"},
        headers=headers(api_key),
    )

    resp = await http_client.get(
        f"/api/v1/academic-years/{year_id}/teaching-days",
        headers=headers(api_key),
    )
    assert resp.status_code == 200
    assert resp.json()["teaching_days"] == 8


async def test_teaching_days_excludes_weekends(http_client, api_key):
    # Sep 13–14 2025 = Sat + Sun → 0 teaching days
    resp = await http_client.post(
        "/api/v1/academic-years",
        json={"name": "Weekend Year", "start_date": "2025-09-13", "end_date": "2025-09-14"},
        headers=headers(api_key),
    )
    assert resp.status_code == 201
    year_id = resp.json()["id"]

    resp = await http_client.get(
        f"/api/v1/academic-years/{year_id}/teaching-days",
        headers=headers(api_key),
    )
    assert resp.status_code == 200
    assert resp.json()["teaching_days"] == 0


async def test_create_academic_year_invalid_dates_rejected(http_client, api_key):
    resp = await http_client.post(
        "/api/v1/academic-years",
        json={"name": "Bad Year", "start_date": "2025-09-12", "end_date": "2025-09-01"},
        headers=headers(api_key),
    )
    assert resp.status_code == 422


async def test_teaching_days_wrong_client_returns_404(http_client, api_key, api_key2):
    resp = await http_client.post(
        "/api/v1/academic-years",
        json={"name": "Client1 Year", "start_date": "2025-09-01", "end_date": "2025-09-12"},
        headers=headers(api_key),
    )
    year_id = resp.json()["id"]

    resp = await http_client.get(
        f"/api/v1/academic-years/{year_id}/teaching-days",
        headers=headers(api_key2),
    )
    assert resp.status_code == 404
