import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.generated_exams.models import GeneratedExam
from dars.generated_lps.models import GeneratedLP
from dars.database import get_db
from dars.deps import get_current_client

from .schemas import (
    AnalyticsResponse,
    DailyCount,
    ExamGenerationAnalytics,
    GradeCount,
    LessonPlanAnalytics,
    StatusCounts,
    SubjectCount,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsResponse:
    logger.info("get_analytics: client_id=%s", current_client.id)

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # ── Generated Lesson Plans ────────────────────────────────────────────────

    lp_status_rows = await db.execute(
        select(GeneratedLP.status, func.count().label("cnt"))
        .where(GeneratedLP.client_id == current_client.id)
        .group_by(GeneratedLP.status)
    )
    lp_status: dict[str, int] = {r.status: r.cnt for r in lp_status_rows}

    lp_subject_rows = await db.execute(
        select(GeneratedLP.subject, func.count().label("cnt"))
        .where(GeneratedLP.client_id == current_client.id)
        .group_by(GeneratedLP.subject)
        .order_by(func.count().desc())
    )
    lp_by_subject = [SubjectCount(subject=r.subject, count=r.cnt) for r in lp_subject_rows]

    lp_grade_rows = await db.execute(
        select(GeneratedLP.grade, func.count().label("cnt"))
        .where(GeneratedLP.client_id == current_client.id)
        .group_by(GeneratedLP.grade)
        .order_by(GeneratedLP.grade)
    )
    lp_by_grade = [GradeCount(grade=r.grade, count=r.cnt) for r in lp_grade_rows]

    lp_daily_rows = await db.execute(
        select(
            func.date(GeneratedLP.created_at).label("day"),
            func.count().label("cnt"),
        )
        .where(
            GeneratedLP.client_id == current_client.id,
            GeneratedLP.created_at >= cutoff,
        )
        .group_by(func.date(GeneratedLP.created_at))
        .order_by(func.date(GeneratedLP.created_at))
    )
    lp_daily = [DailyCount(date=str(r.day), count=r.cnt) for r in lp_daily_rows]

    lp_total = sum(lp_status.values())

    lp_analytics = LessonPlanAnalytics(
        total=lp_total,
        by_status=StatusCounts(
            pending=lp_status.get("PENDING", 0),
            ready=lp_status.get("READY", 0),
            error=lp_status.get("ERROR", 0),
        ),
        by_subject=lp_by_subject,
        by_grade=lp_by_grade,
        daily_last_30=lp_daily,
    )

    # ── Generated Exams ───────────────────────────────────────────────────────

    eg_status_rows = await db.execute(
        select(GeneratedExam.status, func.count().label("cnt"))
        .where(GeneratedExam.client_id == current_client.id)
        .group_by(GeneratedExam.status)
    )
    eg_status: dict[str, int] = {r.status: r.cnt for r in eg_status_rows}

    eg_subject_rows = await db.execute(
        select(GeneratedExam.subject, func.count().label("cnt"))
        .where(GeneratedExam.client_id == current_client.id)
        .group_by(GeneratedExam.subject)
        .order_by(func.count().desc())
    )
    eg_by_subject = [SubjectCount(subject=r.subject, count=r.cnt) for r in eg_subject_rows]

    eg_grade_rows = await db.execute(
        select(GeneratedExam.grade, func.count().label("cnt"))
        .where(GeneratedExam.client_id == current_client.id)
        .group_by(GeneratedExam.grade)
        .order_by(GeneratedExam.grade)
    )
    eg_by_grade = [GradeCount(grade=str(r.grade), count=r.cnt) for r in eg_grade_rows]

    eg_daily_rows = await db.execute(
        select(
            func.date(GeneratedExam.created_at).label("day"),
            func.count().label("cnt"),
        )
        .where(
            GeneratedExam.client_id == current_client.id,
            GeneratedExam.created_at >= cutoff,
        )
        .group_by(func.date(GeneratedExam.created_at))
        .order_by(func.date(GeneratedExam.created_at))
    )
    eg_daily = [DailyCount(date=str(r.day), count=r.cnt) for r in eg_daily_rows]

    eg_total = sum(eg_status.values())

    eg_analytics = ExamGenerationAnalytics(
        total=eg_total,
        by_status=StatusCounts(
            pending=eg_status.get("PENDING", 0),
            ready=eg_status.get("READY", 0),
            error=eg_status.get("ERROR", 0),
        ),
        by_subject=eg_by_subject,
        by_grade=eg_by_grade,
        daily_last_30=eg_daily,
    )

    logger.info(
        "get_analytics: done client_id=%s lp_total=%d eg_total=%d",
        current_client.id, lp_total, eg_total,
    )
    return AnalyticsResponse(lesson_plans=lp_analytics, exam_generations=eg_analytics)
