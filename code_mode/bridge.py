"""Server-side, fail-closed bridge for a narrow read-only MCP tool catalog."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Protocol


class BridgeError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class MCPClient(Protocol):
    def call_tool(self, name: str, arguments: dict[str, object]) -> object: ...


# These names are internal adapter contracts, not client-supplied MCP names.
READ_TOOLS = frozenset(
    {
        "github.list_issues",
        "github.list_pull_requests",
        "github.ci_status",
        "railway.list_deployments",
        "railway.service_status",
    }
)

_FIELDS = {
    "github.list_issues": ("number", "title", "state", "labels", "url"),
    "github.list_pull_requests": ("number", "title", "state", "draft", "url"),
    "github.ci_status": ("ref", "status", "conclusion", "url"),
    "railway.list_deployments": ("id", "service", "environment", "status", "created_at"),
    "railway.service_status": ("service", "environment", "status", "deployment_id"),
}
_TYPES = {
    "github.list_issues": (int, str, str, list, str),
    "github.list_pull_requests": (int, str, str, bool, str),
    "github.ci_status": (str, str, str, str),
    "railway.list_deployments": (str, str, str, str, str),
    "railway.service_status": (str, str, str, str),
}
_LIST_TOOLS = frozenset(
    {"github.list_issues", "github.list_pull_requests", "railway.list_deployments"}
)
_TOKEN = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9_]{12,}|github_pat_[A-Za-z0-9_]{12,}|sk-[A-Za-z0-9_-]{12,})\b"
)
_USERINFO = re.compile(r"(https?://)[^/@\s]+@")


def _safe_text(value: str, limit: int) -> str:
    value = "".join(char for char in value if char.isprintable())[:limit]
    return _TOKEN.sub("[REDACTED]", _USERINFO.sub(r"\1[REDACTED]@", value))


class MCPBridge:
    """An adapter around an injected MCP client; credentials remain in that client.

    The fixture client is used in the pilot. A real client requires a separate
    identity, mandate, credential and source review before injection here.
    """

    def __init__(
        self, client: MCPClient, allowed_tools: frozenset[str], max_response_bytes: int = 16_384
    ):
        if not allowed_tools <= READ_TOOLS:
            raise ValueError("unknown tool in policy")
        self._client = client
        self._allowed = allowed_tools
        self._max_bytes = max_response_bytes

    def call(self, name: str, arguments: object) -> object:
        if not isinstance(name, str):
            raise BridgeError("tool_denied")
        if name not in self._allowed or name not in READ_TOOLS:
            raise BridgeError("tool_denied")
        if not isinstance(arguments, dict) or arguments:
            raise BridgeError("invalid_tool_arguments")
        try:
            raw = self._client.call_tool(name, {})
            encoded = json.dumps(raw, ensure_ascii=False, allow_nan=False)
            if len(encoded.encode("utf-8")) > self._max_bytes:
                raise BridgeError("tool_response_limit")
            return _project(name, raw)
        except BridgeError:
            raise
        except Exception as exc:
            raise BridgeError("tool_response_invalid") from exc


def _project(name: str, raw: object) -> object:
    def row(value: object) -> dict[str, object]:
        if not isinstance(value, Mapping):
            raise BridgeError("tool_response_invalid")
        result: dict[str, object] = {}
        for field, expected_type in zip(_FIELDS[name], _TYPES[name], strict=True):
            item = value.get(field)
            if type(item) is not expected_type:
                raise BridgeError("tool_response_invalid")
            if field == "labels":
                if not all(isinstance(label, str) for label in item):
                    raise BridgeError("tool_response_invalid")
                result[field] = [_safe_text(label, 80) for label in item[:20]]
            else:
                result[field] = _safe_text(item, 512) if isinstance(item, str) else item
        return result

    if name in _LIST_TOOLS:
        if not isinstance(raw, list) or len(raw) > 100:
            raise BridgeError("tool_response_invalid")
        return [row(item) for item in raw]
    return row(raw)


class FixtureMCPClient:
    """Deterministic offline MCP substitute. No network or credentials."""

    def __init__(self, responses: Mapping[str, object]):
        self._responses = dict(responses)

    def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        if arguments or name not in self._responses:
            raise BridgeError("tool_response_invalid")
        return self._responses[name]
