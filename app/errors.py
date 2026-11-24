"""V1 error bodies for paths under ``/v1``.

``/health`` and ``/ready`` keep the bodies they already had. Messages are
German and carry no secrets. ``request_id`` is the id already chosen for the
response header.
"""

from __future__ import annotations

from collections.abc import Mapping

from starlette.responses import JSONResponse

from app.logging_config import REQUEST_ID_PATTERN, request_id_context

# Stable English codes from api/openapi.yaml. ``internal`` is the code for an
# unhandled failure under /v1. Unsupported methods use validation_error.
V1_STATUS: dict[int, tuple[str, str]] = {
    401: ("unauthorized", "Keine anerkannte Identität."),
    403: ("forbidden", "Keine Berechtigung."),
    404: ("not_found", "Nicht gefunden."),
    405: ("validation_error", "Methode nicht erlaubt."),
    500: ("internal", "Interner Fehler."),
}


def is_v1_path(path: str) -> bool:
    """True for ``/v1`` and everything nested under it, not for ``/v10``."""
    return path == "/v1" or path.startswith("/v1/")


def current_request_id() -> str | None:
    request_id = request_id_context.get()
    if isinstance(request_id, str) and REQUEST_ID_PATTERN.fullmatch(request_id):
        return request_id
    return None


def v1_error_response(
    status_code: int, request_id: str, headers: Mapping[str, str] | None = None
) -> JSONResponse | None:
    """Return an ErrorBody, or ``None`` when this status keeps another shape."""
    mapped = V1_STATUS.get(status_code)
    if mapped is None:
        return None
    code, message = mapped
    response_headers = dict(headers or {})
    if status_code == 401:
        response_headers.setdefault("WWW-Authenticate", "Bearer")
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
        headers=response_headers,
    )
