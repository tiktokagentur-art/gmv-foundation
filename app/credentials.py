"""Workload credentials.

A key is a recognizable prefix plus at least 32 bytes of randomness. Only the
SHA-256 hex digest is stored. SHA-256 is enough for this high-entropy key.
Argon2id is for passwords and is not used here. The plaintext is returned to
the caller once and is never logged.

Workers do not share a key: each ``issue`` call creates a new random key.
Human logins are not accepted.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import logging
import secrets
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TextIO

from sqlalchemy import DateTime, String, Uuid, select
from sqlalchemy.orm import Mapped, mapped_column

from app.config import database_url
from app.db import Base, open_session
from app.logging_config import bind_redactions, reset_redactions

logger = logging.getLogger(__name__)

PREFIX = "gmv_wk_"
RANDOM_BYTES = 32
MAX_TOKEN_LENGTH = 256
KINDS = frozenset({"service", "worker"})
_DUMMY_HASH = hashlib.sha256(b"workload-credential-dummy").hexdigest()


class CredentialStoreError(Exception):
    """The credential store could not be used. The message is not a secret."""


class CredentialNotFound(Exception):
    """Revoke was asked to update a row that does not exist."""


class Credential(Base):
    """One workload API key. The plaintext is not a column."""

    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    identity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


@dataclass(frozen=True)
class WorkloadSubject:
    """Authenticated workload. This is the subject, not the key."""

    identity_id: uuid.UUID
    kind: str
    credential_id: uuid.UUID


@dataclass(frozen=True)
class IssuedCredential:
    """Result of issue. ``str`` and ``repr`` hide the key."""

    credential_id: uuid.UUID
    identity_id: uuid.UUID
    kind: str
    prefix: str
    expires_at: datetime | None
    key: str

    def __repr__(self) -> str:
        return (
            "IssuedCredential("
            f"credential_id={self.credential_id!s}, "
            f"identity_id={self.identity_id!s}, "
            f"kind={self.kind!r}, "
            f"prefix={self.prefix!r}, "
            f"expires_at={self.expires_at!r}, "
            "key='[REDACTED]')"
        )

    def __str__(self) -> str:
        return repr(self)


def hash_key(key: str) -> str:
    """SHA-256 hex of the exact key string. The plaintext is not recoverable."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def hashes_match(stored: str, presented_hash: str) -> bool:
    """Compare two digests in constant time, including when the lengths differ."""
    stored_bytes = stored.encode("utf-8")
    presented_bytes = presented_hash.encode("utf-8")
    if len(stored_bytes) != len(presented_bytes):
        secrets.compare_digest(presented_bytes, presented_bytes)
        return False
    return secrets.compare_digest(stored_bytes, presented_bytes)


def generate_key() -> str:
    """Prefix plus 32 bytes of randomness, encoded so the key is one token."""
    return PREFIX + secrets.token_urlsafe(RANDOM_BYTES)


def authenticate(presented: str, *, now: datetime | None = None) -> WorkloadSubject | None:
    """Return the subject for a live workload key, or ``None`` when it is not.

    Missing, unknown, revoked, and expired keys all return ``None``. The hash
    comparison runs even when the token is not a workload key. A credential
    whose prefix is not ``gmv_wk_`` is not a workload credential.
    """
    moment = now if now is not None else datetime.now(UTC)
    if len(presented) > MAX_TOKEN_LENGTH:
        hashes_match(_DUMMY_HASH, _DUMMY_HASH)
        return None
    presented_hash = hash_key(presented) if presented else _DUMMY_HASH
    redaction = bind_redactions(presented, presented_hash)
    try:
        if not _well_formed(presented):
            hashes_match(_DUMMY_HASH, presented_hash)
            return None
        return _lookup(presented_hash, moment)
    finally:
        reset_redactions(redaction)


def issue_credential(
    *,
    kind: str,
    identity_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
) -> IssuedCredential:
    """Create a key. The caller must show ``key`` at most once and not log it."""
    if kind not in KINDS:
        raise ValueError("kind must be service or worker")
    if expires_at is not None and expires_at.tzinfo is None:
        raise ValueError("expires_at requires a timezone")
    if expires_at is not None:
        expires_at = expires_at.astimezone(UTC)
    key = generate_key()
    digest = hash_key(key)
    issued = IssuedCredential(
        credential_id=uuid.uuid4(),
        identity_id=identity_id or uuid.uuid4(),
        kind=kind,
        prefix=PREFIX,
        expires_at=expires_at,
        key=key,
    )
    redaction = bind_redactions(key, digest)
    try:
        _insert(issued, digest)
    finally:
        reset_redactions(redaction)
    return issued


