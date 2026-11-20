"""Fail-closed, single-turn Aline L1 runtime for the existing worker service.

The SQLite ledger must live on a mounted Railway volume. A reservation is
committed before any network request. An interrupted or ambiguous request keeps
its full reservation and prevents another request until an operator reconciles
it. This module never logs prompts, answers, credentials, or provider errors.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from worker import INSTRUCTIONS, WORKER_ID

MODEL = "gpt-6.1-terra"
BUDGET_USD = Decimal("10")
RESERVATION_USD = Decimal("2")
MAX_CALLS = 5
MAX_OUTPUT_TOKENS = 128
MAX_INPUT_BYTES = 8192
INPUT_USD_PER_MILLION = Decimal("1")
OUTPUT_USD_PER_MILLION = Decimal("5")
READBACK_MAX_AGE = timedelta(hours=24)


class RuntimeBlocked(RuntimeError):
    """A prerequisite or a durable safety gate denied execution."""


class RuntimeBusy(RuntimeBlocked):
    """Another model call is in progress."""


class RuntimeUncertain(RuntimeBlocked):
    """A request may have been billed; never retry it automatically."""


class RuntimeDuplicate(RuntimeBlocked):
    """An idempotency key was already reserved; never issue a second call."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _is_persistent_volume(path: Path) -> bool:
    """Require the explicit Railway volume mount, not container ephemeral disk."""
    return path.resolve().is_relative_to(Path("/data")) and os.path.ismount("/data")


def _ledger_path() -> Path:
    raw = os.getenv("ALINE_LEDGER_PATH", "")
    if not raw:
        raise RuntimeBlocked("persistent ledger path missing")
    path = Path(raw)
    if not path.is_absolute() or not path.parent.is_dir() or not _is_persistent_volume(path):
        raise RuntimeBlocked("persistent ledger volume unavailable")
    return path


def _ledger_id() -> str:
    value = os.getenv("ALINE_LEDGER_ID", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", value):
        raise RuntimeBlocked("ledger identity missing")
    return value


def _verified_prior_spend() -> Decimal:
    if os.getenv("ALINE_L1_BUDGET_USD") != "10":
        raise RuntimeBlocked("pilot budget mismatch")
    raw_readback = os.getenv("ALINE_PROVIDER_READBACK_AT", "")
    try:
        readback = datetime.fromisoformat(raw_readback.replace("Z", "+00:00"))
    except ValueError:
        raise RuntimeBlocked("provider readback timestamp missing") from None
    now = datetime.now(UTC)
    if readback.tzinfo is None or readback > now or now - readback > READBACK_MAX_AGE:
        raise RuntimeBlocked("provider readback stale or invalid")
    try:
        prior = Decimal(os.getenv("ALINE_PRIOR_SPEND_USD", ""))
    except InvalidOperation:
        raise RuntimeBlocked("prior provider spend unverified") from None
    if not prior.is_finite() or prior < 0 or prior > BUDGET_USD:
        raise RuntimeBlocked("prior provider spend outside budget")
    return prior


def _configuration() -> tuple[Path, Decimal, str, str]:
    if os.getenv("ALINE_LIVE_ENABLED") != "true":
        raise RuntimeBlocked("live pilot disabled")
    if os.getenv("ALINE_L1_PROJECT_DEDICATED") != "true":
        raise RuntimeBlocked("dedicated project not attested")
    if os.getenv("ALINE_L1_HARD_LIMIT_ATTESTED") != "true":
        raise RuntimeBlocked("provider hard limit not attested")
    if os.getenv("OPENAI_MODEL") != MODEL:
        raise RuntimeBlocked("approved model mismatch")
    if len(os.getenv("ALINE_CEO_TOKEN", "")) < 32:
        raise RuntimeBlocked("CEO authentication not configured")
    project_id = os.getenv("OPENAI_PROJECT_ID", "")
    if not re.fullmatch(r"proj_[A-Za-z0-9_-]{8,}", project_id):
        raise RuntimeBlocked("dedicated project ID missing")
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeBlocked("provider key missing")
    return _ledger_path(), _verified_prior_spend(), project_id, key


def _connect(path: Path) -> sqlite3.Connection:
    """Open an existing, identity-matched ledger; never initialize it here."""
    connection = None
    try:
        connection = sqlite3.connect(
            path.as_uri() + "?mode=rw", uri=True, timeout=0, isolation_level=None,
        )
        connection.execute("PRAGMA synchronous=FULL")
        row = connection.execute("SELECT ledger_id FROM control WHERE id = 1").fetchone()
        if row is None or row[0] != _ledger_id():
            raise RuntimeBlocked("persistent ledger identity mismatch")
        # Reject old schemas too, rather than silently creating columns.
        connection.execute("SELECT idempotency_hash FROM runs LIMIT 0")
        return connection
    except RuntimeBlocked:
        if connection is not None:
            connection.close()
        raise
    except sqlite3.Error:
        if connection is not None:
            connection.close()
        raise RuntimeBlocked("persistent ledger unavailable") from None


def provision_ledger() -> dict[str, object]:
    """Explicit one-time operator action with live mode disabled."""
    if os.getenv("ALINE_LIVE_ENABLED") == "true":
        raise RuntimeBlocked("disable live pilot before provisioning")
    if os.getenv("ALINE_L1_PROJECT_DEDICATED") != "true":
        raise RuntimeBlocked("dedicated project not attested")
    if os.getenv("ALINE_L1_HARD_LIMIT_ATTESTED") != "true":
        raise RuntimeBlocked("provider hard limit not attested")
    if os.getenv("OPENAI_MODEL") != MODEL:
        raise RuntimeBlocked("approved model mismatch")
    if not re.fullmatch(r"proj_[A-Za-z0-9_-]{8,}", os.getenv("OPENAI_PROJECT_ID", "")):
        raise RuntimeBlocked("dedicated project ID missing")
    prior = _verified_prior_spend()
    path = _ledger_path()
    ledger_id = _ledger_id()
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise RuntimeBlocked("ledger already exists; never reset it automatically") from None
    except OSError:
        raise RuntimeBlocked("persistent ledger cannot be created") from None
    os.close(descriptor)
    connection = None
    try:
        connection = sqlite3.connect(
            path.as_uri() + "?mode=rw", uri=True, timeout=0, isolation_level=None,
        )
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            "CREATE TABLE control (id INTEGER PRIMARY KEY CHECK (id = 1), "
            "disabled INTEGER NOT NULL, ledger_id TEXT NOT NULL, "
            "provisioned_at TEXT NOT NULL, starting_spend_usd TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE runs (run_id TEXT PRIMARY KEY, idempotency_hash TEXT NOT NULL UNIQUE, "
            "created_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL, "
            "model TEXT NOT NULL, reserved_usd TEXT NOT NULL, input_tokens INTEGER, "
            "output_tokens INTEGER, total_tokens INTEGER, estimated_cost_usd TEXT, "
            "error_type TEXT)"
        )
        connection.execute(
            "INSERT INTO control (id, disabled, ledger_id, provisioned_at, starting_spend_usd) "
            "VALUES (1, 0, ?, ?, ?)", (ledger_id, _now(), str(prior)),
        )
    except sqlite3.Error:
        # Keep the damaged file: a second attempt must require explicit review.
        raise RuntimeBlocked("ledger provisioning failed; inspect before retrying") from None
    finally:
        if connection is not None:
            connection.close()
    return {"worker_id": WORKER_ID, "status": "provisioned", "prior_spend_usd": str(prior)}


