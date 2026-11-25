import pytest

from app.pr_review.risk_policy import classify
from app.pr_review.schemas import Change, Risk


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("docs/guides/intro.md", Risk.R0),
        ("tests/fixtures/data.json", Risk.R1),
        ("docs/overview.md", Risk.R2),
        (".github/workflows/ci.yml", Risk.R3),
        ("app/main.py", Risk.R3),
        ("unknown/file.txt", Risk.R4),
        ("docs/../app/main.py", Risk.R4),
        ("/absolute/path.md", Risk.R4),
        ("docs//guides/a.md", Risk.R4),
    ],
)
def test_classification(path, expected):
    assert classify((Change(path=path, status="modified"),)) == expected


def test_highest_risk_wins():
    changes = (
        Change(path="docs/guides/intro.md", status="modified"),
        Change(path="app/main.py", status="modified"),
    )
    assert classify(changes) == Risk.R3


def test_deletion_is_not_low_risk():
    assert classify((Change(path="docs/guides/a.md", status="removed"),)) == Risk.R3
