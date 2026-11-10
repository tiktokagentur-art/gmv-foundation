"""Pinned gitleaks fails on a synthetic secret that is not stored in the tree."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gitleaks_scan import (  # noqa: E402
    SYNTHETIC_RULE_ID,
    GitleaksError,
    assert_full_history,
    ensure_binary,
    prove_synthetic,
    repo_config,
    synthetic_access_key,
)

SKIP_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}


def test_synthetic_value_is_absent_from_the_worktree() -> None:
    secret = synthetic_access_key().encode()
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if secret in path.read_bytes():
            pytest.fail(f"{relative.as_posix()} contains the assembled fixture value")


def test_gitleaks_detects_synthetic_secret(tmp_path: Path) -> None:
    findings = prove_synthetic(ensure_binary(), tmp_path, config=repo_config())
    assert {item.rule_id for item in findings} == {SYNTHETIC_RULE_ID}
    assert {item.file for item in findings} == {"leak.txt"}


def test_shallow_clone_is_rejected(tmp_path: Path) -> None:
    dest = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{ROOT}", str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    with pytest.raises(GitleaksError, match="shallow"):
        assert_full_history(dest)
