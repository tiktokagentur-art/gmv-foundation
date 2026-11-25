from app.pr_review.mock_reviewer import mock_review
from app.pr_review.schemas import Change, ReviewRequest


def request():
    return ReviewRequest(
        pr_number=60, head_sha="a" * 40, author_id="author",
        changes=(Change(path="docs/guides/a.md", status="added"),),
    )


def test_self_review_is_rejected():
    evidence = mock_review(request(), "author")
    assert not evidence.approved
    assert not evidence.independent


def test_separate_reviewer_remains_synthetic():
    evidence = mock_review(request(), "reviewer")
    assert evidence.approved
    assert evidence.independent
    assert evidence.synthetic
