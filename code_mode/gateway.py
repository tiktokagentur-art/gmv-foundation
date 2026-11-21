"""Pilot gateway: attest caller outside request, authorize every bridge call, audit."""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from code_mode.bridge import READ_TOOLS, BridgeError, MCPBridge, MCPClient
from code_mode.sandbox import ExecutionLimits, SandboxUnavailable, run_code

_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_SECRET_PREFIX = re.compile(r"(?:gh[pousr]_|github_pat_|sk-)", re.IGNORECASE)


@dataclass(frozen=True)
class TrustedPrincipal:
    """Created by a trusted caller, never parsed from generated code or request JSON."""

    agent_id: str
    active: bool


@dataclass(frozen=True)
class Mandate:
    agent_id: str
    work_item_id: str
    profile: str
    allowed_tools: frozenset[str]
    active: bool = True
    synthetic_only: bool = True


@dataclass(frozen=True)
class ExecutionRequest:
    work_item_id: str
    profile: str
    code: str
    requested_tools: frozenset[str]


@dataclass
class ExecutionResult:
    execution_id: str
    status: str
    error_code: str | None
    result: object | None
    audit: dict[str, object] = field(default_factory=dict)


class JsonlAuditSink:
    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()

    def write(self, record: dict[str, object]) -> None:
        # Audit schema is fixed in Gateway.execute; no prompts, responses or errors.
        with self._lock:
            with self._path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


class Gateway:
    def __init__(
        self,
        mandates: tuple[Mandate, ...],
        client: MCPClient,
        audit_sink: JsonlAuditSink,
        limits: ExecutionLimits | None = None,
        max_concurrent: int = 4,
    ):
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be positive")
        self._mandates = mandates
        self._client = client
        self._audit = audit_sink
        self._limits = limits or ExecutionLimits()
        self._slots = threading.BoundedSemaphore(max_concurrent)

    def execute(
        self,
        request: ExecutionRequest,
        principal: TrustedPrincipal,
        cancel_event: threading.Event | None = None,
    ) -> ExecutionResult:
        execution_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()
        start = time.monotonic()
        calls: list[dict[str, str]] = []
        result: object | None = None
        error_code: str | None = None
        peak_memory_bytes: int | None = None
        mandate = self._authorize(request, principal)
        if mandate is None:
            error_code = "unauthorized"
        elif not self._slots.acquire(blocking=False):
            error_code = "concurrency_limit"
        else:
            try:
                bridge = MCPBridge(self._client, mandate.allowed_tools & request.requested_tools)

                def invoke(name: str, arguments: dict[str, object]) -> object:
                    try:
                        value = bridge.call(name, arguments)
                        calls.append(
                            {"name": name if name in READ_TOOLS else "unknown", "status": "ok"}
                        )
                        return value
                    except BridgeError as exc:
                        calls.append(
                            {"name": name if name in READ_TOOLS else "unknown", "status": exc.code}
                        )
                        raise

                sandbox_result = run_code(request.code, invoke, self._limits, cancel_event)
                result = sandbox_result.result
                error_code = sandbox_result.error_code
                peak_memory_bytes = sandbox_result.peak_memory_bytes
            except (SandboxUnavailable, ValueError):
                error_code = "sandbox_unavailable"
            except Exception:
                # A failed local runtime must still have a classified audit record.
                error_code = "sandbox_error"
            finally:
                self._slots.release()
        record: dict[str, object] = {
            "execution_id": execution_id,
            "agent_id": _safe_id(getattr(principal, "agent_id", None)),
            "work_item_id": _safe_id(getattr(request, "work_item_id", None)),
            "profile": _safe_id(getattr(request, "profile", None)),
            "timestamp": timestamp,
            "tool_calls": calls,
            "duration_ms": round((time.monotonic() - start) * 1000, 2),
            "peak_memory_bytes": peak_memory_bytes,
            "status": "ok" if error_code is None else "error",
            "error_code": error_code,
        }
        self._audit.write(record)
        return ExecutionResult(execution_id, str(record["status"]), error_code, result, record)

    def _authorize(self, request: ExecutionRequest, principal: TrustedPrincipal) -> Mandate | None:
        if not isinstance(principal, TrustedPrincipal) or not isinstance(request, ExecutionRequest):
            return None
        if (
            not principal.active
            or not isinstance(principal.agent_id, str)
            or _safe_id(principal.agent_id) == "invalid"
        ):
            return None
        if _safe_id(request.work_item_id) == "invalid":
            return None
        if _safe_id(request.profile) == "invalid":
            return None
        if not isinstance(request.code, str) or len(request.code.encode("utf-8")) > 16_384:
            return None
        if (
            not isinstance(request.requested_tools, frozenset)
            or not request.requested_tools <= READ_TOOLS
        ):
            return None
        for mandate in self._mandates:
            if (
                mandate.active
                and mandate.synthetic_only
                and mandate.agent_id == principal.agent_id
                and mandate.work_item_id == request.work_item_id
                and mandate.profile == request.profile
                and request.requested_tools <= mandate.allowed_tools
            ):
                return mandate
        return None


def _safe_id(value: object) -> str:
    if isinstance(value, str) and _ID.fullmatch(value) and not _SECRET_PREFIX.search(value):
        return value
    return "invalid"
