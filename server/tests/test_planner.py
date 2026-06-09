"""
Chapter planner tests (chapter-planner-in-dars Phase 1).

Ported + adapted from chapter-planner-app/tests/test_planner.py. No live LLM —
a FakePlannerLLM returns canned JSON. Covers the request-model validators, the
parser, the D-8 validator (each invariant a-e has a failing case), the planner
core, and the authenticated /api/v2/plan endpoint (valid + each failure mode).
"""
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from dars.breakdown.planner import (
    PlanParseError,
    _resolve_topic_text,
    make_chapter_plan,
    parse_plan_units,
    validate_plan,
)
from dars.breakdown.planner_llm import PlannerLLMError
from dars.breakdown.planner_models import PlanRequest, PlanUnit
from dars.main import app
from dars.v2_api import router_planner
from dars.v2_api.deps import OrgContext, get_current_org, get_db_conn


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
def sample_request(period_count: int = 2) -> PlanRequest:
    return PlanRequest(
        subject="Eng",
        grade=1,
        period_count=period_count,
        chapter={
            "title": "Hello, World",
            "topics": [
                {"id": "t1", "topic_text": "hello, good morning",
                 "slos": [{"id": "s1", "statement": "use greetings"}]},
                {"id": "t2", "topic_text": "A B C D E",
                 "slos": [{"id": "s2", "statement": "recognise letters"}]},
            ],
        },
    )


def good_units_json() -> str:
    return json.dumps({"units": [
        {"sequence": 1, "lp_type": "reading", "topic_ids": ["t1"], "slo_ids": ["s1"],
         "rationale": "intro greetings"},
        {"sequence": 2, "lp_type": "grammar", "topic_ids": ["t2"], "slo_ids": ["s2"],
         "rationale": "letters"},
    ]})


class FakePlannerLLM:
    def __init__(self, response: str):
        self._response = response

    async def complete(self, system: str, user: str) -> str:
        return self._response


class BoomLLM:
    async def complete(self, system: str, user: str) -> str:
        raise PlannerLLMError("backend down")


def units_from(req: PlanRequest, raw: str) -> list[PlanUnit]:
    """Parse + build PlanUnit list (mirrors make_chapter_plan internals)."""
    return [
        PlanUnit(
            sequence=int(u["sequence"]), lp_type=u["lp_type"],
            topic_ids=u["topic_ids"], slo_ids=u["slo_ids"],
            topic_text=_resolve_topic_text(u["topic_ids"], req),
            rationale=u.get("rationale", ""),
        )
        for u in parse_plan_units(raw)
    ]


# --------------------------------------------------------------------------
# Request-model validators (F1.1)
# --------------------------------------------------------------------------
def test_shared_sub_slo_across_topics_is_allowed():
    # A sub-SLO taught on >1 topic (same id+statement) must NOT be rejected.
    req = PlanRequest(
        subject="Eng", grade=1, period_count=2,
        chapter={"title": "Hello, World", "topics": [
            {"id": "t1", "topic_text": "greetings",
             "slos": [{"id": "shared", "statement": "Uses 'I' to refer to self."},
                      {"id": "a", "statement": "Names greetings."}]},
            {"id": "t2", "topic_text": "my name",
             "slos": [{"id": "shared", "statement": "Uses 'I' to refer to self."},
                      {"id": "b", "statement": "Writes own name."}]},
        ]},
    )
    assert {s.id for t in req.chapter.topics for s in t.slos} == {"shared", "a", "b"}


def test_same_slo_id_conflicting_statement_rejected():
    with pytest.raises(ValidationError):
        PlanRequest(
            subject="Eng", grade=1, period_count=1,
            chapter={"title": "X", "topics": [
                {"id": "t1", "topic_text": "x",
                 "slos": [{"id": "dup", "statement": "statement one"}]},
                {"id": "t2", "topic_text": "y",
                 "slos": [{"id": "dup", "statement": "DIFFERENT statement"}]},
            ]},
        )


def test_period_count_must_be_positive():
    with pytest.raises(ValidationError):
        sample_request(0)


