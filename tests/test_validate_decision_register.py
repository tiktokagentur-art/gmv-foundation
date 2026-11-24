"""Tests für das Entscheidungs- und Änderungsregister."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/governance/examples/decision-register-beispiel.json"
sys.path.insert(0, str(ROOT / "scripts"))

from validate_decision_register import main, validate  # noqa: E402


@pytest.fixture
def entries():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example(capsys):
    assert main([str(EXAMPLE)]) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("register, field", [({}, "liste"), ([None], "eintrag")])
def test_invalid_structure(register, field):
    assert validate(register)[0].split(": ", 2)[1] == field


@pytest.mark.parametrize(
    "field",
    ["id", "entscheidungstraeger", "freigabe", "scope", "owner", "status", "evidence", "historie"],
)
def test_missing_field(entries, field):
    del entries[1][field]
    label = "eintrag[1]" if field == "id" else "DEC-002"
    assert validate(entries) == [f"{label}: {field}: Pflichtfeld fehlt"]


@pytest.mark.parametrize(
    "field, value, error_field",
    [
        ("zusatz", True, "'zusatz'"),
        ("id", "DEC-12", "id"),
        ("id", 123, "id"),
        ("entscheidungstraeger", "", "entscheidungstraeger"),
        ("freigabe", "  ", "freigabe"),
        ("scope", None, "scope"),
        ("owner", 123, "owner"),
        ("status", "offen", "status"),
        ("status", [], "status"),
        ("evidence", "Nachweis", "evidence"),
        ("evidence", [42], "evidence"),
        ("historie", {}, "historie"),
        ("historie", [], "historie"),
        ("historie", [None], "historie[0]"),
    ],
)
def test_invalid_field(entries, field, value, error_field):
    entries[1][field] = value
    label = "eintrag[1]" if field == "id" else "DEC-002"
    errors = validate(entries)
    assert len(errors) == 1
    assert errors[0].startswith(f"{label}: {error_field}: ")


def test_duplicate_id(entries):
    entries[1]["id"] = entries[0]["id"]
    assert validate(entries) == ["DEC-001: id: doppelte ID"]


@pytest.mark.parametrize("status", ["umgesetzt", "verifiziert", "dokumentiert", "abgeschlossen"])
def test_evidence_required_from_implementation(entries, status):
    entry = entries[0]
    history = entry["historie"]
    step = next(index for index, item in enumerate(history) if item["status"] == status)
    entry.update(status=status, evidence=[], historie=history[: step + 1])
    assert validate(entries) == ["DEC-001: evidence: mindestens ein Nachweis erforderlich"]


@pytest.mark.parametrize("field", ["datum", "status", "von"])
def test_missing_history_field(entries, field):
    del entries[1]["historie"][0][field]
    assert validate(entries) == [f"DEC-002: historie[0].{field}: Pflichtfeld fehlt"]


@pytest.mark.parametrize(
    "field, value, error_field",
    [
        ("datum", "20300112", "datum"),
        ("datum", "2030-02-30", "datum"),
        ("status", {}, "status"),
        ("von", "\t", "von"),
        ("von", 1, "von"),
        ("zusatz", True, "'zusatz'"),
    ],
)
def test_invalid_history_field(entries, field, value, error_field):
    entries[1]["historie"][0][field] = value
    errors = validate(entries)
    assert len(errors) == 1
    assert errors[0].startswith(f"DEC-002: historie[0].{error_field}: ")


def test_history_dates_out_of_order(entries):
    entries[0]["historie"][1]["datum"] = "2030-01-06"
    assert validate(entries) == ["DEC-001: historie[1].datum: Datum liegt vor dem vorherigen Datum"]


def test_last_history_status_mismatch(entries):
    entries[1]["status"] = "freigegeben"
    assert validate(entries) == [
        "DEC-002: historie: letzter Status muss dem Eintragsstatus entsprechen"
    ]


@pytest.mark.parametrize("missing", ["umgesetzt", "verifiziert", "dokumentiert"])
def test_closed_without_required_history_status(entries, missing):
    history = entries[0]["historie"]
    entries[0]["historie"] = [item for item in history if item["status"] != missing]
    assert validate(entries) == [f"DEC-001: historie: fehlende Abschlussstatus ({missing})"]


def test_main_reports_each_validation_error(tmp_path, capsys):
    source = tmp_path / "register.json"
    source.write_text('[{"id": "DEC-001"}]', encoding="utf-8")
    assert main([str(source)]) == 1
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 7
    assert all(
        line.startswith("DEC-001: ") and line.endswith(": Pflichtfeld fehlt") for line in lines
    )


@pytest.mark.parametrize(
    "contents, field", [(None, "datei"), (b"\xff", "datei"), (b"[", "json"), (b"[NaN]", "json")]
)
def test_main_reports_file_or_json_error(tmp_path, capsys, contents, field):
    source = tmp_path / "register.json"
    if contents is not None:
        source.write_bytes(contents)
    assert main([str(source)]) == 2
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith(f"register: {field}: ")
