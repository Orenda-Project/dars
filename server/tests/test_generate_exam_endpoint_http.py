"""
HTTP tests for POST /api/v1/class-assessment-slots/{slot_id}/generate-exam (F-3.3).

Run WITHOUT a database — same approach as test_generate_lp_endpoint_http.py:
override get_current_org + get_db_conn with fakes, monkeypatch the
get_or_generate_exam_for_assessment_slot service fn so no UG_EG HTTP / Postgres
is touched. The endpoint's only DB call is the tenancy lookup
(SELECT org_id FROM class_assessment_slots WHERE id = $1).

The service fn is DB-tested separately (test_fa_exam_slot_service.py, DB-gated);
here we lock the routing layer: tenancy 404s (missing + cross-org +
lesson-slot-id), ValueError → 422, 401 without auth, and the response shape.
"""
from uuid import uuid4

import pytest

from dars.generated_exams.service import GeneratedExam
from dars.main import app
from dars.v2_api import router_generation
from dars.v2_api.deps import OrgContext, get_current_org, get_db_conn

ORG_ID = uuid4()


class FakeConn:
    """Minimal asyncpg-connection stand-in. Returns its seeded row for the
    single tenancy fetchrow the endpoint issues."""

    def __init__(self, slot_row):
        self._slot_row = slot_row
        self.fetchrow_calls: list = []

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query, args))
        return self._slot_row


def _make_exam(status: str = "IN_FLIGHT") -> GeneratedExam:
    return GeneratedExam(
        id=uuid4(),
        cache_key="ck",
        scope="global",
        scope_ref_id=None,
        curriculum_id=uuid4(),
        grade_id=uuid4(),
        subject_id=uuid4(),
        topic_ids_hash="th",
        generation_type="class_assessment",
        question_config_hash="ch",
        status=status,
        job_id="fake-exam-job-123",
        result=None,
    )


@pytest.fixture
def org():
    return OrgContext(
        id=ORG_ID, name="Test Org", curriculum_id=uuid4(), default_teacher_id=None
    )


def _override_deps(slot_row, org: OrgContext) -> FakeConn:
    fake_conn = FakeConn(slot_row)

    async def _conn():
        yield fake_conn

    app.dependency_overrides[get_current_org] = lambda: org
    app.dependency_overrides[get_db_conn] = _conn
    return fake_conn


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_current_org, None)
    app.dependency_overrides.pop(get_db_conn, None)


async def test_valid_fa_slot_generates_exam(client, org, monkeypatch):
    slot_id = uuid4()
    _override_deps({"org_id": ORG_ID}, org)

    captured: list = []
    fake_exam = _make_exam(status="IN_FLIGHT")

    async def fake_service(conn, class_assessment_slot_id):
        captured.append(class_assessment_slot_id)
        return fake_exam

    monkeypatch.setattr(
        router_generation, "get_or_generate_exam_for_assessment_slot", fake_service
    )

    r = await client.post(f"/api/v1/class-assessment-slots/{slot_id}/generate-exam")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["generated_exam_id"] == str(fake_exam.id)
    assert body["exam_status"] == "IN_FLIGHT"
    assert captured == [slot_id]


async def test_slot_in_another_org_returns_404(client, org, monkeypatch):
    slot_id = uuid4()
    _override_deps({"org_id": uuid4()}, org)

    def _boom(*a, **k):  # pragma: no cover
        raise AssertionError("service must not run for a cross-org slot")

    monkeypatch.setattr(
        router_generation, "get_or_generate_exam_for_assessment_slot", _boom
    )

    r = await client.post(f"/api/v1/class-assessment-slots/{slot_id}/generate-exam")
    assert r.status_code == 404, r.text


async def test_missing_or_lesson_slot_returns_404(client, org, monkeypatch):
    """No row in class_assessment_slots (missing id OR a lesson-slot id) →
    fetchrow None → 404, service never called."""
    slot_id = uuid4()
    _override_deps(None, org)

    def _boom(*a, **k):  # pragma: no cover
        raise AssertionError("service must not run for a missing/lesson slot")

    monkeypatch.setattr(
        router_generation, "get_or_generate_exam_for_assessment_slot", _boom
    )

    r = await client.post(f"/api/v1/class-assessment-slots/{slot_id}/generate-exam")
    assert r.status_code == 404, r.text


async def test_value_error_from_service_maps_to_422(client, org, monkeypatch):
    slot_id = uuid4()
    _override_deps({"org_id": ORG_ID}, org)

    async def fake_service(conn, class_assessment_slot_id):
        raise ValueError("class_assessment_slot has no covered topics")

    monkeypatch.setattr(
        router_generation, "get_or_generate_exam_for_assessment_slot", fake_service
    )

    r = await client.post(f"/api/v1/class-assessment-slots/{slot_id}/generate-exam")
    assert r.status_code == 422, r.text
    assert "covered topics" in r.json()["detail"]


async def test_requires_auth(client):
    """No API key / admin session → 401 before any DB access."""

    async def _no_conn():
        yield None

    app.dependency_overrides[get_db_conn] = _no_conn
    try:
        r = await client.post(
            f"/api/v1/class-assessment-slots/{uuid4()}/generate-exam"
        )
    finally:
        app.dependency_overrides.pop(get_db_conn, None)
    assert r.status_code == 401, r.text
