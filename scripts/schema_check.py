"""Wiederverwendbare Prüfungen für JSON-Schemas."""

import json
import re
import sys
from collections.abc import Collection, Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Literal

_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _reject_constant(value: str) -> None:
    raise ValueError(f"Unzulässige JSON-Konstante {value}")


def load_json(path: Path) -> tuple[object, Literal["read", "json"] | None]:
    """Liest UTF-8-JSON und meldet bei Fehlern deren Art."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None, "read"

    try:
        return json.loads(content, parse_constant=_reject_constant), None
    except (ValueError, RecursionError):
        return None, "json"


def check_fields(
    record: Mapping[str, object],
    required: Collection[str],
    allowed: Collection[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Liefert fehlende Pflichtfelder in Vorgabereihenfolge und sortierte unbekannte Felder."""
    if allowed is None:
        allowed = required
    missing = [field for field in required if field not in record]
    unknown = sorted(record.keys() - allowed)
    return missing, unknown


def is_nonempty_text(value: object) -> bool:
    """Prüft, ob nach dem Entfernen von Leerraum Text übrig bleibt."""
    return isinstance(value, str) and bool(value.strip())


def parse_iso_date(value: object) -> date | None:
    """Liefert ein gültiges Kalenderdatum im Format JJJJ-MM-TT oder None."""
    if isinstance(value, str) and _DATE_PATTERN.fullmatch(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return None


def report_errors(errors: Iterable[str], *, exit_code: Literal[1, 2] = 1) -> int:
    """Schreibt Meldungen nach stderr und liefert deren Exit-Code oder 0 ohne Meldung."""
    status = 0
    for error in errors:
        print(error, file=sys.stderr)
        status = exit_code
    return status
