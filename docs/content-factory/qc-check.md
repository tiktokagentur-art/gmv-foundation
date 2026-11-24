# Prüfvermerk für die Content Factory

Vor der Übergabe eines Videos müssen alle acht Prüfpunkte dokumentiert sein.
Die JSON-Datei enthält eine Liste von Prüfvermerken. Jeder Vermerk enthält eine
eindeutige `id`, einen fiktiven Videoverweis (`video`), die `erstellende_rolle`,
ein Kalenderdatum (`datum`, Format `JJJJ-MM-TT`) und das Objekt `punkte`.
Zusätzliche Felder sind auf jeder Ebene unzulässig.

1. Aussagen (`aussagen`)
2. Bild (`bild`)
3. Ton (`ton`)
4. Rechte (`rechte`)
5. Untertitel (`untertitel`)
6. Caption (`caption`)
7. Kennzeichnung (`kennzeichnung`)
8. Tool-Lizenz (`tool_lizenz`)

Je Punkt sind `ergebnis` und `pruefende_rolle` Pflicht. Eine `notiz` als Text
ist optional. Die prüfende Rolle muss von der erstellenden Rolle abweichen.
Beim Vergleich ignoriert das Skript Groß- und Kleinschreibung sowie Leerraum
am Anfang und Ende. Für die Übergabe sind `bestanden` und, außer bei der
Kennzeichnung, `nicht_anwendbar` zulässig. Bei `nicht_bestanden` bleibt
der Vermerk unvollständig.

Bei Punkt 7 ist eine sichtbare KI-Kennzeichnung einschließlich der
Kennzeichnung von KI-Avataren Pflicht (`ki_kennzeichnung_sichtbar: true`).
Das Pflichtfeld `c2pa` akzeptiert `nicht_vorhanden` oder `vorhanden_gueltig`.
Der Wert `vorhanden_ungueltig` führt zu einem Fehler.

Bei Punkt 8 ist `tools` eine Liste. Für jedes Tool sind `name`, `tarif`
(`free` oder `kommerziell`) und `nutzung` (`intern` oder `extern`) Pflicht.
Tools im Free-Tarif dürfen nur intern genutzt werden.

## Prüfvermerke prüfen

Führe den Befehl im Repository-Stamm aus.

```bash
python3 scripts/validate_qc_check.py docs/content-factory/examples/qc-check-beispiel.json
```

Das Skript schreibt Fehler zeilenweise im Format `id: feld: meldung` auf
die Standardfehlerausgabe.

- Exit-Code `0` steht für gültige Prüfvermerke.
- Exit-Code `1` steht für Schemafehler oder unvollständige Prüfvermerke.
- Exit-Code `2` steht für einen Aufruf- oder Lesefehler oder ungültiges JSON.

Die [Beispielvermerke](examples/qc-check-beispiel.json) sind vollständig fiktiv.
Das Skript ersetzt keine Rechtsprüfung. Echte Videos und Personen gehören
nicht in dieses öffentliche Repository.
