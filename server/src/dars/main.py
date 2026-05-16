import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from dars.config import settings
from dars.migrations import run_migrations
from dars.seeds.v2_seed import run_seed_on_startup
from dars.v2_api.router_book import router as v2_book_router
from dars.v2_api.router_breakdown import router as v2_breakdown_router
from dars.v2_api.router_class_actions import router as v2_class_actions_router
from dars.v2_api.router_curriculum import router as v2_curriculum_router
from dars.v2_api.router_holidays import router as v2_holidays_router
from dars.v2_api.router_tenancy import router as v2_tenancy_router
from dars.v2_api.router_today_calendar import router as v2_today_calendar_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_migrations(settings.database_url)
    await run_seed_on_startup(settings.database_url)
    yield


app = FastAPI(
    title="Dars API",
    lifespan=lifespan,
    description="Lesson plan infrastructure for Taleemabad (v2)",
    version="2.0.0",
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

app.include_router(v2_tenancy_router)
app.include_router(v2_curriculum_router)
app.include_router(v2_book_router)
app.include_router(v2_breakdown_router)
app.include_router(v2_holidays_router)
app.include_router(v2_class_actions_router)
app.include_router(v2_today_calendar_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "debug": settings.debug}
