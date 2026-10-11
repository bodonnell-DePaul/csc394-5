import logging
import sqlite3
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


async def handle_database_error(request: Request, exc: sqlite3.Error) -> JSONResponse:
    logger.error(
        "Database request failed for %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "A database error occurred."},
    )


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(sqlite3.Error, handle_database_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
