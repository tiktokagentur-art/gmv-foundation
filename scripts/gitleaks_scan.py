#!/usr/bin/env python3
"""Scan full git history with pinned gitleaks and prove a synthetic secret fails.

Organization repositories need a license before the hosted GitHub Action will run.
This script downloads the upstream binary instead and never reads a license secret.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITLEAKS_VERSION = "8.30.1"
GITLEAKS_SHA256 = "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
ARCHIVE_NAME = f"gitleaks_{GITLEAKS_VERSION}_linux_x64.tar.gz"
DOWNLOAD_URL = (
    "https://github.com/gitleaks/gitleaks/releases/download/"
    f"v{GITLEAKS_VERSION}/{ARCHIVE_NAME}"
)
SYNTHETIC_RULE_ID = "aws-access-token"


class GitleaksError(RuntimeError):
    """The scan could not prove a clean history and a failing fixture."""


@dataclass(frozen=True)
class Finding:
    rule_id: str
    file: str
    line: int
    commit: str


def synthetic_access_key() -> str:
    """Return an obvious fake that matches the pinned aws-access-token rule.

    The fragments stay separate in this file. Gitleaks only sees the joined
    value inside a temporary repository outside this tree. The body is the
    rule alphabet in order, so the value is not a credential.
    """
    prefix = "A" + "KIA"
    body = "".join(("MNPQ", "RSTU", "VWXY", "Z234"))
    return prefix + body


def main() -> int:
    try:
        assert_full_history(ROOT)
        binary = ensure_binary()
        config = repo_config()
        findings = scan_git(binary, ROOT, config=config)
        with tempfile.TemporaryDirectory(prefix="gitleaks-fixture-") as tmp:
            fixture = prove_synthetic(binary, Path(tmp), config=config)
    except GitleaksError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if findings:
        _print_findings(findings)
        print(f"{len(findings)} secret(s) found", file=sys.stderr)
        return 1
    if not any(item.rule_id == SYNTHETIC_RULE_ID for item in fixture):
        print("error: synthetic secret was not detected", file=sys.stderr)
        return 1
    count = _commit_count(ROOT)
    print(
        f"gitleaks {GITLEAKS_VERSION}: {count} commits clean; "
        "synthetic secret failed the scan"
    )
    return 0


def assert_full_history(repo: Path) -> None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--is-shallow-repository"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GitleaksError("git history is not available for the secret scan")
    if proc.stdout.strip() == "true":
        raise GitleaksError(
            "refusing a shallow clone; the secret scan needs full git history "
            "(fetch-depth: 0)"
        )


def ensure_binary() -> Path:
    override = os.environ.get("GITLEAKS_BIN", "").strip()
    if override:
        binary = Path(override)
        _require_version(binary)
        return binary
    if sys.platform != "linux" or platform.machine() != "x86_64":
        raise GitleaksError(
            "pinned gitleaks archive is linux/x86_64, matching GitHub-hosted runners"
        )
    cache = Path.home() / ".cache" / "gmv-foundation" / "gitleaks" / GITLEAKS_VERSION
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / ARCHIVE_NAME
    binary = cache / "gitleaks"
    if not archive.is_file() or _sha256(archive) != GITLEAKS_SHA256:
        _download(archive)
    digest = _sha256(archive)
    if digest != GITLEAKS_SHA256:
        raise GitleaksError("gitleaks archive checksum mismatch")
    _extract(archive, binary)
    _require_version(binary)
    return binary


def scan_git(binary: Path, repo: Path, *, config: Path | None) -> list[Finding]:
    with tempfile.TemporaryDirectory(prefix="gitleaks-report-") as tmp:
        report = Path(tmp) / "report.json"
        command = [
            str(binary),
            "git",
            str(repo),
            "--no-banner",
            "--redact",
            "--log-level=error",
            "--log-opts=--all",
            "--report-format=json",
            "--report-path",
            str(report),
            "--exit-code=1",
        ]
        if config is not None:
            command.extend(["--config", str(config)])
        proc = subprocess.run(command, check=False, capture_output=True, text=True)
        findings = _read_findings(report)
    if proc.returncode not in (0, 1):
        detail = _redact_synthetic((proc.stderr or proc.stdout).strip())
        raise GitleaksError(detail or f"gitleaks exited {proc.returncode}")
    if proc.returncode == 0 and findings:
        raise GitleaksError("gitleaks reported findings with exit code 0")
    if proc.returncode == 1 and not findings:
        raise GitleaksError("gitleaks exited 1 without a report")
    return findings


def prove_synthetic(binary: Path, work: Path, *, config: Path | None = None) -> list[Finding]:
    repo = work / "fixture"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "config", "user.name", "Gitleaks Fixture")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "leak.txt").write_text(
        "# synthetic fixture, not a credential\n"
        "aws_access_key_id=" + synthetic_access_key() + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", "leak.txt")
    _git(repo, "commit", "-m", "synthetic fixture")
    findings = scan_git(binary, repo, config=config)
    if not any(item.rule_id == SYNTHETIC_RULE_ID for item in findings):
        raise GitleaksError("synthetic secret was not detected")
    return findings


def repo_config() -> Path | None:
    path = ROOT / ".gitleaks.toml"
    return path if path.is_file() else None


def _download(dest: Path) -> None:
    partial = dest.with_name(dest.name + ".part")
    request = urllib.request.Request(
        DOWNLOAD_URL,
        headers={"User-Agent": "gmv-foundation-gitleaks-scan"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            partial.write_bytes(response.read())
        digest = _sha256(partial)
        if digest != GITLEAKS_SHA256:
            raise GitleaksError("gitleaks archive checksum mismatch")
        partial.replace(dest)
    except GitleaksError:
        partial.unlink(missing_ok=True)
        raise
    except Exception as exc:
        partial.unlink(missing_ok=True)
        raise GitleaksError(f"gitleaks download failed: {exc}") from exc


def _extract(archive: Path, binary: Path) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        try:
            member = tar.getmember("gitleaks")
        except KeyError as exc:
            raise GitleaksError("gitleaks binary missing from archive") from exc
        if not member.isfile() or member.name != "gitleaks":
            raise GitleaksError("gitleaks archive layout is unexpected")
        extracted = tar.extractfile(member)
        if extracted is None:
            raise GitleaksError("gitleaks binary missing from archive")
        payload = extracted.read()
    binary.write_bytes(payload)
    binary.chmod(0o755)


def _require_version(binary: Path) -> None:
    proc = subprocess.run(
        [str(binary), "version"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or proc.stdout.strip() != GITLEAKS_VERSION:
        raise GitleaksError(f"gitleaks version must be {GITLEAKS_VERSION}")


def _read_findings(report: Path) -> list[Finding]:
    if not report.is_file() or report.stat().st_size == 0:
        return []
    payload = json.loads(report.read_text(encoding="utf-8"))
    if not payload:
        return []
    if not isinstance(payload, list):
        raise GitleaksError("gitleaks report has an unexpected shape")
    findings: list[Finding] = []
    for item in payload:
        findings.append(
            Finding(
                rule_id=str(item.get("RuleID") or ""),
                file=str(item.get("File") or ""),
                line=int(item.get("StartLine") or 0),
                commit=str(item.get("Commit") or ""),
            )
        )
    return findings


def _print_findings(findings: list[Finding]) -> None:
    for item in findings:
        print(
            f"leak: rule={item.rule_id} file={item.file} line={item.line} commit={item.commit}",
            file=sys.stderr,
        )


def _git(repo: Path, *args: str) -> None:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = _redact_synthetic((proc.stderr or proc.stdout).strip())
        raise GitleaksError(detail or f"git {args[0]} failed")


def _commit_count(repo: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--all", "--count"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GitleaksError("git rev-list failed")
    return proc.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redact_synthetic(text: str) -> str:
    return text.replace(synthetic_access_key(), "[REDACTED]")


if __name__ == "__main__":
    sys.exit(main())
