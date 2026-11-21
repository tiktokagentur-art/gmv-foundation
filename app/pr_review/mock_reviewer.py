"""Synthetic reviewer evidence. Never constitutes a GitHub approval."""
from app.pr_review.schemas import ReviewEvidence, ReviewRequest


def mock_review(request: ReviewRequest, reviewer_id: str) -> ReviewEvidence:
    independent = bool(reviewer_id) and reviewer_id != request.author_id
    return ReviewEvidence(
        head_sha=request.head_sha,
        reviewer_id=reviewer_id or "unassigned",
        author_id=request.author_id,
        approved=independent,
        independent=independent,
        synthetic=True,
    )
