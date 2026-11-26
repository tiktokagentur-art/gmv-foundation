"""Prüft den Feldkatalog für fiktive Portal-Einträge im JSON-Format."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from schema_check import check_fields, is_nonempty_text, load_json, report_errors  # noqa: E402

TEXT_FIELDS = ("id", "bezeichnung", "region", "datenquelle")
ALLOWED_VALUES = {
    "rolle": ("haendler", "creator"),
    "rechtsgrundlage": ("platzhalter-bis-datenschutzpruefung",),
    "status": ("fiktiv",),
}
ENTRY_FIELDS = (*TEXT_FIELDS, *ALLOWED_VALUES)
FORBIDDEN_FIELDS = ("name", "personenname", "email", "telefon", "preis", "firmenliste")


def _label(value: str) -> str:
    return json.dumps(value)[1:-1].replace(":", r"\u003a")


def _check_fields(record, fields, label, errors, *, forbidden=()):
    missing, unknown = check_fields(record, fields)
    for field in missing:
        errors.append(f"{label}: {field}: Pflichtfeld fehlt")
    for field in unknown:
        message = "verbotenes Feld" if field in forbidden else "unbekanntes Feld"
        errors.append(f"{label}: {_label(field)}: {message}")


def validate(document: object) -> list[str]:
    """Gibt die Feldfehler eines eingelesenen JSON-Dokuments zurück."""
    if not isinstance(document, dict):
        return ["datei: $: Objekt erwartet"]

    errors: list[str] = []
    _check_fields(document, ("eintraege",), "datei", errors)
    if "eintraege" not in document:
        return errors

    entries = document["eintraege"]
    if not isinstance(entries, list):
        errors.append("datei: eintraege: Liste erwartet")
        return errors

    seen_ids: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"eintraege[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: eintrag: Objekt erwartet")
            continue

        entry_id = entry.get("id")
        if is_nonempty_text(entry_id):
            label = _label(entry_id)
            if entry_id in seen_ids:
                errors.append(f"{label}: id: doppelte ID")
            seen_ids.add(entry_id)

        _check_fields(entry, ENTRY_FIELDS, label, errors, forbidden=FORBIDDEN_FIELDS)
        for field in TEXT_FIELDS:
            if field in entry and not is_nonempty_text(entry[field]):
                errors.append(f"{label}: {field}: nicht leerer Text erwartet")
        for field, values in ALLOWED_VALUES.items():
            if field in entry and entry[field] not in values:
                errors.append(f"{label}: {field}: erwartet {', '.join(values)}")

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
