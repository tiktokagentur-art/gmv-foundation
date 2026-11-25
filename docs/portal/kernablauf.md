# Portal-Kernablauf im Pilot

Sobald das Portal in Staging verfügbar ist, wird der Ablauf einmal mit zwei getrennten fiktiven Konten durchgespielt. Das Händlerkonto arbeitet im Shop-Portal, das Creator-Konto im Creator-Portal. Beim Kontowechsel prüfen, dass jedes Konto Zugriff auf den eigenen Arbeitsbereich hat und der andere Arbeitsbereich gesperrt ist.

## Abnahme in Staging

1. **Kampagne (`kampagne`).** Im Shop-Portal legt die Händlerrolle eine Kampagne für ein fiktives Produkt an. Sie hält Produkt, gewünschtes Videoformat und die Verfügbarkeit eines Musters fest und gibt die Kampagne zur Anzeige im Creator-Portal frei.
2. **Interesse (`interesse`).** Die Creator-Rolle öffnet die Kampagne und meldet Interesse. Die Händlerrolle prüft, ob die Meldung der richtigen Kampagne zugeordnet ist.
3. **Musteranfrage (`musteranfrage`).** Die Creator-Rolle fragt ein fiktives Muster an. Die Händlerrolle prüft Kampagnenbezug, Produkt und Menge im Shop-Portal.
4. **Entscheidung (`entscheidung`).** Die Händlerrolle genehmigt die Musteranfrage und erfasst eine kurze Begründung. Im Creator-Portal ist die Entscheidung sichtbar.
5. **Videolink (`videolink`).** Die Creator-Rolle reicht einen Platzhalterlink ein. Die Händlerrolle prüft, ob der Link im Shop-Portal zur richtigen Kampagne angezeigt wird.
6. **Feedback (`feedback`).** Die Händlerrolle hält eine Rückmeldung zum vereinbarten Videoformat fest. Die Creator-Rolle prüft, ob das Feedback beim eingereichten Link sichtbar ist.

## JSON prüfen

Das [fiktive Beispiel](examples/kernablauf-beispiel.json) hält die Prüfschritte in der vorgesehenen Reihenfolge fest. Bei der Abnahme werden Status und Beobachtungen je Schritt dokumentiert. Aus dem Repo-Stammverzeichnis lässt sich das Beispiel so prüfen.

```sh
python3 scripts/validate_kernablauf.py docs/portal/examples/kernablauf-beispiel.json
```

Der Validator meldet Schemafehler zeilenweise im Format `id: feld: meldung`. Exit-Code `0` steht für ein gültiges Beispiel, `1` für Schemafehler und `2` für Aufruf- oder Eingabefehler wie eine unlesbare Datei oder ungültiges JSON. Die Funktionsprüfung der Portal-Ansichten erfolgt in Staging.

## Fiktive Daten

Für den Pilot gelten ausschließlich fiktive Daten und interne Abläufe ohne externe Ansprache. Echte Personen, Händler und Creators sowie echte Personendaten gehören nicht ins öffentliche Repo. Rechtsgrundlagen bleiben Platzhalter.