def test_grade_out_of_range_rejected():
    with pytest.raises(ValidationError):
        PlanRequest(subject="Eng", grade=6, period_count=1,
                    chapter={"title": "X", "topics": [
                        {"id": "t1", "topic_text": "x",
                         "slos": [{"id": "s1", "statement": "y"}]}]})


def test_unknown_subject_rejected():
    with pytest.raises(ValidationError):
        PlanRequest(subject="Biology", grade=1, period_count=1,
                    chapter={"title": "X", "topics": [
                        {"id": "t1", "topic_text": "x",
                         "slos": [{"id": "s1", "statement": "y"}]}]})


def test_chapter_needs_at_least_one_topic():
    with pytest.raises(ValidationError):
        PlanRequest(subject="Eng", grade=1, period_count=1,
                    chapter={"title": "X", "topics": []})


def test_topic_needs_at_least_one_slo():
    with pytest.raises(ValidationError):
        PlanRequest(subject="Eng", grade=1, period_count=1,
                    chapter={"title": "X", "topics": [
                        {"id": "t1", "topic_text": "x", "slos": []}]})


def test_unique_topic_ids_required():
    with pytest.raises(ValidationError):
        PlanRequest(subject="Eng", grade=1, period_count=1,
                    chapter={"title": "X", "topics": [
                        {"id": "t1", "topic_text": "x",
                         "slos": [{"id": "s1", "statement": "a"}]},
                        {"id": "t1", "topic_text": "y",
                         "slos": [{"id": "s2", "statement": "b"}]}]})


# --------------------------------------------------------------------------
# Parser (F1.4)
# --------------------------------------------------------------------------
def test_parse_plain_json():
    assert len(parse_plan_units(good_units_json())) == 2


def test_parse_fenced_json():
    raw = "```json\n" + good_units_json() + "\n```"
    assert len(parse_plan_units(raw)) == 2


def test_parse_prose_preamble():
    raw = "Here is the plan:\n" + good_units_json()
    assert len(parse_plan_units(raw)) == 2


def test_parse_garbage_raises():
    with pytest.raises(PlanParseError):
        parse_plan_units("not json at all")


def test_parse_missing_units_raises():
    with pytest.raises(PlanParseError):
        parse_plan_units(json.dumps({"foo": 1}))


# --------------------------------------------------------------------------
# Validator — D-8 (a)-(e), each with a failing case
# --------------------------------------------------------------------------
def test_validator_passes_good_plan():
    req = sample_request(2)
    assert validate_plan(units_from(req, good_units_json()), req) is None


def test_validator_wrong_count():  # (a)
    req = sample_request(3)
    msg = validate_plan(units_from(req, good_units_json()), req)
    assert "expected 3 units" in msg


