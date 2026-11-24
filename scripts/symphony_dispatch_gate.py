#!/usr/bin/env python3
"""Draft of the server-side Symphony dispatch gate (ENG-003, issue #74).

ENTWURF. Standardmäßig deaktiviert. Solange das Flag
``GMV_SYMPHONY_DISPATCH_GATE`` nicht exakt ``enabled`` ist, lehnt das Gate
jeden Dispatch ab (fail-closed). Es gibt keine Netzwerk-, GitHub- oder
Codex-Aufrufe in diesem Modul.

Das Gate ist keine zweite Assignment Authority (ADR-0003). Es vergibt keine
Claims. Es prüft vor jedem Codex-Start einen von der Control Plane
ausgestellten Claim und verweigert den Start, wenn

- das Gate aus ist,
- der Claim fehlt, abgelaufen ist oder nicht zum Worker passt,
- das Fencing-Merkmal veraltet ist,
- dasselbe Ticket bereits an einen anderen Worker dispatcht ist,
- das Token-Budget des Laufs fehlt, ungültig oder erschöpft ist.

Siehe docs/symphony/dispatch-gate.md.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import sys
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

REPOSITORY = "tiktokagentur-art/gmv-foundation"
CLONE_URL = f"https://github.com/{REPOSITORY}.git"
GATE_FLAG = "GMV_SYMPHONY_DISPATCH_GATE"
GATE_FLAG_ON = "enabled"
# Harte Obergrenze, die keine Konfiguration überschreiten darf.
MAX_TOKENS_PER_RUN_CEILING = 200_000
WORKER_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,62}$")
CLAIM_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")


class GateDenied(Exception):
    """Dispatch refused. ``reason`` is a stable, secret-free code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


class BudgetExceeded(GateDenied):
    """The per-run token budget is exhausted. The run must stop."""


# --------------------------------------------------------------------------
# Flag
# --------------------------------------------------------------------------


def gate_enabled(env: Mapping[str, str]) -> bool:
    """Only the exact value ``enabled`` switches the gate on. Default: off."""
    return env.get(GATE_FLAG, "") == GATE_FLAG_ON


# --------------------------------------------------------------------------
# Claims (owned by the Control Plane, only read here)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Claim:
    repository: str
    issue_number: int
    worker_id: str
    claim_id: str
    fencing_token: int
    lease_expires_at: float


@dataclass(frozen=True)
class DispatchRequest:
    repository: str
    issue_number: int
    worker_id: str
    claim_id: str
    fencing_token: int


class ClaimAuthority(Protocol):
    """Read-only view on the Control Plane. Implemented in a later PR (CP-002)."""

    def active_claim(self, repository: str, issue_number: int) -> Claim | None: ...


def validate_request(request: DispatchRequest) -> None:
    if request.repository != REPOSITORY:
        raise GateDenied("repository_not_allowed")
    if not isinstance(request.issue_number, int) or request.issue_number <= 0:
        raise GateDenied("invalid_issue")
    if not WORKER_ID.fullmatch(request.worker_id or ""):
        raise GateDenied("invalid_worker_id")
    if not CLAIM_ID.fullmatch(request.claim_id or ""):
        raise GateDenied("invalid_claim_id")
    if (
        not isinstance(request.fencing_token, int)
        or isinstance(request.fencing_token, bool)
        or request.fencing_token <= 0
    ):
        raise GateDenied("invalid_fencing_token")


def verify_claim(request: DispatchRequest, claim: Claim | None, now: float) -> Claim:
    if claim is None:
        raise GateDenied("no_active_claim")
    if (claim.repository, claim.issue_number) != (request.repository, request.issue_number):
        raise GateDenied("claim_mismatch")
    if claim.worker_id != request.worker_id:
        raise GateDenied("claim_bound_to_other_worker")
    if claim.claim_id != request.claim_id:
        raise GateDenied("claim_mismatch")
    if claim.fencing_token != request.fencing_token:
        raise GateDenied("stale_fencing_token")
    if claim.lease_expires_at <= now:
        raise GateDenied("lease_expired")
    return claim


# --------------------------------------------------------------------------
# Sperre gegen Doppelvergabe
# --------------------------------------------------------------------------


