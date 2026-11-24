"""Tests für den Statusmodell-Prüfer."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/governance/examples/status-model-beispiel.json"
sys.path.insert(0, str(ROOT / "scripts"))

from validate_status_model import main, validate  # noqa: E402


@pytest.fixture
def document():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example(capsys):
    assert main([str(EXAMPLE)]) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "removed_steps, error",
    [
        (slice(0, 1), "historie[0].status: erste Stufe muss die Startstufe sein"),
        (slice(1, 2), "historie[1].status: Übergang nicht erlaubt"),
    ],
)
def test_history_path(document, removed_steps, error):
    del document["eintraege"][0]["historie"][removed_steps]
    assert validate(document) == [f"BEISPIEL-001: {error}"]


@pytest.mark.parametrize("value", ["2029-12-31", "2030-02-30", "20300110"])
def test_history_date(document, value):
    document["eintraege"][0]["historie"][1]["datum"] = value
    errors = validate(document)
    assert len(errors) == 1
    assert errors[0].startswith("BEISPIEL-001: historie[1].datum: ")


def test_last_status(document):
    document["eintraege"][0]["status"] = "geprueft"
    assert validate(document) == [
        "BEISPIEL-001: historie: letzter Status muss dem Eintragsstatus entsprechen"
    ]


@pytest.mark.parametrize("value", [None, " \t", [], {}])
def test_required_field_after_leaving_stage(document, value):
    entry = document["eintraege"][0]
    if value is None:
        del entry["pruefvermerk"]
    else:
        entry["pruefvermerk"] = value
    assert validate(document) == ["BEISPIEL-001: pruefvermerk: Pflichtfeld fehlt oder ist leer"]


def test_end_stage_requires_reason(document):
    del document["eintraege"][1]["grund"]
    assert validate(document) == ["BEISPIEL-002: grund: nicht leerer Grund erforderlich"]


@pytest.mark.parametrize("value", [None, "2030-02-30", "2030-01-11"])
def test_follow_up_requires_date_on_or_after_entry(document, value):
    entry = document["eintraege"][2]
    if value is None:
        del entry["wiedervorlage"]
    else:
        entry["wiedervorlage"] = value
    errors = validate(document)
    assert len(errors) == 1
    assert errors[0].startswith("BEISPIEL-003: wiedervorlage: ")


def test_follow_up_on_entry_date(document):
    entry = document["eintraege"][2]
    entry["wiedervorlage"] = entry["historie"][-1]["datum"]
    assert validate(document) == []


@pytest.mark.parametrize(
    "note, field",
    [
        (None, "vermerk"),
        ({"rolle": "Rolle A", "text": "Fiktiver Vermerk"}, "vermerk.rolle"),
        ({"rolle": "Rolle P", "text": " "}, "vermerk.text"),
    ],
)
def test_gate(document, note, field):
    step = document["eintraege"][0]["historie"][-1]
    if note is None:
        del step["vermerk"]
    else:
        step["vermerk"] = note
    errors = validate(document)
    assert len(errors) == 1
    assert errors[0].startswith(f"BEISPIEL-001: historie[3].{field}: ")


@pytest.mark.parametrize(
    "updates, field",
    [
        ({"start": "unbekannt"}, "start"),
        ({"uebergaenge": {"idee": ["unbekannt"]}}, "uebergaenge.idee"),
        ({"uebergaenge": {"verworfen": ["idee"]}}, "uebergaenge.verworfen"),
        ({"pflichtfelder_ab": {"unbekannt": ["pruefvermerk"]}}, "pflichtfelder_ab.unbekannt"),
        ({"gates": {"unbekannt": "Rolle P"}}, "gates.unbekannt"),
        (
            {"endstufen": {"verworfen": {"grund": True, "wiedervorlage": 1}}},
            "endstufen.verworfen.wiedervorlage",
        ),
    ],
)
def test_invalid_model(document, updates, field):
    document["modell"].update(updates)
    errors = validate(document)
    assert len(errors) == 1
    assert errors[0].startswith(f"modell: {field}: ")


def test_duplicate_id(document):
    document["eintraege"][1]["id"] = document["eintraege"][0]["id"]
    assert validate(document) == ["BEISPIEL-001: id: doppelte ID"]


@pytest.mark.parametrize(
    "content, code, label",
    [("{}", 1, "datei: modell:"), ("{", 2, "datei: json:"), (None, 2, "datei: datei:")],
)
def test_main_error_codes(tmp_path, capsys, content, code, label):
    path = tmp_path / "status.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    assert main([str(path)]) == code
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == (2 if code == 1 else 1)
    assert lines[0].startswith(label)