def revoke_credential(credential_id: uuid.UUID, *, now: datetime | None = None) -> datetime:
    """Set ``revoked_at`` if it is still empty. The first timestamp is kept."""
    moment = now if now is not None else datetime.now(UTC)
    url = database_url()
    if url is None:
        raise CredentialStoreError("database not configured")
    try:
        with open_session(url) as session:
            row = session.get(Credential, credential_id)
            if row is None:
                raise CredentialNotFound
            if row.revoked_at is None:
                row.revoked_at = moment
                session.commit()
                return moment
            return row.revoked_at
    except (CredentialStoreError, CredentialNotFound):
        raise
    except Exception as exc:
        raise CredentialStoreError("credential store failed") from exc


def format_issued(issued: IssuedCredential) -> str:
    """Stdout text. The key appears on the ``key=`` line and nowhere else."""
    expires = issued.expires_at.isoformat() if issued.expires_at is not None else ""
    return (
        f"credential_id={issued.credential_id}\n"
        f"identity_id={issued.identity_id}\n"
        f"kind={issued.kind}\n"
        f"prefix={issued.prefix}\n"
        f"expires_at={expires}\n"
        f"key={issued.key}\n"
    )


def main(argv: Sequence[str] | None = None, *, out: TextIO | None = None) -> int:
    """Issue or revoke one workload key. The key is written only to ``out``."""
    from app.logging_config import configure_logging

    configure_logging()
    parser = _parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 2
    stream = out if out is not None else sys.stdout
    try:
        if args.command == "issue":
            issued = issue_credential(
                kind=args.kind,
                identity_id=args.identity_id,
                expires_at=args.expires_at,
            )
            stream.write(format_issued(issued))
            logger.info(
                "credential issued %s %s",
                issued.credential_id,
                issued.identity_id,
            )
            return 0
        revoked_at = revoke_credential(args.credential_id)
        stream.write(f"credential_id={args.credential_id}\nrevoked_at={revoked_at.isoformat()}\n")
        logger.info("credential revoked %s", args.credential_id)
        return 0
    except CredentialNotFound:
        print("Credential nicht gefunden.", file=sys.stderr)
        return 1
    except CredentialStoreError as exc:
        cause = exc.__cause__ or exc
        error_type = type(cause).__name__
        if not error_type.isidentifier():
            error_type = "CredentialStoreError"
        logger.error("credential store failed", extra={"error_type": error_type})
        print("Credential-Speicher nicht erreichbar.", file=sys.stderr)
        return 1


def _lookup(presented_hash: str, moment: datetime) -> WorkloadSubject | None:
    url = database_url()
    if url is None:
        raise CredentialStoreError("database not configured")
    try:
        with open_session(url) as session:
            row = session.scalar(
                select(Credential).where(Credential.key_hash == presented_hash)
            )
            stored = row.key_hash if row is not None else _DUMMY_HASH
            if not hashes_match(stored, presented_hash):
                return None
            if row is None or row.revoked_at is not None:
                return None
            expires_at = _aware(row.expires_at)
            if expires_at is not None and expires_at <= moment:
                return None
            if row.kind not in KINDS or row.prefix != PREFIX:
                return None
            return WorkloadSubject(
                identity_id=row.identity_id,
                kind=row.kind,
                credential_id=row.id,
            )
    except CredentialStoreError:
        raise
    except Exception as exc:
        raise CredentialStoreError("credential store failed") from exc


def _insert(issued: IssuedCredential, digest: str) -> None:
    url = database_url()
    if url is None:
        raise CredentialStoreError("database not configured")
    row = Credential(
        id=issued.credential_id,
        identity_id=issued.identity_id,
        kind=issued.kind,
        key_hash=digest,
        prefix=issued.prefix,
        created_at=datetime.now(UTC),
        expires_at=issued.expires_at,
        revoked_at=None,
    )
    try:
        with open_session(url) as session:
            session.add(row)
            session.commit()
    except CredentialStoreError:
        raise
    except Exception as exc:
        raise CredentialStoreError("credential store failed") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.credentials",
        description="Workload-API-Keys ausstellen oder widerrufen.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    issue = commands.add_parser("issue", help="Einen neuen Key ausstellen")
    issue.add_argument("--kind", required=True, choices=sorted(KINDS))
    issue.add_argument("--identity-id", type=_uuid, default=None)
    issue.add_argument("--expires-at", type=_expires_at, default=None)
    revoke = commands.add_parser("revoke", help="Einen Key widerrufen")
    revoke.add_argument("--credential-id", required=True, type=_uuid)
    return parser


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("UUID erwartet") from exc


def _expires_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ISO-8601 erwartet") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("expires-at braucht eine Zeitzone")
    return parsed.astimezone(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _well_formed(presented: str) -> bool:
    if not presented.startswith(PREFIX):
        return False
    raw = presented[len(PREFIX) :]
    if len(raw) < 43:
        return False
    padding = "=" * (-len(raw) % 4)
    try:
        # ``urlsafe_b64decode`` has no ``validate`` flag. ``b64decode`` does.
        decoded = base64.b64decode(raw + padding, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error):
        return False
    return len(decoded) >= RANDOM_BYTES


if __name__ == "__main__":
    raise SystemExit(main())
