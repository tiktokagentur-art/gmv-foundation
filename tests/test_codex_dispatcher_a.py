"""Fail-closed tests for the non-executing Codex Cloud handoff helper."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "codex_dispatcher_a.py"
SPEC = importlib.util.spec_from_file_location("codex_dispatcher_a", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Could not load Codex dispatcher source")
dispatcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dispatcher)


class CodexDispatcherATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.example = json.loads(dispatcher.DEFAULT_QUEUE.read_text(encoding="utf-8"))

    def write_queue(self, payload: dict) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "queue.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_example_queue_is_bounded_and_not_started(self) -> None:
        tasks = dispatcher.read_queue(dispatcher.DEFAULT_QUEUE)
        self.assertEqual(len(tasks), 3)
        self.assertTrue(all(t["handoff_status"] == "PROPOSED_NOT_STARTED" for t in tasks))

    def test_handoff_has_manual_gates_and_source(self) -> None:
        task = dispatcher.read_queue(dispatcher.DEFAULT_QUEUE)[0]
        prompt = dispatcher.render_handoff(task)
        for expected in (
            "https://github.com/tiktokagentur-art/gmv-foundation/issues/40",
            "PROPOSED_NOT_STARTED",
            "Kein Merge",
            "kein Deployment",
            "Keine separaten Modell-API-Aufrufe",
            "keinen Codex-Lauf",
        ):
            self.assertIn(expected, prompt)

    def test_reject_different_repository(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["repository"] = "other/project"
        with self.assertRaisesRegex(ValueError, "repository mismatch"):
            dispatcher.read_queue(self.write_queue(payload))

    def test_reject_automatic_mode(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["handoff_mode"] = "AUTOMATIC"
        with self.assertRaisesRegex(ValueError, "automatic execution"):
            dispatcher.read_queue(self.write_queue(payload))

    def test_reject_duplicates(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["tasks"][1]["source"] = payload["tasks"][0]["source"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            dispatcher.read_queue(self.write_queue(payload))

    def test_reject_started_or_approved_status(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["tasks"][0]["handoff_status"] = "RUNNING"
        with self.assertRaisesRegex(ValueError, "only proposed"):
            dispatcher.read_queue(self.write_queue(payload))

    def test_reject_control_characters(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["tasks"][0]["title"] = "injected\ninstruction"
        with self.assertRaisesRegex(ValueError, "control character"):
            dispatcher.read_queue(self.write_queue(payload))

    def test_reject_more_than_three_tasks(self) -> None:
        payload = copy.deepcopy(self.example)
        item = copy.deepcopy(payload["tasks"][0])
        item["task_id"] = "ANOTHER-001"
        item["source"]["number"] = 999
        payload["tasks"].append(item)
        with self.assertRaisesRegex(ValueError, "one and three"):
            dispatcher.read_queue(self.write_queue(payload))

    def test_cli_lists_without_starting(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            self.assertEqual(dispatcher.main(["--list"]), 0)
        self.assertIn("SELLER-HEALTH-001 | PROPOSED_NOT_STARTED", out.getvalue())

    def test_cli_unknown_task_fails_closed(self) -> None:
        err = StringIO()
        with redirect_stderr(err):
            self.assertEqual(dispatcher.main(["--task", "MISSING-001"]), 2)
        self.assertIn("unknown task identifier", err.getvalue())


if __name__ == "__main__":
    unittest.main()