def test_validator_bad_sequence():  # (e)
    req = sample_request(2)
    raw = json.dumps({"units": [
        {"sequence": 1, "lp_type": "reading", "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "x"},
        {"sequence": 1, "lp_type": "grammar", "topic_ids": ["t2"], "slo_ids": ["s2"], "rationale": "y"},
    ]})
    assert "permutation" in validate_plan(units_from(req, raw), req)


def test_validator_missing_slo():  # (b)
    req = sample_request(2)
    raw = json.dumps({"units": [
        {"sequence": 1, "lp_type": "reading", "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "x"},
        {"sequence": 2, "lp_type": "grammar", "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "y"},
    ]})
    assert "not covered" in validate_plan(units_from(req, raw), req)


def test_validator_bad_lp_type():  # (c)
    req = sample_request(2)
    raw = json.dumps({"units": [
        {"sequence": 1, "lp_type": "concrete", "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "x"},
        {"sequence": 2, "lp_type": "grammar", "topic_ids": ["t2"], "slo_ids": ["s2"], "rationale": "y"},
    ]})
    assert "not allowed" in validate_plan(units_from(req, raw), req)


def test_validator_unknown_topic_id():  # (d)
    req = sample_request(2)
    raw = json.dumps({"units": [
        {"sequence": 1, "lp_type": "reading", "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "x"},
        {"sequence": 2, "lp_type": "grammar", "topic_ids": ["tZ"], "slo_ids": ["s2"], "rationale": "y"},
    ]})
    assert "unknown topic_ids" in validate_plan(units_from(req, raw), req)


def test_validator_unknown_slo_id():  # (d)
    req = sample_request(2)
    raw = json.dumps({"units": [
        {"sequence": 1, "lp_type": "reading", "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "x"},
        {"sequence": 2, "lp_type": "grammar", "topic_ids": ["t2"], "slo_ids": ["sZ"], "rationale": "y"},
    ]})
    assert "unknown slo_ids" in validate_plan(units_from(req, raw), req)


# --------------------------------------------------------------------------
# make_chapter_plan (F1.4)
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_make_chapter_plan_valid():
    req = sample_request(2)
    plan = await make_chapter_plan(req, FakePlannerLLM(good_units_json()))
    assert len(plan.units) == 2
    assert plan.units[0].topic_text == "hello, good morning"  # resolved by core
    assert {u.lp_type for u in plan.units} == {"reading", "grammar"}


@pytest.mark.asyncio
async def test_make_chapter_plan_llm_error_propagates():
    with pytest.raises(PlannerLLMError):
        await make_chapter_plan(sample_request(2), BoomLLM())


# --------------------------------------------------------------------------
# Endpoint — /api/v2/plan (F1.5)
# --------------------------------------------------------------------------
@pytest.fixture
def auth_override():
    """Override the org auth dependency with a fake org, restore after."""
    org = OrgContext(id=uuid4(), name="Test Org", curriculum_id=uuid4(), default_teacher_id=None)
    app.dependency_overrides[get_current_org] = lambda: org
    yield org
    app.dependency_overrides.pop(get_current_org, None)


def _use_llm(monkeypatch, llm):
    monkeypatch.setattr(router_planner, "AgentSdkPlannerLLM", lambda: llm)


async def test_endpoint_valid(client, auth_override, monkeypatch):
    _use_llm(monkeypatch, FakePlannerLLM(good_units_json()))
    r = await client.post("/api/v2/plan", json=sample_request(2).model_dump())
    assert r.status_code == 200
    body = r.json()
    assert len(body["units"]) == 2
    assert body["units"][0]["topic_text"] == "hello, good morning"


async def test_endpoint_requires_auth(client, monkeypatch):
    # Real get_current_org runs (no auth header) → 401, before any DB access.
    # Stub get_db_conn so the unused DB dependency doesn't touch the sqlite DSN.
    _use_llm(monkeypatch, FakePlannerLLM(good_units_json()))

    async def _no_conn():
        yield None

    app.dependency_overrides[get_db_conn] = _no_conn
    try:
        r = await client.post("/api/v2/plan", json=sample_request(2).model_dump())
    finally:
        app.dependency_overrides.pop(get_db_conn, None)
    assert r.status_code == 401


async def test_endpoint_llm_error_502(client, auth_override, monkeypatch):
    _use_llm(monkeypatch, BoomLLM())
    r = await client.post("/api/v2/plan", json=sample_request(2).model_dump())
    assert r.status_code == 502
    assert "planner LLM error" in r.json()["detail"]


async def test_endpoint_invalid_plan_422(client, auth_override, monkeypatch):
    # LLM returns 2 units but 3 were requested → validation failure.
    _use_llm(monkeypatch, FakePlannerLLM(good_units_json()))
    r = await client.post("/api/v2/plan", json=sample_request(3).model_dump())
    assert r.status_code == 422
    assert "invalid plan" in r.json()["detail"]


async def test_endpoint_bad_json_422(client, auth_override, monkeypatch):
    _use_llm(monkeypatch, FakePlannerLLM("not json at all"))
    r = await client.post("/api/v2/plan", json=sample_request(2).model_dump())
    assert r.status_code == 422
    assert "invalid plan" in r.json()["detail"]


async def test_endpoint_input_validation_422(client, auth_override, monkeypatch):
    _use_llm(monkeypatch, FakePlannerLLM(good_units_json()))
    bad = sample_request(2).model_dump()
    bad["period_count"] = 0  # violates > 0
    r = await client.post("/api/v2/plan", json=bad)
    assert r.status_code == 422


async def test_endpoint_in_openapi(client, auth_override):
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    assert "/api/v2/plan" in r.json()["paths"]
