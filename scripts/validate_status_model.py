"""Prüft ein Statusmodell und seine Einträge im JSON-Format."""

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

MODEL_FIELDS = ("stufen", "start", "endstufen", "uebergaenge", "pflichtfelder_ab", "gates")
ENTRY_FIELDS = ("id", "status", "historie")
STEP_FIELDS = ("datum", "status", "von")


def _label(value: str) -> str:
    return json.dumps(value)[1:-1]


def _check_fields(record, required, errors, label, prefix="", allowed=None):
    missing, unknown = check_fields(record, required, allowed)
    for field in missing:
        errors.append(f"{label}: {prefix}{field}: Pflichtfeld fehlt")
    for field in unknown:
        errors.append(f"{label}: {prefix}{_label(field)!r}: unbekanntes Feld")


def _known_stage(value, stages):
    return isinstance(value, str) and value in stages


def _check_model(model, errors):
    if not isinstance(model, dict):
        errors.append("datei: modell: Objekt erwartet")
        return

    _check_fields(model, MODEL_FIELDS, errors, "modell")
    stages = model.get("stufen")
    if not isinstance(stages, list) or not stages or not all(map(is_nonempty_text, stages)):
        if "stufen" in model:
            errors.append("modell: stufen: nicht leere Liste nicht leerer Stufennamen erwartet")
        return
    if len(set(stages)) != len(stages):
        errors.append("modell: stufen: Stufennamen müssen eindeutig sein")
    if "start" in model and not _known_stage(model["start"], stages):
        errors.append("modell: start: bekannte Stufe erwartet")

    mappings = ("endstufen", "uebergaenge", "pflichtfelder_ab", "gates")
    for field in mappings:
        if field not in model:
            continue
        if not isinstance(model[field], dict):
            errors.append(f"modell: {field}: Objekt erwartet")
            continue
        for stage, rule in model[field].items():
            path = f"{field}.{_label(stage)}"
            if stage not in stages:
                errors.append(f"modell: {path}: unbekannte Stufe")
            if field == "endstufen":
                _check_end_rule(rule, path, errors)
            elif field == "uebergaenge":
                if not isinstance(rule, list) or not all(
                    _known_stage(target, stages) for target in rule
                ):
                    errors.append(f"modell: {path}: Liste bekannter Folgestufen erwartet")
            elif field == "pflichtfelder_ab":
                if not isinstance(rule, list) or not all(map(is_nonempty_text, rule)):
                    errors.append(f"modell: {path}: Liste nicht leerer Feldnamen erwartet")
            elif not is_nonempty_text(rule):
                errors.append(f"modell: {path}: nicht leere Rolle erwartet")

    ends = model.get("endstufen")
    transitions = model.get("uebergaenge")
    if isinstance(ends, dict) and isinstance(transitions, dict):
        for stage in ends:
            if transitions.get(stage):
                errors.append(f"modell: uebergaenge.{_label(stage)}: Endstufe hat Folgestufen")


def _check_end_rule(rule, path, errors):
    if not isinstance(rule, dict):
        errors.append(f"modell: {path}: Objekt erwartet")
        return
    _check_fields(rule, ("grund", "wiedervorlage"), errors, "modell", prefix=f"{path}.")
    if "grund" in rule and rule["grund"] is not True:
        errors.append(f"modell: {path}.grund: true erwartet")
    if "wiedervorlage" in rule and not isinstance(rule["wiedervorlage"], bool):
        errors.append(f"modell: {path}.wiedervorlage: boolescher Wert erwartet")


def _check_note(step, role, path, label, errors):
    if role is None and "vermerk" not in step:
        return
    note = step.get("vermerk")
    if not isinstance(note, dict):
        errors.append(f"{label}: {path}: Vermerk als Objekt erwartet")
        return
    _check_fields(note, ("rolle", "text"), errors, label, prefix=f"{path}.")
    if "rolle" in note:
        if not is_nonempty_text(note["rolle"]):
            errors.append(f"{label}: {path}.rolle: nicht leere Rolle erwartet")
        elif role is not None and note["rolle"] != role:
            errors.append(f"{label}: {path}.rolle: Rolle entspricht nicht der Vorgabe des Modells")
    if "text" in note and not is_nonempty_text(note["text"]):
        errors.append(f"{label}: {path}.text: nicht leerer Text erwartet")


