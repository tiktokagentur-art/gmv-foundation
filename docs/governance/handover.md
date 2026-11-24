# Aufgabenprotokoll und Übergabe

Die Vorlage beschreibt das gemeinsame Format für Aufgabenprotokoll und Übergaben im bestehenden Aufgabenregister. Die [Beispieldatei](examples/handover-beispiel.json) enthält ausschließlich fiktive Daten. Echte Personen und Aufgaben gehören nicht ins öffentliche Repository.

Das JSON-Objekt enthält die Pflichtlisten `aufgabenprotokoll` und `uebergaben`. Beide dürfen leer sein. Jeder Eintrag hat eine nicht leere Text-`id`, die über beide Listen hinweg eindeutig ist. Alle aufgeführten Felder sind Pflichtfelder. Unbekannte Felder sind unzulässig.

## Aufgabenprotokoll

- `verantwortlich` nennt die verantwortliche Rolle als nicht leeren Text.
- `termin` ist ein gültiges Kalenderdatum im Format `JJJJ-MM-TT`.
- `status` ist `vorschlag`, `in_arbeit`, `in_pruefung` oder `erledigt`.
- `naechster_schritt` ist ein Text und darf nur bei `erledigt` leer sein.
- `ergebnis_link` beginnt mit `https://`.

## Übergabe

Neben `id` enthält jeder Eintrag die Felder `eingang`, `owner`, `erwarteter_output`, `uebergabebeleg` und `akzeptierende_stelle` als nicht leere Texte. Die akzeptierende Stelle muss sich vom Owner unterscheiden. Beim Vergleich bleiben Groß- und Kleinschreibung sowie Leerraum am Anfang und Ende außer Betracht.

## Aufruf

```bash
python3 scripts/validate_handover.py docs/governance/examples/handover-beispiel.json
```

Fehler erscheinen auf der Standardfehlerausgabe mit einer Zeile pro Meldung im Format `id: feld: meldung`. Fehlt eine gültige ID, nennt der Prüfer die Position in der Liste. Fehler auf Dateiebene verwenden `datei` als Kennung.

| Exit-Code | Bedeutung |
| --- | --- |
| `0` | Die Datei ist gültig. |
| `1` | Mindestens eine Formatregel ist verletzt. |
| `2` | Der Aufruf ist fehlerhaft oder die Datei ist nicht lesbar beziehungsweise enthält ungültiges JSON. |
