# ALINE-HELLO-001 – begrenzte manuelle Dialogtests

## CEO-Freigabe, 20.11.2026

Mehr als ein Test ist zulässig. Diese konservative technische Umsetzung erlaubt
**höchstens fünf zusätzliche manuelle Dispatches** über die drei bereits
dokumentierten Läufe hinaus; das ist kein unbegrenztes Testmandat.
Die frühere Einmal-Regel wird nur innerhalb dieses Korridors ersetzt.

## Bisherige Läufe

- [#44694430741](https://github.com/tiktokagentur-art/gmv-foundation/actions/runs/44694430741): failure, vor Runnerstart, keine Steps, kein Modellaufruf.
- [#44697167267](https://github.com/tiktokagentur-art/gmv-foundation/actions/runs/44697167267): failure, echte API-Verbindung versucht; `RateLimitError`, keine Aline-Antwort. Ob Quote, Guthaben oder anderes API-Limit auslöste, ist noch nicht verifiziert.
- [#44705555401](https://github.com/tiktokagentur-art/gmv-foundation/actions/runs/44705555401): am 20.11. um 09:49 Uhr wartend auf Environment-Freigabe. **Diesen alten Lauf abbrechen**. Er wurde mit der früheren Workflow-SHA gestartet und übernimmt keine nachträglich gemergten Änderungen. Neue Testläufe sind erst nach seinem Abschluss zulässig.

## Ausführungsgrenzen

- Nur CEO-Actor `tiktokagentur-art` einschließlich unveränderlicher GitHub-ID.
- Nur `workflow_dispatch` auf `main`; keine Zeitplanung, kein Push- oder PR-Trigger.
- Insgesamt maximal acht Dispatches in dieser Workflow-Historie: die drei historischen und **fünf weitere**.
- Historische IDs, Actor, Commit, Status und Abschluss werden per GitHub-API geprüft. Die dritte Ausführung muss beendet (`cancelled` oder `failure`) sein. Alle früheren neuen Läufe müssen abgeschlossen sein. Bei unvollständiger oder unplausibler Historie: fail closed.
- Keine Reruns, keine parallelen API-Tests, keine automatischen Retries (`max_retries=0`). Jede neue Ausführung benötigt die bestehende Environment-Freigabe.
- Pro Dispatch höchstens **ein Modellturn**, maximal 128 Ausgabetokens, keine Tools, Writes, Handoffs oder Live-Ticketdaten.
- Gepinnter Aline-Worker `6dc875ecd4e7acb70b7f09023ab9af08d5c906ec`; Modell bleibt `gpt-6.1-terra`.
- Ein möglicher nächster `RateLimitError` protokolliert ausschließlich einen fest zugelassenen `error.code` (sonst `unclassified`), niemals vollständige API-Fehlermeldungen oder vertrauliche Inhalte.
- Das bereits vom CEO freigegebene **10-USD-Budget** bleibt maßgeblich. Der GitHub-Dispatch-Zähler ist *kein* Geld-Hard-Limit. Projekt-Key-Zuordnung, tatsächliche Quoten, Guthaben und Durchsetzung sind vor weiteren API-Aufrufen im OpenAI-Projekt separat zu prüfen.
- Secret `OPENAI_API_KEY` ausschließlich im geschützten `aline-l1-staging`-Environment; nie im Code oder Log.

## Freigabeprozess und nächster Test

1. Wartenden alten Lauf #44705555401 in GitHub abbrechen; **nicht** freigeben.
2. Den `RateLimitError` des zweiten Laufs im API-Projekt (Rate Limits, Billing/Quota und Usage) diagnostizieren. Kein blindes Wiederholen des fehlgeschlagenen API-Aufrufs.
3. Änderungen als Draft-PR prüfen, CI/Negativtests grün bestätigen und Merge nach `main` gesondert freigeben. **Keine Ausführung durch die Erstellung dieses PR.**
4. Erst dann einen **neuen** manuellen Workflow-Dispatch auf `main` auslösen; die vorherige wartende Ausführung nutzt noch die alte Code-SHA.
5. Den Run über `aline-l1-staging` freigeben und danach Job-Log, tatsächliche Aline-Antwort, Rate-Limit-Fehlerklasse sowie OpenAI-Usage kontrollieren.
6. Vor jedem weiteren Versuch den vorherigen Lauf auswerten; nach fünf zusätzlichen Dispatches ist der Korridor ausgeschöpft.

Dies ist nur ein synthetischer Grußtest. Der separate autonome
`aline-l1-autotest`-Runner und `ALINE_L1_ACTIVATED` bleiben unverändert.
Es erfolgen keine Railway-Deployments oder produktiven Konfigurationsänderungen.
