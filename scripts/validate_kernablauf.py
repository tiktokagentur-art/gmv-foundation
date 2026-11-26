"""Prüft einen Portal-Kernablauf im JSON-Format."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from schema_check import check_fields, is_nonempty_text, load_json, report_errors  # noqa: E402

DOCUMENT_FIELDS = ("id", "haendler_rolle", "creator_rolle", "schritte")
STEP_FIELDS = ("id", "name", "status", "notiz")
STEP_NAMES = ("kampagne", "interesse", "musteranfrage", "entscheidung", "videolink", "feedback")
STATUSES = ("offen", "in_arbeit", "erledigt", "nicht_zutreffend")


def _label(value: str) -> str:
    return json.dumps(value)[1:-1].replace(":", r"\u003a")


def _check_fields(record, fields, label, errors):
    missing, unknown = check_fields(record, fields)
    for field in missing:
        errors.append(f"{label}: {field}: Pflichtfeld fehlt")
    for field in unknown:
        errors.append(f"{label}: {_label(field)}: unbekanntes Feld")


def _check_step(step, index, seen_ids, errors):
    label = f"schritte[{index}]"
    if not isinstance(step, dict):
        errors.append(f"{label}: eintrag: Objekt erwartet")
        return

    step_id = step.get("id")
    if is_nonempty_text(step_id):
        label = _label(step_id)
        if step_id in seen_ids:
            errors.append(f"{label}: id: doppelte ID")
        seen_ids.add(step_id)
    elif "id" in step:
        errors.append(f"{label}: id: nicht leerer Text erwartet")

    _check_fields(step, STEP_FIELDS, label, errors)
    if index < len(STEP_NAMES) and "name" in step and step["name"] != STEP_NAMES[index]:
        errors.append(f"{label}: name: an Position {index + 1} wird {STEP_NAMES[index]} erwartet")
    if "status" in step and step["status"] not in STATUSES:
        errors.append(f"{label}: status: zulässiger Status erwartet")
    if "notiz" in step and not isinstance(step["notiz"], str):
        errors.append(f"{label}: notiz: Text erwartet")


def validate(document: object) -> list[str]:
    """Gibt Regelverletzungen für ein eingelesenes JSON-Dokument zurück."""
    if not isinstance(document, dict):
        return ["datei: $: Objekt erwartet"]

    errors: list[str] = []
    document_id = document.get("id")
    label = _label(document_id) if is_nonempty_text(document_id) else "datei"
    _check_fields(document, DOCUMENT_FIELDS, label, errors)
    for field in ("id", "haendler_rolle", "creator_rolle"):
        if field in document and not is_nonempty_text(document[field]):
            errors.append(f"{label}: {field}: nicht leerer Text erwartet")

    haendler = document.get("haendler_rolle")
    creator = document.get("creator_rolle")
    if is_nonempty_text(haendler) and is_nonempty_text(creator):
        if haendler.strip().casefold() == creator.strip().casefold():
            errors.append(f"{label}: creator_rolle: muss sich von haendler_rolle unterscheiden")

    if "schritte" not in document:
        return errors
    steps = document["schritte"]
    if not isinstance(steps, list):
        errors.append(f"{label}: schritte: Liste erwartet")
        return errors
    if len(steps) != len(STEP_NAMES):
        errors.append(f"{label}: schritte: genau sechs Einträge erwartet")

    seen_ids = {document_id} if is_nonempty_text(document_id) else set()
    for index, step in enumerate(steps):
        _check_step(step, index, seen_ids, errors)
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
