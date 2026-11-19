"""Negative tests for the protected, synthetic-only L1 API."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import api  # noqa: E402

FIXTURE = json.loads((ROOT / "examples" / "synthetic.json").read_text(encoding="utf-8"))
TOKEN = "a" * 48


class AlineApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)

    def test_health_has_no_dependency_on_secret(self):
        with patch.dict(os.environ, {"ALINE_PILOT_TOKEN": ""}):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_ready_fails_closed_without_secret(self):
        with patch.dict(os.environ, {"ALINE_PILOT_TOKEN": ""}):
            response = self.client.get("/ready")
        self.assertEqual(response.status_code, 503)

    def test_analysis_unavailable_without_secret(self):
        with patch.dict(os.environ, {"ALINE_PILOT_TOKEN": ""}):
            response = self.client.post(
                "/v1/offline-analysis",
                json=FIXTURE,
                headers={"X-Pilot-Token": TOKEN},
            )
        self.assertEqual(response.status_code, 503)

    def test_analysis_requires_correct_token(self):
        with patch.dict(os.environ, {"ALINE_PILOT_TOKEN": TOKEN}):
            response = self.client.post("/v1/offline-analysis", json=FIXTURE)
            rejected = self.client.post(
                "/v1/offline-analysis",
                json=FIXTURE,
                headers={"X-Pilot-Token": "incorrect"},
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(rejected.status_code, 401)

    def test_only_bundled_synthetic_snapshot_is_accepted(self):
        changed = json.loads(json.dumps(FIXTURE))
        changed["work_items"][0]["title"] = "Changed fixture"
        with patch.dict(os.environ, {"ALINE_PILOT_TOKEN": TOKEN}):
            response = self.client.post(
                "/v1/offline-analysis",
                json=changed,
                headers={"X-Pilot-Token": TOKEN},
            )
        self.assertEqual(response.status_code, 422)

    def test_synthetic_offline_result_contains_no_writes_or_model_calls(self):
        with patch.dict(os.environ, {"ALINE_PILOT_TOKEN": TOKEN}):
            ready = self.client.get("/ready")
            response = self.client.post(
                "/v1/offline-analysis",
                json=FIXTURE,
                headers={"X-Pilot-Token": TOKEN},
            )
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["api_requests_made"], 0)
        self.assertEqual(response.json()["writes_performed"], 0)
        self.assertEqual(response.json()["execution_mode"], "offline_deterministic_demo")


if __name__ == "__main__":
    unittest.main()
