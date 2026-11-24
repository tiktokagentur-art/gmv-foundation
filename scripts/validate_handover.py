"""Prüft Aufgabenprotokoll und Übergaben im JSON-Format."""

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
    parse_iso_date,
    report_errors,
)

TASK_LIST = "aufgabenprotokoll"
HANDOVER_LIST = "uebergaben"
TASK_FIELDS = ("id", "verantwortlich", "termin", "status", "naechster_schritt", "ergebnis_link")
HANDOVER_FIELDS = (
    "id",
    "eingang",
    "owner",
    "erwarteter_output",
    "uebergabebeleg",
    "akzeptierende_stelle",
)
STATUSES = ("vorschlag", "in_arbeit", "in_pruefung", "erledigt")


def _label(value: str) -> str:
    return json.dumps(value)[1:-1].replace(":", r"\u003a")


def _check_fields(record, fields, label, errors):
    missing, unknown = check_fields(record, fields)
    for field in missing:
        errors.append(f"{label}: {field}: Pflichtfeld fehlt")
    for field in unknown:
        errors.append(f"{label}: {_label(field)}: unbekanntes Feld")


def _check_task(entry, label, errors):
    if "verantwortlich" in entry and not is_nonempty_text(entry["verantwortlich"]):
        errors.append(f"{label}: verantwortlich: nicht leerer Text erwartet")
    if "termin" in entry and parse_iso_date(entry["termin"]) is None:
        errors.append(f"{label}: termin: gültiges Datum im Format JJJJ-MM-TT erwartet")

    status = entry.get("status")
    if "status" in entry and status not in STATUSES:
        errors.append(f"{label}: status: zulässiger Status erwartet")

    if "naechster_schritt" in entry:
        step = entry["naechster_schritt"]
        if not isinstance(step, str) or (status != "erledigt" and not step.strip()):
            errors.append(f"{label}: naechster_schritt: Text erwartet, nur bei erledigt leer")

    if "ergebnis_link" in entry:
        link = entry["ergebnis_link"]
        if not isinstance(link, str) or not link.startswith("https://"):
            errors.append(f"{label}: ergebnis_link: Link muss mit https:// beginnen")


def _check_handover(entry, label, errors):
    for field in HANDOVER_FIELDS[1:]:
        if field in entry and not is_nonempty_text(entry[field]):
            errors.append(f"{label}: {field}: nicht leerer Text erwartet")

    owner = entry.get("owner")
    accepting = entry.get("akzeptierende_stelle")
    if is_nonempty_text(owner) and is_nonempty_text(accepting):
        if owner.strip().casefold() == accepting.strip().casefold():
            errors.append(f"{label}: akzeptierende_stelle: muss sich vom Owner unterscheiden")


def validate(document: object) -> list[str]:
    """Gibt Regelverletzungen für ein eingelesenes JSON-Dokument zurück."""
    if not isinstance(document, dict):
        return ["datei: $: Objekt erwartet"]

    errors: list[str] = []
    _check_fields(document, (TASK_LIST, HANDOVER_LIST), "datei", errors)
    seen_ids: set[str] = set()
    for field, fields, check_entry in (
        (TASK_LIST, TASK_FIELDS, _check_task),
        (HANDOVER_LIST, HANDOVER_FIELDS, _check_handover),
    ):
        if field not in document:
            continue
        entries = document[field]
        if not isinstance(entries, list):
            errors.append(f"datei: {field}: Liste erwartet")
            continue

        for index, entry in enumerate(entries):
            label = f"{field}[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"{label}: eintrag: Objekt erwartet")
                continue

            entry_id = entry.get("id")
            if is_nonempty_text(entry_id):
                label = _label(entry_id)
                if entry_id in seen_ids:
                    errors.append(f"{label}: id: doppelte ID")
                seen_ids.add(entry_id)
            elif "id" in entry:
                errors.append(f"{label}: id: nicht leerer Text erwartet")

            _check_fields(entry, fields, label, errors)
            check_entry(entry, label, errors)
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
