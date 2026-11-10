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

from github_moderator_audit import AuditError, main, run_audit  # noqa: E402
from github_moderator_lib import compare_rulesets, load_json  # noqa: E402


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
    bypass = [
        {
            "actor_id": 424242,
            "actor_type": "Integration",
            "bypass_mode": "always",
        }
    ]
    actual["bypass_actors"] = bypass
    diffs = compare_rulesets(desired, actual)
    assert diffs == [f"bypass_actors: actual={bypass!r} desired={[]!r}"]


def test_compare_omitted_bypass_actors_is_drift() -> None:
    desired = load_json(ROOT / "config/github/rulesets/main-branch-protection.json")
    actual = json.loads(json.dumps(desired))
    del actual["bypass_actors"]
    diffs = compare_rulesets(desired, actual)
    assert len(diffs) == 1
    assert diffs[0].startswith("bypass_actors: unverifiable (API value missing;")
    assert "Not treated as []" in diffs[0]
    assert "desired=[]" in diffs[0]


def test_compare_null_bypass_actors_is_drift() -> None:
    desired = load_json(ROOT / "config/github/rulesets/main-branch-protection.json")
    actual = json.loads(json.dumps(desired))
    actual["bypass_actors"] = None
    diffs = compare_rulesets(desired, actual)
    assert len(diffs) == 1
    assert diffs[0].startswith("bypass_actors: unverifiable (API value null;")
    assert "Not treated as []" in diffs[0]
    assert "desired=[]" in diffs[0]


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


def test_run_audit_reports_bypass_actor_as_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    desired = load_json(ROOT / "config/github/rulesets/main-branch-protection.json")
    actual_detail = json.loads(json.dumps(desired))
    actual_detail["id"] = 1
    actual_detail["bypass_actors"] = [
        {
            "actor_id": 424242,
            "actor_type": "Integration",
            "bypass_mode": "always",
        }
    ]

    def fake_api_get(_api_url: str, path: str, _token: str):
        if path.endswith("/rulesets"):
            return [{"id": 1, "name": "main"}]
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
    assert any(
        "bypass_actors" in item and "Integration" in item
        for item in report["diffs"]["main"]
    )


def test_run_audit_reports_omitted_bypass_actors_as_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    desired = load_json(ROOT / "config/github/rulesets/main-branch-protection.json")
    actual_detail = json.loads(json.dumps(desired))
    actual_detail["id"] = 1
    del actual_detail["bypass_actors"]

    def fake_api_get(_api_url: str, path: str, _token: str):
        if path.endswith("/rulesets"):
            return [{"id": 1, "name": "main"}]
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
    joined = "\n".join(report["diffs"]["main"])
    assert "bypass_actors: unverifiable (API value missing;" in joined
    assert "Not treated as []" in joined


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
