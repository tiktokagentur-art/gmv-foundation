"""Offline contract tests for the isolated Aline L1 worker prototype."""

import asyncio
import contextlib
import importlib.util
import io
import json
import os
import socket
import subprocess
import sys
import traceback
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_forged_synthetic_label_is_rejected(self):
        altered = self.snapshot.model_copy(deep=True)
        altered.work_items[0].title = "Potential real ticket disguised as synthetic"
        with self.assertRaisesRegex(RuntimeError, "reviewed synthetic fixture"):
            worker.assert_pilot_fixture(altered)

    def test_even_explicit_data_flag_cannot_send_real_pilot_data(self):
        real = self.snapshot.model_copy(update={"synthetic": False})
        with self.assertRaisesRegex(RuntimeError, "reviewed synthetic fixture"):
            asyncio.run(worker.run(real, approved=True, data_transfer_approved=True))

    def test_synthetic_transfer_requires_separate_consent(self):
        with self.assertRaisesRegex(RuntimeError, "confirm-data-transfer"):
            asyncio.run(worker.run(self.snapshot, approved=True))

    def test_missing_key_blocks_model_call(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "OPENAI_MODEL": "gpt-6.1-terra",
                                          "ALINE_SECRET_SOURCE": "env"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                asyncio.run(worker.run(self.snapshot, approved=True, data_transfer_approved=True))

    def test_missing_model_blocks_model_call(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "placeholder", "OPENAI_MODEL": ""}):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_MODEL"):
                asyncio.run(worker.run(self.snapshot, approved=True, data_transfer_approved=True))


