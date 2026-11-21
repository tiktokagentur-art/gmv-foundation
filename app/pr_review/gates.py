"""Fail-closed offline decision. Always DENY for real merge execution."""
from app.pr_review.risk_policy import classify
from app.pr_review.schemas import GateDecision, GateInputs, Risk, Verdict

REQUIRED_CHECKS = frozenset({"Lint and structure", "Backend", "Image"})


def evaluate(inputs: GateInputs) -> GateDecision:
    risk = classify(inputs.request.changes)
    reasons: list[str] = []
    evidence = inputs.evidence
    if risk not in (Risk.R0, Risk.R1):
        reasons.append("risk_not_eligible")
    if not inputs.category_approved:
        reasons.append("category_not_approved")
    if not inputs.deployment_separated:
        reasons.append("deployment_not_separated")
    if not REQUIRED_CHECKS.issubset(inputs.passed_checks):
        reasons.append("required_checks_missing")
    if evidence is None:
        reasons.append("review_missing")
    else:
        if evidence.synthetic:
            reasons.append("synthetic_review_not_formal_approval")
        if evidence.head_sha != inputs.request.head_sha:
            reasons.append("stale_review")
        if (
            not evidence.approved
            or not evidence.independent
            or evidence.reviewer_id == inputs.request.author_id
            or evidence.author_id != inputs.request.author_id
        ):
            reasons.append("independent_review_missing")
    if not reasons:
        # This is only a simulation; no actual approval or merge authority is conferred.
        reasons.append("offline_simulation_only")
    return GateDecision(verdict=Verdict.DENY, risk=risk, reasons=tuple(reasons))
