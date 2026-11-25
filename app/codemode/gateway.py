"""Deny-by-default, side-effect-free gateway policy scaffold.

No dynamic code execution or external tool dispatch occurs in this module.
"""
from dataclasses import dataclass
from enum import Enum


class Access(str, Enum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class Tool:
    name: str
    access: Access


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


class Gateway:
    def __init__(self, tools: tuple[Tool, ...], grants: dict[str, frozenset[str]]):
        names = [tool.name for tool in tools]
        if len(names) != len(set(names)):
            raise ValueError("duplicate tool identifier")
        self._tools = {tool.name: tool for tool in tools}
        self._grants = dict(grants)

    def authorize(self, actor: str, tool_name: str, *, approved: bool = False) -> Decision:
        if not actor or not actor.strip():
            return Decision(False, "missing_actor")
        tool = self._tools.get(tool_name)
        if tool is None:
            return Decision(False, "unknown_tool")
        if tool_name not in self._grants.get(actor, frozenset()):
            return Decision(False, "not_granted")
        if tool.access == Access.WRITE and not approved:
            return Decision(False, "approval_required")
        return Decision(True, "authorized")
