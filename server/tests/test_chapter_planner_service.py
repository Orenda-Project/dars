"""
Chapter Planner unit tests (Phase 1 — F-1.1..F-1.5).

Pure, no DB, no network. The LLM is injected as a fake PlannerLLM; the
claude-agent-sdk is never imported by the suite (lazy-import backend).
"""
import json
from uuid import uuid4

import pytest

from dars.breakdown.chapter_planner_service import (
    AgentSdkPlannerLLM,
    ApiKeyPlannerLLM,
    ChapterPlan,
    PlanInputs,
    PlanItem,
    PlannerLLMError,
    SloInput,
    SubSloInput,
    TopicInput,
    get_planner_llm,
    make_chapter_plan,
    plan_deterministic,
    plan_with_llm,
    validate_plan,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class FakeLLM:
    """Returns canned text, or raises, on complete()."""

    def __init__(self, *, returns: str | None = None, raises: Exception | None = None):
        self._returns = returns
        self._raises = raises
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self._raises is not None:
            raise self._raises
        assert self._returns is not None
        return self._returns


def _inputs(period_count: int = 6, n_topics: int = 3, subject: str = "Eng") -> PlanInputs:
    topics = []
    for i in range(n_topics):
        topics.append(
            TopicInput(
                topic_id=uuid4(),
                title=f"Topic {i}",
                topic_text=f"Body of topic {i}",
                sub_slos=[
                    SubSloInput(uuid4(), f"SS{i}.1", f"sub-slo {i}.1"),
                    SubSloInput(uuid4(), f"SS{i}.2", f"sub-slo {i}.2"),
                ],
            )
        )
    return PlanInputs(
        subject_code=subject,
        period_count=period_count,
        topics=topics,
        chapter_slos=[SloInput("S1", "an slo", "reading")],
    )


def _valid_plan_for(inputs: PlanInputs) -> ChapterPlan:
    """Build a hand-made valid plan: one LP per topic + FAs to fill periods."""
    items: list[PlanItem] = []
    for t in inputs.topics:
        items.append(
            PlanItem(
                kind="lp",
                topic_ids=[t.topic_id],
                sub_slo_ids=[ss.sub_slo_id for ss in t.sub_slos],
                lp_type="reading",
            )
        )
    all_topic_ids = [t.topic_id for t in inputs.topics]
    all_sub_ids = [ss.sub_slo_id for t in inputs.topics for ss in t.sub_slos]
    while len(items) < inputs.period_count:
        items.append(
            PlanItem(kind="fa", topic_ids=list(all_topic_ids), sub_slo_ids=list(all_sub_ids))
        )
    return ChapterPlan(items=items[: inputs.period_count], source="llm")


# ---------------------------------------------------------------------------
# F-1.1 — data structures
# ---------------------------------------------------------------------------


def test_lp_item_requires_topic_and_sub_slo():
    with pytest.raises(ValueError):
        PlanItem(kind="lp", topic_ids=[], sub_slo_ids=[uuid4()], lp_type="reading")
    with pytest.raises(ValueError):
        PlanItem(kind="lp", topic_ids=[uuid4()], sub_slo_ids=[], lp_type="reading")
    with pytest.raises(ValueError):
        PlanItem(kind="lp", topic_ids=[uuid4()], sub_slo_ids=[uuid4()], lp_type=None)


def test_fa_item_allows_empty_coverage():
    # FA construction does not require coverage at the dataclass level.
    PlanItem(kind="fa", topic_ids=[], sub_slo_ids=[])


def test_chapter_plan_round_trips_doc_05_shape():
    t1, t2 = uuid4(), uuid4()
    s1, s2 = uuid4(), uuid4()
    raw = {
        "items": [
            {"kind": "lp", "topic_ids": [str(t1)], "lp_type": "reading", "sub_slo_ids": [str(s1)]},
            {"kind": "fa", "topic_ids": [str(t1), str(t2)], "sub_slo_ids": [str(s1), str(s2)]},
        ]
    }
    plan = ChapterPlan.from_json(raw, source="llm")
    assert plan.source == "llm"
    assert plan.items[0].kind == "lp"
    assert plan.items[0].topic_ids == [t1]
    assert plan.items[0].lp_type == "reading"
    assert plan.items[1].kind == "fa"
    assert plan.items[1].topic_ids == [t1, t2]
    # Round-trip back out matches the input shape.
    assert plan.to_json() == raw


# ---------------------------------------------------------------------------
# F-1.2 — validator
# ---------------------------------------------------------------------------


def test_valid_plan_returns_empty():
    inp = _inputs()
    assert validate_plan(_valid_plan_for(inp), inp) == []


def test_violation_period_count_mismatch():
    inp = _inputs(period_count=6)
    plan = _valid_plan_for(inp)
    short = ChapterPlan(items=plan.items[:-1], source="llm")
    v = validate_plan(short, inp)
    assert any("item count" in s for s in v)


def test_violation_bad_lp_type():
    inp = _inputs()
    plan = _valid_plan_for(inp)
    # corrupt first LP's lp_type to a Maths-only value
    bad = PlanItem(
        kind="lp",
        topic_ids=plan.items[0].topic_ids,
        sub_slo_ids=plan.items[0].sub_slo_ids,
        lp_type="concrete",
    )
    plan2 = ChapterPlan(items=[bad, *plan.items[1:]], source="llm")
    v = validate_plan(plan2, inp)
    assert any("invalid for subject" in s for s in v)


def test_violation_hallucinated_topic_id():
    inp = _inputs()
    plan = _valid_plan_for(inp)
    bogus = uuid4()
    bad = PlanItem(kind="lp", topic_ids=[bogus], sub_slo_ids=plan.items[0].sub_slo_ids, lp_type="reading")
    plan2 = ChapterPlan(items=[bad, *plan.items[1:]], source="llm")
    v = validate_plan(plan2, inp)
    # First topic is now uncovered AND an unknown id is referenced.
    assert any("unknown topic_ids" in s for s in v)
    assert any("not taught" in s for s in v)


def test_violation_fa_out_of_chapter_sub_slo():
    inp = _inputs()
    plan = _valid_plan_for(inp)
    # find an fa item and inject a foreign sub-slo
    idx = next(i for i, it in enumerate(plan.items) if it.kind == "fa")
    bad = PlanItem(kind="fa", topic_ids=plan.items[idx].topic_ids, sub_slo_ids=[uuid4()])
    items = list(plan.items)
    items[idx] = bad
    v = validate_plan(ChapterPlan(items=items, source="llm"), inp)
    assert any("out-of-chapter sub_slo_ids" in s for s in v)


def test_violation_no_lp_units():
    inp = _inputs(period_count=2, n_topics=0)  # no topics -> no LP possible
    plan = ChapterPlan(items=[PlanItem(kind="fa", topic_ids=[], sub_slo_ids=[]),
                              PlanItem(kind="fa", topic_ids=[], sub_slo_ids=[])], source="llm")
    v = validate_plan(plan, inp)
    assert any("no LP units" in s for s in v)


def test_violation_missing_fa_when_room():
    # period_count above the FA cadence threshold (6 > 5) -> an FA must exist.
    inp = _inputs(period_count=6, n_topics=3)
    # 6 LP periods, no FA: room exists.
    items = []
    for t in inp.topics:
        items.append(
            PlanItem(kind="lp", topic_ids=[t.topic_id], sub_slo_ids=[t.sub_slos[0].sub_slo_id], lp_type="reading")
        )
        items.append(
            PlanItem(kind="lp", topic_ids=[t.topic_id], sub_slo_ids=[t.sub_slos[1].sub_slo_id], lp_type="reading")
        )
    v = validate_plan(ChapterPlan(items=items, source="llm"), inp)
    assert any("room for an FA" in s for s in v)


# ---------------------------------------------------------------------------
# F-1.3 — LLM path
# ---------------------------------------------------------------------------


def _canned_json(inputs: PlanInputs) -> str:
    return json.dumps(_valid_plan_for(inputs).to_json())


async def test_plan_with_llm_parses_canned_json():
    inp = _inputs()
    llm = FakeLLM(returns=_canned_json(inp))
    plan = await plan_with_llm(inp, llm=llm)
    assert plan.source == "llm"
    assert len(plan.items) == inp.period_count
    assert len(llm.calls) == 1


async def test_plan_with_llm_strips_fences():
    inp = _inputs()
    fenced = "```json\n" + _canned_json(inp) + "\n```"
    plan = await plan_with_llm(inp, llm=FakeLLM(returns=fenced))
    assert len(plan.items) == inp.period_count


async def test_plan_with_llm_malformed_raises():
    inp = _inputs()
    with pytest.raises(PlannerLLMError):
        await plan_with_llm(inp, llm=FakeLLM(returns="not json at all"))


async def test_plan_with_llm_transport_error_raises():
    inp = _inputs()
    with pytest.raises(PlannerLLMError):
        await plan_with_llm(inp, llm=FakeLLM(raises=RuntimeError("boom")))


def test_get_planner_llm_default_is_api_key():
    class S:
        planner_llm_backend = "api_key"

    assert isinstance(get_planner_llm(S()), ApiKeyPlannerLLM)


def test_get_planner_llm_sdk_only_when_flagged():
    class S:
        planner_llm_backend = "agent_sdk"

    assert isinstance(get_planner_llm(S()), AgentSdkPlannerLLM)


# ---------------------------------------------------------------------------
# F-1.4 — deterministic fallback
# ---------------------------------------------------------------------------


def test_deterministic_returns_period_count_items_and_validates():
    inp = _inputs(period_count=9, n_topics=3)
    plan = plan_deterministic(inp)
    assert plan.source == "fallback"
    assert len(plan.items) == inp.period_count
    # all topics covered, self-consistent against its own validator
    assert validate_plan(plan, inp) == []


@pytest.mark.parametrize("periods,topics", [(3, 2), (6, 3), (12, 4), (5, 5)])
def test_deterministic_self_consistent_across_shapes(periods, topics):
    inp = _inputs(period_count=periods, n_topics=topics)
    plan = plan_deterministic(inp)
    assert len(plan.items) == periods
    assert validate_plan(plan, inp) == []


def test_deterministic_lp_sub_slos_match_topic():
    inp = _inputs(period_count=6, n_topics=3)
    plan = plan_deterministic(inp)
    by_topic = {t.topic_id: {ss.sub_slo_id for ss in t.sub_slos} for t in inp.topics}
    for it in plan.items:
        if it.kind == "lp" and len(it.topic_ids) == 1:
            # single-topic LP sub-slos must be that topic's (or revision = all)
            tid = it.topic_ids[0]
            assert set(it.sub_slo_ids) == by_topic[tid] or it.lp_type == "revision"


# ---------------------------------------------------------------------------
# F-1.5 — orchestrator
# ---------------------------------------------------------------------------


async def test_make_chapter_plan_valid_llm_returns_llm_source():
    inp = _inputs()
    plan = await make_chapter_plan(inp, llm=FakeLLM(returns=_canned_json(inp)))
    assert plan.source == "llm"


async def test_make_chapter_plan_llm_raises_falls_back():
    inp = _inputs()
    plan = await make_chapter_plan(inp, llm=FakeLLM(raises=RuntimeError("down")))
    assert plan.source == "fallback"
    assert len(plan.items) == inp.period_count


async def test_make_chapter_plan_invalid_count_falls_back(caplog):
    import logging

    inp = _inputs(period_count=6)
    # canned plan with the wrong number of items
    short = ChapterPlan(items=_valid_plan_for(inp).items[:-1], source="llm")
    bad_json = json.dumps(short.to_json())
    with caplog.at_level(logging.WARNING):
        plan = await make_chapter_plan(inp, llm=FakeLLM(returns=bad_json))
    assert plan.source == "fallback"
    assert any("failed validation" in r.message for r in caplog.records)
