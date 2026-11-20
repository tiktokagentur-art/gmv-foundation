"""Offline negative tests for Aline's bounded manual greeting gate."""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from aline_hello_once import (  # noqa: E402
    MAX_NEW_DISPATCHES,
    GateError,
    validate_bounded_dispatch,
    validate_identity,
    safe_rate_limit_code,
)

FIRST = 44694430741
SECOND = 44697167267
THIRD = 44705555401
CURRENT = 44710000001
ACTOR = {"login": "tiktokagentur-art", "id": 354272348}


def good_env(run_id=CURRENT):
    return {
        "GITHUB_REPOSITORY": "tiktokagentur-art/gmv-foundation",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_ACTOR": "tiktokagentur-art",
        "GITHUB_ACTOR_ID": "354272348",
        "GITHUB_TRIGGERING_ACTOR": "tiktokagentur-art",
        "GITHUB_RUN_ID": str(run_id),
    }


def entry(run_id, sha="c" * 40, status="completed", conclusion="success"):
    return dict(id=run_id, event="workflow_dispatch", head_branch="main",
                head_sha=sha, status=status, conclusion=conclusion,
                run_attempt=1, actor=dict(ACTOR))


def history(new=None, third_conclusion="cancelled"):
    if new is None:
        new = [entry(CURRENT, status="in_progress", conclusion=None)]
    base = [
        entry(FIRST, "71557145872ca31862e1bd617bc6eeb01f7d5826",
              conclusion="failure"),
        entry(SECOND, "eb96d7c714e5557e5c4caeef2e1870faf44c95a7",
              conclusion="failure"),
        entry(THIRD, "eb96d7c714e5557e5c4caeef2e1870faf44c95a7",
              conclusion=third_conclusion,
              status="completed" if third_conclusion else "waiting"),
    ]
    runs = list(reversed(base + new))
    return {"total_count": len(runs), "workflow_runs": runs}


class FakeResponse:
    def __init__(self, payload):
        self.stream = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self.stream

    def __exit__(self, *_args):
        self.stream.close()


def with_history(payload, job_started=False):
    def opener(request, timeout):
        assert timeout == 12
        assert request.full_url.startswith("https://api.github.com/repos/")
        if "/jobs?" in request.full_url:
            return FakeResponse({
                "total_count": 1,
                "jobs": [dict(
                    conclusion="failure", status="completed",
                    runner_name="runner" if job_started else "",
                    steps=[{"name": "executed"}] if job_started else [],
                )],
            })
        return FakeResponse(payload)
    return opener


class BoundedGreetingTests(unittest.TestCase):
    def check(self, payload, run_id=CURRENT, job_started=False):
        validate_bounded_dispatch(
            good_env(run_id), "fake-token",
            with_history(payload, job_started=job_started),
        )

    def test_safe_documented_rate_limit_code(self):
        class MockRateLimit(Exception):
            code = "credit_balance_exhausted"
        self.assertEqual(safe_rate_limit_code(MockRateLimit()), "credit_balance_exhausted")

    def test_safe_project_spend_limit_code_in_body(self):
        class MockRateLimit(Exception):
            body = {"code": "project_spend_limit_exceeded"}
        self.assertEqual(safe_rate_limit_code(MockRateLimit()), "project_spend_limit_exceeded")

    def test_unrecognized_provider_code_is_redacted(self):
        class MockRateLimit(Exception):
            code = "secret-sk-example"
        self.assertEqual(safe_rate_limit_code(MockRateLimit()), "unclassified")

    def test_no_error_detail_is_unclassified(self):
        self.assertEqual(safe_rate_limit_code(Exception("sensitive data")), "unclassified")

    def test_valid_identity(self):
        validate_identity(good_env())

    def test_first_new_test(self):
        self.check(history())

    def test_fifth_new_test(self):
        new = [entry(CURRENT + i, status="completed", conclusion="failure")
               for i in range(MAX_NEW_DISPATCHES - 1)]
        new.append(entry(CURRENT + MAX_NEW_DISPATCHES - 1,
                         status="in_progress", conclusion=None))
        self.check(history(new), CURRENT + MAX_NEW_DISPATCHES - 1)

    def test_sixth_new_test_rejected(self):
        new = [entry(CURRENT + i) for i in range(MAX_NEW_DISPATCHES)]
        new.append(entry(CURRENT + MAX_NEW_DISPATCHES,
                         status="in_progress", conclusion=None))
        with self.assertRaises(GateError):
            self.check(history(new), CURRENT + MAX_NEW_DISPATCHES)

    def test_third_original_still_waiting(self):
        with self.assertRaises(GateError):
            self.check(history(third_conclusion=None))

    def test_other_unfinished_test(self):
        new = [entry(CURRENT, status="waiting", conclusion=None),
               entry(CURRENT + 1, status="in_progress", conclusion=None)]
        with self.assertRaises(GateError):
            self.check(history(new), CURRENT + 1)

    def test_wrong_actor_in_history(self):
        bad = history()
        bad["workflow_runs"][0]["actor"]["id"] = 123
        with self.assertRaises(GateError):
            self.check(bad)

    def test_wrong_historic_sha(self):
        bad = history()
        for run in bad["workflow_runs"]:
            if run["id"] == SECOND:
                run["head_sha"] = "0" * 40
        with self.assertRaises(GateError):
            self.check(bad)

    def test_original_first_run_must_have_zero_steps(self):
        with self.assertRaises(GateError):
            self.check(history(), job_started=True)

    def test_missing_baseline_rejected(self):
        bad = history()
        bad["workflow_runs"] = [r for r in bad["workflow_runs"] if r["id"] != SECOND]
        bad["total_count"] = len(bad["workflow_runs"])
        with self.assertRaises(GateError):
            self.check(bad)

    def test_untrusted_count_rejected(self):
        bad = history()
        bad["total_count"] = 99
        with self.assertRaises(GateError):
            self.check(bad)

    def test_missing_token_rejected(self):
        with self.assertRaises(GateError):
            validate_bounded_dispatch(good_env(), "")

    def test_missing_history_rejected(self):
        with self.assertRaises(GateError):
            self.check({})

    def test_unavailable_history_rejected(self):
        def unavailable(_request, timeout):
            raise OSError(f"test outage: {timeout}")
        with self.assertRaises(GateError):
            validate_bounded_dispatch(good_env(), "fake-token", unavailable)

    def test_rerun_rejected(self):
        env = good_env()
        env["GITHUB_RUN_ATTEMPT"] = "2"
        with self.assertRaises(GateError):
            validate_identity(env)

    def test_non_main_rejected(self):
        env = good_env()
        env["GITHUB_REF"] = "refs/heads/prototype"
        with self.assertRaises(GateError):
            validate_identity(env)

    def test_other_trigger_rejected(self):
        env = good_env()
        env["GITHUB_EVENT_NAME"] = "schedule"
        with self.assertRaises(GateError):
            validate_identity(env)


if __name__ == "__main__":
    unittest.main()
