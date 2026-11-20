# ALINE-START-001 – GitHub-Actions-Einmal-Test

Status: **Draft / technisch vorbereitet / NICHT AUSGEFÜHRT**. Diese Datei ist kein Nachweis für einen echten OpenAI-Modellaufruf.

## Ausgangspunkt

Repository: tiktokagentur-art/gmv-foundation (öffentlich). Der Worker aus Draft-PR #31 bleibt auf dem unveränderten Commit 6dc875ecd4e7acb70b7f09023ab9af08d5c906ec. Nur die synthetische Fixture (Git-Blob d6ff931080fa69de5998f2626e8c2702509242f1) ist zugelassen. Railway GMV-V3/staging bleibt unverändert im Offline-Demo-Modus. Das Testprotokoll vom 20.11.2026, 02:07 UTC dokumentiert null belegte echte Modellaufrufe; manuelle API-Läufe außerhalb der geprüften Logs bleiben unklar.

## Voraussetzungen vor einer Freigabe (NO-GO bei Nichterfüllung)

1. **Doppelausführung ausschließen:** Die OpenAI-Projekt-Usage und frühere manuelle Codex-, CLI- und Agent-Ausführungen vorab prüfen. Dieser Workflow erkennt frühere Läufe nur innerhalb **seiner eigenen** Actions-Historie. Bei unklarem Ergebnis **nicht auslösen**.
2. **OpenAI-Berechtigungen und Budget prüfen:** Das öffentliche Modell gpt-6.1-terra muss für das konkrete Projekt zugänglich sein. Das ursprünglich genehmigte Pilotbudget von maximal 2 USD muss administrativ begrenzt und überprüft sein; die Tokenbegrenzung im Code ist keine Dollar-Sperre. Keine zusätzlichen Modellaufrufe nur zum Prüfen.
3. **GitHub-Environment vorbereiten:** Unter Settings → Environments ein geschütztes Environment namens aline-l1-staging einrichten, Deployment-Branches auf main beschränken und nach Möglichkeit unabhängige Required Reviewer hinterlegen. Nur dort einen dedizierten Projekt-API-Schlüssel als Environment-Secret OPENAI_API_KEY hinterlegen. Railway-Secrets nicht auslesen. Keine Secrets in Chat, Repository, PR, Wiki oder Logs.
4. **Review und CI:** Deniz prüft Engineering, Shafo prüft Secrets, Herkunft des gepinnten Worker-Codes, Ausführungsfreigaben und Negativtests. Alle drei GitHub-CI-Jobs am tatsächlichen Head müssen bestanden sein.
5. **Separate Merge-Freigabe:** GitHub ermöglicht workflow_dispatch erst, wenn die Workflow-Datei auf dem Default-Branch main existiert. Draft-PR nicht ungeprüft mergen. PR #31 bleibt Draft; kein Railway-Deployment, kein produktiver Zugriff und keine Berechtigungsvergabe durch diesen PR.

## Sicherheitskonzept und Ausführung

Workflow: .github/workflows/aline-start-001-once.yml. Guard: scripts/aline_start_001_guard.py.

- Ausschließlich manueller workflow_dispatch; kein Push-, Pull-Request-, Schedule- oder Workflow-Run-Trigger, keine automatischen Retries.
- Actor exakt tiktokagentur-art auf refs/heads/main und GitHub run_attempt gleich 1.
- Eingabebestätigung exakt: **ALINE-START-001 EINMALIG FREIGEGEBEN**.
- GitHub-Actions-Historienprüfung mit actions:read und Fail-Closed-Verhalten: Genau ein Lauf, der aktuelle, darf existieren. Eine zweite Ausführung ist gesperrt, auch nach Fehlern. Nach eventueller GitHub-Environment-Freigabe wird das erneut geprüft.
- Worker-Checkout auf exakten Commit festgelegt, geprüftes Fixture mit Git-Blob-Pin, lokale Offline-Demo und SDK-Sanity-Check vor dem Modellaufruf.
- Einmalige Ausführung des bestehenden Workers mit confirm-api-call und confirm-data-transfer, festem OPENAI_MODEL=gpt-6.1-terra; nur synthetische Daten, keine Tools, keine Handoffs, keine Writes, keine Client-Retries, ein Agent-Turn, maximal 2.000 Output-Tokens, Tracing aus.
- Abnahme verlangt eine gültige strukturierte Antwort mit EX-001 und EX-002 in P0/P1-Reihenfolge und jeweils evidence_status=unknown. Die Logs enthalten nur reduziertes Ergebnis-Metadatum. Die Ausgabe wird nach der Auswertung gelöscht.
- Fehler, Timeout, verlorene Antwort, Budget- oder Berechtigungszweifel: **Nicht wiederholen.** Ein fehlgeschlagener Runner beweist nicht, dass die Anfrage unberechnet blieb.

Der Historienschutz kann keine Modellaufrufe außerhalb dieses Workflows nachweisen. Ein GitHub-Workflow ist keine globale, manipulationssichere Einmal-Sperre und ersetzt keine OpenAI-Ausgabenlimits.

## Manuelle Aktivierung – erst nach vollständiger Abnahme

GitHub → Actions → ALINE-START-001 One-shot OpenAI test → Run workflow → Branch main → Bestätigungszeichenfolge eintragen → Run workflow. Bei aktiviertem Environment-Gate die gesonderte Freigabe einholen. **Niemals mehrfach auslösen oder Re-run verwenden.**

## Nachweise

- Offline-Negativtests: python -m unittest discover -s tests -p test_aline_start_001_guard.py -v
- GitHub-CI auf aktuellem PR-Head (Backend / Image / Lint and structure)
- Erst nach einem autorisierten echten Lauf: Actions-Run-URL, minimaler PASS/NO-GO-Status und manuelle OpenAI-Usage-/Kostenprüfung.
