"""HTTP skeleton. Liveness does not touch the database."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import database_url
from app.db import database_ready
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    application = FastAPI(title="GMV Foundation", version="0.1.0")

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready", response_model=None)
    def ready() -> JSONResponse:
        url = database_url()
        if url is None:
            logger.warning(
                "database readiness check failed",
                extra={"error_type": "MissingDatabaseURL"},
            )
            return _unavailable()
        if not database_ready(url):
            return _unavailable()
        return JSONResponse(status_code=200, content={"status": "ok"})

    return application


def _unavailable() -> JSONResponse:
    return JSONResponse(status_code=503, content={"status": "unavailable"})


app = create_app()
