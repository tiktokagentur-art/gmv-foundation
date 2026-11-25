import pytest
from pydantic import ValidationError

from app.pr_review.schemas import Change, ReviewRequest


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        Change(path="docs/guides/a.md", status="added", unexpected=True)


def test_unsupported_schema_version_rejected():
    with pytest.raises(ValidationError):
        ReviewRequest(
            schema_version=2, pr_number=1, head_sha="a" * 40,
            author_id="writer", changes=(Change(path="docs/guides/a.md", status="added"),),
        )


def test_empty_change_set_rejected():
    with pytest.raises(ValidationError):
        ReviewRequest(pr_number=1, head_sha="a" * 40, author_id="writer", changes=())
