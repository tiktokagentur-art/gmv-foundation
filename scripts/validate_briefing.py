#!/usr/bin/env python3
"""Prüft JSON-Briefings für die Content Factory."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

TEXT_FIELDS = ("thema", "zielgruppe", "format", "rechteinformationen")
REQUIRED_FIELDS = (*TEXT_FIELDS, "quellen")


def validate(briefing: object) -> list[tuple[str, str]]:
    if not isinstance(briefing, dict):
        return [("$", "Ein JSON-Objekt wird erwartet.")]

    errors = []
    for field in REQUIRED_FIELDS:
        if field not in briefing:
            errors.append((field, "Pflichtfeld fehlt."))

    for field in TEXT_FIELDS:
        if field in briefing:
            value = briefing[field]
            if not isinstance(value, str) or not value.strip():
                errors.append((field, "Eine nicht leere Zeichenkette wird erwartet."))

    if "quellen" in briefing:
        sources = briefing["quellen"]
        if not isinstance(sources, list) or not sources:
            errors.append(("quellen", "Eine Liste mit mindestens einer Quelle wird erwartet."))
        else:
            for index, source in enumerate(sources):
                if not isinstance(source, str) or not source.strip():
                    errors.append((f"quellen[{index}]", "Die Quelle muss nicht leerer Text sein."))

    for field in sorted(briefing.keys() - REQUIRED_FIELDS):
        label = json.dumps(field)[1:-1] if field else '""'
        errors.append((label, "Unbekanntes Feld."))

    return errors


def reject_constant(value: str) -> None:
    raise ValueError(f"Unzulässige JSON-Konstante {value}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("datei", nargs="+", type=Path, help="Pfad zu einem JSON-Briefing")
    args = parser.parse_args(argv)

    status = 0
    for path in args.datei:
        filename = str(path).replace("\r", r"\r").replace("\n", r"\n")
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            print(f"{filename}: $: Datei kann nicht als UTF-8 gelesen werden.", file=sys.stderr)
            status = 2
            continue

        try:
            briefing = json.loads(content, parse_constant=reject_constant)
        except (ValueError, RecursionError):
            print(f"{filename}: $: Ungültiges JSON.", file=sys.stderr)
            status = 2
            continue

        for field, message in validate(briefing):
            print(f"{filename}: {field}: {message}", file=sys.stderr)
            status = max(status, 1)

    return status


if __name__ == "__main__":
    sys.exit(main())
