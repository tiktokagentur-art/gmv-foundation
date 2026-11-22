"""Stable V1 domain error codes without HTTP or persistence adapters.

The HTTP adapter may translate these codes later; this module does not
authenticate callers, construct responses or handle side effects.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    VERSION_CONFLICT = "version_conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    FENCING_REJECTED = "fencing_rejected"
    LEASE_EXPIRED = "lease_expired"
    INVALID_STATE = "invalid_state"


HTTP_STATUS_BY_CODE = MappingProxyType(
    {
        ErrorCode.VALIDATION_ERROR: 400,
        ErrorCode.UNAUTHORIZED: 401,
        ErrorCode.FORBIDDEN: 403,
        ErrorCode.NOT_FOUND: 404,
        ErrorCode.VERSION_CONFLICT: 409,
        ErrorCode.IDEMPOTENCY_CONFLICT: 409,
        ErrorCode.FENCING_REJECTED: 409,
        ErrorCode.LEASE_EXPIRED: 409,
        ErrorCode.INVALID_STATE: 409,
    }
)


class DomainContractError(Exception):
    """A contract violation; never implies that any domain state was changed."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        self.code = code
        self.http_status = HTTP_STATUS_BY_CODE[code]
        super().__init__(message)
