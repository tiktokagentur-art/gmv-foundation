import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("aline_worker", ROOT / "worker.py")
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)

class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = worker.load_snapshot(ROOT / "examples/synthetic.json")

    def test_sample_is_synthetic(self):
        self.assertTrue(self.snapshot.synthetic)
        self.assertEqual(len(self.snapshot.work_items), 2)

    def test_duplicate_ticket_rejected(self):
        data = json.loads((ROOT / "examples/synthetic.json").read_text())
        data["work_items"].append(data["work_items"][0])
        with self.assertRaises(ValueError):
            worker.Snapshot.model_validate(data)

    def test_rejects_forged_synthetic_snapshot(self):
        altered = self.snapshot.model_copy(deep=True)
        altered.work_items[0].title = "Unapproved data"
        with self.assertRaisesRegex(RuntimeError, "reviewed synthetic fixture"):
            worker.assert_pilot_fixture(altered)

    def test_unknown_ticket_rejected(self):
        a = worker.Analysis(executive_summary="demo", unresolved_questions=[],
            findings=[worker.Finding(ticket_id="INVALID", severity="high",
                evidence_status="unknown", explanation="demo", evidence_urls=[],
                next_readonly_check="check", ceo_decision_required=False)])
        with self.assertRaisesRegex(ValueError, "unknown ticket"):
            worker.validate_analysis(self.snapshot, a)

    def test_fabricated_verified_rejected(self):
        a = worker.Analysis(executive_summary="demo", unresolved_questions=[],
            findings=[worker.Finding(ticket_id="EX-001", severity="high",
                evidence_status="verified", explanation="demo",
                evidence_urls=["https://example.invalid/evidence/EX-001"],
                next_readonly_check="check", ceo_decision_required=False)])
        with self.assertRaisesRegex(ValueError, "unsupported verification"):
            worker.validate_analysis(self.snapshot, a)

    def test_unknown_source_rejected(self):
        a = worker.Analysis(executive_summary="demo", unresolved_questions=[],
            findings=[worker.Finding(ticket_id="EX-001", severity="high",
                evidence_status="unknown", explanation="demo",
                evidence_urls=["https://fake.invalid/"],
                next_readonly_check="check", ceo_decision_required=False)])
        with self.assertRaisesRegex(ValueError, "unknown source"):
            worker.validate_analysis(self.snapshot, a)

if __name__ == "__main__":
    unittest.main()
