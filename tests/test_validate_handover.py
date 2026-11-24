"""Tests für den Prüfer für Aufgabenprotokoll und Übergaben."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/governance/examples/handover-beispiel.json"
sys.path.insert(0, str(ROOT / "scripts"))

from validate_handover import main, validate  # noqa: E402


@pytest.fixture
def document():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example(capsys):
    assert main([str(EXAMPLE)]) == 0
    assert capsys.readouterr().err == ""


def test_empty_lists():
    assert validate({"aufgabenprotokoll": [], "uebergaben": []}) == []


@pytest.mark.parametrize(
    "document, error",
    [
        ([], "datei: $: Objekt erwartet"),
        ({"aufgabenprotokoll": []}, "datei: uebergaben: Pflichtfeld fehlt"),
        ({"uebergaben": []}, "datei: aufgabenprotokoll: Pflichtfeld fehlt"),
        ({"aufgabenprotokoll": {}, "uebergaben": []}, "datei: aufgabenprotokoll: Liste erwartet"),
        ({"aufgabenprotokoll": [], "uebergaben": None}, "datei: uebergaben: Liste erwartet"),
        (
            {"aufgabenprotokoll": [], "uebergaben": [], "zusatz": "Fiktiv"},
            "datei: zusatz: unbekanntes Feld",
        ),
    ],
)
def test_invalid_document(document, error):
    assert validate(document) == [error]


@pytest.mark.parametrize("field", ["aufgabenprotokoll", "uebergaben"])
def test_entry_must_be_object(document, field):
    document[field][0] = []
    assert validate(document) == [f"{field}[0]: eintrag: Objekt erwartet"]


@pytest.mark.parametrize(
    "field, entry_id", [("aufgabenprotokoll", "FIKTIV-A-001"), ("uebergaben", "FIKTIV-U-001")]
)
def test_missing_and_unknown_entry_fields(document, field, entry_id):
    entry = document[field][0]
    for required_field in tuple(entry):
        value = entry.pop(required_field)
        label = f"{field}[0]" if required_field == "id" else entry_id
        assert validate(document) == [f"{label}: {required_field}: Pflichtfeld fehlt"]
        entry[required_field] = value

    entry["zusatz"] = "Fiktiv"
    assert validate(document) == [f"{entry_id}: zusatz: unbekanntes Feld"]


@pytest.mark.parametrize(
    "field, value, label",
    [
        ("id", " \t", "aufgabenprotokoll[0]"),
        ("verantwortlich", "", "FIKTIV-A-001"),
        ("termin", "2030-02-30", "FIKTIV-A-001"),
        ("termin", "20300110", "FIKTIV-A-001"),
        ("status", "unbekannt", "FIKTIV-A-001"),
        ("status", [], "FIKTIV-A-001"),
        ("naechster_schritt", " \t", "FIKTIV-A-001"),
        ("ergebnis_link", "http://example.invalid/ergebnisse/musterkarte", "FIKTIV-A-001"),
    ],
)
def test_invalid_task_fields(document, field, value, label):
    document["aufgabenprotokoll"][0][field] = value
    errors = validate(document)
    assert len(errors) == 1
    assert errors[0].startswith(f"{label}: {field}: ")


def test_completed_task_requires_text_for_next_step(document):
    document["aufgabenprotokoll"][1]["naechster_schritt"] = None
    errors = validate(document)
    assert len(errors) == 1
    assert errors[0].startswith("FIKTIV-A-002: naechster_schritt: ")


@pytest.mark.parametrize(
    "field, label",
    [
        ("id", "uebergaben[0]"),
        ("eingang", "FIKTIV-U-001"),
        ("owner", "FIKTIV-U-001"),
        ("erwarteter_output", "FIKTIV-U-001"),
        ("uebergabebeleg", "FIKTIV-U-001"),
        ("akzeptierende_stelle", "FIKTIV-U-001"),
    ],
)
def test_handover_text_fields_must_not_be_blank(document, field, label):
    document["uebergaben"][0][field] = " \t"
    assert validate(document) == [f"{label}: {field}: nicht leerer Text erwartet"]


def test_owner_cannot_accept_own_handover(document):
    document["uebergaben"][0]["akzeptierende_stelle"] = "  rOLLE a\t"
    assert validate(document) == [
        "FIKTIV-U-001: akzeptierende_stelle: muss sich vom Owner unterscheiden"
    ]


@pytest.mark.parametrize("field", ["aufgabenprotokoll", "uebergaben"])
def test_duplicate_id_in_file(document, field):
    document[field][1]["id"] = "FIKTIV-A-001"
    assert validate(document) == ["FIKTIV-A-001: id: doppelte ID"]


@pytest.mark.parametrize(
    "content, code, errors",
    [
        (
            "{}",
            1,
            ["datei: aufgabenprotokoll: Pflichtfeld fehlt", "datei: uebergaben: Pflichtfeld fehlt"],
        ),
        ("{", 2, ["datei: json: ungültiges JSON"]),
        (None, 2, ["datei: datei: Datei kann nicht als UTF-8 gelesen werden"]),
    ],
)
def test_main_error_codes(tmp_path, capsys, content, code, errors):
    path = tmp_path / "handover.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    assert main([str(path)]) == code
    assert capsys.readouterr().err.splitlines() == errors


def test_main_requires_file_argument():
    with pytest.raises(SystemExit) as error:
        main([])
    assert error.value.code == 2
