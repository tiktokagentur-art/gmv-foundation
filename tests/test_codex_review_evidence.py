"""CRG-001A: offline input consistency; never a GitHub approval."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from app.codex_review_evidence import evaluate_observation

REPO = "tiktokagentur-art/gmv-foundation"
SHA = "a" * 40


def observation():
    return {
        "schema_version": 1,
        "source": "github_api_snapshot",
        "repository": REPO,
        "pr_number": 101,
        "head_sha": SHA,
        "author_id": "author",
        "risk_class": "R0",
        "reviewer_id": "other",
        "review_commit_sha": SHA,
        "review_url": f"https://github.com/{REPO}/pull/101#pullrequestreview-111",
        "review_state": "COMMENTED",
        "passed_checks": ["Lint and structure", "Backend", "Image"],
        "unresolved_findings": 0,
        "synthetic": False,
    }


def result(data):
    return evaluate_observation(
        data,
        expected_repository=REPO,
        expected_pr=101,
        expected_head_sha=SHA,
        expected_author_id="author",
    )


def test_well_formed_observation_is_still_not_a_merge_approval():
    decision = result(observation())
    assert decision == {
        "verdict": "DENY",
        "merge_authorized": False,
        "reasons": ["github_source_not_authenticated"],
    }


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("review_commit_sha", "b" * 40, "stale_or_invalid_review"),
        ("head_sha", "b" * 40, "head_sha_mismatch"),
        ("reviewer_id", "author", "self_or_missing_reviewer"),
        ("synthetic", True, "synthetic_or_invalid_evidence"),
        ("passed_checks", ["Backend"], "required_checks_missing"),
        ("unresolved_findings", 1, "unresolved_or_invalid_findings"),
        ("review_state", "CHANGES_REQUESTED", "review_not_positive"),
        ("risk_class", "R4", "additional_security_review_required"),
        ("review_url", "https://github.com.evil.test/fake", "invalid_review_url"),
        ("review_url", "https://[", "invalid_review_url"),
        ("source", "local_fixture", "unknown_source"),
        ("pr_number", 999, "pr_mismatch"),
    ],
)
def test_fail_closed_changes(field, value, reason):
    data = observation()
    data[field] = value
    assert reason in result(data)["reasons"]
    assert result(data)["merge_authorized"] is False


def test_extra_field_rejected():
    data = observation()
    data["self_reported_approval"] = True
    assert "invalid_keys" in result(data)["reasons"]


def test_non_object_rejected():
    assert "invalid_payload" in result([])["reasons"]


def test_schema_rejects_extra_field():
    import json
    from pathlib import Path

    schema_path = (
        Path(__file__).resolve().parents[1]
        / "config/code-review/review-evidence-v1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    validator.validate(observation())
    invalid = deepcopy(observation())
    invalid["self_reported_approval"] = True
    with pytest.raises(ValidationError):
        validator.validate(invalid)
