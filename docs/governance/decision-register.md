# Entscheidungs- und Änderungsregister

Das Register ist eine JSON-Liste. Die [Beispieldatei](examples/decision-register-beispiel.json) enthält ausschließlich fiktive Daten. Vertrauliche Entscheidungen gehören nicht ins öffentliche Repository.

## Pflichtfelder

| Feld | Bedeutung und Format |
| --- | --- |
| `id` | Eindeutige Kennung mit `DEC-` und mindestens drei Ziffern, etwa `DEC-001`. |
| `entscheidungstraeger` | Entscheidende Rolle oder Stelle als nicht leere Zeichenkette. |
| `freigabe` | Angabe zur Freigabe als nicht leere Zeichenkette. |
| `scope` | Beschreibung der Entscheidung oder Änderung und ihres Geltungsbereichs als nicht leere Zeichenkette. |
| `owner` | Verantwortliche Rolle oder Stelle als nicht leere Zeichenkette. |
| `status` | Aktueller Status des Eintrags. |
| `evidence` | Liste von Zeichenketten mit Nachweisen oder Verweisen auf Nachweise. |
| `historie` | Nicht leere Liste von Objekten mit `datum`, `status` und `von`. |

Zusätzliche Felder sind in Register- und Historieneinträgen unzulässig. Eine Zeichenkette, die nur Leerraum enthält, gilt bei Pflichttexten als leer.

## Status und Abschluss

Erlaubt sind `vorgeschlagen`, `freigegeben`, `umgesetzt`, `verifiziert`, `dokumentiert`, `abgeschlossen` und `abgelehnt`. Bei `umgesetzt`, `verifiziert`, `dokumentiert` und `abgeschlossen` muss `evidence` mindestens einen Eintrag enthalten.

Jeder Historieneintrag enthält ein gültiges Kalenderdatum im Format `JJJJ-MM-TT`, einen erlaubten `status` und eine nicht leere Zeichenkette `von` für die handelnde Rolle oder Stelle. Die Liste ist nach Datum aufsteigend sortiert. Mehrere Einträge am selben Tag sind zulässig. Der letzte Historienstatus entspricht dem aktuellen Status.

`abgeschlossen` setzt voraus, dass `umgesetzt`, `verifiziert` und `dokumentiert` in der Historie stehen.

## Prüfung

```bash
python3 scripts/validate_decision_register.py docs/governance/examples/decision-register-beispiel.json
```

Das Skript meldet jeden Fehler mit `id: feld: meldung` auf der Standardfehlerausgabe. Ohne gültige ID nennt es die Position des Eintrags in der Liste, beginnend bei `eintrag[0]`. Dateifehler verwenden `register` als Kennung.

| Exit-Code | Ergebnis |
| --- | --- |
| `0` | Register ist gültig. |
| `1` | Register verletzt mindestens eine Regel. |
| `2` | Datei ist nicht lesbar oder enthält ungültiges JSON. |

Der bestehende CI-Job „Backend“ prüft die Beispieldatei über `pytest`.
