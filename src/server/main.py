import logging
from time import perf_counter

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from ..config import STATIC_DIR
from ..routes.database import init_db
from ..middleware.error_handlers import register_error_handlers
from ..routes.routes import router
from ..routes.auth import (
    router as auth_router,
    seed_demo_accounts,
    seed_google_patient_accounts,
)
from ..routes.legal import router as legal_router

logger = logging.getLogger("uvicorn.error")


def create_app() -> FastAPI:
    app = FastAPI(title="Healthwatch Demo")
    register_error_handlers(app)
    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(legal_router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
   

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        started_at = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled request failure for %s %s",
                request.method,
                request.url.path,
            )
            raise

        duration_ms = (perf_counter() - started_at) * 1000
        log = logger.error if response.status_code >= 500 else (
            logger.warning if response.status_code >= 400 else logger.info
        )
        log(
            "%s %s completed with status %d in %.2f ms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    @app.on_event("startup")
    def startup_event() -> None:
        init_db()
        seed_demo_accounts()
        seed_google_patient_accounts()

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("src.server.main:app", host="localhost", port=8000, reload=True)