def _counts(connection: sqlite3.Connection) -> tuple[int, Decimal, bool, bool]:
    rows = connection.execute("SELECT status, reserved_usd FROM runs").fetchall()
    count = len(rows)
    reserved = sum((Decimal(value) for _, value in rows), Decimal("0"))
    # An uncertain response can have incurred a charge. Halt all subsequent
    # calls until an operator reconciles it outside this runtime.
    in_flight = any(status in ("in_flight", "uncertain") for status, _ in rows)
    disabled = bool(connection.execute("SELECT disabled FROM control WHERE id = 1").fetchone()[0])
    return count, reserved, in_flight, disabled


def _starting_spend(connection: sqlite3.Connection) -> Decimal:
    value = connection.execute("SELECT starting_spend_usd FROM control WHERE id = 1").fetchone()
    if value is None:
        raise RuntimeBlocked("ledger starting spend missing")
    try:
        starting = Decimal(value[0])
    except InvalidOperation:
        raise RuntimeBlocked("ledger starting spend invalid") from None
    if not starting.is_finite() or starting < 0 or starting > BUDGET_USD:
        raise RuntimeBlocked("ledger starting spend invalid")
    return starting


def readiness() -> tuple[bool, str]:
    """Report local readiness. Provider access is externally verified, not probed here."""
    try:
        path, prior, _, _ = _configuration()
        connection = _connect(path)
        try:
            count, reserved, in_flight, disabled = _counts(connection)
            if prior < _starting_spend(connection):
                raise RuntimeBlocked("provider spend readback moved backwards")
        finally:
            connection.close()
        if disabled:
            raise RuntimeBlocked("pilot stopped")
        if in_flight:
            raise RuntimeBusy("model request in progress or unresolved")
        if count >= MAX_CALLS or prior + reserved + RESERVATION_USD > BUDGET_USD:
            raise RuntimeBlocked("pilot budget exhausted")
        return True, "ready_for_bounded_request"
    except RuntimeBlocked as exc:
        return False, str(exc)
    except (sqlite3.Error, InvalidOperation):
        return False, "persistent ledger invalid"


