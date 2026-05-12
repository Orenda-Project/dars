import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


import dars.webhooks.models  # noqa: F401 — registers WebhookDelivery with SQLAlchemy Base
import dars.lesson_plans.models  # noqa: F401 — registers LessonPlan with SQLAlchemy Base
import dars.exam_generations.models  # noqa: F401 — registers ExamGeneration with SQLAlchemy Base
import dars.curriculum.models  # noqa: F401 — registers Book and BookChapter with SQLAlchemy Base
import dars.assessments.models  # noqa: F401 — registers Assessment with SQLAlchemy Base
import dars.student_assessments.models  # noqa: F401 — registers StudentAssessment with SQLAlchemy Base
import dars.custom_lesson_plans.models  # noqa: F401 — registers CustomLessonPlan with SQLAlchemy Base
import dars.custom_exam_generations.models  # noqa: F401 — registers CustomExamGeneration with SQLAlchemy Base
import dars.school.models  # noqa: F401 — registers school planning models with SQLAlchemy Base
from dars.auth.router import auth_router
from dars.clients.router import admin_router, client_router
from dars.config import settings
from dars.migrations import run_migrations
from dars.lesson_plans.router import router as lesson_plans_router
from dars.exam_generations.router import router as exam_generations_router
from dars.curriculum.router import admin_router as curriculum_admin_router
from dars.curriculum.router import router as curriculum_router
from dars.assessments.router import router as assessments_router
from dars.student_assessments.router import router as student_assessments_router
from dars.custom_lesson_plans.router import router as custom_lesson_plans_router
from dars.custom_exam_generations.router import router as custom_exam_generations_router
from dars.analytics.router import router as analytics_router
from dars.school.router import router as school_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_migrations(settings.database_url)
    yield


app = FastAPI(
    title="Dars API",
    lifespan=lifespan,
    description="Lesson plan infrastructure for Taleemabad internal teams",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(client_router)
app.include_router(lesson_plans_router)
app.include_router(exam_generations_router)
app.include_router(curriculum_router)
app.include_router(curriculum_admin_router)
app.include_router(assessments_router)
app.include_router(student_assessments_router)
app.include_router(custom_lesson_plans_router)
app.include_router(custom_exam_generations_router)
app.include_router(analytics_router)
app.include_router(school_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "debug": settings.debug}
