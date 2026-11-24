# Kennzahlen prüfen

Echte Kennzahlen und Werte gehören nicht ins öffentliche Repository. Die [Beispieldatei](examples/kpi-beispiel.json) enthält ausschließlich fiktive Daten.

## Aufbau

Die JSON-Datei enthält eine Liste von Kennzahlen. Jedes Objekt enthält alle folgenden Felder. Zusätzliche Felder sind unzulässig.

| Feld | Regel |
| --- | --- |
| `id` | Eindeutige, nicht leere Zeichenkette. |
| `name`, `definition`, `messmethode` | Jeweils eine nicht leere Zeichenkette. |
| `ist_baseline` | `null`, eine Zahl oder eine nicht leere Zeichenkette. Ein gesetzter Wert erfordert eine Quelle. |
| `zielwert` | `null` für `kandidat`. Für `bestaetigt` eine Zahl oder eine nicht leere Zeichenkette. |
| `status` | `kandidat` oder `bestaetigt`. |
| `quelle` | `null` oder eine nicht leere Zeichenkette. |

Text aus reinem Leerraum gilt als leer. Boolesche Werte sind als Ist-Baseline und Zielwert unzulässig. Bestätigte Kennzahlen benötigen einen Zielwert und, wie alle Kennzahlen, eine Messmethode.

## Aufruf

```bash
python3 scripts/validate_kpi.py docs/governance/examples/kpi-beispiel.json
```

Der Prüfer schreibt je Fehler eine Zeile im Format `id: feld: meldung` auf die Standardfehlerausgabe. Ohne gültige ID verwendet er die Position, etwa `eintrag[0]`. Fehler auf Dateiebene verwenden `datei` als Kennung.

| Exit-Code | Ergebnis |
| --- | --- |
| `0` | Die Liste ist gültig. |
| `1` | Das Dokument verletzt mindestens eine Schema- oder Fachregel. |
| `2` | Die Datei ist nicht lesbar, enthält ungültiges JSON oder der Aufruf ist fehlerhaft. |
