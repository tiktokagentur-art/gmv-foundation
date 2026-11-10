"""Tests for GitHub Moderator audit comparison helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from github_moderator_audit import (  # noqa: E402
    AuditError,
    emit_unverified_bypass_warning,
    main,
    run_audit,
)
from github_moderator_lib import compare_rulesets, load_json  # noqa: E402

_APP_BYPASS = [
    {
        "actor_id": 424242,
        "actor_type": "Integration",
        "bypass_mode": "always",
    }
]


def test_compare_detects_missing_required_checks() -> None:
    desired = load_json(ROOT / "config/github/rulesets/main-branch-protection.json")
    actual = json.loads(json.dumps(desired))
    actual["rules"] = [
        rule for rule in actual["rules"] if rule.get("type") != "required_status_checks"
    ]
    diffs = compare_rulesets(desired, actual)
    assert any("required_status_checks" in item for item in diffs)


def test_compare_aligned_when_equal() -> None:
    desired = load_json(ROOT / "config/github/rulesets/main-branch-protection.json")
    actual = json.loads(json.dumps(desired))
    actual["id"] = 123
    actual["source"] = "tiktokagentur-art/gmv-foundation"
    assert desired["bypass_actors"] == []
    assert compare_rulesets(desired, actual) == []


def test_compare_detects_integration_bypass() -> None:
    desired = load_json(ROOT / "config/github/rulesets/main-branch-protection.json")
    actual = json.loads(json.dumps(desired))
    actual["bypass_actors"] = list(_APP_BYPASS)
    diffs = compare_rulesets(desired, actual)
    assert diffs == [f"bypass_actors: actual={_APP_BYPASS!r} desired={[]!r}"]


def test_compare_non_empty_bypass_is_drift_even_when_desired_matches() -> None:
    desired = load_json(ROOT / "config/github/rulesets/main-branch-protection.json")
    desired = json.loads(json.dumps(desired))
    desired["bypass_actors"] = list(_APP_BYPASS)
    actual = json.loads(json.dumps(desired))
    diffs = compare_rulesets(desired, actual)
    assert diffs == [
        f"bypass_actors: actual={_APP_BYPASS!r} desired={_APP_BYPASS!r}"
    ]


def test_compare_omitted_or_null_bypass_actors_is_not_drift() -> None:
    desired = load_json(ROOT / "config/github/rulesets/main-branch-protection.json")
    omitted = json.loads(json.dumps(desired))
    del omitted["bypass_actors"]
    nulled = json.loads(json.dumps(desired))
    nulled["bypass_actors"] = None
    assert compare_rulesets(desired, omitted) == []
    assert compare_rulesets(desired, nulled) == []


def test_run_audit_reports_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    desired = load_json(ROOT / "config/github/rulesets/main-branch-protection.json")
    actual_summary = [{"id": 1, "name": "main"}]
    actual_detail = {
        "id": 1,
        "name": "main",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": desired["conditions"],
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            desired["rules"][2],
        ],
    }

    def fake_api_get(_api_url: str, path: str, _token: str):
        if path.endswith("/rulesets"):
            return actual_summary
        if path.endswith("/rulesets/1"):
            return actual_detail
        raise AssertionError(path)

    monkeypatch.setattr("github_moderator_audit.api_get", fake_api_get)
    report = run_audit(
        root=ROOT,
        repo="tiktokagentur-art/gmv-foundation",
        token="dummy",
        api_url="https://api.github.com",
    )
    assert report["status"] == "drift"
    assert any("required_status_checks" in item for item in report["diffs"]["main"])
    assert not any("bypass_actors" in item for item in report["diffs"]["main"])


def _patch_live_ruleset(monkeypatch: pytest.MonkeyPatch, detail: dict) -> None:
    def fake_api_get(_api_url: str, path: str, _token: str):
        if path.endswith("/rulesets"):
            return [{"id": 1, "name": "main"}]
        if path.endswith("/rulesets/1"):
            return detail
        raise AssertionError(path)

    monkeypatch.setattr("github_moderator_audit.api_get", fake_api_get)


def _live_copy() -> dict:
    desired = load_json(ROOT / "config/github/rulesets/main-branch-protection.json")
    detail = json.loads(json.dumps(desired))
    detail["id"] = 1
    return detail


def test_run_audit_reports_bypass_actor_as_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    detail = _live_copy()
    detail["bypass_actors"] = list(_APP_BYPASS)
    _patch_live_ruleset(monkeypatch, detail)
    report = run_audit(
        root=ROOT,
        repo="tiktokagentur-art/gmv-foundation",
        token="dummy",
        api_url="https://api.github.com",
    )
    assert report["status"] == "drift"
    assert any(
        "bypass_actors" in item and "Integration" in item
        for item in report["diffs"]["main"]
    )
    observed = report["bypass_actors"]["main"]
    assert observed["readable"] is True
    assert observed["count"] == 1
    assert observed["notice"] is None


def test_run_audit_empty_bypass_actors_is_aligned(monkeypatch: pytest.MonkeyPatch) -> None:
    detail = _live_copy()
    detail["bypass_actors"] = []
    _patch_live_ruleset(monkeypatch, detail)
    report = run_audit(
        root=ROOT,
        repo="tiktokagentur-art/gmv-foundation",
        token="dummy",
        api_url="https://api.github.com",
    )
    assert report["status"] == "aligned"
    assert report["diffs"]["main"] == []
    observed = report["bypass_actors"]["main"]
    assert observed == {
        "readable": True,
        "count": 0,
        "api_state": "list",
        "notice": None,
    }


@pytest.mark.parametrize("api_state", ["missing", "null"])
def test_run_audit_unreadable_bypass_actors_is_warning_not_drift(
    monkeypatch: pytest.MonkeyPatch, api_state: str
) -> None:
    detail = _live_copy()
    if api_state == "missing":
        del detail["bypass_actors"]
    else:
        detail["bypass_actors"] = None
    _patch_live_ruleset(monkeypatch, detail)
    report = run_audit(
        root=ROOT,
        repo="tiktokagentur-art/gmv-foundation",
        token="dummy",
        api_url="https://api.github.com",
    )
    assert report["status"] == "bypass_actors_unverified"
    assert report["diffs"]["main"] == []
    observed = report["bypass_actors"]["main"]
    assert observed["readable"] is False
    assert observed["count"] is None
    assert observed["api_state"] == api_state
    assert observed["notice"] == "NICHT VERIFIZIERT"


def test_run_audit_keeps_drift_and_unverified_bypass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detail = _live_copy()
    del detail["bypass_actors"]
    detail["rules"] = [
        rule for rule in detail["rules"] if rule.get("type") != "required_status_checks"
    ]
    _patch_live_ruleset(monkeypatch, detail)
    report = run_audit(
        root=ROOT,
        repo="tiktokagentur-art/gmv-foundation",
        token="dummy",
        api_url="https://api.github.com",
    )
    assert report["status"] == "drift"
    assert any("required_status_checks" in item for item in report["diffs"]["main"])
    assert report["bypass_actors"]["main"]["notice"] == "NICHT VERIFIZIERT"
    assert report["bypass_actors"]["main"]["readable"] is False
    assert report["bypass_actors"]["main"]["count"] is None


def test_run_audit_blocks_on_forbidden() -> None:
    import io
    import urllib.error

    with patch(
        "github_moderator_audit.api_get",
        side_effect=urllib.error.HTTPError(
            "https://api.github.com",
            403,
            "Forbidden",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"Resource not accessible"}'),
        ),
    ):
        with pytest.raises(AuditError, match="BLOCKED"):
            run_audit(
                root=ROOT,
                repo="tiktokagentur-art/gmv-foundation",
                token="dummy",
                api_url="https://api.github.com",
            )


def test_main_blocks_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert main(["--token", ""]) == 3


def test_main_blocks_non_allowlisted_repo() -> None:
    assert main(["--repo", "tiktokagentur-art/other", "--token", "x"]) == 2


def test_expect_aligned_stays_green_when_bypass_actors_unverified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    detail = _live_copy()
    del detail["bypass_actors"]
    _patch_live_ruleset(monkeypatch, detail)
    summary = tmp_path / "summary.md"
    report_path = tmp_path / "audit.json"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    code = main(
        [
            "--token",
            "dummy",
            "--expect-aligned",
            "--report",
            str(report_path),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err.count("::warning::") == 1
    assert "NICHT VERIFIZIERT" in captured.err
    assert summary.read_text(encoding="utf-8").count("NICHT VERIFIZIERT") == 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "bypass_actors_unverified"
    assert payload["bypass_actors"]["main"]["readable"] is False
    assert payload["bypass_actors"]["main"]["count"] is None
    assert "NICHT VERIFIZIERT" in report_path.read_text(encoding="utf-8")


def test_expect_aligned_fails_on_non_empty_bypass_actors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    detail = _live_copy()
    detail["bypass_actors"] = list(_APP_BYPASS)
    _patch_live_ruleset(monkeypatch, detail)
    code = main(["--token", "dummy", "--expect-aligned"])
    captured = capsys.readouterr()
    assert code == 5
    assert "::warning::" not in captured.err
    assert "NICHT VERIFIZIERT" not in captured.out


def test_expect_aligned_passes_when_bypass_actors_empty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    detail = _live_copy()
    detail["bypass_actors"] = []
    _patch_live_ruleset(monkeypatch, detail)
    code = main(["--token", "dummy", "--expect-aligned"])
    captured = capsys.readouterr()
    assert code == 0
    assert "::warning::" not in captured.err
    report = json.loads(captured.out)
    assert report["status"] == "aligned"
    assert report["bypass_actors"]["main"]["readable"] is True
    assert report["bypass_actors"]["main"]["count"] == 0


def test_expect_aligned_fails_on_drift_but_still_warns_when_unverified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    detail = _live_copy()
    detail["bypass_actors"] = None
    detail["rules"] = [
        rule for rule in detail["rules"] if rule.get("type") != "deletion"
    ]
    _patch_live_ruleset(monkeypatch, detail)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    code = main(["--token", "dummy", "--expect-aligned"])
    captured = capsys.readouterr()
    assert code == 5
    assert captured.err.count("::warning::") == 1
    assert "NICHT VERIFIZIERT" in captured.err
    assert summary.read_text(encoding="utf-8").count("NICHT VERIFIZIERT") == 1
    report = json.loads(captured.out)
    assert report["status"] == "drift"
    assert report["bypass_actors"]["main"]["api_state"] == "null"
    assert report["bypass_actors"]["main"]["count"] is None


def test_unverified_warning_is_a_single_annotation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    emit_unverified_bypass_warning(
        {
            "bypass_actors": {
                "main": {
                    "notice": "NICHT VERIFIZIERT",
                    "api_state": "missing",
                    "readable": False,
                    "count": None,
                },
                "release": {
                    "notice": "NICHT VERIFIZIERT",
                    "api_state": "null",
                    "readable": False,
                    "count": None,
                },
            }
        }
    )
    captured = capsys.readouterr()
    assert captured.err.count("::warning::") == 1
    assert "main api_state=missing" in captured.err
    assert "release api_state=null" in captured.err
    text = summary.read_text(encoding="utf-8")
    assert text.count("NICHT VERIFIZIERT") == 1
    assert text.strip() == "bypass_actors: NICHT VERIFIZIERT"
