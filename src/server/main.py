import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..config import STATIC_DIR
from ..routes.database import init_db
from ..middleware.error_handlers import register_error_handlers
from ..routes.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Healthwatch Demo")
    register_error_handlers(app)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.on_event("startup")
    def startup_event() -> None:
        init_db()

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("src.server.main:app", host="127.0.0.1", port=8000, reload=True)