class TestAlineVaultSource(unittest.TestCase):
    def setUp(self):
        self.synthetic_dsn = "synthetic-conninfo-private"
        self.synthetic_key = "synthetic-openai-key"

    def connector(self, row=None, error=None):
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value.__enter__.return_value = cursor
        connect = MagicMock(return_value=connection, side_effect=error)
        return SimpleNamespace(connect=connect), connect, cursor

    def vault_env(self):
        return patch.dict(os.environ, {
            "ALINE_SECRET_SOURCE": "supabase-vault",
            "ALINE_VAULT_DATABASE_URL": self.synthetic_dsn,
            "OPENAI_API_KEY": "synthetic-fallback-must-not-be-used",
        })

    def test_success_uses_fixed_function_and_tls(self):
        module, connect, cursor = self.connector((self.synthetic_key,))
        with self.vault_env(), patch.dict(sys.modules, {"psycopg": module}):
            self.assertEqual(worker.load_openai_api_key(), self.synthetic_key)
        connect.assert_called_once()
        args, kwargs = connect.call_args
        self.assertEqual(args, (self.synthetic_dsn,))
        self.assertEqual(kwargs["sslmode"], "verify-full")
        self.assertLessEqual(kwargs["connect_timeout"], 3)
        self.assertIn("statement_timeout=3000", kwargs["options"])
        cursor.execute.assert_called_once_with("SELECT aline_private.get_openai_api_key()")

    def test_missing_secret_fails_without_environment_fallback(self):
        module, _, _ = self.connector(None)
        with self.vault_env(), patch.dict(sys.modules, {"psycopg": module}):
            with self.assertRaisesRegex(RuntimeError, "secret is unavailable"):
                worker.load_openai_api_key()

    def test_invalid_mode_fails_closed(self):
        with patch.dict(os.environ, {"ALINE_SECRET_SOURCE": "unexpected",
                                   "OPENAI_API_KEY": self.synthetic_key}):
            with self.assertRaisesRegex(RuntimeError, "ALINE_SECRET_SOURCE is invalid"):
                worker.load_openai_api_key()

    def test_connection_error_is_redacted(self):
        self.assert_redacted_failure(ConnectionError)

    def test_permission_error_is_redacted(self):
        self.assert_redacted_failure(PermissionError)

    def assert_redacted_failure(self, exception_type):
        module, _, _ = self.connector(error=exception_type(
            f"denied {self.synthetic_dsn} {self.synthetic_key}"
        ))
        with self.vault_env(), patch.dict(sys.modules, {"psycopg": module}):
            with self.assertRaises(RuntimeError) as caught:
                worker.load_openai_api_key()
        rendered = "".join(traceback.format_exception(caught.exception))
        self.assertIn("Supabase Vault secret lookup failed", rendered)
        self.assertNotIn(self.synthetic_dsn, rendered)
        self.assertNotIn(self.synthetic_key, rendered)

    def test_offline_cli_never_connects_even_when_vault_selected(self):
        module, connect, _ = self.connector((self.synthetic_key,))
        snapshot_path = MODULE_PATH.parent / "examples" / "synthetic.json"
        cli_args = ["worker.py", "--input", str(snapshot_path), "--offline-demo"]
        with self.vault_env(), patch.dict(sys.modules, {"psycopg": module}), \
                patch.object(socket.socket, "connect", side_effect=AssertionError("network")), \
                patch.object(sys, "argv", cli_args), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            worker.main()
        connect.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["api_requests_made"], 0)

    def test_approval_and_fixture_gates_precede_vault_lookup(self):
        snapshot = worker.load_snapshot(MODULE_PATH.parent / "examples" / "synthetic.json")
        with self.vault_env(), patch.object(worker, "load_openai_api_key",
                                            side_effect=AssertionError("lookup")) as lookup:
            with self.assertRaisesRegex(RuntimeError, "confirm-api-call"):
                asyncio.run(worker.run(snapshot))
            altered = snapshot.model_copy(deep=True)
            altered.work_items[0].title = "unreviewed synthetic data"
            with self.assertRaisesRegex(RuntimeError, "reviewed synthetic fixture"):
                asyncio.run(worker.run(altered, approved=True, data_transfer_approved=True))
        lookup.assert_not_called()

    def test_model_gate_precedes_vault_connection(self):
        snapshot = worker.load_snapshot(MODULE_PATH.parent / "examples" / "synthetic.json")
        module, connect, _ = self.connector((self.synthetic_key,))
        with self.vault_env(), patch.dict(os.environ, {"OPENAI_MODEL": "unapproved"}), \
                patch.dict(sys.modules, {"psycopg": module}):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_MODEL"):
                asyncio.run(worker.run(
                    snapshot, approved=True, data_transfer_approved=True
                ))
        connect.assert_not_called()

    def test_model_client_gets_vault_key_without_process_environment(self):
        snapshot = worker.load_snapshot(MODULE_PATH.parent / "examples" / "synthetic.json")
        analysis = worker.offline_demo(snapshot)
        client_factory = MagicMock()
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client_factory.return_value = client
        fake_agents = SimpleNamespace(
            Agent=MagicMock(), ModelSettings=MagicMock(), RunConfig=MagicMock(),
            Runner=SimpleNamespace(run=AsyncMock(
                return_value=SimpleNamespace(final_output=analysis)
            )),
            set_default_openai_client=MagicMock(),
        )
        with patch.dict(os.environ, {"OPENAI_MODEL": "gpt-6.1-terra", "OPENAI_API_KEY": "",
                                   "ALINE_SECRET_SOURCE": "supabase-vault"}), \
                patch.object(worker, "load_openai_api_key", return_value=self.synthetic_key), \
                patch.dict(sys.modules, {"openai": SimpleNamespace(AsyncOpenAI=client_factory),
                                         "agents": fake_agents}):
            result = asyncio.run(worker.run(
                snapshot, approved=True, data_transfer_approved=True
            ))
            self.assertEqual(os.environ["OPENAI_API_KEY"], "")
        self.assertEqual(result, analysis)
        client_factory.assert_called_once_with(api_key=self.synthetic_key, max_retries=0)


if __name__ == "__main__":
    unittest.main()
