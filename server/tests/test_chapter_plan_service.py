"""
Chapter-plan pure-planner tests.

Unit: pure helper math, no DB. Salvaged from the deleted auto_build_service;
the planners now live in dars.breakdown.chapter_plan_service.
"""
from uuid import uuid4

from dars.breakdown.chapter_plan_service import (
    allocate_chapter_days,
    compute_chapter_day_budget,
    plan_chapter_slots,
)


# ---------------------------------------------------------------------------
# Unit: chapter day budget
# ---------------------------------------------------------------------------


def test_chapter_day_budget_proportional():
    # 4 chapters, equal topic counts, 100 days → each gets ~25.
    budget = compute_chapter_day_budget([3, 3, 3, 3], 100)
    assert sum(budget) == 100
    assert all(b >= 1 for b in budget)
    # Difference between min/max ≤ 1 for equal weights.
    assert max(budget) - min(budget) <= 1


def test_chapter_day_budget_weighted():
    # 10 + 5 + 5 topics over 100 days → ~50/25/25.
    budget = compute_chapter_day_budget([10, 5, 5], 100)
    assert sum(budget) == 100
    assert budget[0] >= budget[1]
    assert budget[0] >= budget[2]


def test_chapter_day_budget_no_topics_gives_one_each():
    budget = compute_chapter_day_budget([0, 0, 0], 50)
    assert budget == [1, 1, 1]


def test_chapter_day_budget_each_chapter_has_at_least_one():
    # 100 chapters, 50 days → can't give each ≥1 fairly, but we must give
    # at least 1; sum may exceed total_teaching_days in that case.
    budget = compute_chapter_day_budget([1] * 100, 50)
    assert all(b >= 1 for b in budget)


# ---------------------------------------------------------------------------
# Unit: per-chapter allocation (1 slot = 1 day, D-74)
# ---------------------------------------------------------------------------


def test_allocation_invariant_typical():
    # 27 days, 5 topics, cadence 5, SA=1.
    a = allocate_chapter_days(chapter_days=27, topic_count=5, fa_cadence=5, sa_per_chapter=1)
    assert a.lesson_days + a.fa_count + a.sa_count + a.revision_count == 27
    assert sum(a.days_per_topic) == a.lesson_days
    assert len(a.days_per_topic) == 5
    # Uniform within ±1.
    assert max(a.days_per_topic) - min(a.days_per_topic) <= 1


def test_allocation_tiny_chapter_drops_revision_before_sa():
    # 1 day, 2 topics. Only enough for one SA (priority).
    a = allocate_chapter_days(chapter_days=1, topic_count=2, fa_cadence=5, sa_per_chapter=1)
    assert a.lesson_days + a.fa_count + a.sa_count + a.revision_count == 1
    assert a.sa_count == 1
    assert a.revision_count == 0
    assert a.lesson_days == 0


def test_allocation_zero_topics():
    # Edge case: chapter with no topics. All days become extra SAs to
    # preserve the count invariant.
    a = allocate_chapter_days(chapter_days=5, topic_count=0, fa_cadence=5, sa_per_chapter=1)
    assert a.lesson_days + a.fa_count + a.sa_count + a.revision_count == 5
    assert a.lesson_days == 0
    assert a.days_per_topic == []


def test_allocation_plan_count_equals_chapter_days():
    # The plan output must be exactly chapter_days items.
    for days in (1, 3, 7, 27, 100, 365):
        for topics in (1, 3, 10):
            a = allocate_chapter_days(
                chapter_days=days, topic_count=topics, fa_cadence=5, sa_per_chapter=1,
            )
            assert a.lesson_days + a.fa_count + a.sa_count + a.revision_count == days, (
                f"invariant failed for days={days} topics={topics}: "
                f"{a.lesson_days}+{a.fa_count}+{a.sa_count}+{a.revision_count}"
            )
            tids = [uuid4() for _ in range(topics)]
            slots = plan_chapter_slots(tids, ["reading"] * topics, a, fa_cadence=5)
            assert len(slots) == days, (
                f"plan_chapter_slots produced {len(slots)} slots for chapter_days={days}"
            )


def test_planned_slots_consecutive_same_topic_share_lp_type():
    # 9 days, 3 topics, cadence 5, sa=1 → 6 lesson days (2 per topic).
    a = allocate_chapter_days(chapter_days=9, topic_count=3, fa_cadence=5, sa_per_chapter=1)
    tids = [uuid4() for _ in range(3)]
    lp_types = ["reading", "grammar", "comprehension_qa"]
    slots = plan_chapter_slots(tids, lp_types, a, fa_cadence=5)
    # All lesson slots for topic 0 should have lp_type="reading", etc.
    by_topic: dict = {}
    for s in slots:
        if s.slot_type == "lesson":
            by_topic.setdefault(s.topic_id, []).append(s.lp_type)
    for tid, types in by_topic.items():
        assert len(set(types)) == 1, f"topic {tid} got mixed lp_types: {types}"
