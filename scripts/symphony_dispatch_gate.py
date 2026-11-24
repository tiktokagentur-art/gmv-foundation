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

Zusätzlich liefert das Modul die Host-Kommandos für run-symphony.sh:
gemeinsamer Slot-Zähler mit research.sh (max. 10 Läufe), Einmal-Sperre pro
Issue und Quota-/Login-Stopp (fail-closed, rc=9).

Siehe docs/symphony/dispatch-gate.md und docs/symphony/quota-refresh.md.
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
# Harte Obergrenze, die keine Konfiguration überschreiten darf. Muss mit dem
# Watchdog-Default und ``--budget`` in run-symphony.sh übereinstimmen
# (Petrus 24.11.2026 23:20: 5M pro Lauf; Samira 23:25: nur gemeinsam).
MAX_TOKENS_PER_RUN_CEILING = 5_000_000
# Freigegebener Wert pro Lauf. Erreichen = harter Abbruch.
DEFAULT_MAX_TOKENS_PER_RUN = 5_000_000
# Gemeinsame Obergrenze paralleler Läufe Codex (research.sh) + Symphony
# (Petrus 24.11.2026 23:20). Konfiguration darf nur senken.
MAX_CONCURRENT_RUNS_CEILING = 10
# Exit-Codes der Host-Kommandos (run-symphony.sh reicht sie durch).
RC_BLOCKED = 2
RC_NO_SLOT = 5  # wie research.sh: gemeinsames Parallelitätslimit erreicht
RC_QUOTA_FAIL_CLOSED = 9
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
# Host: gemeinsamer Slot-Zähler, Einmal-Sperre pro Issue, Quota fail-closed
# --------------------------------------------------------------------------
# Kompatibel zu /workspace/research/bin/research.sh (nur auf dem Host):
# - Meta-Lock: flock(2) auf ``/workspace/research/.research.lock``,
# - Slots: eine Datei je laufendem Prozess ``state/slots/<pid>`` mit
#   ``pid=<pid> reserved=<n> id=<lauf-id>``; tote PIDs gelten als frei.
# Symphony-Slots tragen zusätzlich ``kind=symphony issue=<n>`` und
# ``reserved=0`` (kein Anteil am Codex-Tagesbudget).

