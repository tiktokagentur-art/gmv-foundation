# Briefing für die Content Factory

Das Briefing für einen deutschsprachigen TikTok-Kurzbeitrag ist ein JSON-Objekt
mit fünf Pflichtfeldern. Zusätzliche Felder führen zu einem Fehler.

| Feld | Inhalt |
| --- | --- |
| `thema` | Worum es im Beitrag geht. |
| `zielgruppe` | Für wen der Beitrag gedacht ist. |
| `quellen` | Liste der Quellen für die Aussagen im Beitrag. |
| `format` | Geplante Form des Beitrags, etwa Dauer und Bildformat. |
| `rechteinformationen` | Angaben zu Nutzungsrechten und Freigaben für das verwendete Material. |

`quellen` enthält mindestens einen Eintrag. Alle Einträge und die übrigen
Pflichtfelder bestehen aus Text, der nach Entfernen von Leerraum am Anfang und
Ende mindestens ein Zeichen enthält.

## Briefing prüfen

Rufe das Skript im Repository-Stamm auf. Du kannst mehrere Dateipfade übergeben.

```bash
python3 scripts/validate_briefing.py docs/content-factory/examples/briefing-beispiel.json
```

Das Skript schreibt pro Fehler eine Zeile im Format `datei: feld: meldung` auf
die Standardfehlerausgabe. `$` steht für die gesamte Datei.

- Exit-Code `0` bedeutet, dass alle Briefings gültig sind.
- Exit-Code `1` bedeutet, dass mindestens ein Briefing das Schema verletzt.
- Exit-Code `2` bedeutet, dass mindestens eine Datei nicht als UTF-8 lesbar
  ist oder ungültiges JSON enthält. Dieser Code hat Vorrang vor `1`.

Das [Beispielbriefing](examples/briefing-beispiel.json) ist vollständig fiktiv.
Echte Briefings gehören nicht in dieses öffentliche Repository.
