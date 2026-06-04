"""
FastAPI application for the Chapter Planning Engine (CPE).

Standalone service (D-1) — NOT imported by the dars backend, shares no process with it.
Phase 1: health, /plan backed by a deterministic stub (D-2/Phase-2 replaces with LLM),
Pydantic contracts, structured logging, and a static playground.

No claude-agent-sdk import in Phase 1 — the app boots without it installed.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from logging_config import get_logger
from models import PlanRequest, ChapterPlan
from stub_planner import make_stub_plan

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
        result = make_stub_plan(req)
    except Exception:
        logger.error("[PLAN] failed to build plan", exc_info=True)
        raise
    logger.info(
        "[PLAN] exit — units=%s slos_covered=%s",
        len(result.units),
        sum(len(u.slo_ids) for u in result.units),
    )
    return result
