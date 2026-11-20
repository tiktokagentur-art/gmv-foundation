# ALINE-LIVE-001 – Runbook für den L1-Live-Pilot

Stand: 2026-11-20. Status: **STAGING-VORBEREITUNG, NICHT LIVE**.

## Architektur

`prototypes/aline-openai-worker` bleibt die einzige Aline-Runtime. Der vorhandene
Worker aus Draft-PR #31 und der FastAPI-Adapter aus Draft-PR #32 werden erweitert.
Der bestehende Railway-Service `aline-openai-worker-l1` in `GMV-V3/staging`
(Service `5ed8e317-04a6-49b5-828e-d01bc0903b23`) ist das spätere Ziel.
Sein derzeitiger Startbefehl führt `--offline-demo` aus. Das erfolgreiche
Deployment `024bac02-855e-416e-bb2d-26edc5f3bdb0` hatte null API-Aufrufe;
es ist kein Live-Nachweis.

`Dockerfile.api` startet denselben Worker als dauerhaften FastAPI-Prozess.
`GET /health` prüft nur Prozessliveness; `GET /ready` prüft lokale Gates, **nicht**
den Provider. `GET /v1/status`, `POST /v1/dialog` und `POST /v1/stop` benötigen
`X-CEO-Token`; das alte `POST /v1/offline-analysis` behält `X-Pilot-Token`.
OpenAPI/Swagger und Access-Logs sind abgeschaltet. Ereignislogs enthalten nur
Zeitpunkt, Ereignis, Worker-ID, Run-ID und Fehlerklasse, keine Inhalte oder Keys.
Ein gültiges Token ist keine Personalidentitätsprüfung; es muss ausschließlich
dem CEO über den freigegebenen Secret-Prozess zugewiesen werden. Keine Domain
öffnen, bevor HTTPS, Authentisierung und Rate-/Budgetgates abgenommen sind.

## Harte Ausführungsgrenzen

- Agent `GMV-VE-001`, nur `gpt-6.1-terra`, ein Responses-API-Turn, maximal
  128 Ausgabetokens, 45 Sekunden Timeout, null SDK-Retries, keine Tools.
- Standardmäßig nur die exakte synthetische Begrüßung aus ALINE-LIVE-001.
  Weitere CEO-Texte erst nach gesonderter Korridorfreigabe und
  `ALINE_CEO_DIALOG_APPROVED=true`; keine echten Tickets/PII oder externen
  Quellen im bisherigen ADR-0015-Korridor.
- Ein Aufruf gleichzeitig, maximal fünf reservierte Pilot-Aufrufe, maximal
  10 USD **über die gesamte Pilotlaufzeit** inklusive verifiziertem
  Vorverbrauch. Pro Aufruf höchstens 2 USD konservative Reservierung.
  Erfolgreiche Usage wird mit dem geprüften Preis von 1 USD/M Eingabe- und
  5 USD/M Ausgabetokens geschätzt (Stand 2026-11-20). Bei unklarem Ausgang
  bleibt die Reservierung belegt und der Pilot hält an.
- Die SQLite-Buchung muss auf einem vorhandenen persistenten Railway-Volume
  liegen. Ein Neustart darf die Bilanz oder den Stop-Zustand nicht löschen.
  Nur **eine** Railway-Replik; bei Replikas >1 ist der Volumenspeicher kein
  ausreichend geprüfter globaler Ausführungslock.
- Der lokale Zähler ersetzt weder den OpenAI-Projektausgaben-Readback noch ein
  Providerlimit. Durch verzögertes Provider-Billing kann auch `Enforce a hard
  limit` später als der tatsächliche Verbrauch greifen. Deshalb wird weit
  unterhalb der 10-USD-Grenze reserviert und nach Unsicherheit gestoppt.

## Für Staging vorzubereitende Konfiguration

Alle Secret-Werte ausschließlich in Railway-Staging; niemals in Git/PR/Logs.

