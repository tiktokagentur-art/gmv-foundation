#!/usr/bin/env python3
"""Generate bounded Codex Cloud task handoffs from a curated local queue.

The tool is intentionally offline: it reads a JSON file and prints text.
It does not start Codex, authenticate, read GitHub, or mutate any resource.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

EXPECTED_REPO = "tiktokagentur-art/gmv-foundation"
SCHEMA_VERSION = 1
MAX_TASKS = 3
ID_RE = re.compile(r"^[A-Z][A-Z0-9-]{2,63}$")
DEFAULT_QUEUE = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "codex-dispatcher-a"
    / "example-queue.json"
)


def safe_text(value: Any, field: str, limit: int = 1200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"invalid {field}: expected nonempty short text")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"invalid {field}: control character")
    return value.strip()


def read_queue(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {
        "schema_version", "repository", "handoff_mode", "tasks"
    }:
        raise ValueError("unsupported queue document structure")
    if document["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported schema version")
    if document["repository"] != EXPECTED_REPO:
        raise ValueError("repository mismatch")
    if document["handoff_mode"] != "MANUAL_CODEX_CLOUD":
        raise ValueError("automatic execution is not supported")
    tasks = document["tasks"]
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= MAX_TASKS:
        raise ValueError("queue must contain between one and three tasks")

    seen_ids: set[str] = set()
    seen_sources: set[tuple[str, int]] = set()
    for task in tasks:
        if not isinstance(task, dict) or set(task) != {
            "task_id", "title", "source", "scope", "acceptance", "handoff_status"
        }:
            raise ValueError("unexpected task structure")
        task_id = safe_text(task["task_id"], "task_id", 64)
        if not ID_RE.fullmatch(task_id):
            raise ValueError("invalid task identifier")
        safe_text(task["title"], "title", 160)
        safe_text(task["scope"], "scope")
        if task["handoff_status"] != "PROPOSED_NOT_STARTED":
            raise ValueError("only proposed, non-started tasks are supported")
        source = task["source"]
        if not isinstance(source, dict) or set(source) != {"kind", "number"}:
            raise ValueError("invalid source reference")
        kind = source["kind"]
        number = source["number"]
        if kind not in {"issue", "pull"} or type(number) is not int or number <= 0:
            raise ValueError("invalid source type or number")
        acceptance = task["acceptance"]
        if not isinstance(acceptance, list) or not 1 <= len(acceptance) <= 8:
            raise ValueError("acceptance must have between one and eight criteria")
        for criterion in acceptance:
            safe_text(criterion, "acceptance criterion", 300)
        if task_id in seen_ids or (kind, number) in seen_sources:
            raise ValueError("duplicate task or source")
        seen_ids.add(task_id)
        seen_sources.add((kind, number))
    return tasks


def source_url(task: dict[str, Any]) -> str:
    source = task["source"]
    path = "issues" if source["kind"] == "issue" else "pull"
    return f"https://github.com/{EXPECTED_REPO}/{path}/{source['number']}"


def render_handoff(task: dict[str, Any]) -> str:
    criteria = "\n".join(f"- {item}" for item in task["acceptance"])
    return (
        "# Pizza Club | Codex-Cloud-Arbeitspaket (manuelle Übergabe)\n\n"
        f"Auftrag: {task['task_id']} – {task['title']}\n"
        f"Repository: {EXPECTED_REPO}\n"
        f"Referenz: {source_url(task)}\n"
        "Status: PROPOSED_NOT_STARTED; keine Aufgabenannahme, kein Codex-Start.\n\n"
        "## Ziel und Scope\n"
        f"{task['scope']}\n\n"
        "## Pflichtablauf\n"
        "1. Repository, offene Issues/PRs und bestehende Workflows read-only prüfen.\n"
        "2. Dubletten, bestehende Implementierungen und Branch-Abhängigkeiten dokumentieren.\n"
        "3. Erst nach manueller Aufgabenannahme in Codex Cloud isoliert arbeiten.\n"
        "4. Nur einen separaten Feature-Branch und einen Draft-PR für neue Änderungen nutzen; "
        "bestehende PRs zuerst prüfen und nicht duplizieren.\n"
        "5. Tests, reproduzierbare Nachweise, Risiken und offene Freigaben dokumentieren.\n\n"
        "## Abnahmekriterien\n"
        f"{criteria}\n\n"
        "## Sicherheits- und Kosten-Gates\n"
        "- Kein Merge, kein Deployment und keine Änderung an Produktion oder main.\n"
        "- Keine Rechte-, IAM-, Ruleset-, Secret- oder Environment-Änderung.\n"
        "- Keine echten Kundendaten, keine Zugangsdaten in Prompts, Commits oder Logs.\n"
        "- Keine separaten Modell-API-Aufrufe oder API-Keys; verwende ausschließlich "
        "eine vom Nutzer freigegebene Codex-Cloud-Sitzung im ChatGPT-Tarif.\n"
        "- Keine neuen autonom laufenden Trigger, Scheduled Jobs oder Worker-Claims.\n"
        "- CI und unabhängige Review als Nachweise; deren Erfolg ist keine Merge-Freigabe.\n\n"
        "## Ergebnisformat\n"
        "Ist-Bestand, Dubletten, umgesetzter Umfang, Testkommandos und Resultate, "
        "Draft-PR-Link, Risiken, offene Gates und nächste zulässige Schritte.\n\n"
        "Wichtig: Dieses Paket ist ein Vorschlag für die manuelle Übergabe. "
        "Es erzeugt weder einen Codex-Lauf noch eine betriebliche Freigabe.\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true", help="show queued proposals")
    action.add_argument("--task", help="print one manual Codex Cloud handoff")
    args = parser.parse_args(argv)
    try:
        tasks = read_queue(args.queue)
        if args.list:
            for task in tasks:
                print(f"{task['task_id']} | PROPOSED_NOT_STARTED | {source_url(task)}")
            return 0
        match = next((task for task in tasks if task["task_id"] == args.task), None)
        if match is None:
            raise ValueError("unknown task identifier")
        print(render_handoff(match), end="")
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"handoff blocked: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