DEFAULT_SHARED_SLOT_DIR = Path("/workspace/research/state/slots")
DEFAULT_SHARED_SLOT_LOCK = Path("/workspace/research/.research.lock")
DEFAULT_ALERTS_LOG = Path("/workspace/research/ALERTS.log")
DEFAULT_QUOTA_STOP = Path("/workspace/research/state/quota-stop")
SLOT_LOCK_TIMEOUT = 10.0  # wie ``flock -w 10`` in research.sh
SLOT_FIELD = re.compile(r"(\w+)=(\S*)")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def parse_issue(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value < 10_000_000:
        raise GateDenied("invalid_issue")
    return value


def parse_max_total(env: Mapping[str, str]) -> int:
    """``GMV_MAX_TOTAL_RUNS`` darf die gemeinsame Obergrenze nur senken."""
    raw = env.get("GMV_MAX_TOTAL_RUNS", str(MAX_CONCURRENT_RUNS_CEILING))
    if not raw.isdigit() or not 1 <= int(raw) <= MAX_CONCURRENT_RUNS_CEILING:
        raise GateDenied("max_total_runs_invalid")
    return int(raw)


@contextlib.contextmanager
def _flock(path: Path, timeout: float = SLOT_LOCK_TIMEOUT) -> Iterator[None]:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise GateDenied("slot_lock_timeout") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


@dataclass(frozen=True)
class Slot:
    path: Path
    pid: int
    kind: str
    issue: int | None


class SharedSlots:
    """Gemeinsamer Zähler Codex+Symphony, atomar per ``flock`` (max. 10)."""

    def __init__(
        self,
        slot_dir: Path = DEFAULT_SHARED_SLOT_DIR,
        lock_path: Path = DEFAULT_SHARED_SLOT_LOCK,
        max_total: int = MAX_CONCURRENT_RUNS_CEILING,
        pid_alive: Any = _pid_alive,
    ) -> None:
        if (
            isinstance(max_total, bool)
            or not isinstance(max_total, int)
            or not 1 <= max_total <= MAX_CONCURRENT_RUNS_CEILING
        ):
            raise GateDenied("max_total_runs_invalid")
        self.slot_dir = Path(slot_dir)
        self.lock_path = Path(lock_path)
        self.max_total = max_total
        self._alive = pid_alive

    def _live_slots(self) -> list[Slot]:
        self.slot_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        live: list[Slot] = []
        for f in sorted(self.slot_dir.iterdir()):
            if not f.is_file():
                continue
            try:
                fields = dict(SLOT_FIELD.findall(f.read_text(encoding="utf-8")))
            except OSError:
                fields = {}
            kind = fields.get("kind", "research")
            if not f.name.isdigit() or not self._alive(int(f.name)):
                # Nur eigene (Symphony-)Leichen aufräumen; Codex-Slots samt
                # Tagesreservierung räumt research.sh selbst auf. Tote zählen nicht.
                if kind == "symphony":
                    f.unlink(missing_ok=True)
                continue
            issue = fields.get("issue", "")
            live.append(Slot(f, int(f.name), kind, int(issue) if issue.isdigit() else None))
        return live

    def acquire(self, issue: int, pid: int, max_symphony: int) -> Path:
        issue = parse_issue(issue)
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise GateDenied("invalid_pid")
        if (
            isinstance(max_symphony, bool)
            or not isinstance(max_symphony, int)
            or not 1 <= max_symphony <= self.max_total
        ):
            raise GateDenied("max_concurrent_invalid")
        with _flock(self.lock_path):
            live = self._live_slots()
            symphony = [s for s in live if s.kind == "symphony"]
            if any(s.issue == issue for s in symphony):
                raise GateDenied("issue_already_running")
            if any(s.pid == pid for s in live):
                raise GateDenied("slot_pid_in_use")
            if len(live) >= self.max_total:
                raise GateDenied("shared_limit_reached", f"live={len(live)} max={self.max_total}")
            if len(symphony) >= max_symphony:
                raise GateDenied("symphony_limit_reached", f"live={len(symphony)}")
            path = self.slot_dir / str(pid)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(
                    f"pid={pid} reserved=0 id=symphony-issue-{issue} "
                    f"kind=symphony issue={issue}\n"
                )
            return path

    def release(self, issue: int, pid: int) -> bool:
        path = self.slot_dir / str(pid)
        with _flock(self.lock_path):
            try:
                fields = dict(SLOT_FIELD.findall(path.read_text(encoding="utf-8")))
            except OSError:
                return False
            if fields.get("kind") == "symphony" and fields.get("issue") == str(issue):
                path.unlink(missing_ok=True)
                return True
            return False

    def count(self) -> tuple[int, int]:
        """(alle lebenden Slots, davon Symphony)."""
        with _flock(self.lock_path):
            live = self._live_slots()
        return len(live), sum(1 for s in live if s.kind == "symphony")


def acquire_issue_once(once_dir: Path, issue: int) -> Path:
    """Einmal-Sperre pro Issue. ``O_EXCL``: Bei einem Race gewinnt genau einer."""
    issue = parse_issue(issue)
    once_dir = Path(once_dir)
    once_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = once_dir / f"issue-{issue}.once"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise GateDenied("issue_already_started", f"issue={issue}") from None
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(f"issue={issue} pid={os.getpid()} at={int(time.time())}\n")
    return path


def read_max_concurrent(workflow_text: str) -> int:
    """``gmv.dispatch_gate.max_concurrent`` ohne YAML-Abhängigkeit lesen.

    Fehlt der Wert, gilt 1. Ungültige Werte: kein Start (fail-closed).
    """
    front, _ = split_frontmatter(workflow_text)
    path: list[tuple[int, str]] = []
    for raw in front.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, sep, value = line.strip().partition(":")
        if not sep:
            continue
        while path and path[-1][0] >= indent:
            path.pop()
        keys = [k for _, k in path]
        if keys == ["gmv", "dispatch_gate"] and key == "max_concurrent":
            value = value.strip()
            if not value.isdigit() or not 1 <= int(value) <= MAX_CONCURRENT_RUNS_CEILING:
                raise GateDenied("max_concurrent_invalid")
            return int(value)
        if not value.strip():
            path.append((indent, key))
    return 1


# Quota/Refresh: dasselbe Konto (Petrus' ChatGPT/Codex-Login, eine auth.json,
# read-only gemountet) für research.sh und Symphony. Jeder dieser Befunde
# stoppt fail-closed (docs/symphony/quota-refresh.md). Ausgegeben wird nur der Code.
QUOTA_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("quota_exhausted", re.compile(
        r"usage_limit_reached|insufficient_quota|quota[ _]exceeded|"
        r"exceeded your current quota|you've hit your usage limit", re.I)),
    ("rate_limited", re.compile(
        r"rate_limit_exceeded|rate[ -]limit(?:ed| reached)|too many requests|"
        r"(?:status|http|code)[\s\"':=]*429\b", re.I)),
    ("auth_failed", re.compile(
        r"(?:status|http|code)[\s\"':=]*401\b|401 unauthori[sz]ed|\bunauthori[sz]ed\b|"
        r"invalid_grant|token_expired|refresh_token_(?:expired|reused|invalidated)|"
        r"not logged in|please (?:re-?)?log ?in|codex login", re.I)),
    ("auth_refresh_blocked", re.compile(
        r"read-only file system|\bEROFS\b|auth\.json[^\n]{0,80}"
        r"(?:permission denied|read-only|failed to (?:write|save|refresh))", re.I)),
)