| Name | Bedeutung |
| --- | --- |
| `ALINE_LIVE_ENABLED` | `false` bis nach technischer Abnahme und CEO-GO |
| `ALINE_CEO_TOKEN` | separater, zufälliger Wert mit mindestens 32 Zeichen |
| `ALINE_PILOT_TOKEN` | bestehender Offline-Token, separat |
| `OPENAI_API_KEY` | Key des dedizierten Aline-Projekt-Service-Accounts |
| `OPENAI_PROJECT_ID` | verifizierte Projekt-ID des Keys |
| `OPENAI_MODEL` | `gpt-6.1-terra` |
| `ALINE_L1_PROJECT_DEDICATED` | `true` nur nach Plattform-Readback |
| `ALINE_L1_HARD_LIMIT_ATTESTED` | `true` nur nach Prüfung von `Enforce a hard limit` ≤10 USD |
| `ALINE_L1_BUDGET_USD` | `10` |
| `ALINE_PROVIDER_READBACK_AT` | UTC-Zeitstempel der tatsächlichen Projekt-/Usage-Prüfung |
| `ALINE_PRIOR_SPEND_USD` | verifizierter bisheriger Pilotverbrauch, auch frühere Tests |
| `ALINE_LEDGER_PATH` | absoluter Pfad auf einem persistenten Volume, z. B. `/data/aline.sqlite3` |
| `ALINE_CEO_DIALOG_APPROVED` | `false`, bis ein erweiterter Dialogkorridor freigegeben ist |

Die mit `ATTESTED` benannten Variablen sind **Behauptungen**, keine unabhängigen
Provider-Nachweise. Projekt-ID, Key-Zuordnung, Billing/Guthaben,
`gpt-6.1-terra`-Berechtigung/RPM/TPM, bisherige Usage und das wirksame Limit
müssen ein OpenAI-Projektinhaber am konkreten Projekt ablesen und intern
protokollieren. Dieser Readback darf beim nächsten Aufruf höchstens 24 Stunden
alt sein. Der Statusendpunkt zeigt nur das **lokal** verbleibende Budget;
das Provider-Restbudget bleibt ohne externen Readback unbekannt. Das frühere
`RateLimitError` aus Actions-Run `44697167267`
hat keinen auslesbaren `error.code`; Ursache und Kosten sind ungeklärt.
GitHub-Environment-Variablen und Secret-Metadaten sind über den aktuellen
Zugang nicht lesbar (403). Ein GitHub-Admin muss sie separat prüfen.

## Aktivierungsablauf

1. Draft-PRs #31 und #32 sowie diesen gestapelten PR unabhängig reviewen,
   CI auf konkreter SHA prüfen und jeden Merge gesondert durch CEO freigeben.
   PRs #33, #38 und #48 nicht ungeprüft integrieren.
2. OpenAI-Projektinhaber und GitHub-Admin liefern die obigen Readbacks.
   Der CEO entscheidet separat über den erweiterten Freitextkorridor.
3. Im bestehenden Railway-Staging-Service `Dockerfile.api` als Dockerfile,
   den überprüften Branch/Commit, einen persistenten Volume-Mount und **eine**
   Replik konfigurieren. Einmaligen Cron/Offline-Startbefehl entfernen,
   Restart-Policy für den Webdienst und HTTP-Healthcheck `/health` setzen.
   Diese produktive Railway-Konfigurationsänderung benötigt ein konkretes CEO-GO.
4. Mit `ALINE_LIVE_ENABLED=false` deployen, Terminalstatus `SUCCESS`, `/health`
   200 und `/ready` 503 prüfen. Aktivierung erst nach unabhängiger Abnahme.
5. Nach CEO-GO und technischer Abnahme `ALINE_LIVE_ENABLED=true` setzen und
   `/ready` 200 prüfen. Die lokale Readiness beweist noch keinen Modellzugriff.
6. Exakt **einen** Dialog mit dem vorgegebenen Text senden. Run-/Deployment-ID,
   UTC-Zeit, Modell, echte Antwort, Usage, Kostenschätzung und Provider-Usage
   gesondert erfassen. Bei 429/Timeout/fehlender Usage nicht erneut senden;
   Ursache prüfen und den Pilot gestoppt lassen.
7. Neue Unterhaltung ohne Codeänderung prüfen; dann Status und Budget erneut
   ablesen. Keine WorkItem-/Notion-Schreibrechte, Merges, Deploys, Finanzaktionen
   oder Rechteerweiterung durch Aline.

## Widerruf

`POST /v1/stop` mit CEO-Token setzt einen persistenten Stop-Marker; neue
Aufrufe werden verweigert, auch nach Neustart. Zusätzlich
`ALINE_LIVE_ENABLED=false` setzen und bei Bedarf den Projektschlüssel sperren.
Reaktivierung erfordert neue Abnahme; Stop-Marker niemals durch einen
versteckten API-Endpunkt zurücksetzen. Ein laufender oder verlorener
Provideraufruf kann dennoch Kosten verursachen.
