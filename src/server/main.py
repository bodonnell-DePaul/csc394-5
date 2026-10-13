from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..config import STATIC_DIR
from ..routes.database import init_db
from ..middleware.error_handlers import register_error_handlers
from ..routes.mcp import mcp
from ..routes.routes import router


def create_app() -> FastAPI:
    mcp_app = mcp.http_app(path="/")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db()
        async with mcp_app.lifespan(app):
            yield

    app = FastAPI(title="Healthwatch Demo", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(router)
    app.mount("/mcp", mcp_app)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("src.server.main:app", host="127.0.0.1", port=8000, reload=True)
