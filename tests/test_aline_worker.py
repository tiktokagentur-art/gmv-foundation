"""Offline contract tests for the isolated Aline L1 worker prototype."""

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "prototypes" / "aline-openai-worker" / "worker.py"
)
SPEC = importlib.util.spec_from_file_location("aline_worker_prototype", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load Aline prototype")
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "prototypes"
    / "aline-openai-worker"
    / "examples"
    / "synthetic.json"
)


class TestAlineWorker(unittest.TestCase):
    def setUp(self):
        self.snapshot = worker.load_snapshot(SNAPSHOT_PATH)

    def finding(self, **overrides):
        kwargs = {
            "ticket_id": "EX-001",
            "severity": "high",
            "evidence_status": "unknown",
            "explanation": "No independent review evidence",
            "evidence_urls": [],
            "next_readonly_check": "Read source",
            "ceo_decision_required": True,
        }
        kwargs.update(overrides)
        return worker.Finding(**kwargs)

    def analysis(self, finding):
        return worker.Analysis(
            executive_summary="Synthetic test",
            findings=[finding],
            unresolved_questions=[],
        )

    def test_fixture_synthetic_only(self):
        self.assertTrue(self.snapshot.synthetic)
        self.assertEqual(len(self.snapshot.work_items), 2)

    def test_duplicate_ticket_rejected(self):
        payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        payload["work_items"].append(payload["work_items"][0])
        with self.assertRaises(ValueError):
            worker.Snapshot.model_validate(payload)

    def test_unknown_ticket_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown ticket"):
            worker.validate_analysis(
                self.snapshot, self.analysis(self.finding(ticket_id="FABRICATED-001"))
            )

    def test_unknown_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown source"):
            worker.validate_analysis(
                self.snapshot,
                self.analysis(self.finding(evidence_urls=["https://untrusted.invalid/fake"])),
            )

    def test_fabricated_verified_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported verification"):
            worker.validate_analysis(
                self.snapshot,
                self.analysis(
                    self.finding(
                        evidence_status="verified",
                        evidence_urls=["https://example.invalid/evidence/EX-001"],
                    )
                ),
            )

    def test_valid_unknown_finding_accepted(self):
        result = worker.validate_analysis(self.snapshot, self.analysis(self.finding()))
        self.assertEqual(result.findings[0].ticket_id, "EX-001")

    def test_offline_demo_is_priority_sorted_and_not_verified(self):
        result = worker.offline_demo(self.snapshot)
        self.assertEqual([x.ticket_id for x in result.findings], ["EX-001", "EX-002"])
        self.assertEqual([x.evidence_status for x in result.findings], ["unknown", "unknown"])
        self.assertTrue(all(not x.evidence_urls for x in result.findings))

    def test_offline_cli_runs_without_openai_credentials(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "OPENAI_MODEL": ""}):
            result = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "--input",
                    str(SNAPSHOT_PATH),
                    "--offline-demo",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
            )
        report = json.loads(result.stdout)
        self.assertEqual(report["execution_mode"], "offline_deterministic_demo")
        self.assertEqual(report["api_requests_made"], 0)
        self.assertEqual(report["writes_performed"], 0)
        self.assertEqual(len(report["report"]["findings"]), 2)

    def test_remote_call_requires_explicit_approval(self):
        with self.assertRaisesRegex(RuntimeError, "confirm-api-call"):
            asyncio.run(worker.run(self.snapshot))

    def test_non_synthetic_transfer_requires_extra_approval(self):
        real = self.snapshot.model_copy(update={"synthetic": False})
        with self.assertRaisesRegex(RuntimeError, "confirm-data-transfer"):
            worker.require_api_approval(
                real, approved=True, data_transfer_approved=False
            )
        worker.require_api_approval(
            real, approved=True, data_transfer_approved=True
        )

    def test_missing_key_blocks_model_call(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "OPENAI_MODEL": "test"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                asyncio.run(worker.run(self.snapshot, approved=True))

    def test_missing_model_blocks_model_call(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "placeholder", "OPENAI_MODEL": ""}):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_MODEL"):
                asyncio.run(worker.run(self.snapshot, approved=True))


if __name__ == "__main__":
    unittest.main()
