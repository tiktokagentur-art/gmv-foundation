#!/usr/bin/env python3
"""Prüft JSON-Briefings für die Content Factory."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from schema_check import check_fields, is_nonempty_text, load_json, report_errors  # noqa: E402

TEXT_FIELDS = ("thema", "zielgruppe", "format", "rechteinformationen")
REQUIRED_FIELDS = (*TEXT_FIELDS, "quellen")


def validate(briefing: object) -> list[tuple[str, str]]:
    if not isinstance(briefing, dict):
        return [("$", "Ein JSON-Objekt wird erwartet.")]

    missing, unknown = check_fields(briefing, REQUIRED_FIELDS)
    errors = [(field, "Pflichtfeld fehlt.") for field in missing]

    for field in TEXT_FIELDS:
        if field in briefing and not is_nonempty_text(briefing[field]):
            errors.append((field, "Eine nicht leere Zeichenkette wird erwartet."))

    if "quellen" in briefing:
        sources = briefing["quellen"]
        if not isinstance(sources, list) or not sources:
            errors.append(("quellen", "Eine Liste mit mindestens einer Quelle wird erwartet."))
        else:
            for index, source in enumerate(sources):
                if not is_nonempty_text(source):
                    errors.append((f"quellen[{index}]", "Die Quelle muss nicht leerer Text sein."))

    for field in unknown:
        label = json.dumps(field)[1:-1] if field else '""'
        errors.append((label, "Unbekanntes Feld."))

    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("datei", nargs="+", type=Path, help="Pfad zu einem JSON-Briefing")
    args = parser.parse_args(argv)

    status = 0
    for path in args.datei:
        filename = str(path).replace("\r", r"\r").replace("\n", r"\n")
        briefing, load_error = load_json(path)
        if load_error is not None:
            message = (
                "Datei kann nicht als UTF-8 gelesen werden."
                if load_error == "read"
                else "Ungültiges JSON."
            )
            status = report_errors([f"{filename}: $: {message}"], exit_code=2)
            continue

        errors = (f"{filename}: {field}: {message}" for field, message in validate(briefing))
        status = max(status, report_errors(errors))

    return status


if __name__ == "__main__":
    sys.exit(main())