def get_status() -> dict[str, object]:
    """Return non-sensitive operational metadata for the authenticated CEO."""
    ready, reason = readiness()
    result: dict[str, object] = {
        "worker_id": WORKER_ID,
        "runtime_status": "ready_for_probe" if ready else "blocked",
        "ready": ready,
        "reason": reason,
        "model": MODEL,
        "deployment_id": _deployment_id(),
        "budget_limit_usd": str(BUDGET_USD),
        "reserved_usd": None,
        "local_remaining_usd": None,
        "provider_remaining_usd": None,
        "calls_reserved": None,
        "last_run": None,
        "provider_verified_by_runtime": False,
    }
    ledger_valid = False
    starting_spend: Decimal | None = None
    try:
        path = _ledger_path()
        connection = _connect(path)
        try:
            count, reserved, in_flight, disabled = _counts(connection)
            starting_spend = _starting_spend(connection)
            ledger_valid = True
            latest = connection.execute(
                "SELECT run_id, created_at, status, model, input_tokens, output_tokens, "
                "estimated_cost_usd, error_type FROM runs ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            result["calls_reserved"] = count
            result["reserved_usd"] = str(reserved)
            if in_flight:
                result["runtime_status"] = "request_unresolved"
            if disabled:
                result["runtime_status"] = "stopped"
            if latest:
                result["last_run"] = dict(zip(
                    ("run_id", "created_at", "status", "model", "input_tokens",
                     "output_tokens", "estimated_cost_usd", "error_type"), latest,
                    strict=True,
                ))
                if ready and latest[2] == "succeeded":
                    result["runtime_status"] = "l1_live_pilot"
        finally:
            connection.close()
    except (RuntimeBlocked, sqlite3.Error, InvalidOperation):
        pass
    try:
        prior = Decimal(os.getenv("ALINE_PRIOR_SPEND_USD", ""))
        if (
            ledger_valid and starting_spend is not None and prior.is_finite()
            and starting_spend <= prior <= BUDGET_USD
        ):
            result["local_remaining_usd"] = str(max(
                Decimal("0"), BUDGET_USD - prior - Decimal(str(result["reserved_usd"])),
            ))
            result["prior_spend_usd"] = str(prior)
    except InvalidOperation:
        pass
    return result


def _reserve(path: Path, prior: Decimal, idempotency_hash: str) -> str:
    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute(
            "SELECT 1 FROM runs WHERE idempotency_hash = ?", (idempotency_hash,),
        ).fetchone():
            raise RuntimeDuplicate("idempotency key already reserved")
        count, reserved, in_flight, disabled = _counts(connection)
        if prior < _starting_spend(connection):
            raise RuntimeBlocked("provider spend readback moved backwards")
        if disabled:
            raise RuntimeBlocked("pilot stopped")
        if in_flight:
            raise RuntimeBusy("model request in progress or unresolved")
        if count >= MAX_CALLS or prior + reserved + RESERVATION_USD > BUDGET_USD:
            raise RuntimeBlocked("pilot budget exhausted")
        run_id = str(uuid4())
        connection.execute(
            "INSERT INTO runs (run_id, idempotency_hash, created_at, status, model, reserved_usd) "
            "VALUES (?, ?, ?, 'in_flight', ?, ?)",
            (run_id, idempotency_hash, _now(), MODEL, str(RESERVATION_USD)),
        )
        connection.execute("COMMIT")  # durable before the potentially billable request
        return run_id
    except sqlite3.OperationalError:
        raise RuntimeBusy("persistent ledger busy") from None
    finally:
        connection.close()


def _finish(path: Path, run_id: str, *, usage: tuple[int, int, int] | None = None,
            cost: Decimal | None = None, error_type: str | None = None) -> bool:
    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        disabled = bool(
            connection.execute("SELECT disabled FROM control WHERE id = 1").fetchone()[0]
        )
        row = connection.execute("SELECT status FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None or row[0] != "in_flight":
            raise RuntimeUncertain("run state changed during model request")
        status = "succeeded" if usage is not None and not disabled else "uncertain"
        connection.execute(
            "UPDATE runs SET finished_at = ?, status = ?, input_tokens = ?, "
            "output_tokens = ?, total_tokens = ?, estimated_cost_usd = ?, error_type = ? "
            "WHERE run_id = ?",
            (_now(), status, usage[0] if usage else None, usage[1] if usage else None,
             usage[2] if usage else None, str(cost) if cost is not None else None,
             error_type or ("Stopped" if disabled else None), run_id),
        )
        connection.execute("COMMIT")
        return not disabled
    except sqlite3.Error:
        raise RuntimeUncertain("run result could not be durably recorded") from None
    finally:
        connection.close()


async def _invoke_model(message: str, model: str, key: str, project_id: str):
    """Exactly one Responses API request. No tools, retries, traces, or storage."""
    from openai import AsyncOpenAI

    async with AsyncOpenAI(
        api_key=key, project=project_id, max_retries=0, timeout=45,
    ) as client:
        return await client.responses.create(
            model=model,
            instructions=INSTRUCTIONS + "\nL1-Dialog: Antworte kurz auf Deutsch. "
            "Technischer Status dieses Turns: lokale Pilot-Gates bestanden; "
            "ein OpenAI-API-Aufruf läuft. Nenne deine Kennung GMV-VE-001 und "
            "deine rein beratende L1-Rolle. Behaupte keine geprüfte externe "
            "Budget- oder Projektfreigabe und keine weiteren Rechte oder Aktionen.",
            input=message,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            store=False,
            tools=[],
        )


def _deployment_id() -> str | None:
    value = os.getenv("RAILWAY_DEPLOYMENT_ID", "")
    if 0 < len(value) <= 128 and re.fullmatch(r"[A-Za-z0-9_-]+", value):
        return value
    return None


async def dialog(message: str, idempotency_key: str) -> dict[str, object]:
    """Run one bounded model request after reserving the lifetime pilot budget."""
    if not isinstance(message, str) or not message.strip():
        raise RuntimeBlocked("dialog message missing")
    if not isinstance(idempotency_key, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{32,128}", idempotency_key,
    ):
        raise RuntimeBlocked("idempotency key missing or invalid")
    prompt = INSTRUCTIONS + message
    if len(prompt.encode("utf-8")) > MAX_INPUT_BYTES:
        raise RuntimeBlocked("dialog input exceeds pilot bound")
    path, prior, project_id, key = _configuration()
    idempotency_hash = hashlib.sha256(idempotency_key.encode("ascii")).hexdigest()
    run_id = _reserve(path, prior, idempotency_hash)
    try:
        response = await _invoke_model(message, MODEL, key, project_id)
        usage = response.usage
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        total_tokens = usage.total_tokens
        if (
            not all(type(value) is int and value >= 0 for value in (
                input_tokens, output_tokens, total_tokens,
            ))
            or total_tokens != input_tokens + output_tokens
            or output_tokens > MAX_OUTPUT_TOKENS
            or input_tokens > MAX_INPUT_BYTES
            or response.model != MODEL
            or not isinstance(response.output_text, str)
            or not response.output_text.strip()
        ):
            raise RuntimeUncertain("provider response or usage invalid")
        cost = (
            Decimal(input_tokens) * INPUT_USD_PER_MILLION
            + Decimal(output_tokens) * OUTPUT_USD_PER_MILLION
        ) / Decimal(1_000_000)
        if cost > RESERVATION_USD:
            raise RuntimeUncertain("provider usage exceeds reserved cost")
    except Exception as exc:
        _finish(path, run_id, error_type=type(exc).__name__)
        raise RuntimeUncertain("model request failed or usage uncertain") from None
    if not _finish(path, run_id, usage=(input_tokens, output_tokens, total_tokens), cost=cost):
        raise RuntimeUncertain("pilot stopped during model request")
    return {
        "worker_id": WORKER_ID,
        "runtime_status": "l1_live_pilot",
        "execution_mode": "openai_model_call",
        "run_id": run_id,
        "completed_at": _now(),
        "deployment_id": _deployment_id(),
        "model": response.model,
        "reply": response.output_text.strip(),
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        },
        "estimated_cost_usd": str(cost),
        "api_requests_made": 1,
        "writes_performed": 0,
    }


def stop() -> dict[str, object]:
    """Persistently disable this pilot. Re-enabling requires operator action."""
    path = _ledger_path()
    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE control SET disabled = 1 WHERE id = 1")
        affected = connection.execute(
            "UPDATE runs SET status = 'uncertain', finished_at = ?, error_type = 'Stopped' "
            "WHERE status = 'in_flight'", (_now(),),
        ).rowcount
        connection.execute("COMMIT")
        return {
            "worker_id": WORKER_ID,
            "runtime_status": "stopped",
            "in_flight_marked_uncertain": affected,
        }
    except sqlite3.Error:
        raise RuntimeUncertain("stop state could not be durably recorded") from None
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aline ledger operator action")
    parser.add_argument("--provision-ledger", action="store_true", required=True)
    parser.parse_args()
    provision_ledger()
    print("Aline persistent pilot ledger provisioned")
