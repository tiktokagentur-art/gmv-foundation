# ALINE-L1 – Dauerhaftes Testmandat und Aktivierung

Stand: 20.11.2026. CEO-Entscheidung: siehe
[ADR-0015](adr/0015-aline-l1-testmandate.md).

## Entscheidung und tatsächlicher Status

Das dauerhafte, widerrufbare L1-Testmandat ist **fachlich beschlossen**.
Es hebt die einzelne CEO-Freigabe für **künftig** ordnungsgemäß
kontrollierte, synthetische L1-Läufe auf. Es ist **nicht** gleichzusetzen
mit einer unmittelbar wirksamen technischen Startberechtigung.

Diese Dokumentation / ein Draft-PR erzeugt weder einen
GitHub-Environment-Reviewer noch ein Secret, Budgetlimit, einen
OpenAI-Aufruf, ein Deployment oder eine Worker-Identität.

## Ausgangslage und Abgrenzung

- PR #31: L1-Worker, Draft; im Railway-Staging existiert ein
  separater Dienst mit Offline-Demo-Start.
- PR #33: Notion-Adapter, Draft. Keine Erlaubnis zur Übertragung
  echter Notion-Daten an OpenAI und keine Notion-Schreibrechte.
- PR #38: Einmaliger Actions-Test, Draft. Der Einmaligkeits-
  Guard bleibt unverändert; kein Wiederverwenden als Dauer-Runner.
- GitHub-Environment `aline-l1-staging`: Schutzregeln,
  Branch-Policy und GitHub-Environment-Secret sind vor
  Aktivierung separat live zu prüfen. Railway-Servicevariablen
  ersetzen keine GitHub-Environment-Secrets.
- Frühere API-Nutzung außerhalb eines einzelnen Workflows ist
  nicht durch diesen Workflow beweisbar. Vor erstmaliger
  Aktivierung Projekt und Account prüfen.

## Dauerhafter Korridor

- Maximal 2 USD **kalkulierte** Kosten je Test, maximal
  10 USD pro Monat in einem Aline exklusiv zugeordneten
  OpenAI-Projekt mit aktiviertem Hard-Limit.
- Ein API-Aufruf je Run, keine automatischen Retries,
  höchstens ein gleichzeitig laufender Run.
- Ausschließlich verifizierte synthetische Fixture,
  gepinnter, geprüfter Worker und freigegebenes Modell.
- Keine Daten- oder Statusschreibrechte außerhalb
  minimaler nicht-sensitiver Run-Metadaten.
- Run-Identität, Usage, Modell, Ergebnis und Kosten
  in einem internen Audit erfassen; Fail Closed bei
  fehlender oder unklarer Grundlage.

## Technische Umsetzung – Akzeptanzkriterien

- [ ] Dediziertes Projekt/Identität/Secret für Aline L1
      geprüft; keine Freigabe über ein geteiltes Konto.
- [ ] Modellzugriff, Preis, Output-Cap und synthetische
      Fixture inklusive Blob/SHA validiert.
- [ ] Projekt-Limit **10 USD Hard-Limit** in OpenAI
      nachweislich gesetzt. Warnschwelle alleine reicht
      nicht; Abrechnungsverzug als Restrisiko dokumentieren.
- [ ] Gesonderter wiederholbarer L1-Runner auf geschütztem
      Branch, ohne Änderung oder Umgehung von PR #38.
- [ ] Konservative Preflight-Kostenschätzung mit
      Input-/Output-Grenzen und verfügbarem Monatsbudget.
- [ ] Serialisierung, Idempotenz-/Run-Register, keine
      Retry-Kaskade, Stop bei unbekanntem Ausführungsstatus.
- [ ] Negativtests: keine/ungültige Identität, falsches
      Modell, manipulierte Fixture, zu viele Tokens,
      Monatslimit, Run in Arbeit, API-Fehler/Timeout,
      unklare Usage, fehlendes Secret.
- [ ] CI auf aktuellem Runner-Commit grün, Code-
      und Security-Review abgeschlossen.
- [ ] Dokumentierte CEO-**Aktivierung des Korridors
      einmalig**. Danach kein gesondertes CEO-OK
      für jeden konformen Einzeltest.
- [ ] Dashboard / Audit zeigt Tests, Ablehnungen,
      Summenkosten und Widerrufsmöglichkeit.
- [ ] Temporäre Self-Review-Ausnahme nach Ablauf
      zurückgenommen; Admin Bypass bleibt aus.

## Ausführungsentscheidung

Solange ein technisches Gate offen ist: **NO-GO für echte
L1-API-Aufrufe im Dauerbetrieb.** Zulässig bleiben
Implementierung, Reviews, statische Analyse, CI und
Offline-Tests innerhalb der bereits bestehenden Rechte.

Die einmalige Aktivierung ist keine Merge- oder
Produktionsfreigabe und ersetzt nicht die Rechte der
Assignment Authority nach ADR-0003.
