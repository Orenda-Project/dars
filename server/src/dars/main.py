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

import dars.curriculum_data.models  # noqa
import dars.webhooks.models  # noqa
import dars.generated_lps.models  # noqa
import dars.generated_exams.models  # noqa
import dars.curriculum.models  # noqa
import dars.school.models  # noqa
import dars.teachers.models  # noqa
import dars.lookup.models  # noqa
from dars.auth.router import auth_router
from dars.clients.router import admin_router, client_router
from dars.config import settings
from dars.migrations import run_migrations
from dars.generated_lps.router import router as generated_lps_router
from dars.generated_exams.router import router as generated_exams_router
from dars.curriculum.router import admin_router as curriculum_admin_router
from dars.curriculum.router import router as curriculum_router
from dars.analytics.router import router as analytics_router
from dars.school.router import router as school_router
from dars.teachers.router import router as teachers_router
from dars.lookup.router import router as lookup_router


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
app.include_router(generated_lps_router)
app.include_router(generated_exams_router)
app.include_router(curriculum_router)
app.include_router(curriculum_admin_router)
app.include_router(analytics_router)
app.include_router(school_router)
app.include_router(teachers_router)
app.include_router(lookup_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "debug": settings.debug}
