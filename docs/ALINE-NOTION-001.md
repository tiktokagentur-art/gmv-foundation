# ALINE-NOTION-001 – Notion-Leseadapter mit begrenztem Scope

**Status:** Code-Entwurf; kein Notion-Runtime-Smoke, keine neuen Berechtigungen,
keine Staging- oder Produktionsaktivierung. Abhängig von Draft-PR #31.

## Ausgangslage und Dubletten

- Der neue Aline-L1-Worker liegt unter prototypes/aline-openai-worker/
  auf Branch prototype/aline-openai-worker-l1 (Draft-PR #31).
- Historisch existiert der „Notion MCP Governance Adapter V1“ im alten
  Repository fabianmartens95-art/gmv-platform, dokumentiert unter
  https://app.notion.com/p/3e576c6817ac813eaac1fc86f4a17eed.
  Dessen begrenzter Lese-/Schreibvertrag ist eine Governance-Referenz.
  Ein betriebsbereiter Credential-Pfad im aktuellen GMV-V3-Worker
  ist damit nicht nachgewiesen. Keine Übernahme alter Tokens.
- Die Aline-Prototyp-Runtime im neuen Repository besitzt bislang
  keinen Notion-Adapter.
- Notion bleibt Governance- und Ticket-Ansicht; GitHub führt
  Engineering-Nachweise; die Control Plane bleibt einzige
  Assignment- und State-Authority (Accepted ADR-0003).
  Kein zweiter Scheduler und keine zweite SSOT.

## Implementierter Umfang

Der separate Prozess notion_read.py lädt ausschließlich explizit
angegebene und per Umgebungsvariable freigegebene Notion-Ticketseiten.

- Fest vorgegebener Netzwerkpfad: GET am Host api.notion.com,
  Endpunkt /v1/pages/{UUID}, Notion-Version 2026-03-11.
  HTTPS, Redirect-Verbot, Timeout und Antwortgrößenlimit.
- Keine anderen HTTP-Methoden, globale Suche, Datenbankabfrage,
  Child-Block-Fetch oder Seitentraversal.
- Maximal zehn explizite Seiten pro Aufruf. Keine Silent Defaults.
- Die CLI-Option --confirm-notion-read sowie NOTION_ALLOWED_PAGE_IDS
  und NOTION_API_TOKEN sind alle verpflichtend.
- Aus der Aufgaben-Datenbank werden nur benannte Felder gemappt:
  Fach-ID/Aufgaben-ID, Aufgabe, Priorität, Status, Verantwortlich,
  Blocker, Abteilung und Abnahmekriterien. Fehlende Identität,
  Priorität, Titel oder Status führen zum Abbruch.
- Der bestehende deterministische L1-Analysator (offline_demo) wertet
  die Eigenschaften nur lokal aus. Kein OpenAI-Aufruf.
- Ausgegeben werden nur Ticket-ID, Status, Priorität, Risikostufe,
  Bool-Werte für Blocker/Abnahmekriterien, nächster Leseschritt
  und Quellen-URL. Keine Tokens, vollständigen Tickettexte,
  Owner-Namen oder Blockertexte in der Ausgabe.
- Ein erfolgreich gelesener Notion-Eintrag ist kein unabhängiger
  Beleg: evidence_status bleibt unknown. Kein automatisches
  verified, DONE, CEO-Gate oder Zuweisungsrecht.
- Docker-Startbefehl und worker.py bleiben unverändert.
  Keine autonome oder periodische Ausführung.

## Tests ohne Netzwerk und Credentials

    pytest tests/test_aline_notion_read.py

Testabdeckung: fehlende Bestätigung, Token und Allowlist;
ungültige oder doppelte IDs, Scope-Verletzung, GET-only,
falsche Notion-ID, archivierte Seite, fehlende Pflichtfelder,
ungültige oder übergroße Antworten, redaktionell minimierter
Offline-Report. Unit-Tests nutzen ausschließlich Mockdaten.

## Aktivierungsweg – separate CEO-Genehmigung erforderlich

1. Prüfen, ob eine bestehende Notion-Integration für den
   aktuellen Pizza-Club-Workspace mit getrennten Credentials
   wiederverwendet werden kann. Wenn nicht, dedizierte Integration
   mit ausschließlich Read Content erstellen. Keine alten Tokens kopieren.
2. Nur ausdrücklich genehmigte Ticketseiten für die Integration
   freigeben. Minimum-Scope-Sharing und wirksame Access Controls
   nachweisen.
3. Token ausschließlich im genehmigten Secret-Manager verwalten;
   nach separater Freigabe gezielt als Railway-Staging-Secret injizieren.
   Kein Token im Chat, GitHub, Notion, CI oder Testfixtures.
4. NOTION_ALLOWED_PAGE_IDS mit höchstens zehn genehmigten Ticketseiten
   konfigurieren; Seite und Ticket-Fach-ID vorher abgleichen.
5. Nach separater CEO-Freigabe einmaligen Staging-Smoke ausführen.
   Voraussetzung: NOTION_API_TOKEN und NOTION_ALLOWED_PAGE_IDS
   sind in der autorisierten Runtime verfügbar:

       python prototypes/aline-openai-worker/notion_read.py \
         --page-id <freigegebene-ticket-uuid> --confirm-notion-read

6. Negative Runtime-Proben durchführen: nicht freigegebene Seite,
   fehlender Token, 403/404, Umleitung und abweichendes Schema.
   PII-/Secret-Logging, Eingabedaten und eventuelle API-Kosten prüfen.
7. CI und unabhängigen Security-Review auf dem konkreten
   PR-Head abnehmen. Kein Merge oder Railway-Deployment ohne
   weitere konkrete CEO-Freigabe.
8. Datenbankweite Abfragen, periodischer Leseplan und produktive
   Nutzung sind getrennte Folgeentscheidungen, nicht Teil
   dieser Implementierungsfreigabe.

## Abnahmekriterien

- [ ] Unit-Tests für Scope, Auth, Mapping, Fehler und Ausgabe grün
- [ ] CI auf konkretem Head und unabhängiger Review dokumentiert
- [ ] Kein Token, neue Notion-Rechte oder Railway-Änderungen durch PR
- [ ] Dubletten- und CredentiaI-Prüfung dokumentiert
- [ ] Separate Minimum-Scope-/Secret-Freigabe
- [ ] Positiver und negativer Staging-Runtime-Smoke
- [ ] Kein Notion-Schreibvorgang und keine OpenAI-Datenübermittlung
- [ ] Separate CEO-Entscheidung über Merge und Runtime-Aktivierung

**Offenes Gate:** ChatGPTs Notion-Verbindung ist keine attestierte
Runtime-Identität des Railway-Workers. NOTION_API_TOKEN fehlt aktuell
im geprüften Aline-Service. Ein Live-Beweis ist nicht erbracht.
