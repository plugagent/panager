from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from panager.api.auth import router as auth_router
from panager.config import Settings
from panager.db.connection import close_pool, init_pool

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool(settings.postgres_dsn_asyncpg)
    yield
    await close_pool()


app = FastAPI(title="Panager API", lifespan=lifespan)
app.include_router(auth_router, prefix="/auth")


@app.get("/health")
async def health():
    return {"status": "ok"}
