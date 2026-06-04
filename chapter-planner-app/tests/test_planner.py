"""
CPE Phase 2 tests (F-2.5). No live LLM — a FakePlannerLLM returns canned JSON.
Covers the validator (each D-8 invariant), the parser, and the /plan endpoint
(valid + each failure mode).
"""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Make the app importable (flat module layout, like UG_LP).
APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

import main  # noqa: E402
from models import PlanRequest  # noqa: E402
from planner import (  # noqa: E402
    PlanParseError,
    make_chapter_plan,
    parse_plan_units,
    validate_plan,
)
from planner_llm import PlannerLLMError  # noqa: E402


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
def sample_request(period_count=2) -> PlanRequest:
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


def good_units_json(period_count=2) -> str:
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


def units_from(req, raw):
    """Helper: parse + build PlanUnit list (mirrors make_chapter_plan internals)."""
    from planner import _resolve_topic_text
    from models import PlanUnit
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
# Parser
# --------------------------------------------------------------------------
def test_shared_sub_slo_across_topics_is_allowed():
    # A sub-SLO taught on >1 topic (same id+statement) must NOT be rejected
    # (real data — e.g. Ch.1 "Hello, World"). Regression for the cross-chapter
    # uniqueness bug.
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
    with pytest.raises(Exception):
        PlanRequest(
            subject="Eng", grade=1, period_count=1,
            chapter={"title": "X", "topics": [
                {"id": "t1", "topic_text": "x",
                 "slos": [{"id": "dup", "statement": "statement one"}]},
                {"id": "t2", "topic_text": "y",
                 "slos": [{"id": "dup", "statement": "DIFFERENT statement"}]},
            ]},
        )


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
# Validator — D-8 (a)-(e)
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


def test_validator_unknown_id():  # (d)
    req = sample_request(2)
    raw = json.dumps({"units": [
        {"sequence": 1, "lp_type": "reading", "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "x"},
        {"sequence": 2, "lp_type": "grammar", "topic_ids": ["tZ"], "slo_ids": ["s2"], "rationale": "y"},
    ]})
    assert "unknown topic_ids" in validate_plan(units_from(req, raw), req)


# --------------------------------------------------------------------------
# make_chapter_plan + endpoint
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_make_chapter_plan_valid():
    req = sample_request(2)
    plan = await make_chapter_plan(req, FakePlannerLLM(good_units_json()))
    assert len(plan.units) == 2
    assert plan.units[0].topic_text == "hello, good morning"  # resolved by CPE
    assert {u.lp_type for u in plan.units} == {"reading", "grammar"}


def _client_with(llm):
    main.AgentSdkPlannerLLM = lambda: llm  # type: ignore
    return TestClient(main.app)


def test_endpoint_valid(monkeypatch):
    client = _client_with(FakePlannerLLM(good_units_json()))
    r = client.post("/plan", json=sample_request(2).model_dump())
    assert r.status_code == 200
    assert len(r.json()["units"]) == 2


def test_endpoint_llm_error_502():
    client = _client_with(BoomLLM())
    r = client.post("/plan", json=sample_request(2).model_dump())
    assert r.status_code == 502
    assert "planner LLM error" in r.json()["detail"]


def test_endpoint_invalid_plan_422():
    client = _client_with(FakePlannerLLM(good_units_json(2)))  # 2 units...
    r = client.post("/plan", json=sample_request(3).model_dump())  # ...but 3 requested
    assert r.status_code == 422
    assert "invalid plan" in r.json()["detail"]


def test_endpoint_input_validation_422():
    client = _client_with(FakePlannerLLM(good_units_json()))
    bad = sample_request(2).model_dump()
    bad["period_count"] = 0  # violates > 0
    r = client.post("/plan", json=bad)
    assert r.status_code == 422
