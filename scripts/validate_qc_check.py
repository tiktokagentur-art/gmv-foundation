"""Prüft eine JSON-Liste von Prüfvermerken für die Content Factory."""

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

ENTRY_FIELDS = ("id", "video", "erstellende_rolle", "datum", "punkte")
POINTS = (
    "aussagen",
    "bild",
    "ton",
    "rechte",
    "untertitel",
    "caption",
    "kennzeichnung",
    "tool_lizenz",
)
POINT_FIELDS = ("ergebnis", "pruefende_rolle")
EXTRA_FIELDS = {
    "kennzeichnung": ("ki_kennzeichnung_sichtbar", "c2pa"),
    "tool_lizenz": ("tools",),
}
TOOL_FIELDS = ("name", "tarif", "nutzung")


def _check_object(
    value: object,
    label: str,
    path: str,
    required: tuple[str, ...],
    errors: list[str],
    *,
    optional: tuple[str, ...] = (),
) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label}: {path or 'eintrag'}: Objekt erwartet")
        return False

    prefix = f"{path}." if path else ""
    missing, unknown = check_fields(value, required, (*required, *optional))
    for field in missing:
        errors.append(f"{label}: {prefix}{field}: Pflichtfeld fehlt")
    for field in unknown:
        errors.append(f"{label}: {prefix}{json.dumps(field)}: unbekanntes Feld")
    return True


def _check_tools(tools: object, location: str, label: str, errors: list[str]) -> None:
    if not isinstance(tools, list):
        errors.append(f"{label}: {location}: Liste von Tools erwartet")
        return

    for index, tool in enumerate(tools):
        path = f"{location}[{index}]"
        if not _check_object(tool, label, path, TOOL_FIELDS, errors):
            continue
        if "name" in tool and not is_nonempty_text(tool["name"]):
            errors.append(f"{label}: {path}.name: nicht leere Zeichenkette erwartet")
        if "tarif" in tool and tool["tarif"] not in ("free", "kommerziell"):
            errors.append(f"{label}: {path}.tarif: free oder kommerziell erwartet")
        if "nutzung" in tool and tool["nutzung"] not in ("intern", "extern"):
            errors.append(f"{label}: {path}.nutzung: intern oder extern erwartet")
        if tool.get("tarif") == "free" and tool.get("nutzung") == "extern":
            errors.append(f"{label}: {path}.nutzung: Free-Tools sind nur intern zulässig")


def _check_point(
    name: str, point: object, creator: object, label: str, errors: list[str]
) -> None:
    path = f"punkte.{name}"
    required = (*POINT_FIELDS, *EXTRA_FIELDS.get(name, ()))
    if not _check_object(point, label, path, required, errors, optional=("notiz",)):
        return

    if "ergebnis" in point:
        result = point["ergebnis"]
        if result == "nicht_bestanden":
            errors.append(
                f"{label}: {path}.ergebnis: Prüfvermerk unvollständig (nicht_bestanden)"
            )
        elif result == "nicht_anwendbar" and name == "kennzeichnung":
            errors.append(f"{label}: {path}.ergebnis: nicht_anwendbar ist hier unzulässig")
        elif result not in ("bestanden", "nicht_anwendbar"):
            errors.append(f"{label}: {path}.ergebnis: ungültiges Ergebnis")

    reviewer = point.get("pruefende_rolle")
    if "pruefende_rolle" in point:
        if not isinstance(reviewer, str) or not is_nonempty_text(reviewer):
            errors.append(f"{label}: {path}.pruefende_rolle: nicht leere Zeichenkette erwartet")
        elif isinstance(creator, str) and reviewer.strip().casefold() == creator.strip().casefold():
            errors.append(
                f"{label}: {path}.pruefende_rolle: muss von der erstellenden Rolle abweichen"
            )
    if "notiz" in point and not isinstance(point["notiz"], str):
        errors.append(f"{label}: {path}.notiz: Zeichenkette erwartet")

    if name == "kennzeichnung":
        if "ki_kennzeichnung_sichtbar" in point and point["ki_kennzeichnung_sichtbar"] is not True:
            errors.append(f"{label}: {path}.ki_kennzeichnung_sichtbar: true ist Pflicht")
        if "c2pa" in point and point["c2pa"] not in ("vorhanden_gueltig", "nicht_vorhanden"):
            errors.append(f"{label}: {path}.c2pa: vorhanden_gueltig oder nicht_vorhanden erwartet")
    if name == "tool_lizenz" and "tools" in point:
        _check_tools(point["tools"], f"{path}.tools", label, errors)


def validate(document: object) -> list[str]:
    """Gibt Regelverletzungen für ein eingelesenes JSON-Dokument zurück."""
    if not isinstance(document, list):
        return ["datei: $: Liste von Prüfvermerken erwartet"]

    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(document):
        label = f"eintrag[{index}]"
        entry_id = entry.get("id") if isinstance(entry, dict) else None
        if isinstance(entry_id, str) and is_nonempty_text(entry_id):
            label = json.dumps(entry_id)[1:-1]
            if entry_id in seen_ids:
                errors.append(f"{label}: id: doppelte ID")
            seen_ids.add(entry_id)
        if not _check_object(entry, label, "", ENTRY_FIELDS, errors):
            continue

        for field in ("id", "video", "erstellende_rolle"):
            if field in entry and not is_nonempty_text(entry[field]):
                errors.append(f"{label}: {field}: nicht leere Zeichenkette erwartet")
        if "datum" in entry and parse_iso_date(entry["datum"]) is None:
            errors.append(f"{label}: datum: gültiges Kalenderdatum im Format JJJJ-MM-TT erwartet")
        creator = entry.get("erstellende_rolle")
        if "punkte" in entry:
            points = entry["punkte"]
            if _check_object(points, label, "punkte", POINTS, errors):
                for name in POINTS:
                    if name in points:
                        _check_point(name, points[name], creator, label, errors)
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
