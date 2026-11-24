"""Tests für den Playbook-Prüfer mit fiktiven Beispielen."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs/developer/templates/playbook.md"
sys.path.insert(0, str(ROOT / "scripts"))

from check_playbook import main  # noqa: E402

PLAYBOOK = """# Playbook Beispielabteilung

**Version** 0.1
**Fachliche Verantwortung** Rolle A

## Einsatz und Eingang

**Benötigt** Musterauftrag

## Ablauf

1. Musterauftrag prüfen.

## Abnahme und Eskalation

**Fertig, wenn dokumentiert** Prüfergebnis
**Aufgabenprotokoll** Mustervermerk

## Kennzahlen und erster Auftrag

Rolle A zählt geprüfte Musteraufträge.

## Grundlagen

- Musterleitfaden
"""


def test_template_and_example(tmp_path, capsys):
    example = tmp_path / "beispiel.md"
    example.write_text(PLAYBOOK, encoding="utf-8")

    assert main([str(TEMPLATE), str(example)]) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    ("old", "new", "error"),
    [
        ("# Playbook Beispielabteilung", "#", "Titel: genau eine H1"),
        ("# Playbook Beispielabteilung", "\n# Playbook Beispielabteilung", "Titel: genau eine H1"),
        ("Rolle A zählt", "# Zweiter Titel\n\nRolle A zählt", "Titel: genau eine H1"),
        ("**Version** 0.1\n", "", "Kopfbereich: **Version** fehlt"),
        (
            "**Fachliche Verantwortung** Rolle A\n\n## Einsatz und Eingang",
            "## Einsatz und Eingang\n\n**Fachliche Verantwortung** Rolle A",
            "Kopfbereich: **Fachliche Verantwortung** fehlt",
        ),
        (
            "**Version** 0.1",
            "**Version** 0.1\n**Version** 0.2",
            "Kopfbereich: **Version** kommt mehrfach vor",
        ),
        (
            "## Kennzahlen und erster Auftrag\n",
            "",
            "Kennzahlen und erster Auftrag: Abschnitt fehlt",
        ),
        (
            "## Einsatz und Eingang\n\n**Benötigt** Musterauftrag\n\n"
            "## Ablauf\n\n1. Musterauftrag prüfen.",
            "## Ablauf\n\n1. Musterauftrag prüfen.\n\n"
            "## Einsatz und Eingang\n\n**Benötigt** Musterauftrag",
            "Überschriften: Abschnitte stehen in falscher Reihenfolge",
        ),
        (
            "1. Musterauftrag prüfen.",
            "1. Musterauftrag prüfen.\n\n## Ablauf",
            "Ablauf: Abschnitt kommt mehrfach vor",
        ),
        ("## Ablauf", "## Ablauf\n\n## Musterabschnitt", "Überschriften: unerwarteter Abschnitt"),
        (
            "**Benötigt** Musterauftrag",
            "Musterauftrag",
            "Einsatz und Eingang: **Benötigt** fehlt",
        ),
        (
            "**Fertig, wenn dokumentiert** Prüfergebnis\n",
            "",
            "Abnahme und Eskalation: **Fertig, wenn dokumentiert** fehlt",
        ),
        (
            "**Aufgabenprotokoll** Mustervermerk\n",
            "",
            "Abnahme und Eskalation: **Aufgabenprotokoll** fehlt",
        ),
        (
            "1. Musterauftrag prüfen.",
            "- Musterauftrag prüfen.",
            "Ablauf: nummerierte Liste fehlt",
        ),
        ("- Musterleitfaden", "Musterleitfaden", "Grundlagen: Listenpunkt fehlt"),
        (
            "## Grundlagen\n\n- Musterleitfaden",
            "```markdown\n## Grundlagen\n\n- Musterleitfaden\n```",
            "Grundlagen: Abschnitt fehlt",
        ),
        (
            "1. Musterauftrag prüfen.",
            "~~~~text\n~~~\n1. Musterauftrag prüfen.\n~~~~",
            "Ablauf: nummerierte Liste fehlt",
        ),
        (
            "**Benötigt** Musterauftrag",
            "    **Benötigt** Musterauftrag",
            "Einsatz und Eingang: **Benötigt** fehlt",
        ),
    ],
)
def test_invalid_structure(tmp_path, capsys, old, new, error):
    path = tmp_path / "beispiel.md"
    path.write_text(PLAYBOOK.replace(old, new, 1), encoding="utf-8")

    assert main([str(path)]) == 1
    assert any(line.startswith(f"{path}: {error}") for line in capsys.readouterr().err.splitlines())


@pytest.mark.parametrize("invalid_utf8", [False, True])
def test_unreadable_file_takes_precedence(tmp_path, capsys, invalid_utf8):
    unreadable = tmp_path / "unlesbar.md"
    if invalid_utf8:
        unreadable.write_bytes(b"\xff")
    invalid = tmp_path / "ungueltig.md"
    invalid.write_text(
        PLAYBOOK.replace("# Playbook Beispielabteilung", "Kein Titel"), encoding="utf-8"
    )

    assert main([str(unreadable), str(invalid)]) == 2
    errors = capsys.readouterr().err.splitlines()
    assert errors == [
        f"{unreadable}: Datei: Datei kann nicht als UTF-8 gelesen werden",
        f"{invalid}: Titel: genau eine H1 mit Inhalt als erste Zeile erwartet",
    ]
