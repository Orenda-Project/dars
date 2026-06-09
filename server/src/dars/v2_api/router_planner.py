"""
Chapter planner endpoint (chapter-planner-in-dars Phase 1, D-4 + D-6).

POST /api/v2/plan — a pure transform: PlanRequest in → ChapterPlan out. NO DB
write (D-6); no wiring into generate_chapter_plan (that's Phase 2). The planner
core (parse/validate/build) and the agent-sdk LLM backend live in
`dars.breakdown.planner*`.

Auth: same as sibling v2_api routers — X-API-Key (per-org) or X-Admin-Session,
resolved by `get_current_org`. Never unauthenticated.

Error mapping mirrors the standalone chapter-planner-app/main.py:
  PlannerLLMError                       -> 502 (LLM transport)
  PlanParseError / PlanValidationError  -> 422 (bad/invalid plan)
  pydantic request validation           -> 422 (FastAPI default)
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from dars.breakdown.planner import (
    PlanParseError,
    PlanValidationError,
    make_chapter_plan,
)
from dars.breakdown.planner_llm import AgentSdkPlannerLLM, PlannerLLMError
from dars.breakdown.planner_models import ChapterPlan, PlanRequest
from dars.v2_api.deps import OrgContext, get_current_org

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["v2-planner"])


@router.post("/plan", response_model=ChapterPlan)
async def plan_chapter(
    request: PlanRequest,
    org: OrgContext = Depends(get_current_org),
) -> ChapterPlan:
    """Produce an ordered ChapterPlan for a chapter. Pure transform (D-6)."""
    log.info(
        "[PLAN] entry — org=%s subject=%s grade=%s period_count=%s topics=%d",
        org.id, request.subject, request.grade, request.period_count,
        len(request.chapter.topics),
    )
    llm = AgentSdkPlannerLLM()
    try:
        plan = await make_chapter_plan(request, llm)
    except PlannerLLMError as exc:
        log.error("[PLAN] LLM error — org=%s", org.id, exc_info=True)
        raise HTTPException(status_code=502, detail=f"planner LLM error: {exc}") from exc
    except (PlanParseError, PlanValidationError) as exc:
        log.error("[PLAN] invalid plan — org=%s", org.id, exc_info=True)
        raise HTTPException(status_code=422, detail=f"invalid plan: {exc}") from exc

    log.info("[PLAN] exit — org=%s units=%d", org.id, len(plan.units))
    return plan
