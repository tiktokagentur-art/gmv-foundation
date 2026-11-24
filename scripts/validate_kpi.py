"""Prüft eine Liste von Kennzahlen im JSON-Format."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from schema_check import (  # noqa: E402
    check_fields,
    is_nonempty_text,
    load_json,
    report_errors,
)

TEXT_FIELDS = ("name", "definition", "messmethode")
VALUE_FIELDS = ("ist_baseline", "zielwert")
KPI_FIELDS = ("id", *TEXT_FIELDS, *VALUE_FIELDS, "status", "quelle")


def _check_entry(
    entry: dict[str, object], label: str, seen_ids: set[str], errors: list[str]
) -> None:
    entry_id = entry.get("id")
    if isinstance(entry_id, str) and is_nonempty_text(entry_id):
        label = json.dumps(entry_id)[1:-1]
        if entry_id in seen_ids:
            errors.append(f"{label}: id: doppelte ID")
        seen_ids.add(entry_id)
    elif "id" in entry:
        errors.append(f"{label}: id: nicht leere Zeichenkette erwartet")

    missing, unknown = check_fields(entry, KPI_FIELDS)
    for field in missing:
        errors.append(f"{label}: {field}: Pflichtfeld fehlt")
    for field in unknown:
        errors.append(f"{label}: {json.dumps(field)}: unbekanntes Feld")

    for field in TEXT_FIELDS:
        if field in entry and not is_nonempty_text(entry[field]):
            errors.append(f"{label}: {field}: nicht leere Zeichenkette erwartet")
    for field in VALUE_FIELDS:
        value = entry.get(field)
        is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
        if value is not None and not (is_number or is_nonempty_text(value)):
            errors.append(f"{label}: {field}: null, Zahl oder nicht leere Zeichenkette erwartet")

    status = entry.get("status")
    if "status" in entry and status not in ("kandidat", "bestaetigt"):
        errors.append(f"{label}: status: kandidat oder bestaetigt erwartet")
    if "zielwert" in entry:
        target = entry["zielwert"]
        if status == "kandidat" and target is not None:
            errors.append(f"{label}: zielwert: muss für kandidat null sein")
        elif status == "bestaetigt" and target is None:
            errors.append(f"{label}: zielwert: für bestaetigt erforderlich")

    if "quelle" in entry:
        source = entry["quelle"]
        if source is None and entry.get("ist_baseline") is not None:
            errors.append(f"{label}: quelle: bei gesetzter Ist-Baseline erforderlich")
        elif source is not None and not is_nonempty_text(source):
            errors.append(f"{label}: quelle: null oder nicht leere Zeichenkette erwartet")


def validate(document: object) -> list[str]:
    """Gibt Regelverletzungen für ein eingelesenes JSON-Dokument zurück."""
    if not isinstance(document, list):
        return ["datei: $: Liste von Kennzahlen erwartet"]

    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(document):
        label = f"eintrag[{index}]"
        if isinstance(entry, dict):
            _check_entry(entry, label, seen_ids, errors)
        else:
            errors.append(f"{label}: eintrag: Objekt erwartet")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("datei", type=Path, help="Pfad zur JSON-Datei")
    args = parser.parse_args(argv)

    document, load_error = load_json(args.datei)
    if load_error == "read":
        return report_errors(
            ["datei: datei: Datei kann nicht als UTF-8 gelesen werden"], exit_code=2
        )
    if load_error == "json":
        return report_errors(["datei: json: ungültiges JSON"], exit_code=2)
    return report_errors(validate(document))


if __name__ == "__main__":
    sys.exit(main())
