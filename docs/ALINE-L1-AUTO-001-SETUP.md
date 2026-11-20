# ALINE-L1-AUTO-001 – Aktivierungs- und Widerrufsverfahren

Stand: 2026-11-20. **NICHT AKTIVIERT.** Der separate Runner in
`.github/workflows/aline-l1-repeatable.yml` darf erst nach
Abschluss der folgenden Nachweise benutzt werden.

## Funktion und Grenzen

Dies ist ein **manuell via `workflow_dispatch` startbarer**, wiederholbarer
synthetischer Test. Nach Freigabe kann ein eigenständig autorisierter,
dedizierter GitHub-App-Bot die Ausführung anstoßen. Der Code allein
installiert **keinen Scheduler und keinen dauerhaft laufenden Agenten**.
Ein GitHub-Login ist keine vollständige autonome Workforce-Identität.

Die CEO-Entscheidung ist in
[ADR-0015](adr/0015-aline-l1-testmandate.md) auf dem separaten
Governance-PR #41 dokumentiert. **PR #38 bleibt ein separater
Einmal-Test und wird nicht umgangen.**

## 1. OpenAI-Projekt durch CEO/Project-Owner vorbereiten

1. Eigenes OpenAI-API-Projekt für Aline L1 zuordnen oder anlegen.
   **Nicht das allgemeine Default-Projekt** oder ein von anderen
   Workern verwendetes Projekt benutzen.
2. In den Projekt-Limits **Monthly spend limit 10 USD** setzen und
   **Enforce a hard limit** aktivieren. Ausschließlich
   Benachrichtigungsschwellen reichen **nicht** aus.
   Durchsetzungsverzug kann eine geringe Überschreitung erlauben.
3. `gpt-6.1-terra` in Model usage zulassen, unter der freigegebenen
   Preis- und Ratenlimit-Konfiguration.
4. Eigene Projekt-Service-Account-Identität samt minimalem API-Key
   erstellen; keine allgemeinen Admin-Schlüssel kopieren.
5. **Beleg**: Organisation/Projektkennung (ohne Secret),
   Hard-Limit-Status, Modellzugriff, Prüfer und Datum als private
   Abnahme dokumentieren. Eine CI-Variable ist hierfür **kein Beleg**.
6. Vor der Aktivierung die tatsächliche Nutzung dieses Projekts
   prüfen. Bei unklaren früheren Aufrufen oder offenen Kosten: NO-GO.

OpenAI-Quelle für Projekte und Hard-Limit:
https://help.openai.com/en/articles/9186755-managing-projects-in-the-api-platform

## 2. GitHub-Identität und Environment

1. Eine dedizierte GitHub-App- oder Bot-Identität installieren,
   die nur die für `workflow_dispatch` erforderlichen Rechte besitzt.
   Das normale `tiktokagentur-art`-Login ist **nicht** der Bot.
2. Bei GitHub die stabile Actor-ID und den exakten Actor-Login prüfen.
   Der Runner vergleicht `GITHUB_ACTOR_ID`,
   `GITHUB_TRIGGERING_ACTOR` und `GITHUB_ACTOR`.
3. Environment `aline-l1-autotest` separat anlegen; zulässige
   Deployment-Branches ausschließlich `main`. Kein Admin-Bypass.
4. Geschütztes **Environment-Secret** `OPENAI_API_KEY` setzen,
   nicht als Repo-Secret und niemals in Chat, Docs oder Logs.
5. Die folgenden Variablen **auf Environment-Ebene** setzen:
   `ALINE_L1_ACTIVATED=false` (bis zum Schluss),
   `ALINE_L1_PROJECT_DEDICATED=true`,
   `ALINE_L1_HARD_LIMIT_ATTESTED=true` (nur nach echtem
   OpenAI-Readback), `ALINE_L1_BUDGET_USD=10`,
   `ALINE_L1_MODEL=gpt-6.1-terra`,
   `ALINE_L1_ACTOR=<bot-login>`,
   `ALINE_L1_ACTOR_ID=<immutable-bot-id>`.
