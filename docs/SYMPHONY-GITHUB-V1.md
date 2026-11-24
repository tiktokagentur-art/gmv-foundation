# SYMPHONY-GITHUB-V1 – Integrationsentwurf

- Status: Proposed / Draft, nicht aktiviert
- Stand: 2026-11-22
- Basis: `main` @ `3c585c7cf167ade171282a495b7b211284c15778`
- Scope: GitHub Issues als Eingang für OpenAI Symphony; kein Linear
- Referenz: [Symphony SPEC](https://github.com/openai/symphony/blob/main/SPEC.md)
- Implementierung: [Symphony Elixir](https://github.com/openai/symphony/blob/main/elixir/README.md)
- Geprüfte Symphony-Version: `openai/symphony@be10a1b` (2026-09-15), Release `nightly` `linux_x86_64`

## Ziel

Symphony soll freigegebene Engineering-Aufträge aus GitHub Issues in isolierte
Codex-Arbeitsverzeichnisse übergeben, Nachweise für Tests und Draft-PRs sammeln
und Review-Handoffs vorbereiten. Es darf keine zweite Assignment Authority
einführen oder ohne weitere Freigabe produktive Aktionen ausführen.

Dieser Entwurf installiert oder startet **keinen** Symphony-Dienst, ändert
keine GitHub-Einstellungen und erteilt keine Identitäten oder Berechtigungen.

## Ist-Stand und harte Invarianten

- `ADR-0003` ist Accepted: Die GMVGANG Control Plane ist der einzige Owner
  von WorkItem-Status, Assignment, Claims, Leases und Fencing.
- `docs/WORKITEM_LIFECYCLE.md` beschreibt acht WorkItem-Status;
  GitHub-Issue-Status `open`/`closed` sind **keine** WorkItem-Status.
- Repository-Änderungen laufen über PR und die vorhandenen CI-/Review-Regeln.
- Der Code für einen vollständig durchsetzenden, produktionsreifen
  Control-Plane-Claim-/Lease-Preflight ist auf `main` nicht nachgewiesen.
- OpenAI bezeichnet die Elixir-Referenzimplementierung als Prototyp für
  Evaluation; ihre GitHub-Issues-Integration ist bereits vorhanden.

## Verantwortungsmodell

| Funktion | Autoritative Instanz |
| --- | --- |
| Öffentlicher Eingang, Spezifikation, PR und CI | GitHub |
| Projektansicht und Planungspriorität | GitHub Projects (optional, nur Projektion) |
| WorkItem-Status und Agenten-/Worker-Mandat | GMVGANG Control Plane |
| Einmalige Zuweisung, Claim, Lease, Fencing | Aline/Assignment Authority in der Control Plane |
| Isolierter Codex-Prozess und technische Ausführungssteuerung | Symphony als Worker |
| Änderungen, Tests und PR-Evidenz | Codex mit eingeschränktem GitHub-Adapter |
| Unabhängiges technisches Review | Codex Code Review, getrennt vom Implementierer |
| Sicherheits-Freigabe und formeller Merge | Externe Kontrollinstanz / bestehende GitHub-Schutzregeln |

**GitHub-Issue-Labels sind nur ein Filter, keine Autorisierungsnachweise.**
Symphony darf einen Agenten erst nach erfolgreichem serverseitigen
Control-Plane-Preflight starten. Ist der Preflight nicht implementiert,
nicht erreichbar oder ungültig, gilt fail-closed: **kein Dispatch**.

## GitHub-Projektion

- Schlüssel: `repository_full_name + issue_number`, dauerhaft gebunden
  an genau eine Control-Plane-WorkItem-ID.
- Kandidat: offenes GitHub Issue mit expliziter Pilotmarkierung;
  Pull Requests niemals als Issues dispatchen.
- Ein tatsächlicher Dispatch erfordert zusätzlich passende Worker-Identität,
  autorisierten WorkItem-Status, Lease und gültiges Fencing.
- Projektspalten wie Backlog, Ready, In Progress, Review, Blocked und Done
  dürfen angezeigt werden, bestimmen aber keinen WorkItem-Status.
- Jeder GitHub-Kommentar, Labelwechsel und PR-Link ist nicht vertrauenswürdige
  externe Evidenz. Zustandsänderungen werden nur von ihrem Owner autorisiert.
- Ein Schließen des Issues darf nicht eigenmächtig den WorkItem-Status auf
  `done` setzen. Ein Widerruf durch die Control Plane stoppt die Ausführung.

## Workflow und Review

1. GitHub Issue: Auftrag, Scope, Akzeptanzkriterien und Änderungsgrenzen.
2. Control Plane: WorkItem übernehmen bzw. zuordnen, Mandat und Claim prüfen.
3. Vor jedem Dispatch: eindeutiger Owner, gültige Lease/Fencing-Bindung,
   erlaubte Pfade, Risiko- und Budget-Gates serverseitig attestieren.
4. Symphony: pro autorisiertem WorkItem isolierten Workspace anlegen,
   Codex starten, Abbruch und Heartbeats über einen kontrollierten Adapter.
5. Codex: nur erlaubte Dateien bearbeiten, offline prüfen, Ergebnisse an
   die Control Plane melden und gegebenenfalls Draft-PR vorbereiten.
6. GitHub CI: Struktur, Ruff, Pytest, Sicherheits-/Secretscan und Image.
7. Unabhängiger Reviewer: Codex Code Review; bei höherem Risiko zusätzliche
   Sicherheitsprüfung. Kein Selbstreview und keine selbstattestierte Approval.
8. Handoff: Ergebnisbeleg, GitHub-PR-Link und gültigen Head-SHA prüfen;
   Freigabe/Merge/Deployment bleiben gesondert und sind hier **verboten**.

Die wiederholten Dispatches, Retries und der Stop nach Lease-Verlust müssen
durch die Control Plane gefenced sein. In-Memory-Blockadezustände und
GitHub-Labels reichen ausdrücklich **nicht** für Restart-Sicherheit.

## Sicherheit, Betrieb und Kosten

- Eigenständige Worker-Identität und minimal berechtigte GitHub-App bzw.
  kurzlebiges Token, keine persönlichen oder gemeinsam genutzten Konten.
- Kein Secret in `WORKFLOW.md`, Code, Logs, Issues oder PRs.
- Ein GitHub-API-Tool mit Host-seitigem Token ist nicht automatisch
  read-only: dessen Rechte begrenzen den effektiven Zugriffsbereich.
- GitHub-Issue-Texte und PR-Kommentare sind untrusted input; Prompt Injection,
  Pfadtraversal, unerlaubte Tool-Aufrufe und Token-Exfiltration abwehren.
- Geprüfte Isolierung für Codex-Ausführung; Host/Container-Sandbox nicht als
  automatisch gehärtete MicroVM ausgeben.
- Limitierte Parallelität, Laufzeit, Turn-Zahl, API-Ausgaben, kontrollierte
  Retries und Kill Switch; konkrete harte Budgetgrenzen vor Aktivierung prüfen.
- Vollständiger Audit-Trail für WorkItem-ID, GitHub Issue, Worker-ID,
  Lease/Fencing, Code-SHA, PR-SHA, Tests, Review, Kosten und Stop-Grund.
- Keine produktiven Railway-Dienste, Migrationen, Repository-Rulesets,
  Berechtigungen, Merges oder Deployments in dieser Phase verändern.

## CEO-Entscheidung 24.11.2026 und lokaler Ein-Worker-Pilot

Petrus hat am 24.11.2026 entschieden: Issue #74 ist P0, PR #66 wird geprüft,
danach folgt ein lokaler Pilot mit genau einem Codex-Worker. Das ist eine
bewusste, eng begrenzte Ausnahme von Phase B: Das serverseitige
Dispatch-Gate fehlt weiterhin. Ersatzweise vergeben Aline oder Deniz das Label
`gmv-symphony-pilot` an genau ein harmloses Issue, und Symphony läuft mit
`max_concurrent_agents: 1`, wenigen Turns und wird nach einem Lauf gestoppt.
Merge bleibt bei Petrus über die bestehende Review-Pflicht auf `main`.

Erkenntnisse aus dem Pilot (Issue #87, Draft-PR #88):

- Der Start verlangt das Flag
  `--i-understand-that-this-will-be-running-without-the-usual-guardrails`.
- Die Vorlage braucht `hooks.after_create` (Repo-Klon), sonst ist der Workspace leer.
  Ergänzt in `docs/symphony/WORKFLOW.example.txt`; Prüfung und Gate-Entwurf:
  [symphony/dispatch-gate.md](symphony/dispatch-gate.md), App-Rechte:
  [symphony/github-app-spec.md](symphony/github-app-spec.md).
- Solange das Issue `open` ist, dispatcht Symphony erneut. Ohne
  Control-Plane-Statusübergang muss der Lauf manuell gestoppt werden.
- Das Host-Token für `github_api` hatte im Pilot die Rechte des persönlichen
  Kontos. Vor jedem weiteren Lauf: eigene GitHub-App bzw. minimal berechtigtes Token.
- Token-Verbrauch für einen README-Absatz: ca. 480.000 (überwiegend Kontext-Input).

## Implementierungsphasen

### A – jetzt: Dokumentation und Offline-Vertrag

- Diese Spezifikation und die nicht aktivierte
  [Workflow-Vorlage](symphony/WORKFLOW.example.txt) versionieren.
- GitHub-API-Read-Adapter, Issue-Normalisierung, Label-Filter und
  Prompt-Template anhand von Offline-Fixtures prüfen.
- Kein dauerhaft laufender Dienst, keine echten Codex- oder GitHub-Schreibaktionen.

### B – nach separater Code-Freigabe: Controller-gesteuerter Pilot

- Ein strikt vorgeschaltetes Control-Plane-Dispatch-Gate entwickeln:
  serverseitiges Claim/Lease/Fencing, idempotentes Mapping und Audit.
- Nach Restart oder Reconcile zunächst Lease neu validieren, sonst abbrechen.
- Negative Tests: Doppelclaim, ungültiges Fencing, Lease-Ablauf,
  GitHub-Label-Manipulation, geschlossene Issues, fehlende Berechtigung,
  Rate-Limit, Retry, Prompt Injection, Budgetüberschreitung.
- Einen **synthetischen** Pilotauftrag mit genau einem Worker unter
  minimalen Rechten und überprüfbarem Stop-/Widerrufspfad testen.

### C – nur nach separatem CEO-Go: begrenzte PR-Arbeit

- Gezielte GitHub-Schreibberechtigungen nur für kontrollierte Draft-PRs.
- CI und unabhängige Reviews als Abnahmebeleg; keine automatische
  Merge-/Deploy-Autorität.
- Stufenweiser Ausbau erst nach gemessener Stabilität und Kostenkontrolle.

## Schnittstellen- und Kollisionsprüfung

Vor Codeänderungen erneut die offenen Vertragsarbeiten zu Control Plane,
Code Mode und Review prüfen, insbesondere PR #63 (CP-002-01), PR #64
(CRG-001A), PR #62 (APR-005A) und PR #55 (GMV-CODE-MODE-001).
Keine parallel definierte Lifecycle-State-Machine oder eigene Worker-Registry.

## Abnahme

- [ ] GitHub-Issue-Adapter anhand der gepinnten Symphony-Version verifiziert
- [ ] Eindeutiger WorkItem-Owner; kein zweiter Scheduler mit Claim-Autorität
- [ ] Hard-fail bei fehlendem/ungültigem Lease, Fencing oder Worker-Mandat
- [ ] Restart-/Retry-Szenarien und idempotente Issue-Zuordnung getestet
- [ ] Identitäten, Secrets, Rechte, Sandbox und Kostengrenzen attestiert
- [ ] CI und unabhängiger Review nachgewiesen
- [ ] Gesonderte CEO-Freigabe für Pilotbetrieb dokumentiert

**Status: Konzept und Vorlage zur Review. Kein Running Service.**