class DispatchLock:
    """Host-local mutual exclusion: one ticket is never dispatched to two workers.

    Not a source of truth for assignment (ADR-0003). It is a second, independent
    barrier that still holds if the authority or Symphony misbehaves, e.g.
    Symphony re-dispatching an ``open`` issue or two orchestrator processes.

    Rules (all under one exclusive ``flock``):

    - free ticket: the first request wins,
    - same worker, same claim, same fencing token: idempotent (restart/retry),
    - other worker while the holder's lease is valid: denied,
    - takeover after lease expiry only with a strictly higher fencing token,
    - a lower or equal fencing token than recorded is always denied.
    """

    def __init__(self, state_dir: Path) -> None:
        self._dir = Path(state_dir)
        self._state = self._dir / "dispatch-locks.json"
        self._lockfile = self._dir / "dispatch-locks.lock"

    @contextlib.contextmanager
    def _locked(self) -> Iterator[dict[str, Any]]:
        self._dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(self._lockfile, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            state = self._read()
            yield state
            tmp = self._state.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self._state)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _read(self) -> dict[str, Any]:
        if not self._state.exists():
            return {}
        try:
            data = json.loads(self._state.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # Unlesbarer Zustand: lieber nichts starten als doppelt starten.
            raise GateDenied("lock_state_unreadable") from exc
        if not isinstance(data, dict):
            raise GateDenied("lock_state_unreadable")
        return data

    @staticmethod
    def _key(repository: str, issue_number: int) -> str:
        return f"{repository}#{issue_number}"

    def acquire(self, claim: Claim, now: float) -> None:
        key = self._key(claim.repository, claim.issue_number)
        with self._locked() as state:
            held = state.get(key)
            if held is not None:
                same = (
                    held.get("worker_id") == claim.worker_id
                    and held.get("claim_id") == claim.claim_id
                    and held.get("fencing_token") == claim.fencing_token
                )
                if not same:
                    if claim.fencing_token <= int(held.get("fencing_token", 0)):
                        raise GateDenied("stale_fencing_token")
                    if float(held.get("lease_expires_at", 0)) > now:
                        raise GateDenied("already_dispatched_to_other_worker")
            state[key] = {
                "worker_id": claim.worker_id,
                "claim_id": claim.claim_id,
                "fencing_token": claim.fencing_token,
                "lease_expires_at": claim.lease_expires_at,
            }

    def release(self, claim: Claim) -> bool:
        key = self._key(claim.repository, claim.issue_number)
        with self._locked() as state:
            held = state.get(key)
            if (
                held is not None
                and held.get("worker_id") == claim.worker_id
                and held.get("fencing_token") == claim.fencing_token
            ):
                del state[key]
                return True
            return False

    def holder(self, repository: str, issue_number: int) -> str | None:
        with self._locked() as state:
            held = state.get(self._key(repository, issue_number))
            return None if held is None else str(held.get("worker_id"))


# --------------------------------------------------------------------------
# Token-Budget pro Lauf (hartes Limit, fail-closed)
# --------------------------------------------------------------------------


def parse_token_budget(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GateDenied("token_budget_missing_or_invalid")
    if value <= 0 or value > MAX_TOKENS_PER_RUN_CEILING:
        raise GateDenied("token_budget_out_of_range")
    return value


@dataclass
class TokenBudget:
    """Cumulative token budget for exactly one run.

    - Kein Budget oder ein ungültiges Budget: kein Start.
    - Unbekannter oder negativer Verbrauch zählt als erschöpft.
    - Einmal überschritten bleibt der Lauf gestoppt (sticky).
    - Vor jedem Turn muss die Reserve für den nächsten Turn passen.
    """

    max_tokens: int
    used: int = 0
    exhausted: bool = field(default=False)

    def __post_init__(self) -> None:
        self.max_tokens = parse_token_budget(self.max_tokens)

    @property
    def remaining(self) -> int:
        return max(self.max_tokens - self.used, 0)

    def ensure_can_start_turn(self, reserve: int) -> None:
        if self.exhausted:
            raise BudgetExceeded("token_budget_exhausted")
        if isinstance(reserve, bool) or not isinstance(reserve, int) or reserve <= 0:
            self.exhausted = True
            raise BudgetExceeded("token_reserve_invalid")
        if self.used + reserve > self.max_tokens:
            self.exhausted = True
            raise BudgetExceeded("token_budget_exhausted", f"remaining={self.remaining}")

    def record(self, tokens: Any) -> None:
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
            self.exhausted = True
            raise BudgetExceeded("token_usage_unknown")
        self.used += tokens
        if self.used >= self.max_tokens:
            self.exhausted = True
            raise BudgetExceeded("token_budget_exhausted", f"used={self.used}")


# --------------------------------------------------------------------------
# Gate
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Permit:
    claim: Claim
    budget: TokenBudget


class DispatchGate:
    def __init__(
        self,
        env: Mapping[str, str],
        authority: ClaimAuthority | None,
        lock: DispatchLock,
        max_tokens_per_run: Any,
        clock: Any = time.time,
    ) -> None:
        self._env = env
        self._authority = authority
        self._lock = lock
        self._max_tokens = max_tokens_per_run
        self._clock = clock

    def authorize(self, request: DispatchRequest) -> Permit:
        if not gate_enabled(self._env):
            raise GateDenied("gate_disabled")
        if self._authority is None:
            raise GateDenied("authority_unavailable")
        validate_request(request)
        budget = TokenBudget(self._max_tokens)
        now = float(self._clock())
        try:
            claim = self._authority.active_claim(request.repository, request.issue_number)
        except GateDenied:
            raise
        except Exception as exc:  # Authority nicht erreichbar: fail-closed.
            raise GateDenied("authority_unavailable") from exc
        claim = verify_claim(request, claim, now)
        self._lock.acquire(claim, now)
        return Permit(claim=claim, budget=budget)


# --------------------------------------------------------------------------
# Workflow-Vorlage prüfen (Repo-Klon-Hook, Pilotgrenzen)
# --------------------------------------------------------------------------

FORBIDDEN_HOOK_SNIPPETS = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "@github.com",
    "x-access-token",
    "--recurse-submodules",
    "curl ",
    "wget ",
    "| sh",
    "| bash",
    "git push",
    "gh ",
)


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("workflow must start with YAML front matter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("workflow front matter is not closed")
    return text[4:end], text[end + 5 :]


def validate_workflow(config: Mapping[str, Any]) -> list[str]:
    """Return a list of violations of the pilot rules. Empty list means valid."""
    errors: list[str] = []
    tracker = config.get("tracker") or {}
    provider = tracker.get("provider") or {}
    if tracker.get("kind") != "github" or provider.get("repo") != REPOSITORY:
        errors.append("tracker must be github on the allowlisted repository")
    if provider.get("token") != "$GITHUB_TOKEN":
        errors.append("tracker token must be an env reference, never a literal")

    hooks = config.get("hooks") or {}
    clone = hooks.get("after_create")
    if not isinstance(clone, str) or not clone.strip():
        errors.append("hooks.after_create must clone the repository")
    else:
        lines = [ln.strip() for ln in clone.strip().splitlines() if ln.strip()]
        if not lines or lines[0] != "set -eu":
            errors.append("hooks.after_create must start with 'set -eu'")
        clone_lines = [ln for ln in lines if ln.startswith("git clone ")]
        if len(clone_lines) != 1:
            errors.append("hooks.after_create must contain exactly one git clone")
        else:
            cmd = clone_lines[0]
            for needed in ("--depth 1", "--single-branch", "--no-tags", CLONE_URL):
                if needed not in cmd:
                    errors.append(f"git clone must use {needed}")
            if not cmd.endswith(" ."):
                errors.append("git clone must target the workspace directory '.'")
        for snippet in FORBIDDEN_HOOK_SNIPPETS:
            if snippet in clone:
                errors.append(f"hooks.after_create must not contain {snippet.strip()!r}")
    timeout = hooks.get("timeout_ms")
    if not isinstance(timeout, int) or not 0 < timeout <= 300_000:
        errors.append("hooks.timeout_ms must be set and at most 300000")

    agent = config.get("agent") or {}
    if agent.get("max_concurrent_agents") != 1:
        errors.append("agent.max_concurrent_agents must be 1")
    codex = config.get("codex") or {}
    if codex.get("thread_sandbox") != "read-only":
        errors.append("codex.thread_sandbox must stay read-only in the pilot")

    gmv = config.get("gmv") or {}
    gate = gmv.get("dispatch_gate") or {}
    if gate.get("enabled") is not False:
        errors.append("gmv.dispatch_gate.enabled must be false in the template")
    if gate.get("flag") != GATE_FLAG:
        errors.append(f"gmv.dispatch_gate.flag must be {GATE_FLAG}")
    budget = gmv.get("token_budget") or {}
    try:
        parse_token_budget(budget.get("max_tokens_per_run"))
    except GateDenied as exc:
        errors.append(f"gmv.token_budget.max_tokens_per_run: {exc.reason}")
    if budget.get("on_exceeded") != "stop" or budget.get("on_unknown_usage") != "stop":
        errors.append("gmv.token_budget must stop on exceeded and unknown usage")
    return errors


def _load_yaml(text: str) -> Mapping[str, Any]:
    import yaml  # dev dependency; only needed for the validator CLI

    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("front matter must be a mapping")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    vw = sub.add_parser("validate-workflow")
    vw.add_argument("path", type=Path)
    sub.add_parser("check")
    args = parser.parse_args(argv)

    if args.cmd == "validate-workflow":
        front, _ = split_frontmatter(args.path.read_text(encoding="utf-8"))
        errors = validate_workflow(_load_yaml(front))
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1 if errors else 0

    # "check": Es gibt in diesem Entwurf keine angebundene Authority.
    if not gate_enabled(os.environ):
        print("BLOCKED: gate_disabled", file=sys.stderr)
    else:
        print("BLOCKED: authority_unavailable", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
