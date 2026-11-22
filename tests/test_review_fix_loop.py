"""RFL-001 offline policy tests: no API, no writes, no merge rights."""

import json
import sys

import pytest
from pydantic import ValidationError

from app.review_fix_loop import LoopSnapshot, _eligible_path, evaluate, main

SHA = "a" * 40


def sample(**changes):
    data = {
        "schema_version": 1,
        "repository": "tiktokagentur-art/gmv-foundation",
        "pr_number": 101,
        "pr_state": "open",
        "draft": True,
        "head_sha": SHA,
        "review_head_sha": SHA,
        "checks_head_sha": SHA,
        "author_id": "author",
        "reviewer_id": "codex-review-bot",
        "review_source": "codex_review",
        "review_completed": True,
        "review_state": "COMMENTED",
        "risk_class": "R0",
        "changed_files": [{"path": "docs/guides/readme.md", "status": "modified"}],
        "findings": [{"path": "docs/guides/readme.md", "priority": "P2"}],
        "passed_checks": ["Lint and structure", "Backend", "Image"],
        "approved_paths": ["docs/guides/readme.md"],
        "category_approved": True,
        "fix_attempts": 0,
        "spend_limit_cents": 100,
        "spent_cents": 10,
        "estimated_next_fix_cents": 50,
    }
    data.update(changes)
    return LoopSnapshot.model_validate(data)


def decision(**kwargs):
    return evaluate(sample(**kwargs))


def test_eligible_low_risk_is_only_a_proposal():
    outcome = decision()
    assert outcome.next_action == "PROPOSE_FIX_ONLY"
    assert outcome.reasons == ()
    assert outcome.remaining_attempts == 2
    assert outcome.estimated_remaining_budget_cents == 90
    assert not outcome.write_authorized
    assert not outcome.merge_authorized
    assert not outcome.deploy_authorized


def test_clean_review_requests_formal_approval_not_merge():
    outcome = decision(findings=[])
    assert outcome.next_action == "REQUEST_FINAL_REVIEW"
    assert outcome.merge_authorized is False


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"pr_state": "closed"}, "pilot_requires_open_draft_pr"),
        ({"draft": False}, "pilot_requires_open_draft_pr"),
        ({"review_head_sha": "b" * 40}, "stale_review"),
        ({"checks_head_sha": "c" * 40}, "stale_ci"),
        ({"head_sha": "not-a-sha"}, "invalid_sha"),
        ({"reviewer_id": "author"}, "self_review"),
        ({"review_completed": False}, "review_not_completed"),
        ({"review_state": "DISMISSED"}, "review_not_completed"),
        ({"passed_checks": ["Backend"]}, "required_checks_missing"),
        ({"risk_class": "R3"}, "risk_requires_manual_review"),
        ({"category_approved": False}, "category_not_approved"),
        ({"approved_paths": []}, "unapproved_paths"),
        ({"fix_attempts": 2}, "fix_attempt_limit_reached"),
        ({"spend_limit_cents": 0}, "hard_budget_not_configured"),
        ({"estimated_next_fix_cents": 0}, "hard_budget_not_configured"),
        ({"spent_cents": 60}, "hard_budget_exceeded"),
        (
            {"findings": [{"path": "docs/guides/readme.md", "priority": "P0"}]},
            "high_priority_finding_requires_manual_review",
        ),
        (
            {"findings": [{"path": "other/file.py", "priority": "P2"}]},
            "finding_outside_change_scope",
        ),
        (
            {"changed_files": [{"path": "docs/guides/readme.md", "status": "removed"}]},
            "unsafe_change_scope",
        ),
        (
            {"changed_files": [
                {"path": "docs/guides/readme.md", "status": "modified"},
                {"path": "docs/guides/readme.md", "status": "added"},
            ]},
            "invalid_change_scope",
        ),
        (
            {"changed_files": [
                {"path": "docs/guides/readme.md", "status": "modified"},
                {"path": "app/main.py", "status": "modified"},
            ], "approved_paths": ["docs/guides/readme.md", "app/main.py"]},
            "unsafe_change_scope",
        ),
    ],
)
def test_blocks_unsafe_events(changes, reason):
    outcome = decision(**changes)
    assert outcome.next_action == "BLOCKED"
    assert reason in outcome.reasons
    assert not outcome.write_authorized


@pytest.mark.parametrize("path", [
    "docs/guides/../app.py",
    "/docs/guides/test.md",
    "docs//guides/test.md",
    "docs/guides/x\\y.md",
    "docs/guides/test.md\n",
    "app/main.py",
    ".github/workflows/ci.yml",
    "docs/tutorials/payload.py",
])
def test_path_scope_fail_closed(path):
    assert not _eligible_path(path, "R0")


def test_exact_budget_and_final_attempt_are_still_candidates():
    outcome = decision(fix_attempts=1, spent_cents=50, estimated_next_fix_cents=50)
    assert outcome.next_action == "PROPOSE_FIX_ONLY"
    assert outcome.remaining_attempts == 1


def test_clean_review_can_finish_after_second_fix_and_budget_exhaustion():
    outcome = decision(
        findings=[],
        fix_attempts=2,
        spent_cents=100,
        spend_limit_cents=100,
        estimated_next_fix_cents=0,
    )
    assert outcome.next_action == "REQUEST_FINAL_REVIEW"
    assert outcome.remaining_attempts == 0
    assert not outcome.write_authorized
    assert not outcome.merge_authorized


def test_clean_review_without_new_fix_budget_is_not_blocked():
    outcome = decision(
        findings=[],
        spend_limit_cents=0,
        spent_cents=0,
        estimated_next_fix_cents=0,
    )
    assert outcome.next_action == "REQUEST_FINAL_REVIEW"
    assert not outcome.merge_authorized


def test_r1_fixture_scope():
    outcome = decision(
        risk_class="R1",
        changed_files=[{"path": "tests/fixtures/mock.json", "status": "modified"}],
        findings=[{"path": "tests/fixtures/mock.json", "priority": "P3"}],
        approved_paths=["tests/fixtures/mock.json"],
    )
    assert outcome.next_action == "PROPOSE_FIX_ONLY"


def test_p2_from_pr64_is_not_low_risk():
    outcome = decision(
        risk_class="R3",
        changed_files=[{"path": "app/codex_review_evidence.py", "status": "modified"}],
        findings=[{"path": "app/codex_review_evidence.py", "priority": "P2"}],
        approved_paths=["app/codex_review_evidence.py"],
    )
    assert outcome.next_action == "BLOCKED"
    assert "risk_requires_manual_review" in outcome.reasons


def test_unexpected_fields_and_wrong_schema_rejected():
    data = sample().model_dump()
    data["authorization_override"] = True
    with pytest.raises(ValidationError):
        LoopSnapshot.model_validate(data)
    data.pop("authorization_override")
    data["schema_version"] = 2
    with pytest.raises(ValidationError):
        LoopSnapshot.model_validate(data)


def test_cli_invalid_json_produces_structured_denial(tmp_path, monkeypatch, capsys):
    fixture = tmp_path / "invalid.json"
    fixture.write_text("{ bad", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["review_fix_loop", str(fixture)])
    assert main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["next_action"] == "BLOCKED"
    assert not result["merge_authorized"]


def test_cli_nominal_is_a_nonexecuting_proposal(tmp_path, monkeypatch, capsys):
    fixture = tmp_path / "snapshot.json"
    fixture.write_text(sample().model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["review_fix_loop", str(fixture)])
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["next_action"] == "PROPOSE_FIX_ONLY"
    assert result["write_authorized"] is False
