"""Tests für den Validator des Portal-Kernablaufs."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/portal/examples/kernablauf-beispiel.json"
DOCUMENT_ID = "kernablauf-fiktiv-001"
sys.path.insert(0, str(ROOT / "scripts"))

from validate_kernablauf import main  # noqa: E402


@pytest.fixture
def document():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


@pytest.fixture
def schema_errors(tmp_path, capsys):
    def run(document):
        path = tmp_path / "kernablauf.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        assert main([str(path)]) == 1
        return capsys.readouterr().err.splitlines()

    return run


def test_example(capsys):
    assert main([str(EXAMPLE)]) == 0
    assert capsys.readouterr().err == ""


def test_empty_note_and_allowed_statuses(document, tmp_path, capsys):
    for step, status in zip(
        document["schritte"], ("offen", "in_arbeit", "nicht_zutreffend"), strict=False
    ):
        step.update(status=status, notiz="")
    path = tmp_path / "kernablauf.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert main([str(path)]) == 0
    assert capsys.readouterr().err == ""


def test_document_must_be_object(schema_errors):
    assert schema_errors([]) == ["datei: $: Objekt erwartet"]


@pytest.mark.parametrize("field", ["id", "haendler_rolle", "creator_rolle", "schritte"])
def test_document_requires_field(document, schema_errors, field):
    del document[field]
    label = "datei" if field == "id" else DOCUMENT_ID
    assert schema_errors(document) == [f"{label}: {field}: Pflichtfeld fehlt"]


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("id", " \t", "nicht leerer Text erwartet"),
        ("haendler_rolle", "", "nicht leerer Text erwartet"),
        ("creator_rolle", 12, "nicht leerer Text erwartet"),
        (
            "creator_rolle",
            "  rOLLE hÄNDLER nORDLICHT\t",
            "muss sich von haendler_rolle unterscheiden",
        ),
        ("schritte", {}, "Liste erwartet"),
        ("zusatz", "fiktiv", "unbekanntes Feld"),
    ],
)
def test_invalid_document_field(document, schema_errors, field, value, message):
    document[field] = value
    label = "datei" if field == "id" else DOCUMENT_ID
    assert schema_errors(document) == [f"{label}: {field}: {message}"]


@pytest.mark.parametrize("count", [5, 7])
def test_requires_exactly_six_steps(document, schema_errors, count):
    steps = document["schritte"]
    steps.append(dict(steps[-1], id="fiktiv-07"))
    document["schritte"] = steps[:count]
    assert schema_errors(document) == [f"{DOCUMENT_ID}: schritte: genau sechs Einträge erwartet"]


def test_step_must_be_object(document, schema_errors):
    document["schritte"][0] = None
    assert schema_errors(document) == ["schritte[0]: eintrag: Objekt erwartet"]


@pytest.mark.parametrize("field", ["id", "name", "status", "notiz"])
def test_step_requires_field(document, schema_errors, field):
    del document["schritte"][0][field]
    label = "schritte[0]" if field == "id" else "fiktiv-01"
    assert schema_errors(document) == [f"{label}: {field}: Pflichtfeld fehlt"]


@pytest.mark.parametrize(
    "field, value, label, message",
    [
        ("id", "", "schritte[0]", "nicht leerer Text erwartet"),
        ("id", "fiktiv-02", "fiktiv-02", "doppelte ID"),
        ("id", DOCUMENT_ID, DOCUMENT_ID, "doppelte ID"),
        ("name", "unbekannt", "fiktiv-01", "an Position 1 wird kampagne erwartet"),
        ("name", "interesse", "fiktiv-01", "an Position 1 wird kampagne erwartet"),
        ("status", "unbekannt", "fiktiv-01", "zulässiger Status erwartet"),
        ("notiz", None, "fiktiv-01", "Text erwartet"),
        ("zusatz", "fiktiv", "fiktiv-01", "unbekanntes Feld"),
    ],
)
def test_invalid_step_field(document, schema_errors, field, value, label, message):
    document["schritte"][0][field] = value
    assert schema_errors(document) == [f"{label}: {field}: {message}"]


def test_step_order(document, schema_errors):
    steps = document["schritte"]
    steps[0], steps[1] = steps[1], steps[0]
    assert schema_errors(document) == [
        "fiktiv-02: name: an Position 1 wird kampagne erwartet",
        "fiktiv-01: name: an Position 2 wird interesse erwartet",
    ]


@pytest.mark.parametrize(
    "content, error",
    [
        ("{", "datei: json: ungültiges JSON"),
        (None, "datei: datei: Datei kann nicht als UTF-8 gelesen werden"),
    ],
)
def test_main_input_errors(tmp_path, capsys, content, error):
    path = tmp_path / "kernablauf.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    assert main([str(path)]) == 2
    assert capsys.readouterr().err.splitlines() == [error]
