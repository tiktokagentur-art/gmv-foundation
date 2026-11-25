# Datenfeldkatalog für den Portal-Pilot

Die Datenschutzprüfung ist offen. Für den Pilot sind ausschließlich fiktive Testdaten zulässig. Echte Einträge, Personen- und Kontaktdaten sowie Listen gehören weder ins Repo noch nach Notion. `rechtsgrundlage` bleibt bis zum Abschluss der Datenschutzprüfung auf `platzhalter-bis-datenschutzpruefung`.

Das JSON-Objekt enthält ausschließlich die Pflichtliste `eintraege`. Sie darf leer sein. Jeder Eintrag hat diese Pflichtfelder.

| Feld | Vorgabe |
| --- | --- |
| `id` | Nicht leerer Text, in der Datei eindeutig |
| `rolle` | `haendler` oder `creator` |
| `bezeichnung` | Nicht leere, fiktive Geschäfts- oder Shopbezeichnung |
| `region` | Nicht leerer Text |
| `datenquelle` | Nicht leerer Text zur Herkunft der fiktiven Daten |
| `rechtsgrundlage` | `platzhalter-bis-datenschutzpruefung` |
| `status` | `fiktiv` |

Zusätzliche Felder sind unzulässig, insbesondere `name`, `personenname`, `email`, `telefon`, `preis` und `firmenliste`. Die inhaltliche Prüfung der Freitextfelder auf fiktive Angaben erfolgt bei der Durchsicht.

```bash
python scripts/validate_portal_datenfelder.py docs/portal/examples/datenfelder-beispiel.json
```

Der Validator liefert Exit-Code `0` bei gültigen Daten, `1` bei Feldfehlern und `2` bei einem Aufruf-, Lese- oder JSON-Fehler. Feldfehler erscheinen je Zeile im Format `id: feld: meldung`.
