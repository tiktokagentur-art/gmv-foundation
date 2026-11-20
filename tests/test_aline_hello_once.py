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
