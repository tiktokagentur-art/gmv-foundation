"""HTTP authentication for workload API keys.

The dependency reads ``Authorization: Bearer`` and returns the subject. It does
not issue keys and it does not decide whether the subject may change state.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Header, HTTPException

from app.credentials import (
    MAX_TOKEN_LENGTH,
    CredentialStoreError,
    WorkloadSubject,
    authenticate,
)

logger = logging.getLogger(__name__)


def require_workload_credential(
    authorization: Annotated[str | None, Header()] = None,
) -> WorkloadSubject:
    """Accept one live workload key. Anything else is 401, store failure is 500."""
    token = bearer_token(authorization)
    if token is None:
        raise HTTPException(status_code=401)
    try:
        subject = authenticate(token)
    except CredentialStoreError as exc:
        cause = exc.__cause__ or exc
        error_type = type(cause).__name__
        if not error_type.isidentifier():
            error_type = "CredentialStoreError"
        logger.error(
            "workload credential check failed",
            extra={"error_type": error_type},
        )
        raise HTTPException(status_code=500) from None
    if subject is None:
        logger.info("workload credential rejected")
        raise HTTPException(status_code=401)
    return subject


def bearer_token(header: str | None) -> str | None:
    """Return the bearer token, or ``None`` when the header is not that scheme.

    A token without the workload prefix is still returned. Authentication
    rejects it, so a future human credential cannot be mistaken for a key.
    """
    if header is None:
        return None
    if len(header) > MAX_TOKEN_LENGTH + len("Bearer "):
        return None
    scheme, separator, token = header.partition(" ")
    if separator != " " or scheme.lower() != "bearer":
        return None
    token = token.strip()
    if not token or any(char.isspace() for char in token):
        return None
    if len(token) > MAX_TOKEN_LENGTH:
        return None
    return token
