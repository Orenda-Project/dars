"""
FastAPI application for the Chapter Planning Engine (CPE).

Standalone service (D-1) — NOT imported by the dars backend, shares no process with it.
/plan is backed by the real LLM planner (D-2: LLM-only, no fallback). The deterministic
stub remains importable for tests only.

claude-agent-sdk is lazily imported inside the LLM backend, so the app still boots
without it (a /plan call then fails loudly with a clear 502).
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from logging_config import get_logger
from models import PlanRequest, ChapterPlan
from planner import (
    PlanParseError,
    PlanValidationError,
    make_chapter_plan,
)
from planner_llm import AgentSdkPlannerLLM, PlannerLLMError

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Chapter Planning Engine (CPE)",
    description="Plans which lesson plans (Plan Units) to generate for a chapter.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health() -> dict:
    logger.info("[HEALTH] entry")
    result = {"status": "ok"}
    logger.info("[HEALTH] exit — status=ok")
    return result


@app.get("/")
async def playground() -> FileResponse:
    logger.info("[PLAYGROUND] serving index.html")
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.post("/plan", response_model=ChapterPlan)
async def plan(req: PlanRequest) -> ChapterPlan:
    logger.info(
        "[PLAN] entry — subject=%s grade=%s curriculum=%s period_count=%s topics=%s",
        req.subject, req.grade, req.curriculum, req.period_count, len(req.chapter.topics),
    )
    try:
        result = await make_chapter_plan(req, AgentSdkPlannerLLM())
    except PlannerLLMError as exc:
        logger.error("[PLAN] LLM error", exc_info=True)
        raise HTTPException(status_code=502, detail=f"planner LLM error: {exc}") from exc
    except (PlanParseError, PlanValidationError) as exc:
        logger.error("[PLAN] invalid plan — %s", exc)
        raise HTTPException(status_code=422, detail=f"invalid plan: {exc}") from exc
    logger.info(
        "[PLAN] exit — units=%s slos_covered=%s",
        len(result.units),
        sum(len(u.slo_ids) for u in result.units),
    )
    return result
