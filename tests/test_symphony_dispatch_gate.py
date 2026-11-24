"""Negative tests for the draft Symphony dispatch gate (ENG-003, issue #74)."""

from __future__ import annotations

import copy
import multiprocessing
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from symphony_dispatch_gate import (  # noqa: E402
    DEFAULT_MAX_TOKENS_PER_RUN,
    GATE_FLAG,
    MAX_TOKENS_PER_RUN_CEILING,
    REPOSITORY,
    BudgetExceeded,
    Claim,
    DispatchGate,
    DispatchLock,
    DispatchRequest,
    GateDenied,
    TokenBudget,
    main,
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

    def test_approved_budget_is_2m_and_hard_stops_on_reaching(self) -> None:
        self.assertEqual(DEFAULT_MAX_TOKENS_PER_RUN, 2_000_000)
        self.assertEqual(MAX_TOKENS_PER_RUN_CEILING, 2_000_000)
        b = TokenBudget(DEFAULT_MAX_TOKENS_PER_RUN)
        b.record(1_999_999)
        self.assertFalse(b.exhausted)
        with self.assertRaises(BudgetExceeded):
            b.record(1)  # genau 2.000.000 erreicht
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
                "reserve_per_turn", 400_000),
            "literal token": lambda c: c["tracker"]["provider"].__setitem__("token", "abc"),
        }
        for name, mutate in mutations.items():
            cfg = copy.deepcopy(base)
            mutate(cfg)
            with self.subTest(name=name):
                self.assertNotEqual(validate_workflow(cfg), [])


if __name__ == "__main__":
    unittest.main()
