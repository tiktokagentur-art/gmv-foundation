"""Offline-only negative tests for the ALINE-START-001 dispatch guard."""
import importlib.util
import unittest
from pathlib import Path

guard_path = Path(__file__).resolve().parents[1] / "scripts" / "aline_start_001_guard.py"
spec = importlib.util.spec_from_file_location("aline_start_001_guard", guard_path)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
GateError = guard.GateError
check_context = guard.check_context
check_history = guard.check_history

ENV = {
    "GITHUB_REPOSITORY": "tiktokagentur-art/gmv-foundation",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_ACTOR": "tiktokagentur-art",
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_RUN_ID": "12345",
    "ALINE_AUTHORIZATION": "ALINE-START-001 EINMALIG FREIGEGEBEN",
}
RUN = {
    "id": 12345,
    "event": "workflow_dispatch",
    "head_branch": "main",
    "run_attempt": 1,
    "actor": {"login": "tiktokagentur-art"},
}


class GuardTests(unittest.TestCase):
    def test_one_confirmed_run(self):
        self.assertEqual(check_context(ENV), 12345)
        check_history({"total_count": 1, "workflow_runs": [RUN]}, 12345)

    def test_requires_exact_confirmation(self):
        with self.assertRaises(GateError):
            check_context({**ENV, "ALINE_AUTHORIZATION": "yes"})

    def test_rejects_rerun(self):
        with self.assertRaises(GateError):
            check_context({**ENV, "GITHUB_RUN_ATTEMPT": "2"})

    def test_rejects_nondefault_branch(self):
        with self.assertRaises(GateError):
            check_context({**ENV, "GITHUB_REF": "refs/heads/feature"})

    def test_rejects_other_actor(self):
        with self.assertRaises(GateError):
            check_context({**ENV, "GITHUB_ACTOR": "someone-else"})

    def test_rejects_other_event(self):
        with self.assertRaises(GateError):
            check_context({**ENV, "GITHUB_EVENT_NAME": "pull_request"})

    def test_rejects_prior_run_even_failed(self):
        with self.assertRaises(GateError):
            check_history({"total_count": 2, "workflow_runs": [RUN, {
                **RUN, "id": 10000, "conclusion": "failure",
            }]}, 12345)

    def test_rejects_incomplete_history(self):
        with self.assertRaises(GateError):
            check_history({"total_count": 100, "workflow_runs": [RUN]}, 12345)

    def test_rejects_wrong_current_id(self):
        with self.assertRaises(GateError):
            check_history({"total_count": 1, "workflow_runs": [RUN]}, 99999)

    def test_rejects_empty_history(self):
        with self.assertRaises(GateError):
            check_history({"total_count": 0, "workflow_runs": []}, 12345)

    def test_rejects_missing_history(self):
        with self.assertRaises(GateError):
            check_history({}, 12345)

    def test_rejects_wrong_history_actor(self):
        with self.assertRaises(GateError):
            check_history({"total_count": 1, "workflow_runs": [
                {**RUN, "actor": {"login": "unknown"}},
            ]}, 12345)


if __name__ == "__main__":
    unittest.main()