def _check_history(history, status, model, label, errors):
    if not isinstance(history, list) or not history:
        errors.append(f"{label}: historie: nicht leere Liste erwartet")
        return set()

    previous_date = None
    previous_stage = None
    reached = set()
    for index, step in enumerate(history):
        path = f"historie[{index}]"
        if not isinstance(step, dict):
            errors.append(f"{label}: {path}: Objekt erwartet")
            previous_stage = None
            continue
        _check_fields(step, STEP_FIELDS, errors, label, f"{path}.", (*STEP_FIELDS, "vermerk"))
        current_date = parse_iso_date(step.get("datum"))
        if current_date is not None:
            if previous_date is not None and current_date < previous_date:
                errors.append(f"{label}: {path}.datum: Datum liegt vor dem vorherigen Datum")
            previous_date = current_date
        elif "datum" in step:
            errors.append(f"{label}: {path}.datum: gültiges Datum im Format JJJJ-MM-TT erwartet")
        if "von" in step and not is_nonempty_text(step["von"]):
            errors.append(f"{label}: {path}.von: nicht leere Zeichenkette erwartet")

        stage = step.get("status")
        if not _known_stage(stage, model["stufen"]):
            if "status" in step:
                errors.append(f"{label}: {path}.status: bekannte Stufe erwartet")
            _check_note(step, None, f"{path}.vermerk", label, errors)
            previous_stage = None
            continue
        reached.add(stage)
        if index == 0 and stage != model["start"]:
            errors.append(f"{label}: {path}.status: erste Stufe muss die Startstufe sein")
        if previous_stage is not None and stage not in model["uebergaenge"].get(previous_stage, []):
            errors.append(f"{label}: {path}.status: Übergang nicht erlaubt")
        previous_stage = stage
        _check_note(step, model["gates"].get(stage), f"{path}.vermerk", label, errors)

    if previous_stage is not None and status is not None and previous_stage != status:
        errors.append(f"{label}: historie: letzter Status muss dem Eintragsstatus entsprechen")
    return reached


def _has_value(value):
    if isinstance(value, str):
        return is_nonempty_text(value)
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def _check_entry(entry, model, label, seen_ids, errors):
    if not isinstance(entry, dict):
        errors.append(f"{label}: eintrag: Objekt erwartet")
        return

    entry_id = entry.get("id")
    if is_nonempty_text(entry_id):
        label = _label(entry_id)
        if entry_id in seen_ids:
            errors.append(f"{label}: id: doppelte ID")
        seen_ids.add(entry_id)
    elif "id" in entry:
        errors.append(f"{label}: id: nicht leere Zeichenkette erwartet")

    _check_fields(entry, ENTRY_FIELDS, errors, label, allowed=entry.keys())
    status = entry.get("status")
    if not _known_stage(status, model["stufen"]):
        if "status" in entry:
            errors.append(f"{label}: status: bekannte Stufe erwartet")
        status = None

    history = entry.get("historie")
    if "historie" in entry:
        reached = _check_history(history, status, model, label, errors)
        required = {
            field for stage in reached for field in model["pflichtfelder_ab"].get(stage, [])
        }
        for field in sorted(required):
            if not _has_value(entry.get(field)):
                errors.append(f"{label}: {_label(field)}: Pflichtfeld fehlt oder ist leer")

    end_rule = model["endstufen"].get(status)
    if end_rule is None:
        return
    if not is_nonempty_text(entry.get("grund")):
        errors.append(f"{label}: grund: nicht leerer Grund erforderlich")
    if end_rule["wiedervorlage"]:
        due = parse_iso_date(entry.get("wiedervorlage"))
        if due is None:
            errors.append(f"{label}: wiedervorlage: gültiges Datum im Format JJJJ-MM-TT erwartet")
        elif isinstance(history, list) and history and isinstance(history[-1], dict):
            last = history[-1]
            entered = parse_iso_date(last.get("datum"))
            if last.get("status") == status and entered is not None and due < entered:
                errors.append(
                    f"{label}: wiedervorlage: Datum liegt vor dem Eintritt in die Endstufe"
                )


def validate(document: object) -> list[str]:
    """Gibt Regelverletzungen für ein eingelesenes JSON-Dokument zurück."""
    if not isinstance(document, dict):
        return ["datei: $: Objekt erwartet"]

    errors = []
    _check_fields(document, ("modell", "eintraege"), errors, "datei")
    if "modell" in document:
        _check_model(document["modell"], errors)
    if "eintraege" in document and not isinstance(document["eintraege"], list):
        errors.append("datei: eintraege: Liste von Einträgen erwartet")
    if errors:
        return errors

    seen_ids = set()
    for index, entry in enumerate(document["eintraege"]):
        _check_entry(entry, document["modell"], f"eintrag[{index}]", seen_ids, errors)
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
