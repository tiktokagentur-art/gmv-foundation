"""HTTP skeleton. Liveness does not touch the database.

Responses carry ``X-Request-ID``. ``/health`` and ``/ready`` keep their bodies.
Paths under ``/v1`` use the V1 ErrorBody for 401, 403, 404, and for an
unhandled 500.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth import require_workload_credential
from app.config import database_url
from app.credentials import WorkloadSubject
from app.db import database_ready
from app.errors import current_request_id, is_v1_path, v1_error_response
from app.logging_config import configure_logging
from app.request_id import RequestIdMiddleware

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    application = FastAPI(title="GMV Foundation", version="0.1.0")
    application.add_middleware(RequestIdMiddleware)
    application.add_exception_handler(StarletteHTTPException, _http_error)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready", response_model=None)
    def ready() -> JSONResponse:
        configured_url = database_url()
        if configured_url is None:
            logger.warning(
                "database readiness check failed",
                extra={"error_type": "MissingDatabaseURL"},
            )
            return _unavailable()
        if not database_ready(configured_url):
            return _unavailable()
        return JSONResponse(status_code=200, content={"status": "ok"})

    @application.get("/v1/whoami")
    def whoami(
        subject: Annotated[WorkloadSubject, Depends(require_workload_credential)],
    ) -> dict[str, str]:
        return {"identity_id": str(subject.identity_id), "kind": subject.kind}

    return application


async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Map selected ``/v1`` statuses onto ErrorBody. Other paths stay as they were."""
    if is_v1_path(request.url.path):
        request_id = current_request_id()
        if request_id is not None:
            body = v1_error_response(exc.status_code, request_id)
            if body is not None:
                return body
    headers = exc.headers if exc.headers else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


def _unavailable() -> JSONResponse:
    return JSONResponse(status_code=503, content={"status": "unavailable"})


app = create_app()
