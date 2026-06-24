from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorPayload


logger = logging.getLogger("evalledger.errors")


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


def error_response(
    code: str,
    message: str,
    *,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(
            error=ErrorPayload(code=code, message=message, details=details)
        ).model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        details = dict(exc.details or {})
        request_id = getattr(request.state, "request_id", None)
        if request_id is not None:
            details.setdefault("request_id", request_id)

        log_extra: dict[str, Any] = {
            "request_id": request_id,
            "error_code": exc.code,
            "status_code": exc.status_code,
            "method": request.method,
            "path": request.url.path,
        }
        if exc.status_code >= 500:
            logger.error("app_error.server_error", extra=log_extra)
        elif exc.status_code == 429:
            logger.warning("ratelimit.request_throttled", extra=log_extra)
        elif exc.status_code in (401, 403):
            logger.warning("app_error.auth_rejected", extra=log_extra)
        # Other 4xx are ordinary client errors; logged at request.completed level.

        response = error_response(
            exc.code,
            exc.message,
            status_code=exc.status_code,
            details=details or None,
        )
        if exc.status_code == 429:
            retry_after = (exc.details or {}).get("retry_after")
            if retry_after is not None:
                response.headers["Retry-After"] = str(retry_after)
        return response

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
        request_id = getattr(request.state, "request_id", None)
        if request_id is not None:
            detail.setdefault("request_id", request_id)
        if exc.status_code >= 500:
            logger.error(
                "http_error.server_error",
                extra={
                    "request_id": request_id,
                    "status_code": exc.status_code,
                    "path": request.url.path,
                },
            )
        return error_response(
            "http_error",
            detail.get("detail", "Request failed"),
            status_code=exc.status_code,
            details=detail,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        details: dict[str, Any] = {"errors": jsonable_encoder(exc.errors())}
        if request_id is not None:
            details["request_id"] = request_id
        return error_response(
            "validation_error",
            "Request validation failed",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "database.integrity_error",
            extra={
                "request_id": request_id,
                "error": str(exc.orig),
                "path": request.url.path,
            },
        )
        details: dict[str, Any] | None = None
        if request_id is not None:
            details = {"request_id": request_id}
        return error_response(
            "integrity_error",
            "Database constraint violated",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception(
            "request.unhandled_exception",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )
        details: dict[str, Any] | None = None
        if request_id is not None:
            details = {"request_id": request_id}
        return error_response(
            "internal_error",
            "An unexpected error occurred",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )
