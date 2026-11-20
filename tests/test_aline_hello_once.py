"""Offline negative tests for the isolated one-shot Aline greeting gate."""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from aline_hello_once import GateError, validate_first_dispatch, validate_identity  # noqa: E402


def good_env() -> dict[str, str]:
    return {
        "GITHUB_REPOSITORY": "tiktokagentur-art/gmv-foundation",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_ACTOR": "tiktokagentur-art",
        "GITHUB_ACTOR_ID": "354272348",
        "GITHUB_TRIGGERING_ACTOR": "tiktokagentur-art",
        "GITHUB_RUN_ID": "98765",
    }


class FakeResponse:
    def __init__(self, payload: object):
        self.stream = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self.stream

    def __exit__(self, *_args):
        self.stream.close()


def with_history(payload: object):
    def opener(request, timeout):
        assert request.full_url.startswith("https://api.github.com/repos/")
        assert timeout == 12
        return FakeResponse(payload)

    return opener


class HelloOnceTests(unittest.TestCase):
    def test_valid_human_trigger(self):
        validate_identity(good_env())

    def test_only_current_dispatch(self):
        validate_first_dispatch(
            good_env(),
            "mock-token",
            with_history({"total_count": 1, "workflow_runs": [{"id": 98765}]}),
        )

    def test_recovery_only_from_verified_zero_step_failure(self):
        old = {
            "id": 44694430741,
            "conclusion": "failure",
            "status": "completed",
            "run_attempt": 1,
            "head_sha": "71557145872ca31862e1bd617bc6eeb01f7d5826",
            "head_branch": "main",
        }
        current = {"id": 98765}
        history = {"total_count": 2, "workflow_runs": [current, old]}
        jobs = {
            "total_count": 1,
            "jobs": [{
                "conclusion": "failure",
                "status": "completed",
                "runner_name": "",
                "steps": [],
            }],
        }

        def opener(request, timeout):
            assert timeout == 12
            if request.full_url.endswith("/jobs?per_page=100"):
                return FakeResponse(jobs)
            return FakeResponse(history)

        validate_first_dispatch(good_env(), "mock-token", opener)

    def test_recovery_denied_if_first_job_started(self):
        old = {
            "id": 44694430741,
            "conclusion": "failure",
            "status": "completed",
            "run_attempt": 1,
            "head_sha": "71557145872ca31862e1bd617bc6eeb01f7d5826",
            "head_branch": "main",
        }
        history = {"total_count": 2, "workflow_runs": [{"id": 98765}, old]}
        jobs = {
            "total_count": 1,
            "jobs": [{
                "conclusion": "failure",
                "status": "completed",
                "runner_name": "GitHub Actions 1",
                "steps": [{"name": "Execute", "conclusion": "failure"}],
            }],
        }

        def opener(request, timeout):
            return FakeResponse(jobs if "/jobs?" in request.full_url else history)

        with self.assertRaises(GateError):
            validate_first_dispatch(good_env(), "mock-token", opener)

    def test_third_dispatch_denied(self):
        history = {
            "total_count": 3,
            "workflow_runs": [
                {"id": 98765},
                {"id": 44694430741},
                {"id": 222},
            ],
        }
        with self.assertRaises(GateError):
            validate_first_dispatch(good_env(), "mock-token", with_history(history))

    def test_recovery_denied_if_job_metadata_missing(self):
        old = {
            "id": 44694430741,
            "conclusion": "failure",
            "status": "completed",
            "run_attempt": 1,
            "head_sha": "71557145872ca31862e1bd617bc6eeb01f7d5826",
            "head_branch": "main",
        }
        history = {"total_count": 2, "workflow_runs": [{"id": 98765}, old]}

        def opener(request, timeout):
            return FakeResponse({"total_count": 0, "jobs": []}
                                if "/jobs?" in request.full_url else history)

        with self.assertRaises(GateError):
            validate_first_dispatch(good_env(), "mock-token", opener)

    def test_missing_token_denied(self):
        with self.assertRaises(GateError):
            validate_first_dispatch(good_env(), "")

    def test_other_dispatch_already_exists(self):
        history = {"total_count": 2, "workflow_runs": [{"id": 98765}, {"id": 123}]}
        with self.assertRaises(GateError):
            validate_first_dispatch(good_env(), "mock-token", with_history(history))

    def test_wrong_history_run_denied(self):
        with self.assertRaises(GateError):
            validate_first_dispatch(
                good_env(),
                "mock-token",
                with_history({"total_count": 1, "workflow_runs": [{"id": 111}]}),
            )

    def test_missing_history_denied(self):
        with self.assertRaises(GateError):
            validate_first_dispatch(good_env(), "mock-token", with_history({}))

    def test_unavailable_history_denied(self):
        def unavailable(_request, timeout):
            raise OSError(f"mock timeout {timeout}")

        with self.assertRaises(GateError):
            validate_first_dispatch(good_env(), "mock-token", unavailable)

    def test_wrong_event_denied(self):
        env = good_env()
        env["GITHUB_EVENT_NAME"] = "push"
        with self.assertRaises(GateError):
            validate_identity(env)

    def test_wrong_branch_denied(self):
        env = good_env()
        env["GITHUB_REF"] = "refs/heads/test/aline-hello-001"
        with self.assertRaises(GateError):
            validate_identity(env)

    def test_second_attempt_denied(self):
        env = good_env()
        env["GITHUB_RUN_ATTEMPT"] = "2"
        with self.assertRaises(GateError):
            validate_identity(env)

    def test_other_actor_denied(self):
        env = good_env()
        env["GITHUB_ACTOR"] = "somebody-else"
        with self.assertRaises(GateError):
            validate_identity(env)

    def test_changed_actor_id_denied(self):
        env = good_env()
        env["GITHUB_ACTOR_ID"] = "1234"
        with self.assertRaises(GateError):
            validate_identity(env)

    def test_missing_run_id_denied(self):
        env = good_env()
        env["GITHUB_RUN_ID"] = ""
        with self.assertRaises(GateError):
            validate_identity(env)


if __name__ == "__main__":
    unittest.main()