def classify_quota_failure(text: str) -> str | None:
    for code, rule in QUOTA_RULES:
        if rule.search(text):
            return code
    return None


def check_quota_stop(marker: Path) -> None:
    if Path(marker).exists():
        raise GateDenied("quota_stop_active")


def record_quota_stop(alerts: Path, marker: Path, issue: int, reason: str) -> None:
    """ALERTS.log-Eintrag plus Stopp-Marker: keine weiteren Starts, kein Retry."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    alerts = Path(alerts)
    marker = Path(marker)
    alerts.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(alerts, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(
            f"{stamp} ALERT symphony issue={issue} quota_fail_closed reason={reason} "
            "- keine weiteren Starts bis 'codex login' ausserhalb der Huelle erneuert "
            "und Marker entfernt\n"
        )
    marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(f"{stamp} source=symphony issue={issue} reason={reason}\n")


def scan_files_for_quota(paths: list[Path]) -> str | None:
    for p in paths:
        try:
            text = Path(p).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        code = classify_quota_failure(text)
        if code:
            return code
    return None


def host_paths(env: Mapping[str, str]) -> dict[str, Path]:
    return {
        "slot_dir": Path(env.get("GMV_SHARED_SLOT_DIR", str(DEFAULT_SHARED_SLOT_DIR))),
        "slot_lock": Path(env.get("GMV_SHARED_SLOT_LOCK", str(DEFAULT_SHARED_SLOT_LOCK))),
        "alerts": Path(env.get("GMV_ALERTS_LOG", str(DEFAULT_ALERTS_LOG))),
        "quota_stop": Path(env.get("GMV_QUOTA_STOP", str(DEFAULT_QUOTA_STOP))),
    }


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
    # Pro Symphony-Prozess genau ein Agent: Der Watchdog stoppt bei einem
    # zweiten Dispatch (unverändert). Parallelität = getrennte Prozesse je Issue.
    if agent.get("max_concurrent_agents") != 1:
        errors.append("agent.max_concurrent_agents must be 1 (one issue per Symphony process)")
    errors.extend(validate_sandbox(config))

    gmv = config.get("gmv") or {}
    gate = gmv.get("dispatch_gate") or {}
    if gate.get("enabled") is not False:
        errors.append("gmv.dispatch_gate.enabled must be false in the template")
    if gate.get("flag") != GATE_FLAG:
        errors.append(f"gmv.dispatch_gate.flag must be {GATE_FLAG}")
    max_concurrent = gate.get("max_concurrent")
    if (
        isinstance(max_concurrent, bool)
        or not isinstance(max_concurrent, int)
        or not 1 <= max_concurrent <= MAX_CONCURRENT_RUNS_CEILING
    ):
        errors.append(
            "gmv.dispatch_gate.max_concurrent must be an integer from 1 to "
            f"{MAX_CONCURRENT_RUNS_CEILING}"
        )
    elif isinstance(agent.get("max_concurrent_agents"), int) and (
        agent["max_concurrent_agents"] > max_concurrent
    ):
        errors.append(
            "agent.max_concurrent_agents must not exceed gmv.dispatch_gate.max_concurrent"
        )
    budget = gmv.get("token_budget") or {}
    try:
        parse_token_budget(budget.get("max_tokens_per_run"))
    except GateDenied as exc:
        errors.append(f"gmv.token_budget.max_tokens_per_run: {exc.reason}")
    reserve = budget.get("reserve_per_turn")
    turns = agent.get("max_turns")
    max_tokens = budget.get("max_tokens_per_run")
    if (
        not isinstance(reserve, int)
        or isinstance(reserve, bool)
        or reserve <= 0
        or not isinstance(turns, int)
        or not isinstance(max_tokens, int)
        or reserve * turns > max_tokens
    ):
        errors.append("gmv.token_budget.reserve_per_turn * agent.max_turns must fit the budget")
    if budget.get("on_exceeded") != "stop" or budget.get("on_unknown_usage") != "stop":
        errors.append("gmv.token_budget must stop on exceeded and unknown usage")
    return errors


# Sandbox-Allowlist: nur GitHub und OpenAI. Download-Hosts (codeload,
# objects.githubusercontent.com) sind nicht nötig, weil Klon und github_api
# außerhalb der Codex-Sandbox laufen.
ALLOWED_DOMAINS = frozenset({"github.com", "api.github.com", "api.openai.com"})
EGRESS_PROXY_URL = "http://127.0.0.1:18443"
# Nur der Modellverkehr des Codex-Prozesses (ChatGPT-Login) umgeht den Proxy.
ALLOWED_NO_PROXY = frozenset({"chatgpt.com", ".chatgpt.com", "auth.openai.com"})
# Symphony@be10a1b sendet diese Policy bei jedem Turn. Nur cwd ist beschreibbar.
EXPECTED_TURN_POLICY = {
    "type": "workspaceWrite",
    "writableRoots": [],
    "networkAccess": False,
    "excludeTmpdirEnvVar": True,
    "excludeSlashTmp": True,
}
# Symphony nimmt bei "never" alle Anfragen automatisch an; bei "on-request"
# endet der Turn mit approval_required (fail-closed).
EXPECTED_APPROVAL_POLICY = "on-request"
FORBIDDEN_CODEX_SNIPPETS = (
    "danger",
    "--yolo",
    "--full-auto",
    "bypass",
    "sandbox_mode",
    '"*',
)
DOMAIN_RULE = re.compile(r'"([^"]+)"\s*=\s*"(allow|deny)"')


def validate_sandbox(config: Mapping[str, Any]) -> list[str]:
    """Sandbox rules for the Codex app-server as launched by Symphony@be10a1b."""
    errors: list[str] = []
    workspace_root = str((config.get("workspace") or {}).get("root") or "")
    if not workspace_root or workspace_root.startswith(("/tmp", "/var/tmp")):
        errors.append("workspace.root must be set and outside /tmp")
    codex = config.get("codex") or {}
    if codex.get("thread_sandbox") not in ("read-only", "workspace-write"):
        errors.append("codex.thread_sandbox must be read-only or workspace-write")
    if codex.get("turn_sandbox_policy") != EXPECTED_TURN_POLICY:
        errors.append("codex.turn_sandbox_policy must restrict writes to the issue workspace")
    if codex.get("approval_policy") != EXPECTED_APPROVAL_POLICY:
        errors.append("codex.approval_policy must reject escalations (never auto-approve)")
    command = codex.get("command")
    if not isinstance(command, str):
        errors.append("codex.command must be set")
        return errors
    for snippet in FORBIDDEN_CODEX_SNIPPETS:
        if snippet in command:
            errors.append(f"codex.command must not contain {snippet!r}")
    for needed in ("features.network_proxy=true", 'default_permissions="gmv_symphony"'):
        if needed not in command:
            errors.append(f"codex.command must set {needed}")
    if not command.rstrip().endswith("app-server"):
        errors.append("codex.command must end with app-server")
    rules = DOMAIN_RULE.findall(command)
    allowed = {host for host, verdict in rules if verdict == "allow"}
    if allowed != ALLOWED_DOMAINS:
        errors.append("codex network allowlist must be exactly GitHub and OpenAI")
    if "permissions.gmv_symphony.network={enabled=true" not in command:
        errors.append("codex network profile must be enabled explicitly")
    # allow_local_binding nur zusammen mit dem lokalen Allowlist-Upstream.
    if "allow_local_binding=true" in command:
        for needed in (
            f"HTTPS_PROXY={EGRESS_PROXY_URL}",
            f"HTTP_PROXY={EGRESS_PROXY_URL}",
            "allow_upstream_proxy=true",
        ):
            if needed not in command:
                errors.append(f"allow_local_binding requires {needed}")
    no_proxy = re.search(r"NO_PROXY=(\S+)", command)
    if no_proxy and not set(no_proxy.group(1).split(",")) <= ALLOWED_NO_PROXY:
        errors.append("NO_PROXY may only exempt the Codex model hosts")
    if re.search(r"(?i)(?:https?|all)_proxy=(?!http://127\.0\.0\.1:18443\b)", command):
        errors.append("proxy variables must point to the local egress proxy")
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
    sa = sub.add_parser("slot-acquire", help="Slot im gemeinsamen Zähler belegen")
    sa.add_argument("--issue", type=int, required=True)
    sa.add_argument("--pid", type=int, required=True)
    sa.add_argument("--workflow", type=Path, required=True)
    sr = sub.add_parser("slot-release", help="eigenen Slot freigeben")
    sr.add_argument("--issue", type=int, required=True)
    sr.add_argument("--pid", type=int, required=True)
    oa = sub.add_parser("once-acquire", help="Einmal-Sperre pro Issue anlegen")
    oa.add_argument("--issue", type=int, required=True)
    oa.add_argument("--dir", type=Path, required=True)
    sub.add_parser("quota-check", help="Quota-Stopp-Marker prüfen")
    qs = sub.add_parser("quota-scan", help="Laufprotokolle auf Quota/Auth prüfen")
    qs.add_argument("--issue", type=int, required=True)
    qs.add_argument("files", type=Path, nargs="*")
    args = parser.parse_args(argv)

    if args.cmd == "validate-workflow":
        front, _ = split_frontmatter(args.path.read_text(encoding="utf-8"))
        errors = validate_workflow(_load_yaml(front))
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1 if errors else 0

    paths = host_paths(os.environ)
    try:
        if args.cmd == "slot-acquire":
            max_symphony = read_max_concurrent(args.workflow.read_text(encoding="utf-8"))
            slots = SharedSlots(paths["slot_dir"], paths["slot_lock"],
                                parse_max_total(os.environ))
            try:
                slots.acquire(args.issue, args.pid, min(max_symphony, slots.max_total))
            except GateDenied as exc:
                if exc.reason in ("shared_limit_reached", "symphony_limit_reached"):
                    print(f"BLOCKED: {exc}", file=sys.stderr)
                    return RC_NO_SLOT
                raise
            print(f"slot ok issue={args.issue} max_symphony={max_symphony}", file=sys.stderr)
            return 0
        if args.cmd == "slot-release":
            SharedSlots(paths["slot_dir"], paths["slot_lock"]).release(args.issue, args.pid)
            return 0
        if args.cmd == "once-acquire":
            acquire_issue_once(args.dir, args.issue)
            return 0
        if args.cmd == "quota-check":
            try:
                check_quota_stop(paths["quota_stop"])
            except GateDenied as exc:
                print(f"BLOCKED: {exc.reason} ({paths['quota_stop']})", file=sys.stderr)
                return RC_QUOTA_FAIL_CLOSED
            return 0
        if args.cmd == "quota-scan":
            code = scan_files_for_quota(args.files)
            if code is None:
                return 0
            record_quota_stop(paths["alerts"], paths["quota_stop"],
                              parse_issue(args.issue), code)
            print(f"ALERT: quota_fail_closed reason={code}", file=sys.stderr)
            return RC_QUOTA_FAIL_CLOSED
    except (GateDenied, OSError, ValueError) as exc:
        reason = exc.reason if isinstance(exc, GateDenied) else type(exc).__name__
        print(f"BLOCKED: {reason}", file=sys.stderr)
        return RC_BLOCKED

    # "check": Es gibt in diesem Entwurf keine angebundene Authority.
    if not gate_enabled(os.environ):
        print("BLOCKED: gate_disabled", file=sys.stderr)
    else:
        print("BLOCKED: authority_unavailable", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
