"""
HTTP tests for POST /api/v1/class-lesson-slots/{slot_id}/generate-lp.

These run WITHOUT a database. We override the two FastAPI deps used by the
endpoint (`get_current_org`, `get_db_conn`) with fakes, and monkeypatch the
two generated_lps service functions so no LP-Assistant HTTP and no Postgres
is touched. The endpoint itself only issues one tenancy `fetchrow` before
delegating to the service, so a tiny fake connection is enough.

The service functions are unit/DB-tested separately in
test_generated_lps_service.py (DB-gated); here we lock the *routing* layer:
tenancy 404s, slot_type → which service fn, ValueError → 422, and the
response shape the teacher app polls against.
"""
from uuid import uuid4

import pytest

from dars.generated_lps.service import GeneratedLP
from dars.main import app
from dars.v2_api import router_generation
from dars.v2_api.deps import OrgContext, get_current_org, get_db_conn

ORG_ID = uuid4()


class FakeConn:
    """Minimal asyncpg-connection stand-in.

    Returns whatever single-row mapping it's seeded with for `fetchrow`.
    The endpoint's only DB call is the tenancy lookup
    (`SELECT org_id, slot_type FROM class_lesson_slots WHERE id = $1`).
    """

    def __init__(self, slot_row):
        self._slot_row = slot_row
        self.fetchrow_calls: list = []

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query, args))
        return self._slot_row


def _make_lp(status: str = "IN_FLIGHT") -> GeneratedLP:
    return GeneratedLP(
        id=uuid4(),
        cache_key="ck",
        scope="global",
        scope_ref_id=None,
        curriculum_id=uuid4(),
        grade_id=uuid4(),
        subject_id=uuid4(),
        topic_id=uuid4(),
        lp_type="reading",
        status=status,
        job_id="fake-job-123",
        content=None,
    )


@pytest.fixture
def org():
    return OrgContext(
        id=ORG_ID, name="Test Org", curriculum_id=uuid4(), default_teacher_id=None
    )


def _override_deps(slot_row, org: OrgContext) -> FakeConn:
    """Wire fake org + a one-row fake connection into the app. Returns the
    FakeConn so the test can assert on what the endpoint queried."""
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


async def test_normal_lesson_slot_generates_lp(client, org, monkeypatch):
    """A plain lesson slot routes to get_or_generate_lp and returns the new
    LP id + status. The revision path must NOT be called."""
    slot_id = uuid4()
    _override_deps({"org_id": ORG_ID, "slot_type": "lesson"}, org)

    captured: list = []
    fake_lp = _make_lp(status="IN_FLIGHT")

    async def fake_global(conn, lesson_slot_id):
        captured.append(("global", lesson_slot_id))
        return fake_lp

    async def fake_revision(conn, lesson_slot_id):  # pragma: no cover
        captured.append(("revision", lesson_slot_id))
        raise AssertionError("revision path must not run for a lesson slot")

    monkeypatch.setattr(router_generation, "get_or_generate_lp", fake_global)
    monkeypatch.setattr(router_generation, "get_or_generate_revision_lp", fake_revision)

    r = await client.post(f"/api/v1/class-lesson-slots/{slot_id}/generate-lp")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["generated_lp_id"] == str(fake_lp.id)
    assert body["lp_status"] == "IN_FLIGHT"
    # Routed to the global path with the path slot_id.
    assert captured == [("global", slot_id)]


async def test_revision_slot_routes_to_revision_fn(client, org, monkeypatch):
    """A revision slot must call get_or_generate_revision_lp (calling
    get_or_generate_lp on it raises ValueError in the service)."""
    slot_id = uuid4()
    _override_deps({"org_id": ORG_ID, "slot_type": "revision"}, org)

    captured: list = []
    fake_lp = _make_lp(status="PENDING")

    async def fake_global(conn, lesson_slot_id):  # pragma: no cover
        captured.append(("global", lesson_slot_id))
        raise AssertionError("global path must not run for a revision slot")

    async def fake_revision(conn, lesson_slot_id):
        captured.append(("revision", lesson_slot_id))
        return fake_lp

    monkeypatch.setattr(router_generation, "get_or_generate_lp", fake_global)
    monkeypatch.setattr(router_generation, "get_or_generate_revision_lp", fake_revision)

    r = await client.post(f"/api/v1/class-lesson-slots/{slot_id}/generate-lp")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["generated_lp_id"] == str(fake_lp.id)
    assert body["lp_status"] == "PENDING"
    assert captured == [("revision", slot_id)]


async def test_slot_in_another_org_returns_404(client, org, monkeypatch):
    """Slot exists but belongs to a different org → 404 (no cross-org leak),
    and the service is never called."""
    slot_id = uuid4()
    other_org_id = uuid4()
    _override_deps({"org_id": other_org_id, "slot_type": "lesson"}, org)

    def _boom(*a, **k):  # pragma: no cover
        raise AssertionError("service must not run for a cross-org slot")

    monkeypatch.setattr(router_generation, "get_or_generate_lp", _boom)
    monkeypatch.setattr(router_generation, "get_or_generate_revision_lp", _boom)

    r = await client.post(f"/api/v1/class-lesson-slots/{slot_id}/generate-lp")
    assert r.status_code == 404, r.text


async def test_nonexistent_slot_returns_404(client, org, monkeypatch):
    """No such slot (fetchrow → None) → 404, service never called."""
    slot_id = uuid4()
    _override_deps(None, org)

    def _boom(*a, **k):  # pragma: no cover
        raise AssertionError("service must not run for a missing slot")

    monkeypatch.setattr(router_generation, "get_or_generate_lp", _boom)
    monkeypatch.setattr(router_generation, "get_or_generate_revision_lp", _boom)

    r = await client.post(f"/api/v1/class-lesson-slots/{slot_id}/generate-lp")
    assert r.status_code == 404, r.text


async def test_value_error_from_service_maps_to_422(client, org, monkeypatch):
    """Slot context problems (no topic, empty topic_text, etc.) surface as a
    ValueError from the service → 422, not 500."""
    slot_id = uuid4()
    _override_deps({"org_id": ORG_ID, "slot_type": "lesson"}, org)

    async def fake_global(conn, lesson_slot_id):
        raise ValueError("lesson_slot has no topic_id; cannot build LP request")

    monkeypatch.setattr(router_generation, "get_or_generate_lp", fake_global)

    r = await client.post(f"/api/v1/class-lesson-slots/{slot_id}/generate-lp")
    assert r.status_code == 422, r.text
    assert "topic_id" in r.json()["detail"]


async def test_requires_auth(client, monkeypatch):
    """No API key / admin session → 401 before any DB access. Stub the DB
    dep so the unused connection doesn't try the real pool."""

    async def _no_conn():
        yield None

    app.dependency_overrides[get_db_conn] = _no_conn
    try:
        r = await client.post(
            f"/api/v1/class-lesson-slots/{uuid4()}/generate-lp"
        )
    finally:
        app.dependency_overrides.pop(get_db_conn, None)
    assert r.status_code == 401, r.text
