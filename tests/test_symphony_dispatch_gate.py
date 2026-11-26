"""Negative tests for the draft Symphony dispatch gate (ENG-003, issue #74)."""

from __future__ import annotations

import copy
import json
import multiprocessing
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from symphony_dispatch_gate import (  # noqa: E402
    DEFAULT_MAX_TOKENS_PER_RUN,
    GATE_FLAG,
    MAX_CONCURRENT_RUNS_CEILING,
    MAX_TOKENS_PER_RUN_CEILING,
    RC_NO_SLOT,
    RC_QUOTA_FAIL_CLOSED,
    RC_UNKNOWN_FAIL_CLOSED,
    REPOSITORY,
    BudgetExceeded,
    Claim,
    DispatchGate,
    DispatchLock,
    DispatchRequest,
    GateDenied,
    SharedSlots,
    TokenBudget,
    acquire_issue_once,
    classify_quota_failure,
    host_paths,
    main,
    read_max_concurrent,
    release_lock,
    run_verdict,
    split_frontmatter,
    validate_workflow,
)

WORKFLOW = ROOT / "docs" / "symphony" / "WORKFLOW.example.txt"
NOW = 1_000_000.0
ON = {GATE_FLAG: "enabled"}


def claim(worker: str = "worker-a", fencing: int = 1, expires: float = NOW + 600) -> Claim:
    return Claim(REPOSITORY, 74, worker, f"claim-{worker}-{fencing}", fencing, expires)


def request_for(c: Claim) -> DispatchRequest:
    return DispatchRequest(c.repository, c.issue_number, c.worker_id, c.claim_id, c.fencing_token)


class FakeAuthority:
    def __init__(self, active: Claim | None = None, fail: bool = False) -> None:
        self.active = active
        self.fail = fail

    def active_claim(self, repository: str, issue_number: int) -> Claim | None:
        if self.fail:
            raise ConnectionError("down")
        return self.active


class GateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name)
        self.lock = DispatchLock(self.state_dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def gate(self, authority, env=ON, budget=100_000, now=NOW) -> DispatchGate:
        return DispatchGate(env, authority, self.lock, budget, clock=lambda: now)

    def assertDenied(self, reason: str, fn, *args) -> None:
        with self.assertRaises(GateDenied) as ctx:
            fn(*args)
        self.assertEqual(ctx.exception.reason, reason)


class FlagTests(GateTestCase):
    def test_default_is_off_and_denies(self) -> None:
        c = claim()
        for env in ({}, {GATE_FLAG: ""}, {GATE_FLAG: "true"}, {GATE_FLAG: "1"},
                    {GATE_FLAG: "ENABLED"}, {GATE_FLAG: " enabled"}):
            self.assertDenied("gate_disabled", self.gate(FakeAuthority(c), env).authorize,
                              request_for(c))
        self.assertIsNone(self.lock.holder(REPOSITORY, 74))

    def test_cli_check_is_blocked(self) -> None:
        self.assertEqual(main(["check"]), 2)

    def test_missing_or_failing_authority_denies(self) -> None:
        c = claim()
        self.assertDenied("authority_unavailable", self.gate(None).authorize, request_for(c))
        self.assertDenied("authority_unavailable",
                          self.gate(FakeAuthority(fail=True)).authorize, request_for(c))


class ClaimTests(GateTestCase):
    def test_valid_claim_is_permitted(self) -> None:
        c = claim()
        permit = self.gate(FakeAuthority(c)).authorize(request_for(c))
        self.assertEqual(permit.claim, c)
        self.assertEqual(permit.budget.max_tokens, 100_000)
        self.assertEqual(self.lock.holder(REPOSITORY, 74), "worker-a")

    def test_claim_failures_deny(self) -> None:
        c = claim()
        cases = {
            "no_active_claim": None,
            "claim_bound_to_other_worker": claim("worker-b"),
            "stale_fencing_token": Claim(REPOSITORY, 74, "worker-a", c.claim_id, 2, NOW + 60),
            "lease_expired": claim(expires=NOW),
        }
        for reason, active in cases.items():
            with self.subTest(reason=reason):
                self.assertDenied(reason, self.gate(FakeAuthority(active)).authorize,
                                  request_for(c))

    def test_invalid_requests_deny(self) -> None:
        c = claim()
        base = request_for(c)
        cases = {
            "repository_not_allowed": base.__class__("evil/repo", 74, "worker-a", c.claim_id, 1),
            "invalid_issue": base.__class__(REPOSITORY, 0, "worker-a", c.claim_id, 1),
            "invalid_worker_id": base.__class__(REPOSITORY, 74, "Worker A", c.claim_id, 1),
            "invalid_claim_id": base.__class__(REPOSITORY, 74, "worker-a", "", 1),
            "invalid_fencing_token": base.__class__(REPOSITORY, 74, "worker-a", c.claim_id, True),
        }
        for reason, req in cases.items():
            with self.subTest(reason=reason):
                self.assertDenied(reason, self.gate(FakeAuthority(c)).authorize, req)


class DoubleDispatchTests(GateTestCase):
    def test_second_worker_is_denied_while_lease_valid(self) -> None:
        a = claim("worker-a", 1)
        self.lock.acquire(a, NOW)
        # Authority-Fehler simuliert: liefert einem zweiten Worker einen neuen Claim.
        b = claim("worker-b", 2)
        self.assertDenied("already_dispatched_to_other_worker",
                          self.gate(FakeAuthority(b)).authorize, request_for(b))
        self.assertEqual(self.lock.holder(REPOSITORY, 74), "worker-a")

    def test_same_worker_same_claim_is_idempotent(self) -> None:
        a = claim()
        gate = self.gate(FakeAuthority(a))
        gate.authorize(request_for(a))
        gate.authorize(request_for(a))  # Symphony-Re-Dispatch eines offenen Issues
        self.assertEqual(self.lock.holder(REPOSITORY, 74), "worker-a")

    def test_takeover_after_expiry_needs_higher_fencing(self) -> None:
        self.lock.acquire(claim("worker-a", 5, expires=NOW - 1), NOW - 100)
        self.assertDenied("stale_fencing_token", self.lock.acquire,
                          claim("worker-b", 5), NOW)
        self.assertDenied("stale_fencing_token", self.lock.acquire,
                          claim("worker-b", 4), NOW)
        self.lock.acquire(claim("worker-b", 6), NOW)
        self.assertEqual(self.lock.holder(REPOSITORY, 74), "worker-b")

    def test_release_only_by_holder(self) -> None:
        a = claim("worker-a", 1)
        self.lock.acquire(a, NOW)
        self.assertFalse(self.lock.release(claim("worker-b", 1)))
        self.assertTrue(self.lock.release(a))
        self.assertIsNone(self.lock.holder(REPOSITORY, 74))

    def test_corrupt_state_fails_closed(self) -> None:
        self.state_dir.mkdir(exist_ok=True)
        (self.state_dir / "dispatch-locks.json").write_text("{not json", encoding="utf-8")
        self.assertDenied("lock_state_unreadable", self.lock.acquire, claim(), NOW)

    def test_concurrent_workers_get_exactly_one_dispatch(self) -> None:
        ctx = multiprocessing.get_context("fork")
        results = ctx.Queue()
        procs = [ctx.Process(target=_race, args=(str(self.state_dir), i, results))
                 for i in range(8)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(20)
        outcomes = [results.get(timeout=5) for _ in procs]
        self.assertEqual(outcomes.count("ok"), 1, outcomes)


def _race(state_dir: str, i: int, results) -> None:
    lock = DispatchLock(Path(state_dir))
    c = Claim(REPOSITORY, 74, f"worker-{i}", f"claim-{i}", 1, NOW + 600)
    try:
        lock.acquire(c, NOW)
        results.put("ok")
    except GateDenied as exc:
        results.put(exc.reason)


class TokenBudgetTests(unittest.TestCase):
    def test_missing_or_invalid_budget_blocks_start(self) -> None:
        for value in (None, 0, -1, "1000", 1.5, True, MAX_TOKENS_PER_RUN_CEILING + 1):
            with self.subTest(value=value), self.assertRaises(GateDenied):
                TokenBudget(value)

    def test_gate_without_budget_denies_before_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock = DispatchLock(Path(tmp))
            c = claim()
            gate = DispatchGate(ON, FakeAuthority(c), lock, None, clock=lambda: NOW)
            with self.assertRaises(GateDenied) as ctx:
                gate.authorize(request_for(c))
            self.assertEqual(ctx.exception.reason, "token_budget_missing_or_invalid")
            self.assertIsNone(lock.holder(REPOSITORY, 74))

    def test_hard_limit_is_sticky(self) -> None:
        b = TokenBudget(1_000)
        b.ensure_can_start_turn(400)
        b.record(400)
        b.ensure_can_start_turn(400)
        b.record(400)
        with self.assertRaises(BudgetExceeded):
            b.ensure_can_start_turn(400)  # 800 + 400 > 1000
        self.assertTrue(b.exhausted)
        with self.assertRaises(BudgetExceeded):
            b.ensure_can_start_turn(1)

    def test_approved_budget_is_5m_and_hard_stops_on_reaching(self) -> None:
        self.assertEqual(DEFAULT_MAX_TOKENS_PER_RUN, 5_000_000)
        self.assertEqual(MAX_TOKENS_PER_RUN_CEILING, 5_000_000)
        b = TokenBudget(DEFAULT_MAX_TOKENS_PER_RUN)
        b.record(4_999_999)
        self.assertFalse(b.exhausted)
        with self.assertRaises(BudgetExceeded):
            b.record(1)  # genau 5.000.000 erreicht
        self.assertTrue(b.exhausted)
        self.assertEqual(b.remaining, 0)
        with self.assertRaises(BudgetExceeded):
            b.ensure_can_start_turn(1)

    def test_overrun_stops(self) -> None:
        b = TokenBudget(1_000)
        with self.assertRaises(BudgetExceeded):
            b.record(1_500)
        self.assertEqual(b.remaining, 0)
        with self.assertRaises(BudgetExceeded):
            b.ensure_can_start_turn(1)

    def test_unknown_usage_counts_as_exhausted(self) -> None:
        for usage in (None, -5, "100", 1.0, True):
            b = TokenBudget(1_000)
            with self.subTest(usage=usage), self.assertRaises(BudgetExceeded):
                b.record(usage)
            self.assertTrue(b.exhausted)

    def test_invalid_reserve_stops(self) -> None:
        b = TokenBudget(1_000)
        with self.assertRaises(BudgetExceeded):
            b.ensure_can_start_turn(0)
        self.assertTrue(b.exhausted)


class WorkflowTemplateTests(unittest.TestCase):
    def load(self) -> dict:
        front, body = split_frontmatter(WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn("nicht aktivieren", body)
        return yaml.safe_load(front)

    def test_template_is_valid(self) -> None:
        cfg = self.load()
        self.assertEqual(validate_workflow(cfg), [])
        budget = cfg["gmv"]["token_budget"]
        self.assertEqual(budget["max_tokens_per_run"], DEFAULT_MAX_TOKENS_PER_RUN)
        turns = cfg["agent"]["max_turns"]
        self.assertLessEqual(budget["reserve_per_turn"] * turns, budget["max_tokens_per_run"])
        self.assertEqual(main(["validate-workflow", str(WORKFLOW)]), 0)

    def test_prompt_is_patch_and_report_only(self) -> None:
        _, body = split_frontmatter(WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn("nur ein Patch und ein Bericht", body)
        self.assertIn("Commit, Push und\n   Pull Request macht ein Mensch", body)

    def test_clone_hook_has_no_credentials(self) -> None:
        hook = self.load()["hooks"]["after_create"]
        self.assertIn("https://github.com/tiktokagentur-art/gmv-foundation.git .", hook)
        for bad in ("TOKEN", "@github.com", "git push"):
            self.assertNotIn(bad, hook)
        self.assertNotIn("before_run", self.load()["hooks"])  # Phase B noch nicht aktiv

    def test_violations_are_detected(self) -> None:
        base = self.load()
        mutations = {
            "no hook": lambda c: c["hooks"].pop("after_create"),
            "token in hook": lambda c: c["hooks"].__setitem__(
                "after_create",
                "set -eu\ngit clone --depth 1 --single-branch --no-tags "
                "https://x-access-token:$GITHUB_TOKEN@github.com/"
                "tiktokagentur-art/gmv-foundation.git ."),
            "other repo": lambda c: c["hooks"].__setitem__(
                "after_create", c["hooks"]["after_create"].replace("gmv-foundation", "other")),
            "no set -eu": lambda c: c["hooks"].__setitem__(
                "after_create", c["hooks"]["after_create"].replace("set -eu", "true")),
            "no timeout": lambda c: c["hooks"].pop("timeout_ms"),
            "gate enabled": lambda c: c["gmv"]["dispatch_gate"].__setitem__("enabled", True),
            "no budget": lambda c: c["gmv"]["token_budget"].pop("max_tokens_per_run"),
            "budget too high": lambda c: c["gmv"]["token_budget"].__setitem__(
                "max_tokens_per_run", MAX_TOKENS_PER_RUN_CEILING + 1),
            "budget continue": lambda c: c["gmv"]["token_budget"].__setitem__(
                "on_exceeded", "warn"),
            "two agents": lambda c: c["agent"].__setitem__("max_concurrent_agents", 2),
            "danger sandbox": lambda c: c["codex"].__setitem__(
                "thread_sandbox", "danger-full-access"),
            "no turn policy": lambda c: c["codex"].pop("turn_sandbox_policy"),
            "network on": lambda c: c["codex"]["turn_sandbox_policy"].__setitem__(
                "networkAccess", True),
            "tmp writable": lambda c: c["codex"]["turn_sandbox_policy"].__setitem__(
                "excludeSlashTmp", False),
            "extra root": lambda c: c["codex"]["turn_sandbox_policy"].__setitem__(
                "writableRoots", ["/workspace"]),
            "auto approve": lambda c: c["codex"].__setitem__("approval_policy", "never"),
            "no proxy": lambda c: c["codex"].__setitem__(
                "command", c["codex"]["command"].replace("features.network_proxy=true", "")),
            "extra domain": lambda c: c["codex"].__setitem__(
                "command", c["codex"]["command"].replace(
                    '"api.openai.com"="allow"', '"api.openai.com"="allow","pypi.org"="allow"')),
            "wildcard": lambda c: c["codex"].__setitem__(
                "command", c["codex"]["command"].replace('"github.com"', '"*.github.com"')),
            "danger flag": lambda c: c["codex"].__setitem__(
                "command", c["codex"]["command"].replace(
                    "app-server", "--dangerously-bypass-approvals-and-sandbox app-server")),
            "workspace in tmp": lambda c: c["workspace"].__setitem__("root", "/tmp/ws"),
            "local binding without upstream": lambda c: c["codex"].__setitem__(
                "command", c["codex"]["command"].replace(
                    "HTTPS_PROXY=http://127.0.0.1:18443 ", "")),
            "no_proxy widened": lambda c: c["codex"].__setitem__(
                "command", c["codex"]["command"].replace(
                    "NO_PROXY=chatgpt.com", "NO_PROXY=pypi.org,chatgpt.com")),
            "foreign proxy": lambda c: c["codex"].__setitem__(
                "command", c["codex"]["command"].replace(
                    "HTTP_PROXY=http://127.0.0.1:18443", "HTTP_PROXY=http://10.0.0.5:3128")),
            "download host": lambda c: c["codex"].__setitem__(
                "command", c["codex"]["command"].replace(
                    '"api.openai.com"="allow"',
                    '"api.openai.com"="allow","codeload.github.com"="allow"')),
            "reserve too high": lambda c: c["gmv"]["token_budget"].__setitem__(
                "reserve_per_turn", 900_000),
            "no max_concurrent": lambda c: c["gmv"]["dispatch_gate"].pop("max_concurrent"),
            "max_concurrent 0": lambda c: c["gmv"]["dispatch_gate"].__setitem__(
                "max_concurrent", 0),
            "max_concurrent 11": lambda c: c["gmv"]["dispatch_gate"].__setitem__(
                "max_concurrent", 11),
            "max_concurrent bool": lambda c: c["gmv"]["dispatch_gate"].__setitem__(
                "max_concurrent", True),
            "agents 3 per process": lambda c: (
                c["gmv"]["dispatch_gate"].__setitem__("max_concurrent", 3),
                c["agent"].__setitem__("max_concurrent_agents", 3)),
            "literal token": lambda c: c["tracker"]["provider"].__setitem__("token", "abc"),
        }
        for name, mutate in mutations.items():
            cfg = copy.deepcopy(base)
            mutate(cfg)
            with self.subTest(name=name):
                self.assertNotEqual(validate_workflow(cfg), [])


def _once_worker(once_dir: str, issue: int, barrier, results) -> None:
    barrier.wait()
    try:
        acquire_issue_once(Path(once_dir), issue)
        results.put("won")
    except GateDenied as exc:
        results.put(exc.reason)


def _slot_worker(slot_dir: str, lock: str, issue: int, pid: int, barrier, results) -> None:
    barrier.wait()
    slots = SharedSlots(Path(slot_dir), Path(lock), pid_alive=lambda _pid: True)
    try:
        slots.acquire(issue, pid, max_symphony=MAX_CONCURRENT_RUNS_CEILING)
        results.put("won")
    except GateDenied as exc:
        results.put(exc.reason)


class SharedSlotTests(unittest.TestCase):
    """Gemeinsamer Zähler Codex (research.sh) + Symphony, max. 10."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.slot_dir = base / "state" / "slots"
        self.lock = base / ".research.lock"
        self.dead: set[int] = set()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def slots(self, max_total: int = MAX_CONCURRENT_RUNS_CEILING) -> SharedSlots:
        return SharedSlots(self.slot_dir, self.lock, max_total,
                           pid_alive=lambda pid: pid not in self.dead)

    def research_slot(self, pid: int) -> None:
        # Format wie research.sh: "pid=<pid> reserved=<n> id=<id> dayfile=<pfad>"
        self.slot_dir.mkdir(parents=True, exist_ok=True)
        (self.slot_dir / str(pid)).write_text(
            f"pid={pid} reserved=500000 id=20261124-x dayfile=/x/tokens.txt\n",
            encoding="utf-8")

    def test_ceiling_is_10_and_only_lowerable(self) -> None:
        self.assertEqual(MAX_CONCURRENT_RUNS_CEILING, 10)
        for bad in (0, 11, True, "10"):
            with self.subTest(bad=bad), self.assertRaises(GateDenied):
                SharedSlots(self.slot_dir, self.lock, bad)

    def test_up_to_10_symphony_runs_then_denied(self) -> None:
        s = self.slots()
        for i in range(1, 11):
            s.acquire(100 + i, 1000 + i, max_symphony=10)
        self.assertEqual(s.count(), (10, 10))
        with self.assertRaises(GateDenied) as ctx:
            s.acquire(200, 2000, max_symphony=10)
        self.assertEqual(ctx.exception.reason, "shared_limit_reached")

    def test_research_and_symphony_share_the_counter(self) -> None:
        for pid in range(500, 507):
            self.research_slot(pid)  # 7 Codex-Recherchen laufen
        s = self.slots()
        for i in range(3):
            s.acquire(10 + i, 900 + i, max_symphony=10)
        with self.assertRaises(GateDenied) as ctx:
            s.acquire(20, 999, max_symphony=10)
        self.assertEqual(ctx.exception.reason, "shared_limit_reached")
        self.assertEqual(s.count(), (10, 3))

    def test_symphony_share_limited_by_max_concurrent(self) -> None:
        s = self.slots()
        s.acquire(1, 11, max_symphony=1)
        with self.assertRaises(GateDenied) as ctx:
            s.acquire(2, 12, max_symphony=1)
        self.assertEqual(ctx.exception.reason, "symphony_limit_reached")
        for bad in (0, 11):
            with self.subTest(bad=bad), self.assertRaises(GateDenied):
                s.acquire(3, 13, max_symphony=bad)

    def test_same_issue_never_twice(self) -> None:
        s = self.slots()
        s.acquire(7, 70, max_symphony=10)
        with self.assertRaises(GateDenied) as ctx:
            s.acquire(7, 71, max_symphony=10)
        self.assertEqual(ctx.exception.reason, "issue_already_running")

    def test_slot_file_format_is_research_compatible(self) -> None:
        path = self.slots().acquire(7, 4242, max_symphony=1)
        self.assertEqual(path, self.slot_dir / "4242")
        text = path.read_text(encoding="utf-8")
        self.assertRegex(text, r"^pid=4242 reserved=0 id=symphony-issue-7 ")
        self.assertIn("kind=symphony issue=7", text)
        self.assertNotIn("dayfile=", text)  # kein Anteil am Codex-Tagesbudget
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_release_and_stale_cleanup(self) -> None:
        s = self.slots()
        s.acquire(1, 31, max_symphony=10)
        s.acquire(2, 32, max_symphony=10)
        self.research_slot(33)
        self.assertFalse(s.release(2, 31))  # fremdes Issue: nichts löschen
        self.assertTrue(s.release(1, 31))
        self.dead.update({32, 33})
        self.assertEqual(s.count(), (0, 0))
        self.assertFalse((self.slot_dir / "32").exists())  # tote Symphony-Slots weg
        self.assertTrue((self.slot_dir / "33").exists())  # Codex-Slot räumt research.sh

    def test_lock_timeout_is_fail_closed(self) -> None:
        import fcntl
        import os

        import symphony_dispatch_gate as gate_mod

        self.lock.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.lock, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        old = gate_mod.SLOT_LOCK_TIMEOUT
        try:
            gate_mod.SLOT_LOCK_TIMEOUT = 0.2
            with self.assertRaises(GateDenied) as ctx:
                with gate_mod._flock(self.lock, gate_mod.SLOT_LOCK_TIMEOUT):
                    pass
            self.assertEqual(ctx.exception.reason, "slot_lock_timeout")
        finally:
            gate_mod.SLOT_LOCK_TIMEOUT = old
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def test_concurrent_acquire_respects_limit(self) -> None:
        ctx = multiprocessing.get_context("fork")
        barrier, results = ctx.Barrier(15), ctx.Queue()
        procs = [ctx.Process(target=_slot_worker, args=(
            str(self.slot_dir), str(self.lock), 300 + i, 3000 + i, barrier, results))
            for i in range(15)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(30)
        outcomes = [results.get(timeout=5) for _ in procs]
        self.assertEqual(outcomes.count("won"), 10)
        self.assertEqual(outcomes.count("shared_limit_reached"), 5)
        self.assertEqual(len(list(self.slot_dir.iterdir())), 10)

    def test_concurrent_same_issue_has_one_winner(self) -> None:
        ctx = multiprocessing.get_context("fork")
        barrier, results = ctx.Barrier(8), ctx.Queue()
        procs = [ctx.Process(target=_slot_worker, args=(
            str(self.slot_dir), str(self.lock), 77, 7000 + i, barrier, results))
            for i in range(8)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(30)
        outcomes = [results.get(timeout=5) for _ in procs]
        self.assertEqual(outcomes.count("won"), 1)
        self.assertEqual(outcomes.count("issue_already_running"), 7)


class IssueOnceTests(unittest.TestCase):
    def test_once_per_issue_not_global(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            acquire_issue_once(Path(tmp), 5)
            acquire_issue_once(Path(tmp), 6)  # anderes Issue: erlaubt
            with self.assertRaises(GateDenied) as ctx:
                acquire_issue_once(Path(tmp), 5)
            self.assertEqual(ctx.exception.reason, "issue_already_started")
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),
                             ["issue-5.once", "issue-6.once"])

    def test_invalid_issue_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for bad in (0, -1, True, "5"):
                with self.subTest(bad=bad), self.assertRaises(GateDenied):
                    acquire_issue_once(Path(tmp), bad)

    def test_race_has_exactly_one_winner(self) -> None:
        ctx = multiprocessing.get_context("fork")
        with tempfile.TemporaryDirectory() as tmp:
            barrier, results = ctx.Barrier(12), ctx.Queue()
            procs = [ctx.Process(target=_once_worker, args=(tmp, 88, barrier, results))
                     for _ in range(12)]
            for p in procs:
                p.start()
            for p in procs:
                p.join(30)
            outcomes = [results.get(timeout=5) for _ in procs]
        self.assertEqual(outcomes.count("won"), 1)
        self.assertEqual(outcomes.count("issue_already_started"), 11)


class MaxConcurrentTests(unittest.TestCase):
    @staticmethod
    def wf(block: str) -> str:
        return f"---\nagent:\n  max_concurrent_agents: 1\ngmv:\n{block}---\nbody\n"

    def test_reads_values_1_to_10(self) -> None:
        for n in range(1, 11):
            text = self.wf(f"  dispatch_gate:\n    enabled: false\n    max_concurrent: {n}\n")
            self.assertEqual(read_max_concurrent(text), n)

    def test_missing_defaults_to_1_invalid_denied(self) -> None:
        self.assertEqual(read_max_concurrent(self.wf("  dispatch_gate:\n    enabled: false\n")), 1)
        for bad in ("0", "11", "abc", "2.5", "-1"):
            text = self.wf(f"  dispatch_gate:\n    max_concurrent: {bad}\n")
            with self.subTest(bad=bad), self.assertRaises(GateDenied):
                read_max_concurrent(text)

    def test_ignores_other_blocks(self) -> None:
        text = ("---\nagent:\n  max_concurrent: 9\ngmv:\n  token_budget:\n"
                "    max_concurrent: 8\n  dispatch_gate:\n    max_concurrent: 2 # Kommentar\n"
                "---\n")
        self.assertEqual(read_max_concurrent(text), 2)

    def test_matches_yaml_on_template(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        cfg = yaml.safe_load(split_frontmatter(text)[0])
        self.assertEqual(read_max_concurrent(text), cfg["gmv"]["dispatch_gate"]["max_concurrent"])

    def test_template_is_consistent_and_gate_off(self) -> None:
        cfg = yaml.safe_load(split_frontmatter(WORKFLOW.read_text(encoding="utf-8"))[0])
        self.assertIs(cfg["gmv"]["dispatch_gate"]["enabled"], False)
        self.assertEqual(cfg["agent"]["max_concurrent_agents"], 1)
        self.assertLessEqual(cfg["gmv"]["dispatch_gate"]["max_concurrent"], 10)
        for n in (1, 3, 10):
            cfg["gmv"]["dispatch_gate"]["max_concurrent"] = n
            with self.subTest(n=n):
                self.assertEqual(validate_workflow(cfg), [])


class QuotaFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        import symphony_dispatch_gate as gate_mod

        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.env: dict[str, str] = {}
        # Pfade sind fest verdrahtet: Tests patchen die Konstanten, nicht die Umgebung.
        self._patches = [
            mock.patch.object(gate_mod, "DEFAULT_SHARED_SLOT_DIR", self.base / "slots"),
            mock.patch.object(gate_mod, "DEFAULT_SHARED_SLOT_LOCK", self.base / ".research.lock"),
            mock.patch.object(gate_mod, "DEFAULT_ALERTS_LOG", self.base / "ALERTS.log"),
            mock.patch.object(gate_mod, "DEFAULT_QUOTA_STOP", self.base / "state" / "quota-stop"),
            mock.patch.object(gate_mod, "DEFAULT_RUN_STOP", self.base / "state" / "symphony-stop"),
        ]
        for patch in self._patches:
            patch.start()

    def tearDown(self) -> None:
        for patch in self._patches:
            patch.stop()
        self._tmp.cleanup()

    def run_main(self, *argv: str) -> int:
        clean = {k: v for k, v in os.environ.items() if not k.startswith("GMV_")}
        with mock.patch.dict("os.environ", {**clean, **self.env}, clear=True):
            return main(list(argv))

    def test_classifier(self) -> None:
        cases = {
            "error: usage_limit_reached for plan": "quota_exhausted",
            '{"code":"insufficient_quota"}': "quota_exhausted",
            "HTTP 429 Too Many Requests": "rate_limited",
            "rate_limit_exceeded": "rate_limited",
            "status: 401": "auth_failed",
            "refresh_token_expired": "auth_failed",
            "Please log in again with codex login": "auth_failed",
            "failed to persist auth.json: Read-only file system (os error 30)":
                "auth_refresh_blocked",
        }
        for text, code in cases.items():
            with self.subTest(text=text):
                self.assertEqual(classify_quota_failure(text), code)
        # Normale Dashboard-/Logzeilen eines grünen Laufs lösen nichts aus.
        for ok in ("Rate Limits", "rate limits updated", "Tokens: in 1,401 | out 429 | total 1,830",
                   "child_exited code=0", "NET https://api.openai.com/v1/models -> 200"):
            with self.subTest(ok=ok):
                self.assertIsNone(classify_quota_failure(ok))

    def test_scan_hit_writes_alert_and_marker_then_blocks(self) -> None:
        log = self.base / "run.out"
        log.write_text("... usage_limit_reached ...\n", encoding="utf-8")
        self.assertEqual(self.run_main("quota-check"), 0)
        self.assertEqual(self.run_main("quota-scan", "--issue", "12", str(log)),
                         RC_QUOTA_FAIL_CLOSED)
        alerts = (self.base / "ALERTS.log").read_text(encoding="utf-8")
        self.assertIn("ALERT symphony issue=12 quota_fail_closed reason=quota_exhausted", alerts)
        self.assertNotIn("usage_limit_reached ...", alerts)  # keine Log-Inhalte
        self.assertEqual((self.base / "ALERTS.log").stat().st_mode & 0o777, 0o600)
        # kein Retry-Sturm: jeder weitere Start bleibt gesperrt, bis ein Mensch eingreift
        for _ in range(3):
            self.assertEqual(self.run_main("quota-check"), RC_QUOTA_FAIL_CLOSED)

    def test_clean_scan_and_missing_files_pass(self) -> None:
        log = self.base / "run.out"
        log.write_text("Rate Limits\nAgent task finished\n", encoding="utf-8")
        self.assertEqual(self.run_main("quota-scan", "--issue", "12", str(log),
                                       str(self.base / "missing.log")), 0)
        self.assertFalse((self.base / "ALERTS.log").exists())
        self.assertEqual(self.run_main("quota-check"), 0)

    def test_cli_slot_cycle_and_limits(self) -> None:
        wf = self.base / "WORKFLOW.md"
        wf.write_text("---\ngmv:\n  dispatch_gate:\n    max_concurrent: 1\n---\n",
                      encoding="utf-8")
        me = str(os.getpid())
        self.assertEqual(self.run_main("slot-acquire", "--issue", "5", "--pid", me,
                                       "--workflow", str(wf)), 0)
        self.assertEqual(self.run_main("slot-acquire", "--issue", "6", "--pid", "1",
                                       "--workflow", str(wf)), RC_NO_SLOT)
        self.assertEqual(self.run_main("slot-release", "--issue", "5", "--pid", me), 0)
        self.assertEqual(list((self.base / "slots").iterdir()), [])
        self.env["GMV_MAX_TOTAL_RUNS"] = "11"  # darf nur senken
        self.assertEqual(self.run_main("slot-acquire", "--issue", "5", "--pid", me,
                                       "--workflow", str(wf)), 2)

    def test_path_overrides_rejected_unless_identical(self) -> None:
        import symphony_dispatch_gate as gate_mod

        for var in gate_mod.PATH_ENV_VARS.values():
            with self.subTest(var=var):
                with self.assertRaises(GateDenied) as ctx:
                    host_paths({var: "/tmp/elsewhere"})
                self.assertEqual(ctx.exception.reason, "path_override_forbidden")
                self.env = {var: "/tmp/elsewhere"}
                self.assertEqual(self.run_main("quota-check"), 2)
        self.env = {}
        same = {"GMV_SHARED_SLOT_DIR": str(self.base / "slots")}
        self.assertEqual(host_paths(same)["slot_dir"], self.base / "slots")

    def test_shipped_paths_are_the_research_host_paths(self) -> None:
        src = (ROOT / "scripts" / "symphony_dispatch_gate.py").read_text(encoding="utf-8")
        for line in ('DEFAULT_SHARED_SLOT_DIR = Path("/workspace/research/state/slots")',
                     'DEFAULT_SHARED_SLOT_LOCK = Path("/workspace/research/.research.lock")',
                     'DEFAULT_ALERTS_LOG = Path("/workspace/research/ALERTS.log")',
                     'DEFAULT_QUOTA_STOP = Path("/workspace/research/state/quota-stop")',
                     'DEFAULT_RUN_STOP = Path("/workspace/research/state/symphony-stop")'):
            self.assertIn(line, src)

    def test_max_total_env_only_lowers(self) -> None:
        wf = self.base / "WORKFLOW.md"
        wf.write_text("---\ngmv:\n  dispatch_gate:\n    max_concurrent: 10\n---\n",
                      encoding="utf-8")
        for bad in ("11", "0", "-1", "abc", ""):
            self.env = {"GMV_MAX_TOTAL_RUNS": bad}
            with self.subTest(bad=bad):
                self.assertEqual(self.run_main("slot-acquire", "--issue", "5", "--pid",
                                               str(os.getpid()), "--workflow", str(wf)), 2)
        self.env = {"GMV_MAX_TOTAL_RUNS": "2"}
        for issue, pid in (("5", os.getpid()), ("6", os.getppid())):
            self.assertEqual(self.run_main("slot-acquire", "--issue", issue, "--pid", str(pid),
                                           "--workflow", str(wf)), 0)
        self.assertEqual(self.run_main("slot-acquire", "--issue", "7", "--pid", "1",
                                       "--workflow", str(wf)), RC_NO_SLOT)


class RunVerdictTests(unittest.TestCase):
    def log(self, *events: dict) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", delete=False, suffix=".log", encoding="utf-8")
        with tmp:
            tmp.write("Python noise line\n")
            for e in events:
                tmp.write(json.dumps(e) + "\n")
        self.addCleanup(os.unlink, tmp.name)
        return Path(tmp.name)

    @staticmethod
    def stop(reason: str) -> dict:
        return {"watchdog": "stop", "reason": reason}

    CLEAN = {"watchdog": "terminated", "clean": True}

    def test_known_stops_pass(self) -> None:
        for reason, rc in (("first_run_finished", 0), ("child_exited code=0", 0),
                           ("retry_cycle_scheduled", 1), ("second_dispatch issue=5", 1),
                           ("second_issue issue=6 first=5", 1), ("max_runtime", 1),
                           ("token_budget_reached total=4700001 stop_at=4700000", 1),
                           ("loop_sessions sessions=4 max=3", 1)):
            with self.subTest(reason=reason):
                self.assertIsNone(run_verdict(rc, self.log(self.stop(reason), self.CLEAN)))

    def test_unclear_outcomes_fail_closed(self) -> None:
        cases = {
            "exit_rc_unexpected": (3, [self.stop("first_run_finished"), self.CLEAN]),
            "no_watchdog_verdict": (1, []),
            "unknown_stop_reason": (1, [self.stop("token_readout_missing"), self.CLEAN]),
            "unknown_stop_reason ": (1, [self.stop("child_exited code=-9"), self.CLEAN]),
            "unclean_termination": (1, [self.stop("max_runtime"),
                                        {"watchdog": "terminated", "clean": False}]),
        }
        for code, (rc, events) in cases.items():
            with self.subTest(code=code):
                self.assertEqual(run_verdict(rc, self.log(*events)), code.strip())
        self.assertEqual(run_verdict(1, None), "no_watchdog_verdict")
        self.assertEqual(run_verdict(99, None), "exit_rc_unexpected")
        two = self.log(self.stop("max_runtime"), self.stop("first_run_finished"), self.CLEAN)
        self.assertEqual(run_verdict(1, two), "no_watchdog_verdict")


class ManualReleaseTests(QuotaFailClosedTests):
    """Sperren nur manuell und protokolliert freigeben: wer, wann, warum."""

    def paths(self) -> dict:
        return host_paths({})

    def test_run_verdict_cli_sets_marker_and_blocks(self) -> None:
        self.assertEqual(self.run_main("run-verdict", "--issue", "8", "--rc", "99"),
                         RC_UNKNOWN_FAIL_CLOSED)
        self.assertIn("issue=8 unknown_fail_closed reason=exit_rc_unexpected",
                      (self.base / "ALERTS.log").read_text(encoding="utf-8"))
        self.assertEqual(self.run_main("quota-check"), RC_UNKNOWN_FAIL_CLOSED)

    def test_release_requires_who_and_why_and_logs_it(self) -> None:
        self.run_main("run-verdict", "--issue", "8", "--rc", "99")
        marker = self.base / "state" / "symphony-stop"
        for by, why in (("", "Ursache geklärt, Login erneuert"), ("Samira", "kurz"),
                        ("x", "Ursache geklärt, Login erneuert"),
                        ("Samira", "Zeile1\nZeile2 mit genug Text")):
            with self.subTest(by=by, why=why), self.assertRaises(GateDenied):
                release_lock("run-stop", by, why, self.paths())
            self.assertTrue(marker.exists())
        archived = release_lock("run-stop", "Samira Nouri", "Watchdog-Log geprüft, Ursache: Proxy",
                                self.paths())
        self.assertFalse(marker.exists())
        self.assertTrue(archived.exists())  # archiviert, nicht gelöscht
        alerts = (self.base / "ALERTS.log").read_text(encoding="utf-8")
        self.assertRegex(alerts, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} .*RELEASE kind=run-stop "
                                 r"by='Samira Nouri' reason='Watchdog-Log geprüft, Ursache: Proxy'")
        self.assertEqual(self.run_main("quota-check"), 0)
        with self.assertRaises(GateDenied) as ctx:
            release_lock("run-stop", "Samira Nouri", "nochmal freigeben bitte", self.paths())
        self.assertEqual(ctx.exception.reason, "release_nothing_locked")

    def test_release_once_per_issue_only_when_not_running(self) -> None:
        once_dir = self.base / "once"
        acquire_issue_once(once_dir, 9)
        acquire_issue_once(once_dir, 10)
        slots = SharedSlots(self.base / "slots", self.base / ".research.lock",
                            pid_alive=lambda _pid: True)
        slots.acquire(9, os.getpid(), max_symphony=10)  # lebender Prozess
        with self.assertRaises(GateDenied) as ctx:
            release_lock("once", "Deniz Kaya", "Fehlstart nach Token-Fehler", self.paths(),
                         issue=9, once_dir=once_dir)
        self.assertEqual(ctx.exception.reason, "issue_still_running")
        self.assertEqual(self.run_main(
            "release", "--kind", "once", "--issue", "10", "--dir", str(once_dir),
            "--by", "Deniz Kaya", "--reason", "Fehlstart nach Proxy-Fehler, neues Go von Aline"), 0)
        self.assertFalse((once_dir / "issue-10.once").exists())
        self.assertTrue((once_dir / "issue-9.once").exists())
        self.assertIn("RELEASE kind=once issue=10 by='Deniz Kaya'",
                      (self.base / "ALERTS.log").read_text(encoding="utf-8"))
        acquire_issue_once(once_dir, 10)  # erst danach wieder startbar
        self.assertEqual(self.run_main("release", "--kind", "once", "--issue", "10", "--dir",
                                       str(once_dir), "--by", "Deniz Kaya", "--reason", "x"), 2)


class OperatorRuleDocsTests(unittest.TestCase):
    def test_docs_state_manual_logged_release_and_fail_closed(self) -> None:
        for name in ("dispatch-gate.md", "quota-refresh.md"):
            text = (ROOT / "docs" / "symphony" / name).read_text(encoding="utf-8")
            with self.subTest(doc=name):
                for needed in ("release --kind", "ALERTS.log", "rc=13", "symphony-stop",
                               "neues Go", "box"):
                    self.assertIn(needed, text)
                self.assertRegex(text, r"(?i)manuell")
                self.assertRegex(text, r"(?i)protokolliert")


class IssueIsolationTests(unittest.TestCase):
    """Samira, Bedingungen 1 und 2: eigene WORKFLOW je Issue, Proxy-Stopp nur ohne Slot."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_rendered_workflow_routes_only_own_issue_and_stays_valid(self) -> None:
        import symphony_dispatch_gate as gate

        text = WORKFLOW.read_text(encoding="utf-8")
        run_dir = Path("/workspace/symphony-pilot/runs/issue-7")  # nur Text, kein Schreiben
        rendered = gate.render_issue_workflow(text, 7, run_dir)
        orig = yaml.safe_load(gate.split_frontmatter(text)[0])
        new = yaml.safe_load(gate.split_frontmatter(rendered)[0])
        self.assertEqual(new["tracker"]["required_labels"],
                         ["gmv-symphony-pilot", "gmv-symphony-issue-7"])
        self.assertEqual(new["workspace"]["root"], str(run_dir / "workspaces"))
        self.assertEqual(gate.validate_workflow(new), [])
        self.assertEqual(new["gmv"]["dispatch_gate"], orig["gmv"]["dispatch_gate"])
        for key in set(orig) - {"tracker", "workspace"}:
            self.assertEqual(new[key], orig[key], key)
        self.assertEqual(gate.split_frontmatter(rendered)[1], gate.split_frontmatter(text)[1])
        # Vorlage bleibt bei max_concurrent 1 und Gate aus
        self.assertEqual(orig["gmv"]["dispatch_gate"]["max_concurrent"], 1)
        self.assertIs(orig["gmv"]["dispatch_gate"]["enabled"], False)

    def test_render_is_fail_closed_on_unexpected_structure(self) -> None:
        import symphony_dispatch_gate as gate

        text = WORKFLOW.read_text(encoding="utf-8")
        bad = [
            text.replace("  required_labels:\n    - gmv-symphony-pilot\n", ""),
            text.replace("    - gmv-symphony-pilot\n", "    - gmv-symphony-issue-3\n"),
            text.replace("workspace:\n", "workspace_x:\n"),
            text.replace("  root: ~/gmv-symphony/workspaces\n",
                         "  root: a\n  root: b\n"),
        ]
        for variant in bad:
            self.assertNotEqual(variant, text)
            with self.subTest(variant=variant[:0]), self.assertRaises(gate.GateDenied):
                gate.render_issue_workflow(variant, 3, self.base)

    def test_prepare_run_dir_is_exclusive_and_private(self) -> None:
        import symphony_dispatch_gate as gate

        runs = self.base / "runs"
        run_dir = gate.prepare_run_dir(runs, 8, WORKFLOW)
        self.assertEqual(run_dir, runs / "issue-8")
        self.assertEqual(run_dir.stat().st_mode & 0o777, 0o700)
        self.assertEqual((run_dir / "WORKFLOW.md").stat().st_mode & 0o777, 0o600)
        self.assertTrue((run_dir / "workspaces").is_dir())
        self.assertTrue((run_dir / "log").is_dir())
        with self.assertRaises(gate.GateDenied) as ctx:
            gate.prepare_run_dir(runs, 8, WORKFLOW)
        self.assertEqual(ctx.exception.reason, "run_dir_exists")
        other = gate.prepare_run_dir(runs, 9, WORKFLOW)
        self.assertNotEqual(other, run_dir)

    def test_prepare_run_dir_leaves_nothing_on_bad_workflow_and_rejects_symlink(self) -> None:
        import symphony_dispatch_gate as gate

        runs = self.base / "runs"
        bad = self.base / "bad.md"
        bad.write_text(WORKFLOW.read_text(encoding="utf-8").replace("workspace:\n", "ws:\n"),
                       encoding="utf-8")
        with self.assertRaises(gate.GateDenied) as ctx:
            gate.prepare_run_dir(runs, 4, bad)
        self.assertEqual(ctx.exception.reason, "workflow_structure_unexpected")
        self.assertFalse(runs.exists())
        target = self.base / "elsewhere"
        target.mkdir()
        runs.symlink_to(target)
        with self.assertRaises(gate.GateDenied) as ctx:
            gate.prepare_run_dir(runs, 4, WORKFLOW)
        self.assertEqual(ctx.exception.reason, "runs_dir_symlink")
        self.assertEqual(list(target.iterdir()), [])

    def _proxy(self) -> tuple[Path, Path]:
        calls = self.base / "calls"
        script = self.base / "proxy.sh"
        script.write_text(f'#!/bin/sh\necho "$1" >> {calls}\n', encoding="utf-8")
        script.chmod(0o755)
        return script, calls

    def test_proxy_stop_if_idle(self) -> None:
        import subprocess

        import symphony_dispatch_gate as gate

        slots = gate.SharedSlots(self.base / "slots", self.base / ".lock")
        script, calls = self._proxy()
        alerts = self.base / "ALERTS.log"
        child = subprocess.Popen(["sleep", "60"])
        try:
            (self.base / "slots").mkdir()
            (self.base / "slots" / str(child.pid)).write_text(
                f"pid={child.pid} reserved=0 id=symphony-issue-5 kind=symphony issue=5\n",
                encoding="utf-8")
            self.assertEqual(gate.proxy_stop_if_idle(slots, script, alerts, 6), 14)
            self.assertFalse(calls.exists())
            self.assertIn("issue=6 proxy_stop_refused live_symphony_slots=1 issues=5",
                          alerts.read_text(encoding="utf-8"))
        finally:
            child.kill()
            child.wait()
        # Slot tot: Proxy wird gestoppt
        self.assertEqual(gate.proxy_stop_if_idle(slots, script, alerts, 6), 0)
        self.assertEqual(calls.read_text(encoding="utf-8"), "stop\n")
        self.assertEqual(gate.proxy_start(slots, script), 0)
        self.assertEqual(calls.read_text(encoding="utf-8"), "stop\nstart\n")

    def test_alert_appends_are_locked_and_line_atomic(self) -> None:
        import symphony_dispatch_gate as gate

        alerts = self.base / "ALERTS.log"
        procs = [multiprocessing.Process(target=_alert_burst, args=(str(alerts), i))
                 for i in range(4)]
        for proc in procs:
            proc.start()
        for proc in procs:
            proc.join(30)
        lines = alerts.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 200)
        self.assertTrue(all(ln.endswith(" ALERT test") for ln in lines))
        self.assertTrue(callable(gate._append_alert))


def _alert_burst(path: str, _i: int) -> None:
    import symphony_dispatch_gate as gate

    for _ in range(50):
        gate._append_alert(Path(path), "ALERT test")


if __name__ == "__main__":
    unittest.main()
