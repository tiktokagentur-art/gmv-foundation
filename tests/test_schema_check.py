"""Tests für die gemeinsamen JSON-Prüfungen mit fiktiven Daten."""

import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from schema_check import (  # noqa: E402
    check_fields,
    is_nonempty_text,
    load_json,
    parse_iso_date,
    report_errors,
)


def test_load_json_reads_utf8(tmp_path):
    path = tmp_path / "beispiel.json"
    path.write_text('{"thema": "Fiktives Märchen"}', encoding="utf-8")

    assert load_json(path) == ({"thema": "Fiktives Märchen"}, None)


def test_load_json_accepts_null(tmp_path):
    path = tmp_path / "beispiel.json"
    path.write_text("null", encoding="utf-8")

    assert load_json(path) == (None, None)


@pytest.mark.parametrize("content", [None, b"\xff"])
def test_load_json_reports_read_error(tmp_path, content):
    path = tmp_path / "beispiel.json"
    if content is not None:
        path.write_bytes(content)

    assert load_json(path) == (None, "read")


@pytest.mark.parametrize("content", ["{", "[NaN]", "[Infinity]", "[-Infinity]"])
def test_load_json_reports_invalid_json(tmp_path, content):
    path = tmp_path / "beispiel.json"
    path.write_text(content, encoding="utf-8")

    assert load_json(path) == (None, "json")


def test_check_fields_preserves_required_order_and_sorts_unknown_fields():
    record = {"zusatz": None, "titel": None, "alias": None}

    assert check_fields(record, ("titel", "ziel", "format")) == (
        ["ziel", "format"],
        ["alias", "zusatz"],
    )


def test_check_fields_accepts_optional_fields():
    assert check_fields({"titel": "Fiktiv", "notiz": ""}, ("titel",), ("titel", "notiz")) == (
        [],
        [],
    )


@pytest.mark.parametrize("value", ["", " \t\n", None, 1, ["Fiktiv"]])
def test_is_nonempty_text_rejects_empty_text_and_other_types(value):
    assert not is_nonempty_text(value)


def test_is_nonempty_text_accepts_text_with_surrounding_whitespace():
    assert is_nonempty_text(" Fiktiv ")


@pytest.mark.parametrize(
    "value", [None, 20320229, "20320229", "2032-2-29", "2032-02-29\n", "2030-02-29"]
)
def test_parse_iso_date_rejects_invalid_dates(value):
    assert parse_iso_date(value) is None


def test_parse_iso_date_accepts_leap_day():
    assert parse_iso_date("2032-02-29") == date(2032, 2, 29)


def test_report_errors_is_silent_without_messages(capsys):
    assert report_errors(iter(())) == 0
    assert capsys.readouterr() == ("", "")


def test_report_errors_writes_validation_messages_in_order(capsys):
    assert report_errors(iter(["Erster Fehler", "Zweiter Fehler"])) == 1
    assert capsys.readouterr() == ("", "Erster Fehler\nZweiter Fehler\n")


def test_report_errors_returns_code_for_load_errors(capsys):
    assert report_errors(["Ungültiges JSON"], exit_code=2) == 2
    assert capsys.readouterr() == ("", "Ungültiges JSON\n")
