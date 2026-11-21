"""Offline protocol benchmark for GMV-CODE-MODE-001.

This is a deterministic *simulation*, not a model or infrastructure benchmark.
It compares message envelopes for two ways to inspect exactly the same fixtures.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from code_mode.bridge import READ_TOOLS, MCPBridge  # noqa: E402
from code_mode.fixtures import PILOT_CODE, PILOT_RESPONSES, fixture_client  # noqa: E402
from code_mode.gateway import (  # noqa: E402
    ExecutionRequest,
    Gateway,
    JsonlAuditSink,
    Mandate,
    TrustedPrincipal,
)

TASK = (
    "Prüfe offene GitHub-Issues, Pull Requests, CI-Status und Railway-Staging. "
    "Identifiziere technische Blocker und gib eine strukturierte Zusammenfassung zurück."
)

FIXTURE: dict[str, Any] = PILOT_RESPONSES

TOOLS = tuple(FIXTURE)
CLASSIC_SCHEMA = "tools: " + ", ".join(TOOLS) + "; use read-only calls."
CODE_SCHEMA = "tools.call(name, args): Promise<JSON>; available: " + ", ".join(TOOLS)
CODE = PILOT_CODE


@dataclass(frozen=True)
class Settings:
    model_roundtrip_ms: float = 250
    tool_call_ms: float = 40
    executor_start_ms: float = 25
    input_usd_per_million: float = 1
    output_usd_per_million: float = 4


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def token_proxy(value: str) -> int:
    """Crude, explicit size proxy. It is not a provider tokenizer."""
    return (len(value.encode("utf-8")) + 3) // 4


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    """Deterministic stand-in for model reasoning, shared by both protocols."""
    return {
        "open_issue_count": len([
            item for item in data["github.list_issues"] if item["state"] == "open"
        ]),
        "blockers": [
            {"number": item["number"], "title": item["title"]}
            for item in data["github.list_issues"] if "blocker" in item["labels"]
        ],
        "open_pr_count": len([
            item for item in data["github.list_pull_requests"] if item["state"] == "open"
        ]),
        "ci_conclusion": data["github.ci_status"]["conclusion"],
        "staging_service": data["railway.service_status"]["status"],
        "failed_deployments": [
            item["id"] for item in data["railway.list_deployments"]
            if item["status"] == "failed"
        ],
    }


def run_classic() -> tuple[dict[str, Any], int, int, int]:
    transcript = [TASK, CLASSIC_SCHEMA]
    input_tokens = output_tokens = 0
    data = {}
    for name in TOOLS:
        input_tokens += token_proxy("\n".join(transcript))
        model_output = json_text({"tool": name, "arguments": {}})
        output_tokens += token_proxy(model_output)
        result = FIXTURE[name]
        data[name] = result
        transcript.extend((model_output, json_text(result)))
    input_tokens += token_proxy("\n".join(transcript))
    summary = summarize(data)
    output_tokens += token_proxy(json_text(summary))
    return summary, len(TOOLS) + 1, input_tokens, output_tokens


def run_code_mode() -> tuple[dict[str, Any], int, int, int]:
    # The executor invokes the four fixture tools and returns one compact value.
    # Code generation and summarization are simulated model responses.
    input_tokens = token_proxy(TASK + "\n" + CODE_SCHEMA)
    output_tokens = token_proxy(CODE)
    summary = summarize(FIXTURE)
    input_tokens += token_proxy(TASK + "\n" + CODE + "\n" + json_text(summary))
    output_tokens += token_proxy(json_text(summary))
    return summary, 2, input_tokens, output_tokens


def measure(runner: Any, runs: int, settings: Settings) -> dict[str, Any]:
    durations_ms = []
    successes = 0
    failures = 0
    expected = summarize(FIXTURE)
    last_rounds = last_input = last_output = 0
    for _ in range(runs):
        start = time.perf_counter_ns()
        try:
            result, last_rounds, last_input, last_output = runner()
            successes += result == expected
            failures += result != expected
        except Exception:
            failures += 1
        durations_ms.append((time.perf_counter_ns() - start) / 1_000_000)
    if not last_rounds:
        raise RuntimeError("No successful simulation run")
    local_ms = statistics.median(durations_ms)
    model_usd = (
        last_input * settings.input_usd_per_million
        + last_output * settings.output_usd_per_million
    ) / 1_000_000
    return {
        "model_roundtrips_simulated": last_rounds,
        "tool_calls_simulated": len(TOOLS),
        "input_tokens_proxy": last_input,
        "output_tokens_proxy": last_output,
        "local_processing_ms_median_measured": round(local_ms, 4),
        "total_latency_ms_scenario_simulated": round(
            last_rounds * settings.model_roundtrip_ms
            + len(TOOLS) * settings.tool_call_ms
            + (settings.executor_start_ms if runner is run_code_mode else 0)
            + local_ms,
            4,
        ),
        "model_cost_usd_scenario_simulated": round(model_usd, 8),
        "executor_incremental_cost_usd_measured": None,
        "success_rate_fixture": successes / runs,
        "error_rate_fixture": failures / runs,
        "completeness_fixture": successes / runs,
        "runs": runs,
    }


def local_e2e(runs: int = 10) -> dict[str, Any]:
    """Measure only local orchestration, with no model, remote service or sleep."""
    if runs < 1:
        raise ValueError("runs must be positive")
    expected = summarize(FIXTURE)
    measurements: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="gmv-code-mode-benchmark-") as directory:
        gateway = Gateway(
            mandates=(Mandate("benchmark-agent", "SYNTHETIC-BENCH", "fixture-read", READ_TOOLS),),
            client=fixture_client(),
            audit_sink=JsonlAuditSink(Path(directory) / "audit.jsonl"),
        )

        def classic() -> object:
            bridge = MCPBridge(fixture_client(), READ_TOOLS)
            return summarize({name: bridge.call(name, {}) for name in TOOLS})

        def code_mode() -> object:
            result = gateway.execute(
                ExecutionRequest("SYNTHETIC-BENCH", "fixture-read", PILOT_CODE, READ_TOOLS),
                TrustedPrincipal("benchmark-agent", active=True),
            )
            if result.status != "ok":
                raise RuntimeError(f"local code mode failed: {result.error_code}")
            return result.result

        for label, runner in (("classic", classic), ("code_mode", code_mode)):
            samples = []
            successes = 0
            errors = 0
            for _ in range(runs):
                start = time.perf_counter_ns()
                try:
                    result = runner()
                    successes += result == expected
                    errors += result != expected
                except Exception:
                    errors += 1
                samples.append(round((time.perf_counter_ns() - start) / 1_000_000, 3))
            ordered = sorted(samples)
            measurements[label] = {
                "latency_ms_samples_measured": samples,
                "latency_ms_median_measured": round(statistics.median(samples), 3),
                "latency_ms_p95_nearest_rank_measured": ordered[(95 * runs + 99) // 100 - 1],
                "successes_measured": successes,
                "errors_measured": errors,
                "completeness_against_fixture_measured": successes / runs,
                "runs": runs,
            }
    return {
        "classification": (
            "measured local fixture orchestration only; no model, network or external MCP"
        ),
        "environment_note": (
            "classic is in-process bridge calls; code mode includes gateway, bubblewrap "
            "and Node process startup; protocols have different local runtime overhead"
        ),
        "tool_calls_per_run": len(TOOLS),
        **measurements,
    }


def benchmark(
    runs: int = 100,
    settings: Settings | None = None,
    local_e2e_runs: int = 0,
) -> dict[str, Any]:
    settings = settings or Settings()
    if runs < 1:
        raise ValueError("runs must be positive")
    if min(
        settings.model_roundtrip_ms,
        settings.tool_call_ms,
        settings.executor_start_ms,
        settings.input_usd_per_million,
        settings.output_usd_per_million,
    ) < 0:
        raise ValueError("scenario parameters must be non-negative")
    result = {
        "classification": "offline deterministic simulation; no model or live API calls",
        "token_method": "ceil(UTF-8 bytes / 4), not provider tokens",
        "fixture": FIXTURE,
        "scenario": settings.__dict__,
        "classic": measure(run_classic, runs, settings),
        "code_mode": measure(run_code_mode, runs, settings),
    }
    if local_e2e_runs:
        result["local_e2e"] = local_e2e(local_e2e_runs)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--local-e2e-runs", type=int, default=0)
    parser.add_argument("--model-roundtrip-ms", type=float, default=250)
    parser.add_argument("--tool-call-ms", type=float, default=40)
    parser.add_argument("--executor-start-ms", type=float, default=25)
    parser.add_argument("--input-usd-per-million", type=float, default=1)
    parser.add_argument("--output-usd-per-million", type=float, default=4)
    args = parser.parse_args()
    settings = Settings(
        args.model_roundtrip_ms,
        args.tool_call_ms,
        args.executor_start_ms,
        args.input_usd_per_million,
        args.output_usd_per_million,
    )
    result = benchmark(args.runs, settings, args.local_e2e_runs)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