6. **Review-Gate-Design**: Die einmalige CEO-Aktivierung ist
   ein Konfigurationsentscheid. Ein ständig eingeschalteter
   `Required Reviewer` würde **jede einzelne Ausführung** erneut
   blockieren und damit das beschlossene Mandat konterkarieren.
   Für das eigene L1-Environment nach einmaliger Prüfung deshalb
   kein per-Run-Reviewer-Gate; Kompensation durch eigenes
   Projekt-Hard-Limit, eingeschränkte Bot-ID, Secret-Isolation,
   Branch-Einschränkung, Audit und Widerruf. Eine Ausnahme
   an `aline-l1-staging` wird ausdrücklich **nicht** verlängert.
7. Readback von Environment, Branch-Regel, Variablen,
   Secret-**Existenz** und Bot-Rechten. Secret niemals auslesen.

## 3. Technische Abnahme und Erstaktivierung

- [ ] ADR-0015 integriert und seine Rechts-/Betriebsgrenzen geklärt.
- [ ] PR #43 unabhängig technisch geprüft und CI auf Head grün;
      kein Merge ohne gesonderte Freigabe.
- [ ] Modell- und Preisprüfung mit aktuellem Datum dokumentiert.
      Der integrierte 2/10-USD-Preflight ist ein konservatives
      Rechenmodell, **keine** Echtzeit-Kostenkontrolle.
- [ ] Der gepinnte Worker-SHA und die synthetische Fixture geprüft.
- [ ] Negative Testfälle und Kosten-Ausreißer geprüft.
- [ ] GitHub Actor-ID des Bots geprüft, keine geteilte Identität.
- [ ] Supply-Chain-Risiko der Python-Abhängigkeiten geprüft;
      für den regulären Betrieb Versionen/Hashes absichern.
- [ ] Projektausgaben und vorherige Testläufe verifiziert.
- [ ] Eine einmalige dokumentierte CEO-Aktivierung für diesen
      unveränderten Korridor liegt vor.

Erst nach diesen Gates `ALINE_L1_ACTIVATED=true` setzen.
Jede Ausweitung des Modells, Inputs, Secrets, Workflows,
Bot-Scopes oder der Rechte braucht erneute Korridorprüfung.

**Vorbehalt:** Der aktuelle Runner enthält keine eigenständige
Provider-Usage-Abfrage oder persistente lokale Monatsabrechnung.
Das überprüfte OpenAI-Projekt-Hard-Limit ist daher ein
verpflichtender externer Sicherheitsmechanismus. Bis ergänzende
Kontrollen die Nutzungs- und Kostenhistorie laufend erfassen,
ist eine vollautonome Testserie nicht als dauerhaft freigabereif
zu behandeln.

## 4. Laufnachweis

Pro Lauf die GitHub-Run-ID, Bot-ID, Worker-SHA, Modell,
Fixture-Hash, PASS/NO-GO und geprüfte OpenAI-Usage/Kosten im
internen Audit erfassen. Öffentliche CI-Logs dürfen nur
nicht-sensitive Metadaten enthalten. GitHub-Logs allein sind
kein dauerhaftes Auditregister.

Bei fehlender Antwort, unbekannter Usage, Fehler,
verdächtigem Status oder Preisänderung: weitere Läufe stoppen,
keinen automatischen Retry starten.

## 5. Widerruf / Stopp

1. `ALINE_L1_ACTIVATED=false` setzen, Ausführung nur
   noch ablehnen.
2. Bot-Ausführungsberechtigung entziehen und den dedizierten
   OpenAI-Projektschlüssel widerrufen, falls erforderlich.
3. Eventuell laufende API-Anfragen samt Kosten nachverfolgen;
   nicht behaupten, dass ein Abbruch die Abrechnung verhindert.
4. Incident und Bestandskontrolle intern dokumentieren.
5. Erst nach neuer CEO-Abnahme reaktivieren.

## Abgrenzung

Keine Freigabe zur Änderung von WorkItems, Notion, `main`,
Produktions-Railway, GitHub-Organisation, OpenAI-Projekten
oder Secrets **durch Aline**. Alle diese Operationen brauchen
getrennte Rollen und Freigaben.
