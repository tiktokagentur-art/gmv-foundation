# Statusmodell prüfen

Die [Beispieldatei](examples/status-model-beispiel.json) enthält ausschließlich fiktive Daten. Echte Abteilungsmodelle und Daten gehören nicht ins öffentliche Repository.

## Aufbau

Die JSON-Datei enthält das Objekt `modell` und die Liste `eintraege`.

| Modellfeld | Bedeutung |
| --- | --- |
| `stufen` | Liste eindeutiger Statusnamen. |
| `start` | Erste Stufe jeder Historie. |
| `endstufen` | Für jede Endstufe ein Objekt mit `grund: true` und einem booleschen Wert für `wiedervorlage`. |
| `uebergaenge` | Erlaubte Folgestufen pro Stufe. Ein fehlender Eintrag bedeutet, dass keine Folgestufe erlaubt ist. Endstufen haben keine Folgestufen. |
| `pflichtfelder_ab` | Pflichtfelder auf Eintragsebene ab dem ersten Erreichen der jeweiligen Stufe. |
| `gates` | Pro Stufe die Rolle, deren Vermerk für den Eintritt erforderlich ist. |

Jeder Eintrag enthält eine eindeutige Text-`id`, den aktuellen `status` und eine nicht leere `historie`. Weitere Felder sind frei. Ein Pflichtfeld braucht einen Wert. `null`, leere Objekte und Listen sowie leere Texte oder Texte aus reinem Leerraum gelten als leer.

Jeder Historienschritt enthält `datum` im Format `JJJJ-MM-TT`, `status` und `von` für die handelnde Rolle. Die Schritte sind nach Datum aufsteigend sortiert. Mehrere Schritte am selben Tag sind zulässig. Die Historie beginnt mit der Startstufe, folgt den erlaubten Übergängen und endet beim aktuellen Status. Eine Stufe mit Gate erfordert im betreffenden Schritt einen `vermerk` mit passender `rolle` und nicht leerem `text`.

Ein Eintrag in einer Endstufe braucht einen nicht leeren `grund`. Ist für die Endstufe eine Wiedervorlage vorgesehen, muss `wiedervorlage` ein gültiges Datum am Eintrittstag oder später sein.

## Aufruf

```bash
python3 scripts/validate_status_model.py docs/governance/examples/status-model-beispiel.json
```

Die Standardfehlerausgabe enthält eine Zeile pro Fehler im Format `id: feld: meldung`. Ohne gültige ID verwendet der Prüfer die Position `eintrag[0]` oder entsprechend höhere Indizes. Fehler im Modell oder in der Datei verwenden `modell` oder `datei` als Kennung.

| Exit-Code | Ergebnis |
| --- | --- |
| `0` | Modell und Einträge sind gültig. |
| `1` | Modell oder Einträge verletzen mindestens eine Regel. |
| `2` | Die Datei ist nicht lesbar oder enthält ungültiges JSON. Auch ein fehlerhafter Aufruf liefert `2`. |
