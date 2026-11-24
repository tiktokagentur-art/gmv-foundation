"""Validiert ein Entscheidungs- und Änderungsregister im JSON-Format."""

import argparse
import re
import sys
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

TEXT_FIELDS = {"entscheidungstraeger", "freigabe", "scope", "owner"}
ENTRY_FIELDS = TEXT_FIELDS | {"id", "status", "evidence", "historie"}
HISTORY_FIELDS = {"datum", "status", "von"}
CLOSING_STATUSES = {"umgesetzt", "verifiziert", "dokumentiert"}
EVIDENCE_STATUSES = CLOSING_STATUSES | {"abgeschlossen"}
STATUSES = EVIDENCE_STATUSES | {"vorgeschlagen", "freigegeben", "abgelehnt"}
ID_PATTERN = re.compile(r"DEC-[0-9]{3,}")


def _check_fields(record, fields, label, errors, prefix=""):
    missing, unknown = check_fields(record, sorted(fields))
    for field in missing:
        errors.append(f"{label}: {prefix}{field}: Pflichtfeld fehlt")
    for field in unknown:
        errors.append(f"{label}: {prefix}{field!r}: unbekanntes Feld")


def _valid_status(value):
    return isinstance(value, str) and value in STATUSES


def _check_history(history, status, label, errors):
    if not isinstance(history, list) or not history:
        errors.append(f"{label}: historie: nicht leere Liste erwartet")
        return

    previous_date = None
    history_statuses = set()
    for index, item in enumerate(history):
        field = f"historie[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label}: {field}: Objekt erwartet")
            continue
        _check_fields(item, HISTORY_FIELDS, label, errors, prefix=f"{field}.")

        if "datum" in item:
            current_date = parse_iso_date(item["datum"])
            if current_date is None:
                errors.append(
                    f"{label}: {field}.datum: gültiges Datum im Format JJJJ-MM-TT erwartet"
                )
            else:
                if previous_date is not None and current_date < previous_date:
                    errors.append(f"{label}: {field}.datum: Datum liegt vor dem vorherigen Datum")
                previous_date = current_date

        if "status" in item:
            if _valid_status(item["status"]):
                history_statuses.add(item["status"])
            else:
                errors.append(f"{label}: {field}.status: ungültiger Status")

        if "von" in item and not is_nonempty_text(item["von"]):
            errors.append(f"{label}: {field}.von: nicht leere Zeichenkette erwartet")

    last = history[-1]
    if (
        _valid_status(status)
        and isinstance(last, dict)
        and _valid_status(last.get("status"))
        and last["status"] != status
    ):
        errors.append(f"{label}: historie: letzter Status muss dem Eintragsstatus entsprechen")

    if status == "abgeschlossen":
        missing = CLOSING_STATUSES - history_statuses
        if missing:
            missing_list = ", ".join(sorted(missing))
            errors.append(f"{label}: historie: fehlende Abschlussstatus ({missing_list})")


def validate(register):
    """Gibt alle Fehler für ein eingelesenes JSON-Register zurück."""
    if not isinstance(register, list):
        return ["register: liste: Liste von Einträgen erwartet"]

    errors = []
    seen_ids = set()
    for index, entry in enumerate(register):
        label = f"eintrag[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: eintrag: Objekt erwartet")
            continue

        entry_id = entry.get("id")
        if isinstance(entry_id, str) and ID_PATTERN.fullmatch(entry_id):
            label = entry_id
            if entry_id in seen_ids:
                errors.append(f"{label}: id: doppelte ID")
            seen_ids.add(entry_id)
        elif "id" in entry:
            errors.append(f"{label}: id: DEC- gefolgt von mindestens drei Ziffern erwartet")

        _check_fields(entry, ENTRY_FIELDS, label, errors)
        for field in sorted(TEXT_FIELDS & entry.keys()):
            if not is_nonempty_text(entry[field]):
                errors.append(f"{label}: {field}: nicht leere Zeichenkette erwartet")

        status = entry.get("status")
        if "status" in entry and not _valid_status(status):
            errors.append(f"{label}: status: ungültiger Status")

        if "evidence" in entry:
            evidence = entry["evidence"]
            if not isinstance(evidence, list) or not all(
                isinstance(item, str) for item in evidence
            ):
                errors.append(f"{label}: evidence: Liste von Zeichenketten erwartet")
            elif not evidence and _valid_status(status) and status in EVIDENCE_STATUSES:
                errors.append(f"{label}: evidence: mindestens ein Nachweis erforderlich")

        if "historie" in entry:
            _check_history(entry["historie"], status, label, errors)

    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("datei", type=Path, help="Pfad zur JSON-Datei")
    args = parser.parse_args(argv)

    register, load_error = load_json(args.datei)
    if load_error == "read":
        return report_errors(
            ["register: datei: Datei kann nicht als UTF-8 gelesen werden"], exit_code=2
        )
    if load_error == "json":
        return report_errors(["register: json: ungültiges JSON"], exit_code=2)
    return report_errors(validate(register))


if __name__ == "__main__":
    sys.exit(main())
