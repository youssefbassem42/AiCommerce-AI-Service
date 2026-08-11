import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.ai_exceptions import AIException
from app.core.exceptions import DomainException, InfrastructureException

logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "details": details},
    )


async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:  # noqa: ARG001
    return _error_response(
        status_code=exc.status_code,
        code=exc.__class__.__name__,
        message=exc.message,
        details=getattr(exc, "details", None),
    )


async def infrastructure_exception_handler(
    request: Request,  # noqa: ARG001
    exc: InfrastructureException,  # noqa: ARG001
) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        code=exc.__class__.__name__,
        message=exc.message,
    )


async def ai_exception_handler(request: Request, exc: AIException) -> JSONResponse:  # noqa: ARG001
    return _error_response(
        status_code=exc.status_code,
        code=exc.__class__.__name__,
        message=exc.message,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return _error_response(
        status_code=500,
        code="internal_error",
        message="Internal server error",
    )
