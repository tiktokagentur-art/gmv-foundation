"""No-cost tests for the gated Aline dialogue and persistent pilot ledger."""

import asyncio
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import live_runtime  # noqa: E402

import api  # noqa: E402

TOKEN = "C" * 48
GREETING = api.GREETING


async def call_dialog(message, key=None):
    return await live_runtime.dialog(message, key or uuid4().hex)


def fake_response(text="Hallo, ich bin Aline.", input_tokens=42, output_tokens=17):
    return SimpleNamespace(
        model="gpt-6.1-terra",
        output_text=text,
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
    )


class HttpDialogueTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)

    def test_health_is_liveness_only(self):
        with patch.dict(os.environ, {"ALINE_CEO_TOKEN": ""}):
            result = self.client.get("/health")
            ready = self.client.get("/ready")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(ready.status_code, 503)

    def test_dialogue_and_status_require_distinct_ceo_secret(self):
        with patch.dict(os.environ, {"ALINE_CEO_TOKEN": TOKEN}, clear=True):
            missing = self.client.post(
                "/v1/dialog", json={"message": GREETING, "synthetic": True}
            )
            wrong = self.client.get("/v1/status", headers={"X-CEO-Token": "wrong"})
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)

    def test_dialogue_denies_unapproved_input_without_model_call(self):
        with (
            patch.dict(os.environ, {"ALINE_CEO_TOKEN": TOKEN}, clear=True),
            patch.object(api.live_runtime, "dialog", new_callable=AsyncMock) as invoke,
        ):
            invalid = self.client.post(
                "/v1/dialog",
                json={"message": "Unbekannte Aufgabe", "synthetic": True},
                headers={"X-CEO-Token": TOKEN, "Idempotency-Key": uuid4().hex},
            )
            nonsynthetic = self.client.post(
                "/v1/dialog",
                json={"message": GREETING, "synthetic": False},
                headers={"X-CEO-Token": TOKEN, "Idempotency-Key": uuid4().hex},
            )
        self.assertEqual(invalid.status_code, 403)
        self.assertEqual(nonsynthetic.status_code, 422)
        invoke.assert_not_called()

    def test_dialogue_requires_idempotency_header(self):
        with (
            patch.dict(os.environ, {"ALINE_CEO_TOKEN": TOKEN}, clear=True),
            patch.object(api.live_runtime, "dialog", new_callable=AsyncMock) as invoke,
        ):
            denied = self.client.post(
                "/v1/dialog",
                json={"message": GREETING, "synthetic": True},
                headers={"X-CEO-Token": TOKEN},
            )
        self.assertEqual(denied.status_code, 400)
        invoke.assert_not_called()

    def test_duplicate_key_maps_to_conflict(self):
        with (
            patch.dict(os.environ, {"ALINE_CEO_TOKEN": TOKEN}, clear=True),
            patch.object(api.live_runtime, "dialog", new_callable=AsyncMock) as invoke,
        ):
            invoke.side_effect = live_runtime.RuntimeDuplicate("already used")
            result = self.client.post(
                "/v1/dialog",
                json={"message": GREETING, "synthetic": True},
                headers={"X-CEO-Token": TOKEN, "Idempotency-Key": uuid4().hex},
            )
        self.assertEqual(result.status_code, 409)

    def test_new_conversation_requires_no_code_change_or_restart(self):
        response = {
            "worker_id": "GMV-VE-001",
            "reply": "Ich bin Aline und im L1-Pilot bereit.",
            "model": "gpt-6.1-terra",
            "usage": {"input_tokens": 42, "output_tokens": 17, "total_tokens": 59},
        }
        with (
            patch.dict(
                os.environ,
                {"ALINE_CEO_TOKEN": TOKEN, "ALINE_CEO_DIALOG_APPROVED": "true"},
                clear=True,
            ),
            patch.object(api.live_runtime, "dialog", new_callable=AsyncMock) as invoke,
        ):
            invoke.return_value = response
            first = self.client.post(
                "/v1/dialog",
                json={"message": GREETING, "synthetic": True},
                headers={"X-CEO-Token": TOKEN, "Idempotency-Key": uuid4().hex},
            )
            second = self.client.post(
                "/v1/dialog",
                json={"message": "Wie ist dein Status?", "synthetic": True},
                headers={"X-CEO-Token": TOKEN, "Idempotency-Key": uuid4().hex},
            )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(invoke.await_count, 2)

    def test_stop_requires_authentication(self):
        with (
            patch.dict(os.environ, {"ALINE_CEO_TOKEN": TOKEN}, clear=True),
            patch.object(api.live_runtime, "stop") as stop,
        ):
            denied = self.client.post("/v1/stop")
            allowed = self.client.post("/v1/stop", headers={"X-CEO-Token": TOKEN})
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(allowed.status_code, 200)
        stop.assert_called_once()

    def test_uncertain_outcome_returns_error_without_provider_details(self):
        with (
            patch.dict(os.environ, {"ALINE_CEO_TOKEN": TOKEN}, clear=True),
            patch.object(api.live_runtime, "dialog", new_callable=AsyncMock) as invoke,
        ):
            invoke.side_effect = live_runtime.RuntimeUncertain("secret provider body")
            result = self.client.post(
                "/v1/dialog",
                json={"message": GREETING, "synthetic": True},
                headers={"X-CEO-Token": TOKEN, "Idempotency-Key": uuid4().hex},
            )
        self.assertEqual(result.status_code, 502)
        self.assertNotIn("secret provider body", result.text)


class PersistentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = str(Path(self.tmp.name) / "pilot.sqlite3")
        self.env = {
            "ALINE_LIVE_ENABLED": "true",
            "ALINE_L1_PROJECT_DEDICATED": "true",
            "ALINE_L1_HARD_LIMIT_ATTESTED": "true",
            "ALINE_L1_BUDGET_USD": "10",
            "ALINE_PROVIDER_READBACK_AT": datetime.now(UTC).isoformat(),
            "ALINE_PRIOR_SPEND_USD": "0",
            "OPENAI_PROJECT_ID": "proj_test_aline",
            "OPENAI_MODEL": "gpt-6.1-terra",
            "OPENAI_API_KEY": "test-key-never-sent",
            "ALINE_CEO_TOKEN": TOKEN,
            "ALINE_LEDGER_PATH": self.ledger,
            "ALINE_LEDGER_ID": "L" * 40,
        }
        with (
            patch.dict(os.environ, dict(self.env, ALINE_LIVE_ENABLED="false"), clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
        ):
            live_runtime.provision_ledger()

    async def test_disabled_runtime_makes_no_model_call(self):
        env = dict(self.env, ALINE_LIVE_ENABLED="false")
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
            patch.object(live_runtime, "_invoke_model", new_callable=AsyncMock) as invoke,
        ):
            with self.assertRaises(live_runtime.RuntimeBlocked):
                await call_dialog(GREETING)
        invoke.assert_not_called()

    async def test_operator_cannot_provision_over_existing_ledger(self):
        with (
            patch.dict(os.environ, dict(self.env, ALINE_LIVE_ENABLED="false"), clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
        ):
            with self.assertRaises(live_runtime.RuntimeBlocked):
                live_runtime.provision_ledger()

    async def test_missing_key_and_nonpersistent_ledger_fail_closed(self):
        env = dict(self.env)
        env.pop("OPENAI_API_KEY")
        with patch.dict(os.environ, env, clear=True):
            okay, _ = live_runtime.readiness()
        self.assertFalse(okay)
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=False),
        ):
            okay, _ = live_runtime.readiness()
        self.assertFalse(okay)

    async def test_model_and_project_gates_reject_without_model_call(self):
        for override in (
            {"OPENAI_MODEL": "different-model"},
            {"OPENAI_PROJECT_ID": ""},
            {"ALINE_L1_HARD_LIMIT_ATTESTED": "false"},
        ):
            with self.subTest(override=override):
                with (
                    patch.dict(os.environ, dict(self.env, **override), clear=True),
                    patch.object(live_runtime, "_is_persistent_volume", return_value=True),
                    patch.object(live_runtime, "_invoke_model", new_callable=AsyncMock) as invoke,
                ):
                    with self.assertRaises(live_runtime.RuntimeBlocked):
                        await call_dialog(GREETING)
                    invoke.assert_not_called()

    async def test_prior_spend_exhausts_total_pilot_budget(self):
        env = dict(self.env, ALINE_PRIOR_SPEND_USD="10")
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
            patch.object(live_runtime, "_invoke_model", new_callable=AsyncMock) as invoke,
        ):
            with self.assertRaises(live_runtime.RuntimeBlocked):
                await call_dialog(GREETING)
        invoke.assert_not_called()

    async def test_prior_spend_cannot_be_lowered_after_provision(self):
        another_path = str(Path(self.tmp.name) / "prior.sqlite3")
        env = dict(
            self.env,
            ALINE_LEDGER_PATH=another_path,
            ALINE_LEDGER_ID="P" * 40,
            ALINE_PRIOR_SPEND_USD="3",
            ALINE_LIVE_ENABLED="false",
        )
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
        ):
            live_runtime.provision_ledger()
        env["ALINE_LIVE_ENABLED"] = "true"
        env["ALINE_PRIOR_SPEND_USD"] = "0"
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
            patch.object(live_runtime, "_invoke_model", new_callable=AsyncMock) as invoke,
        ):
            with self.assertRaises(live_runtime.RuntimeBlocked):
                await call_dialog(GREETING)
        invoke.assert_not_called()

    async def test_success_records_usage_and_cost_without_real_api(self):
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
            patch.object(live_runtime, "_invoke_model", new_callable=AsyncMock) as invoke,
        ):
            invoke.return_value = fake_response()
            result = await call_dialog(GREETING)
            status = live_runtime.get_status()
        self.assertEqual(invoke.await_count, 1)
        self.assertEqual(result["reply"], "Hallo, ich bin Aline.")
        self.assertEqual(result["usage"]["total_tokens"], 59)
        self.assertGreater(float(result["estimated_cost_usd"]), 0)
        self.assertEqual(status["worker_id"], "GMV-VE-001")

    async def test_five_reservations_exhaust_local_ten_dollar_cap(self):
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
            patch.object(live_runtime, "_invoke_model", new_callable=AsyncMock) as invoke,
        ):
            invoke.return_value = fake_response()
            for _ in range(5):
                await call_dialog(GREETING)
            with self.assertRaises(live_runtime.RuntimeBlocked):
                await call_dialog(GREETING)
            status = live_runtime.get_status()
        self.assertEqual(invoke.await_count, 5)
        self.assertEqual(status["reserved_usd"], "10")
        self.assertEqual(status["calls_reserved"], 5)

    async def test_deleted_ledger_cannot_reset_budget_or_calls(self):
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
            patch.object(live_runtime, "_invoke_model", new_callable=AsyncMock) as invoke,
        ):
            invoke.return_value = fake_response()
            await call_dialog(GREETING)
            Path(self.ledger).unlink()
            with self.assertRaises(live_runtime.RuntimeBlocked):
                await call_dialog(GREETING)
        self.assertEqual(invoke.await_count, 1)

    async def test_reused_idempotency_key_does_not_repeat_model_call(self):
        key = uuid4().hex
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
            patch.object(live_runtime, "_invoke_model", new_callable=AsyncMock) as invoke,
        ):
            invoke.return_value = fake_response()
            await call_dialog(GREETING, key)
            with self.assertRaises(live_runtime.RuntimeDuplicate):
                await call_dialog(GREETING, key)
        self.assertEqual(invoke.await_count, 1)

    async def test_replaced_ledger_identity_is_rejected(self):
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
            patch.object(live_runtime, "_invoke_model", new_callable=AsyncMock) as invoke,
        ):
            invoke.return_value = fake_response()
            await call_dialog(GREETING)
            Path(self.ledger).unlink()
            with sqlite3.connect(self.ledger) as connection:
                connection.execute(
                    "CREATE TABLE control (id INTEGER PRIMARY KEY, ledger_id TEXT)"
                )
                connection.execute(
                    "INSERT INTO control (id, ledger_id) VALUES (1, ?)",
                    ("wrong-ledger-id",),
                )
            with self.assertRaises(live_runtime.RuntimeBlocked):
                await call_dialog(GREETING)
        self.assertEqual(invoke.await_count, 1)

    async def test_concurrent_request_is_rejected_without_second_call(self):
        started = asyncio.Event()
        finish = asyncio.Event()

        async def slow_invoke(*_args, **_kwargs):
            started.set()
            await finish.wait()
            return fake_response()

        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
            patch.object(live_runtime, "_invoke_model", side_effect=slow_invoke) as invoke,
        ):
            first = asyncio.create_task(call_dialog(GREETING))
            await asyncio.wait_for(started.wait(), timeout=2)
            try:
                with self.assertRaises((live_runtime.RuntimeBusy, live_runtime.RuntimeBlocked)):
                    await call_dialog(GREETING)
            finally:
                finish.set()
            await first
        self.assertEqual(invoke.call_count, 1)

    async def test_provider_error_stays_reserved_and_stops_future_calls(self):
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
            patch.object(live_runtime, "_invoke_model", new_callable=AsyncMock) as invoke,
        ):
            invoke.side_effect = TimeoutError("provider detail should not escape")
            with self.assertRaises(live_runtime.RuntimeUncertain):
                await call_dialog(GREETING)
            with self.assertRaises(live_runtime.RuntimeBlocked):
                await call_dialog(GREETING)
            status = live_runtime.get_status()
        self.assertEqual(invoke.await_count, 1)
        self.assertNotIn("provider detail", str(status))

    async def test_missing_usage_pauses_pilot(self):
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
            patch.object(live_runtime, "_invoke_model", new_callable=AsyncMock) as invoke,
        ):
            invoke.return_value = SimpleNamespace(output_text="Hallo", usage=None)
            with self.assertRaises(live_runtime.RuntimeUncertain):
                await call_dialog(GREETING)
            okay, _ = live_runtime.readiness()
        self.assertFalse(okay)

    async def test_inconsistent_total_usage_pauses_pilot(self):
        response = fake_response()
        response.usage.total_tokens += 1
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
            patch.object(live_runtime, "_invoke_model", new_callable=AsyncMock) as invoke,
        ):
            invoke.return_value = response
            with self.assertRaises(live_runtime.RuntimeUncertain):
                await call_dialog(GREETING)
            with self.assertRaises(live_runtime.RuntimeBlocked):
                await call_dialog(GREETING)
        self.assertEqual(invoke.await_count, 1)

    async def test_stop_is_durable_across_calls(self):
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(live_runtime, "_is_persistent_volume", return_value=True),
            patch.object(live_runtime, "_invoke_model", new_callable=AsyncMock) as invoke,
        ):
            live_runtime.stop()
            okay, _ = live_runtime.readiness()
            with self.assertRaises(live_runtime.RuntimeBlocked):
                await call_dialog(GREETING)
        self.assertFalse(okay)
        invoke.assert_not_called()


if __name__ == "__main__":
    unittest.main()
