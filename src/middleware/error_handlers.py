import logging
import sqlite3

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


async def handle_database_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Database request failed for %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "A database error occurred."},
    )


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        logger.error(
            "Unexpected validation handler error for %s %s",
            request.method,
            request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred."},
        )

    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
    )


async def handle_type_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Type error while handling %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(sqlite3.Error, handle_database_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(TypeError, handle_type_error)
