from app.codemode.gateway import Access, Gateway, Tool


def gateway():
    return Gateway(
        (Tool("github.issues.read", Access.READ), Tool("github.issues.write", Access.WRITE)),
        {"GMV-VE-001": frozenset({"github.issues.read", "github.issues.write"})},
    )


def test_unknown_actor_denied():
    assert gateway().authorize("unknown", "github.issues.read").reason == "not_granted"


def test_unknown_tool_denied():
    assert gateway().authorize("GMV-VE-001", "shell.exec").reason == "unknown_tool"


def test_missing_actor_denied():
    assert gateway().authorize("", "github.issues.read").reason == "missing_actor"


def test_granted_read_allowed():
    assert gateway().authorize("GMV-VE-001", "github.issues.read").allowed


def test_write_requires_approval():
    assert gateway().authorize("GMV-VE-001", "github.issues.write").reason == "approval_required"
    assert gateway().authorize("GMV-VE-001", "github.issues.write", approved=True).allowed


def test_duplicate_tool_rejected():
    import pytest

    with pytest.raises(ValueError):
        Gateway((Tool("x", Access.READ), Tool("x", Access.WRITE)), {})
