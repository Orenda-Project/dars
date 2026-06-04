"""
FastAPI application for the Chapter Planning Engine (CPE).

Standalone service (D-1) — NOT imported by the dars backend, shares no process with it.
/plan is backed by the real LLM planner (D-2: LLM-only, no fallback). The deterministic
stub remains importable for tests only.

claude-agent-sdk is lazily imported inside the LLM backend, so the app still boots
without it (a /plan call then fails loudly with a clear 502).
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import db
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


@app.on_event("shutdown")
async def _shutdown() -> None:
    await db.close_pool()


# ============================================================================
# Browse endpoints — read-only staging DB (D-1, SELECT-only)
# ============================================================================
@app.get("/books")
async def get_books() -> list[dict]:
    logger.info("[BOOKS] entry")
    try:
        books = await db.list_books()
    except db.StagingDbError as exc:
        logger.error("[BOOKS] staging DB error", exc_info=True)
        raise HTTPException(status_code=503, detail=f"staging DB unavailable: {exc}") from exc
    logger.info("[BOOKS] exit — books=%d", len(books))
    return books


@app.get("/books/{book_id}/chapters")
async def get_chapters(book_id: str) -> list[dict]:
    logger.info("[CHAPTERS] entry — book_id=%s", book_id)
    try:
        chapters = await db.list_chapters(book_id)
    except db.StagingDbError as exc:
        logger.error("[CHAPTERS] staging DB error", exc_info=True)
        raise HTTPException(status_code=503, detail=f"staging DB unavailable: {exc}") from exc
    logger.info("[CHAPTERS] exit — book_id=%s chapters=%d", book_id, len(chapters))
    return chapters


@app.get("/books/{book_id}/chapters/{chapter_id}/plan-input")
async def get_plan_input(
    book_id: str,
    chapter_id: str,
    period_count: int = Query(..., gt=0),
    subject: str = Query("Eng"),
    grade: int | None = Query(None),
    curriculum: str = Query("ICT"),
) -> dict:
    logger.info(
        "[PLAN_INPUT] entry — book_id=%s chapter_id=%s period_count=%s subject=%s grade=%s",
        book_id, chapter_id, period_count, subject, grade,
    )
    try:
        # Resolve grade from the book if not explicitly provided.
        if grade is None:
            books = await db.list_books()
            match = next((b for b in books if b["id"] == book_id), None)
            grade = int(match["grade"]) if match else 1
        plan_input = await db.get_chapter_as_plan_input(
            book_chapter_id=chapter_id,
            subject=subject,
            grade=grade,
            period_count=period_count,
            curriculum=curriculum,
        )
    except db.StagingDbError as exc:
        logger.error("[PLAN_INPUT] staging DB error", exc_info=True)
        raise HTTPException(status_code=503, detail=f"staging DB unavailable: {exc}") from exc
    logger.info(
        "[PLAN_INPUT] exit — chapter=%r topics=%d",
        plan_input["chapter"]["title"], len(plan_input["chapter"]["topics"]),
    )
    return plan_input


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
