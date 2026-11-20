"""Negative tests for the separate, repeatable Aline L1 activation guard."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.aline_l1_runner_guard import (
    GuardError,
    conservative_estimate_usd,
    validate_environment,
    validate_fixture,
)


def valid_env() -> dict[str, str]:
    return {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": "tiktokagentur-art/gmv-foundation",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_ACTOR": "dedicated-aline-bot",
        "ALINE_L1_ACTOR": "dedicated-aline-bot",
        "ALINE_L1_ACTIVATED": "true",
        "ALINE_L1_PROJECT_DEDICATED": "true",
        "ALINE_L1_HARD_LIMIT_ATTESTED": "true",
        "ALINE_L1_BUDGET_USD": "10",
        "ALINE_L1_MODEL": "gpt-6.1-terra",
    }


class L1GuardTests(unittest.TestCase):
    def test_valid_synthetic_activation(self):
        validate_environment(valid_env())
        self.assertLess(conservative_estimate_usd(), 2.00)

    def test_no_activation(self):
        e = valid_env()
        e["ALINE_L1_ACTIVATED"] = ""
        with self.assertRaises(GuardError):
            validate_environment(e)

    def test_shared_admin_forbidden(self):
        e = valid_env()
        e["GITHUB_ACTOR"] = e["ALINE_L1_ACTOR"] = "tiktokagentur-art"
        with self.assertRaises(GuardError):
            validate_environment(e)

    def test_unknown_actor(self):
        e = valid_env()
        e["GITHUB_ACTOR"] = "another-user"
        with self.assertRaises(GuardError):
            validate_environment(e)

    def test_rerun_forbidden(self):
        e = valid_env()
        e["GITHUB_RUN_ATTEMPT"] = "2"
        with self.assertRaises(GuardError):
            validate_environment(e)

    def test_wrong_branch_forbidden(self):
        e = valid_env()
        e["GITHUB_REF"] = "refs/heads/feature"
        with self.assertRaises(GuardError):
            validate_environment(e)

    def test_missing_hard_limit_attestation(self):
        e = valid_env()
        e["ALINE_L1_HARD_LIMIT_ATTESTED"] = "false"
        with self.assertRaises(GuardError):
            validate_environment(e)

    def test_wrong_budget_forbidden(self):
        e = valid_env()
        e["ALINE_L1_BUDGET_USD"] = "999"
        with self.assertRaises(GuardError):
            validate_environment(e)

    def test_wrong_model_forbidden(self):
        e = valid_env()
        e["ALINE_L1_MODEL"] = "unapproved-model"
        with self.assertRaises(GuardError):
            validate_environment(e)

    def test_wrong_event_forbidden(self):
        e = valid_env()
        e["GITHUB_EVENT_NAME"] = "push"
        with self.assertRaises(GuardError):
            validate_environment(e)

    def test_fixture_only_synthetic_expected_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic.json"
            path.write_text(
                json.dumps({"synthetic": True, "work_items": [
                    {"ticket_id": "EX-001"}, {"ticket_id": "EX-002"}]}),
                encoding="utf-8",
            )
            validate_fixture(path)
            path.write_text(json.dumps({"synthetic": False, "work_items": []}))
            with self.assertRaises(GuardError):
                validate_fixture(path)

    def test_oversized_fixture_forbidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic.json"
            path.write_text("x" * 8193, encoding="utf-8")
            with self.assertRaises(GuardError):
                validate_fixture(path)


if __name__ == "__main__":
    unittest.main()
