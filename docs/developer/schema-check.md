# Gemeinsame JSON-Schemaprüfung

`scripts/schema_check.py` stellt dem Briefing-Validator und dem
Entscheidungsregister gemeinsame Prüfungen aus der Python-Standardbibliothek
bereit. Jeder Validator legt seine Fachregeln und Meldungen fest.

## Ein neues Schema anbinden

Ergänze im neuen Skript wie in `validate_briefing.py` das eigene
Skriptverzeichnis in `sys.path`. Importiere danach die benötigten Funktionen
aus `schema_check` mit `# noqa: E402`.

1. Lies die Datei mit `load_json(path)`. Die Funktion erwartet einen
   `Path` und liefert den JSON-Wert und einen Fehlercode. `read` steht für
   einen Lese- oder UTF-8-Fehler, `json` für ungültiges JSON einschließlich
   `NaN` und `Infinity`. Bei Erfolg ist der Fehlercode `None`, auch wenn
   der JSON-Wert `null` ist.
2. Prüfe die erwartete Grundstruktur. Verwende für ein Objekt
   `check_fields(record, required, allowed)`. Die Funktion liefert fehlende
   Pflichtfelder in der vorgegebenen Reihenfolge und unbekannte Felder
   alphabetisch sortiert. Gib für `allowed` bei Bedarf alle zulässigen
   Felder an, einschließlich der Pflichtfelder. Ohne `allowed` sind nur
   die Pflichtfelder zulässig.
3. Prüfe Text mit `is_nonempty_text(value)` und Kalenderdaten mit
   `parse_iso_date(value)`. Letztere Funktion liefert ein `date` für ein
   gültiges Datum im Format `JJJJ-MM-TT`, sonst `None`.
4. Formatiere die Meldungen im Validator und übergib sie an
   `report_errors(errors)`. Die Funktion schreibt nach `stderr` und
   liefert bei Regelverstößen `1`, bei Lese- oder JSON-Fehlern mit
   `exit_code=2` den Code `2` und ohne Meldungen `0`.
