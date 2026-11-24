"""Prüft die Markdown-Struktur von Playbooks."""

import argparse
import re
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from schema_check import report_errors  # noqa: E402

SECTIONS = (
    "Einsatz und Eingang",
    "Ablauf",
    "Abnahme und Eskalation",
    "Kennzahlen und erster Auftrag",
    "Grundlagen",
)
HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*)|$)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
ORDERED_ITEM = re.compile(r"^ {0,3}[0-9]{1,9}[.)][ \t]+\S")
BULLET_ITEM = re.compile(r"^ {0,3}[-+*][ \t]+\S")


def _text_lines(document: str) -> Iterator[tuple[int, str]]:
    fence = ""
    for number, line in enumerate(document.splitlines(), start=1):
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = ""
        elif marker and (marker[1][0] == "~" or "`" not in marker[2]):
            fence = marker[1]
        elif not line.expandtabs(4).startswith("    "):
            yield number, line


def _check_labels(
    lines: list[str], labels: Sequence[str], *, unique: bool = False
) -> Iterator[str]:
    for label in labels:
        pattern = re.compile(rf"^ {{0,3}}\*\*{re.escape(label)}\*\*(?=[ \t:]|$)")
        count = sum(bool(pattern.match(line)) for line in lines)
        if count == 0:
            yield f"**{label}** fehlt"
        elif unique and count > 1:
            yield f"**{label}** kommt mehrfach vor"


def validate(document: str, path: Path) -> Iterator[str]:
    """Liefert die Strukturfehler mit Dateipfad und Abschnitt."""
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}
    lines = preamble
    titles: list[tuple[int, str]] = []

    for number, line in _text_lines(document):
        heading = HEADING.match(line)
        if not heading:
            lines.append(line)
            continue
        title = re.sub(r"(?:^|[ \t]+)#+$", "", (heading[2] or "").strip()).rstrip()
        if heading[1] == "#":
            titles.append((number, title))
        elif heading[1] == "##":
            lines = []
            if title not in SECTIONS:
                yield f"{path}: Überschriften: unerwarteter Abschnitt in Zeile {number}"
            elif title in sections:
                yield f"{path}: {title}: Abschnitt kommt mehrfach vor"
            else:
                sections[title] = lines

    if len(titles) != 1 or titles[0][0] != 1 or not titles[0][1]:
        yield f"{path}: Titel: genau eine H1 mit Inhalt als erste Zeile erwartet"

    for error in _check_labels(preamble, ("Version", "Fachliche Verantwortung"), unique=True):
        yield f"{path}: Kopfbereich: {error}"

    for section in SECTIONS:
        if section not in sections:
            yield f"{path}: {section}: Abschnitt fehlt"
    if tuple(sections) != tuple(section for section in SECTIONS if section in sections):
        yield f"{path}: Überschriften: Abschnitte stehen in falscher Reihenfolge"

    required_labels = {
        "Einsatz und Eingang": ("Benötigt",),
        "Abnahme und Eskalation": ("Fertig, wenn dokumentiert", "Aufgabenprotokoll"),
    }
    for section, labels in required_labels.items():
        if section in sections:
            for error in _check_labels(sections[section], labels):
                yield f"{path}: {section}: {error}"

    if "Ablauf" in sections and not any(ORDERED_ITEM.match(line) for line in sections["Ablauf"]):
        yield f"{path}: Ablauf: nummerierte Liste fehlt"
    if "Grundlagen" in sections and not any(
        BULLET_ITEM.match(line) or ORDERED_ITEM.match(line) for line in sections["Grundlagen"]
    ):
        yield f"{path}: Grundlagen: Listenpunkt fehlt"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dateien", type=Path, nargs="+", help="Pfade zu den Markdown-Dateien")
    args = parser.parse_args(argv)

    status = 0
    for path in args.dateien:
        try:
            document = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            result = report_errors(
                [f"{path}: Datei: Datei kann nicht als UTF-8 gelesen werden"], exit_code=2
            )
        else:
            result = report_errors(validate(document, path))
        status = max(status, result)
    return status


if __name__ == "__main__":
    sys.exit(main())
