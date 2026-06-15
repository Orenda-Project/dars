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
# Formative Assessment support — PlanUnit.slot_type (F-2.1, D-6/D-7/D-13)
# --------------------------------------------------------------------------
def test_planunit_without_slot_type_defaults_to_lesson():
    # Back-compat (D-13): a unit dict with no slot_type parses as a lesson.
    u = PlanUnit(sequence=1, lp_type="reading", topic_ids=["t1"],
                 slo_ids=["s1"], topic_text="x", rationale="y")
    assert u.slot_type == "lesson"
    assert u.lp_type == "reading"


def test_planunit_fa_with_lp_type_rejected():
    # D-7: an FA must NOT carry an lp_type.
    with pytest.raises(ValidationError):
        PlanUnit(sequence=1, slot_type="formative_assessment", lp_type="reading",
                 topic_ids=["t1"], slo_ids=["s1"], topic_text="x", rationale="y")


def test_planunit_lesson_without_lp_type_rejected():
    # D-7: a lesson MUST carry an lp_type.
    with pytest.raises(ValidationError):
        PlanUnit(sequence=1, slot_type="lesson", lp_type=None,
                 topic_ids=["t1"], slo_ids=["s1"], topic_text="x", rationale="y")


def test_planunit_fa_without_lp_type_ok():
    u = PlanUnit(sequence=1, slot_type="formative_assessment", lp_type=None,
                 topic_ids=["t1"], slo_ids=["s1"], topic_text="x", rationale="y")
    assert u.slot_type == "formative_assessment"
    assert u.lp_type is None


def test_planunit_unknown_slot_type_rejected():
    # D-6/D-12: summative (or anything else) is not an allowed slot_type here.
    with pytest.raises(ValidationError):
        PlanUnit(sequence=1, slot_type="summative", topic_ids=["t1"],
                 slo_ids=["s1"], topic_text="x", rationale="y")


def _build_units(req, raw):
    """Like units_from, but slot_type-aware (mirrors make_chapter_plan)."""
    from dars.breakdown.planner import _build_unit
    return [_build_unit(u, req) for u in parse_plan_units(raw)]


