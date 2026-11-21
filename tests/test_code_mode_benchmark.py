"""Offline benchmark invariants; no external model, service, or credentials."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from code_mode_benchmark import (  # noqa: E402
    FIXTURE,
    TOOLS,
    Settings,
    benchmark,
    run_classic,
    run_code_mode,
    summarize,
)


def test_same_fixture_and_complete_blockers() -> None:
    expected = summarize(FIXTURE)
    classic, classic_rounds, *_ = run_classic()
    code_mode, code_rounds, *_ = run_code_mode()
    assert classic == code_mode == expected
    assert expected["blockers"] == [
        {"number": 101, "title": "Staging migration blocked"}
    ]
    assert expected["ci_conclusion"] == "failure"
    assert expected["staging_service"] == "degraded"
    assert expected["failed_deployments"] == ["dep-1"]
    assert (classic_rounds, code_rounds) == (len(TOOLS) + 1, 2)


def test_benchmark_labels_simulated_values_and_same_tool_count() -> None:
    result = benchmark(runs=3)
    assert "simulation" in result["classification"]
    assert "not provider tokens" in result["token_method"]
    assert result["classic"]["tool_calls_simulated"] == len(TOOLS)
    assert result["code_mode"]["tool_calls_simulated"] == len(TOOLS)
    assert result["classic"]["success_rate_fixture"] == 1
    assert result["code_mode"]["completeness_fixture"] == 1
    assert result["code_mode"]["executor_incremental_cost_usd_measured"] is None


def test_invalid_scenario_fails_closed() -> None:
    with pytest.raises(ValueError):
        benchmark(runs=0)
    with pytest.raises(ValueError):
        benchmark(settings=Settings(model_roundtrip_ms=-1))
