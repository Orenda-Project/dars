from fastapi import FastAPI

from dars.clients.router import client_router, internal_router
from dars.config import settings

app = FastAPI(
    title="Dars API",
    description="Lesson plan infrastructure for Taleemabad internal teams",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(internal_router)
app.include_router(client_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "debug": settings.debug}