def test_validator_accepts_lessons_plus_one_fa_covering_last_slo():
    # F-2.2: (N-1) lessons + 1 FA. The FA covers s2, otherwise uncovered.
    req = sample_request(2)
    raw = json.dumps({"units": [
        {"sequence": 1, "slot_type": "lesson", "lp_type": "reading",
         "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "teach greetings"},
        {"sequence": 2, "slot_type": "formative_assessment",
         "topic_ids": ["t2"], "slo_ids": ["s2"], "rationale": "check letters"},
    ]})
    assert validate_plan(_build_units(req, raw), req) is None


def test_validator_rejects_fa_carrying_lp_type():
    # F-2.2: an FA that somehow carries an lp_type fails validation. Build the
    # PlanUnit list directly (bypassing _build_unit's lp_type drop) to reach the
    # validator's defence-in-depth branch.
    req = sample_request(2)
    units = [
        PlanUnit(sequence=1, slot_type="lesson", lp_type="reading",
                 topic_ids=["t1"], slo_ids=["s1"], topic_text="x", rationale="a"),
        # Construct a malformed-but-parseable FA by model_construct (skips the
        # model validator) to test that validate_plan still catches it.
        PlanUnit.model_construct(sequence=2, slot_type="formative_assessment",
                                 lp_type="grammar", topic_ids=["t2"],
                                 slo_ids=["s2"], topic_text="y", rationale="b"),
    ]
    msg = validate_plan(units, req)
    assert msg is not None and "must not" in msg


def test_validator_fa_plan_wrong_count_fails():
    # F-2.2: count invariant still holds with FAs in the mix.
    req = sample_request(3)  # but only 2 units returned
    raw = json.dumps({"units": [
        {"sequence": 1, "slot_type": "lesson", "lp_type": "reading",
         "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "a"},
        {"sequence": 2, "slot_type": "formative_assessment",
         "topic_ids": ["t2"], "slo_ids": ["s2"], "rationale": "b"},
    ]})
    assert "expected 3 units" in validate_plan(_build_units(req, raw), req)


def test_validator_fa_plan_missing_coverage_fails():
    # F-2.2: a plan where neither lesson nor FA covers s2 fails coverage.
    req = sample_request(2)
    raw = json.dumps({"units": [
        {"sequence": 1, "slot_type": "lesson", "lp_type": "reading",
         "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "a"},
        {"sequence": 2, "slot_type": "formative_assessment",
         "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "b"},
    ]})
    assert "not covered" in validate_plan(_build_units(req, raw), req)


def test_validator_fa_plan_bad_permutation_fails():
    # F-2.2: sequence permutation invariant still holds with FAs.
    req = sample_request(2)
    raw = json.dumps({"units": [
        {"sequence": 1, "slot_type": "lesson", "lp_type": "reading",
         "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "a"},
        {"sequence": 1, "slot_type": "formative_assessment",
         "topic_ids": ["t2"], "slo_ids": ["s2"], "rationale": "b"},
    ]})
    assert "permutation" in validate_plan(_build_units(req, raw), req)


@pytest.mark.asyncio
async def test_make_chapter_plan_with_fa_unit():
    # F-2.1/F-2.3: a mixed plan flows through make_chapter_plan, the FA's
    # lp_type is dropped to None, and validation passes.
    req = sample_request(2)
    raw = json.dumps({"units": [
        {"sequence": 1, "slot_type": "lesson", "lp_type": "reading",
         "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "a"},
        {"sequence": 2, "slot_type": "formative_assessment",
         "topic_ids": ["t2"], "slo_ids": ["s2"], "rationale": "b"},
    ]})
    plan = await make_chapter_plan(req, FakePlannerLLM(raw))
    assert [u.slot_type for u in plan.units] == ["lesson", "formative_assessment"]
    assert plan.units[1].lp_type is None
    assert plan.units[0].lp_type == "reading"


@pytest.mark.asyncio
async def test_make_chapter_plan_drops_lp_type_echoed_on_fa():
    # F-2.3: even if the model echoes an lp_type onto an FA, the core drops it so
    # the resulting plan is a clean FA (no validation error).
    req = sample_request(2)
    raw = json.dumps({"units": [
        {"sequence": 1, "slot_type": "lesson", "lp_type": "reading",
         "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "a"},
        {"sequence": 2, "slot_type": "formative_assessment", "lp_type": "grammar",
         "topic_ids": ["t2"], "slo_ids": ["s2"], "rationale": "b"},
    ]})
    plan = await make_chapter_plan(req, FakePlannerLLM(raw))
    assert plan.units[1].slot_type == "formative_assessment"
    assert plan.units[1].lp_type is None


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


# --------------------------------------------------------------------------
# Dynamic Chapter Planner Phase 2 — flex units + budget math (F-2.1, F-2.4)
# --------------------------------------------------------------------------
from dars.breakdown.chapter_plan_service import compute_buffer_budget  # noqa: E402


# --- F-2.1: flex unit parse + validate (D-15) ----------------------------

def test_planunit_flex_revision_lesson_ok():
    # A flex unit is a lesson with lp_type='revision'.
    u = PlanUnit(sequence=1, slot_type="lesson", lp_type="revision",
                 topic_ids=["t1"], slo_ids=["s1"], topic_text="x",
                 rationale="consolidate", flex=True)
    assert u.flex is True
    assert u.slot_type == "lesson"
    assert u.lp_type == "revision"


def test_planunit_flex_defaults_false():
    u = PlanUnit(sequence=1, slot_type="lesson", lp_type="reading",
                 topic_ids=["t1"], slo_ids=["s1"], topic_text="x", rationale="y")
    assert u.flex is False


def test_planunit_flex_non_revision_lp_type_rejected():
    # D-15: flex MUST be lp_type='revision'.
    with pytest.raises(ValidationError):
        PlanUnit(sequence=1, slot_type="lesson", lp_type="reading",
                 topic_ids=["t1"], slo_ids=["s1"], topic_text="x",
                 rationale="y", flex=True)


def test_planunit_flex_fa_rejected():
    # D-15: a flex unit can never be a formative_assessment.
    with pytest.raises(ValidationError):
        PlanUnit(sequence=1, slot_type="formative_assessment", lp_type=None,
                 topic_ids=["t1"], slo_ids=["s1"], topic_text="x",
                 rationale="y", flex=True)


def test_build_unit_coerces_flex_to_revision_lesson():
    # F-2.3: even if the model marks flex but echoes a different slot_type /
    # lp_type, _build_unit coerces it to a clean flex revision lesson.
    from dars.breakdown.planner import _build_unit
    req = sample_request(2)
    u = _build_unit(
        {"sequence": 1, "slot_type": "formative_assessment", "lp_type": "grammar",
         "flex": True, "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "r"},
        req,
    )
    assert u.flex is True
    assert u.slot_type == "lesson"
    assert u.lp_type == "revision"


@pytest.mark.asyncio
async def test_make_chapter_plan_with_flex_unit():
    # F-2.1/F-2.3: a mandatory lesson + an interleaved flex revision slot flows
    # through make_chapter_plan; the flex unit is preserved.
    req = sample_request(2)
    raw = json.dumps({"units": [
        {"sequence": 1, "slot_type": "lesson", "lp_type": "reading",
         "topic_ids": ["t1", "t2"], "slo_ids": ["s1", "s2"], "rationale": "teach"},
        {"sequence": 2, "slot_type": "lesson", "lp_type": "revision", "flex": True,
         "topic_ids": ["t1"], "slo_ids": ["s1"], "rationale": "consolidate"},
    ]})
    plan = await make_chapter_plan(req, FakePlannerLLM(raw))
    assert [u.flex for u in plan.units] == [False, True]
    assert plan.units[1].lp_type == "revision"


# --- F-2.4: budget math splits across representative chapter sizes --------

def test_budget_split_default_target_typical():
    # 10 teaching days @ 0.80 → 8 mandatory + 2 flex.
    assert compute_buffer_budget(10, 0.80) == (8, 2)


def test_budget_split_lower_target_more_buffer():
    # Lower target = more buffer. 10 @ 0.70 → 7 + 3.
    assert compute_buffer_budget(10, 0.70) == (7, 3)


def test_budget_split_rounds_to_nearest():
    # 3 days @ 0.80 → round(2.4)=2 mandatory + 1 flex.
    assert compute_buffer_budget(3, 0.80) == (2, 1)
    # 7 days @ 0.80 → round(5.6)=6 mandatory + 1 flex.
    assert compute_buffer_budget(7, 0.80) == (6, 1)


def test_budget_short_chapter_rounds_flex_to_zero():
    # A short chapter leans on the shared pool: flex rounds to 0 (D-4).
    assert compute_buffer_budget(1, 0.80) == (1, 0)   # 1 day → all mandatory
    assert compute_buffer_budget(2, 0.80) == (2, 0)   # round(1.6)=2 → 0 flex
    # @0.70 a 2-day chapter rounds mandatory to round(1.4)=1, 1 flex.
    assert compute_buffer_budget(2, 0.70) == (1, 1)


def test_budget_mandatory_clamped_to_at_least_one():
    # A pathological tiny target never zeroes mandatory (a chapter always
    # teaches at least one mandatory unit, D-16).
    assert compute_buffer_budget(5, 0.0) == (1, 4)


def test_budget_full_target_no_flex():
    # target 1.0 → everything mandatory, no buffer.
    assert compute_buffer_budget(10, 1.0) == (10, 0)


def test_budget_zero_days_yields_zero():
    assert compute_buffer_budget(0, 0.80) == (0, 0)


def test_budget_sum_equals_teaching_days():
    # Invariant: mandatory + flex == teaching_days for every size (1 slot=1 day).
    for days in range(1, 60):
        m, f = compute_buffer_budget(days, 0.80)
        assert m + f == days
        assert m >= 1


# --- F-2.4: PlanRequest carries + validates the budget --------------------

def test_plan_request_budget_within_period_count_ok():
    req = PlanRequest(subject="Eng", grade=1, period_count=10,
                      mandatory_budget=8,
                      chapter={"title": "X", "topics": [
                          {"id": "t1", "topic_text": "x",
                           "slos": [{"id": "s1", "statement": "y"}]}]})
    assert req.mandatory_budget == 8


def test_plan_request_budget_exceeding_period_count_rejected():
    with pytest.raises(ValidationError):
        PlanRequest(subject="Eng", grade=1, period_count=5,
                    mandatory_budget=6,
                    chapter={"title": "X", "topics": [
                        {"id": "t1", "topic_text": "x",
                         "slos": [{"id": "s1", "statement": "y"}]}]})


def test_user_prompt_carries_budget_and_flex_target():
    from dars.breakdown.planner_prompts import build_user_prompt
    req = PlanRequest(subject="Eng", grade=1, period_count=10,
                      mandatory_budget=8,
                      chapter={"title": "X", "topics": [
                          {"id": "t1", "topic_text": "x",
                           "slos": [{"id": "s1", "statement": "y"}]}]})
    payload = json.loads(build_user_prompt(req))
    assert payload["mandatory_budget"] == 8
    assert payload["flex_target"] == 2


def test_user_prompt_no_budget_means_all_mandatory():
    # The bare /plan endpoint sets no budget → everything mandatory, no flex.
    from dars.breakdown.planner_prompts import build_user_prompt
    req = sample_request(3)
    payload = json.loads(build_user_prompt(req))
    assert payload["mandatory_budget"] == 3
    assert payload["flex_target"] == 0
