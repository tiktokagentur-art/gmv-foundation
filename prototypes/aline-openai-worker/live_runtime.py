"""Fail-closed, single-turn Aline L1 runtime for the existing worker service.

The SQLite ledger must live on a mounted Railway volume. A reservation is
committed before any network request. An interrupted or ambiguous request keeps
its full reservation and prevents another request until an operator reconciles
it. This module never logs prompts, answers, credentials, or provider errors.
"""

from __future__ import annotations

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


def _configuration() -> tuple[Path, Decimal, str, str]:
    if os.getenv("ALINE_LIVE_ENABLED") != "true":
        raise RuntimeBlocked("live pilot disabled")
    if os.getenv("ALINE_L1_PROJECT_DEDICATED") != "true":
        raise RuntimeBlocked("dedicated project not attested")
    if os.getenv("ALINE_L1_HARD_LIMIT_ATTESTED") != "true":
        raise RuntimeBlocked("provider hard limit not attested")
    if os.getenv("ALINE_L1_BUDGET_USD") != "10":
        raise RuntimeBlocked("pilot budget mismatch")
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
    return _ledger_path(), prior, project_id, key


def _connect(path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(path, timeout=0, isolation_level=None)
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS control "
            "(id INTEGER PRIMARY KEY CHECK (id = 1), disabled INTEGER NOT NULL)"
        )
        connection.execute("INSERT OR IGNORE INTO control (id, disabled) VALUES (1, 0)")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS runs ("
            "run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, finished_at TEXT, "
            "status TEXT NOT NULL, model TEXT NOT NULL, reserved_usd TEXT NOT NULL, "
            "input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER, "
            "estimated_cost_usd TEXT, error_type TEXT)"
        )
        return connection
    except sqlite3.Error:
        raise RuntimeBlocked("persistent ledger unavailable") from None


def _counts(connection: sqlite3.Connection) -> tuple[int, Decimal, bool, bool]:
    rows = connection.execute("SELECT status, reserved_usd FROM runs").fetchall()
    count = len(rows)
    reserved = sum((Decimal(value) for _, value in rows), Decimal("0"))
    # An uncertain response can have incurred a charge. Halt all subsequent
    # calls until an operator reconciles it outside this runtime.
    in_flight = any(status in ("in_flight", "uncertain") for status, _ in rows)
    disabled = bool(connection.execute("SELECT disabled FROM control WHERE id = 1").fetchone()[0])
    return count, reserved, in_flight, disabled


def readiness() -> tuple[bool, str]:
    """Report local readiness. Provider access is externally verified, not probed here."""
    try:
        path, prior, _, _ = _configuration()
        connection = _connect(path)
        try:
            count, reserved, in_flight, disabled = _counts(connection)
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
        "reserved_usd": "0",
        "local_remaining_usd": None,
        "provider_remaining_usd": None,
        "calls_reserved": 0,
        "last_run": None,
        "provider_verified_by_runtime": False,
    }
    try:
        path = _ledger_path()
        connection = _connect(path)
        try:
            count, reserved, in_flight, disabled = _counts(connection)
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
        if prior.is_finite() and prior >= 0:
            result["local_remaining_usd"] = str(max(
                Decimal("0"), BUDGET_USD - prior - Decimal(str(result["reserved_usd"])),
            ))
            result["prior_spend_usd"] = str(prior)
    except InvalidOperation:
        pass
    return result


def _reserve(path: Path, prior: Decimal) -> str:
    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        count, reserved, in_flight, disabled = _counts(connection)
        if disabled:
            raise RuntimeBlocked("pilot stopped")
        if in_flight:
            raise RuntimeBusy("model request in progress or unresolved")
        if count >= MAX_CALLS or prior + reserved + RESERVATION_USD > BUDGET_USD:
            raise RuntimeBlocked("pilot budget exhausted")
        run_id = str(uuid4())
        connection.execute(
            "INSERT INTO runs (run_id, created_at, status, model, reserved_usd) "
            "VALUES (?, ?, 'in_flight', ?, ?)",
            (run_id, _now(), MODEL, str(RESERVATION_USD)),
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
            "Melde keine nicht verifizierten Freigaben oder Aktionen als Tatsache.",
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


async def dialog(message: str) -> dict[str, object]:
    """Run one bounded model request after reserving the lifetime pilot budget."""
    if not isinstance(message, str) or not message.strip():
        raise RuntimeBlocked("dialog message missing")
    prompt = INSTRUCTIONS + message
    if len(prompt.encode("utf-8")) > MAX_INPUT_BYTES:
        raise RuntimeBlocked("dialog input exceeds pilot bound")
    path, prior, project_id, key = _configuration()
    run_id = _reserve(path, prior)
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
            or total_tokens < input_tokens + output_tokens
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
