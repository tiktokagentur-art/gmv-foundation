"""Tests für den Portal-Feldkatalog."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/portal/examples/datenfelder-beispiel.json"
sys.path.insert(0, str(ROOT / "scripts"))

from validate_portal_datenfelder import main  # noqa: E402


def test_example(capsys):
    assert main([str(EXAMPLE)]) == 0
    assert capsys.readouterr().err == ""


def test_empty_list(tmp_path, capsys):
    path = tmp_path / "datenfelder.json"
    path.write_text(json.dumps({"eintraege": []}), encoding="utf-8")
    assert main([str(path)]) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("rechtsgrundlage", "fiktiv", "erwartet platzhalter-bis-datenschutzpruefung"),
        ("email", None, "verbotenes Feld"),
        ("zusatz", "fiktiv", "unbekanntes Feld"),
        ("rolle", "tester", "erwartet haendler, creator"),
        ("status", "test", "erwartet fiktiv"),
        ("bezeichnung", " \t", "nicht leerer Text erwartet"),
    ],
)
def test_invalid_entry(tmp_path, capsys, field, value, message):
    document = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    entry = document["eintraege"][0]
    entry[field] = value
    path = tmp_path / "datenfelder.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert main([str(path)]) == 1
    assert capsys.readouterr().err.splitlines() == [f"{entry['id']}: {field}: {message}"]


def test_duplicate_id(tmp_path, capsys):
    document = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    first, second = document["eintraege"]
    second["id"] = first["id"]
    path = tmp_path / "datenfelder.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert main([str(path)]) == 1
    assert capsys.readouterr().err.splitlines() == [f"{first['id']}: id: doppelte ID"]


@pytest.mark.parametrize(
    "content, code, message",
    [
        ("{}", 1, "datei: eintraege: Pflichtfeld fehlt"),
        ('{"eintraege": {}}', 1, "datei: eintraege: Liste erwartet"),
        ('{"eintraege": [], "zusatz": null}', 1, "datei: zusatz: unbekanntes Feld"),
        ("{", 2, "datei: json: ungültiges JSON"),
        (None, 2, "datei: datei: Datei kann nicht als UTF-8 gelesen werden"),
    ],
)
def test_document_errors(tmp_path, capsys, content, code, message):
    path = tmp_path / "datenfelder.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    assert main([str(path)]) == code
    assert capsys.readouterr().err.splitlines() == [message]
