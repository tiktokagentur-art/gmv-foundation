"""Offline FE-003B contract, negative, and concurrency tests."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import pytest
from pydantic import ValidationError

from app.factory.budget import MockBudgetLedger
from app.factory.mock_runtime import MockRuntime, MockResult
from app.factory.models import AgentProfile, ApprovalRecord, BudgetPolicy, FactoryRecord
from app.factory.policy import MockPolicyRequest, evaluate_action

NOW = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def valid_request(**overrides):
    values = dict(worker_identity="worker-1", mandate_id="mandate-1", workitem_id="item-1",
                  action="test_mock", allowed_actions=frozenset({"test_mock"}),
                  authorized_workitem_id="item-1", lease_valid=True, mandate_active=True, isolated=True)
    values.update(overrides)
    return MockPolicyRequest(**values)


def test_contract_defaults_and_unknown_fields():
    assert BudgetPolicy().pilot_total_limit_cents == 2500
    assert FactoryRecord(factory_id="research", name="Research", organizational_owner_ve_id="owner").status == "planned"
    assert AgentProfile(display_name="Robin Keller", position="Research", factory_id="research").ve_id is None
    with pytest.raises(ValidationError):
        BudgetPolicy(currency="USD")
    with pytest.raises(ValidationError):
        BudgetPolicy(unexpected="forbidden")


def test_schemas_parse_and_are_strict():
    for filename in ("factory", "agent-profile", "budget-policy", "approval"):
        data = json.loads((ROOT / "schemas" / "factory" / "v1" / f"{filename}.schema.json").read_text())
        assert data["additionalProperties"] is False
        assert data["$schema"].endswith("2020-12/schema")


def test_self_approval_rejected():
    args = dict(approval_id="a", workitem_id="w", requester_ve_id="requester",
                executor_ve_id="executor", reviewer_ve_id="requester", decision="approved")
    with pytest.raises(ValidationError):
        ApprovalRecord(**args)
    args["reviewer_ve_id"] = "reviewer"
    assert ApprovalRecord(**args).decision == "approved"


@pytest.mark.parametrize("override", [
    {"worker_identity": ""}, {"mandate_id": ""}, {"lease_valid": False},
    {"mandate_active": False}, {"isolated": False},
    {"authorized_workitem_id": "other"}, {"action": "deploy"},
    {"action": "external_api"}, {"allowed_actions": frozenset()},
])
def test_policy_denies(override):
    assert not evaluate_action(valid_request(**override))


def test_policy_allows_only_isolated_mock():
    assert evaluate_action(valid_request())


def test_budget_limits_and_idempotency():
    ledger = MockBudgetLedger()
    assert ledger.reserve(request_id="a", workitem_id="w", amount_cents=500, now=NOW)
    assert ledger.reserve(request_id="a", workitem_id="w", amount_cents=500, now=NOW)
    assert not ledger.reserve(request_id="a", workitem_id="w", amount_cents=499, now=NOW)
    assert not ledger.reserve(request_id="b", workitem_id="w", amount_cents=1, now=NOW)
    assert ledger.reserve(request_id="c", workitem_id="w2", amount_cents=500, now=NOW)
    assert not ledger.reserve(request_id="d", workitem_id="w3", amount_cents=1, now=NOW)
    assert ledger.reserved_cents() == 1000


def test_global_limit_across_days():
    ledger = MockBudgetLedger()
    for i in range(5):
        day = NOW + timedelta(days=i // 2)
        assert ledger.reserve(request_id=str(i), workitem_id=str(i), amount_cents=500, now=day)
    assert not ledger.reserve(request_id="extra", workitem_id="extra", amount_cents=1, now=NOW + timedelta(days=5))
    assert ledger.reserved_cents() == 2500


def test_concurrent_budget_reservations_cannot_exceed_limit():
    ledger = MockBudgetLedger()
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda i: ledger.reserve(request_id=str(i), workitem_id=str(i), amount_cents=500, now=NOW), range(20)))
    assert sum(results) == 2
    assert ledger.reserved_cents() == 1000


def test_mock_runtime_window_and_deny():
    runtime = MockRuntime(started_at=NOW)
    assert runtime.execute(valid_request(), now=NOW).accepted
    assert not runtime.execute(valid_request(action="publish"), now=NOW).accepted
    assert not runtime.execute(valid_request(), now=NOW + timedelta(minutes=60)).accepted
    with pytest.raises(ValueError):
        MockRuntime(started_at=NOW, max_workers=3)

@pytest.mark.parametrize("action", [
    "deploy", "publish", "pay", "migrate", "change_permissions",
    "external_api", "activate_agent",
])
def test_every_prohibited_action_is_denied(action):
    assert not evaluate_action(valid_request(action=action, allowed_actions=frozenset({action})))


def test_optional_null_fields_and_defaults_match_json_schemas():
    import jsonschema
    for filename, instance in [
        ("factory", FactoryRecord(factory_id="f", name="Factory", organizational_owner_ve_id="owner")),
        ("agent-profile", AgentProfile(display_name="Alex Winter", position="Data", factory_id="data")),
        ("budget-policy", BudgetPolicy()),
        ("approval", ApprovalRecord(approval_id="a", workitem_id="w", requester_ve_id="r", executor_ve_id="e", reviewer_ve_id="q", decision="approved")),
    ]:
        schema = json.loads((ROOT / "schemas" / "factory" / "v1" / f"{filename}.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(instance.model_dump(), schema)


def test_runtime_rejects_expired_monotonic_clock(monkeypatch):
    from app.factory import mock_runtime
    runtime = MockRuntime(started_at=NOW)
    monkeypatch.setattr(mock_runtime, "monotonic", lambda: runtime._monotonic_started + 3600)
    assert not runtime.execute(valid_request(), now=NOW).accepted


def test_runtime_rejects_third_parallel_worker():
    entered = Event()
    release = Event()
    lock = Lock()
    active = 0

    class SlowMock(MockRuntime):
        def _run_mock(self, request):
            nonlocal active
            with lock:
                active += 1
                if active == 2:
                    entered.set()
            release.wait(timeout=2)
            return MockResult(True, request.workitem_id, "mock completed")

    runtime = SlowMock(started_at=NOW)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(runtime.execute, valid_request(), now=NOW)
        second = pool.submit(runtime.execute, valid_request(), now=NOW)
        try:
            assert entered.wait(timeout=2)
            third = runtime.execute(valid_request(), now=NOW)
            assert not third.accepted
            assert third.message == "capacity exceeded"
        finally:
            release.set()
        assert first.result().accepted and second.result().accepted
