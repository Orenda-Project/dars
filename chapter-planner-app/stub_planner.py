"""
Deterministic stub planner (F-1.3).

Exists only to exercise the request/response contract and the playground end-to-end
before the real LLM planner lands in Phase 2. NOT a fallback (D-2): Phase 2 replaces
this entirely. No claude-agent-sdk import here — Phase 1 must boot without it.

Behaviour:
  - Round-robin topics across `period_count` units.
  - lp_type = first allowed lp_type for the subject (VALID_LP_TYPES[subject][0]).
  - Each unit's slo_ids = all SLOs of its assigned topics.
  - topic_text = member topics' text joined (in topic_ids order).
  - sequence = 1..period_count.

Produces exactly `period_count` units and covers every chapter SLO.
"""
from logging_config import get_logger
from config import VALID_LP_TYPES
from models import PlanRequest, ChapterPlan, PlanUnit

logger = get_logger(__name__)


def make_stub_plan(req: PlanRequest) -> ChapterPlan:
    logger.info(
        "[STUB] make_stub_plan entry — subject=%s grade=%s period_count=%s topics=%s",
        req.subject, req.grade, req.period_count, len(req.chapter.topics),
    )

    topics = req.chapter.topics
    period_count = req.period_count
    lp_type = VALID_LP_TYPES[req.subject][0]

    # Round-robin topics into period_count buckets.
    buckets: list[list] = [[] for _ in range(period_count)]
    for i, topic in enumerate(topics):
        buckets[i % period_count].append(topic)

    units: list[PlanUnit] = []
    for seq, bucket in enumerate(buckets, start=1):
        topic_ids = [t.id for t in bucket]
        slo_ids = [s.id for t in bucket for s in t.slos]
        topic_text = "\n\n".join(t.topic_text for t in bucket)
        units.append(
            PlanUnit(
                sequence=seq,
                lp_type=lp_type,
                topic_ids=topic_ids,
                slo_ids=slo_ids,
                topic_text=topic_text,
                rationale=(
                    f"Stub plan: round-robin assignment of "
                    f"{len(topic_ids)} topic(s) to unit {seq}."
                ),
            )
        )

    plan = ChapterPlan(
        subject=req.subject,
        grade=req.grade,
        curriculum=req.curriculum,
        period_count=period_count,
        units=units,
    )

    logger.info(
        "[STUB] make_stub_plan exit — units=%s slos_covered=%s",
        len(plan.units),
        sum(len(u.slo_ids) for u in plan.units),
    )
    return plan
