from app.pr_review.gates import REQUIRED_CHECKS, evaluate
from app.pr_review.mock_reviewer import mock_review
from app.pr_review.schemas import Change, GateInputs, ReviewRequest, Verdict


def request(path="docs/guides/a.md"):
    return ReviewRequest(
        pr_number=60, head_sha="a" * 40, author_id="author",
        changes=(Change(path=path, status="added"),),
    )


def test_even_perfect_synthetic_evidence_cannot_merge():
    req = request()
    decision = evaluate(GateInputs(
        request=req, evidence=mock_review(req, "reviewer"),
        passed_checks=REQUIRED_CHECKS, deployment_separated=True,
        category_approved=True,
    ))
    assert decision.verdict == Verdict.DENY
    assert "synthetic_review_not_formal_approval" in decision.reasons


def test_missing_checks_and_deployment_block():
    req = request()
    decision = evaluate(GateInputs(request=req))
    assert "required_checks_missing" in decision.reasons
    assert "deployment_not_separated" in decision.reasons


def test_stale_review_blocks():
    req = request()
    evidence = mock_review(req.model_copy(update={"head_sha": "b" * 40}), "reviewer")
    decision = evaluate(GateInputs(request=req, evidence=evidence))
    assert "stale_review" in decision.reasons


def test_application_code_is_ineligible():
    req = request("app/main.py")
    decision = evaluate(GateInputs(request=req))
    assert "risk_not_eligible" in decision.reasons
