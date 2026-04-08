import logging

import colorlog
from fastapi import FastAPI

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s %(levelname)s%(reset)s %(blue)s%(name)s%(reset)s — %(message)s"
))
logging.basicConfig(level=logging.INFO, handlers=[handler])


import dars.webhooks.models  # noqa: F401 — registers WebhookDelivery with SQLAlchemy Base
import dars.lesson_plans.edit_models  # noqa: F401 — registers LessonPlanEdit with SQLAlchemy Base
from dars.clients.router import admin_router, client_router
from dars.config import settings
from dars.lesson_plans.router import router as lesson_plans_router

app = FastAPI(
    title="Dars API",
    description="Lesson plan infrastructure for Taleemabad internal teams",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(admin_router)
app.include_router(client_router)
app.include_router(lesson_plans_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "debug": settings.debug}
