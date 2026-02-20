from __future__ import annotations

from fastapi import FastAPI

from panager.api.auth import router as auth_router


def create_app(bot) -> FastAPI:
    app = FastAPI(title="Panager API")
    app.state.bot = bot
    app.include_router(auth_router, prefix="/auth")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
