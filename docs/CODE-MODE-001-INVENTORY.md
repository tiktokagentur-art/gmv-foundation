# GMV-CODE-MODE-001: Bestandsanalyse und Dublettenprüfung

Stand: 2026-11-21. Untersucht wurden `main` (`3c585c7`), alle Dateien einschließlich
`.github/` sowie die thematisch relevanten Remote-Branches. Diese Analyse wurde
vor Beginn der Pilotimplementierung abgeschlossen.

| Bereich | Ist-Zustand | Wiederverwendung / Grenze |
| --- | --- | --- |
| MCP und Tool-Registrierung | Auf `main` keine MCP-Clients, Server oder registrierten Tools. `scripts/aline_hello_once.py` verwendet das Agents SDK ausdrücklich mit `tools=[]` und `handoffs=[]`. | Neue Bridge nötig; kein bestehender MCP-Adapter für Issues, PRs, CI oder Railway. |
| Aline und Model Gateway | `scripts/aline_hello_once.py` und `.github/workflows/aline-l1-repeatable.yml` führen streng begrenzte, manuelle Modelltests aus. Der eigentliche Worker wird auf einen Commit eines anderen Branches fixiert. Auf `main` kein allgemeines Model Gateway. | Den L1-Runner nicht umbauen. ADR-0015 erlaubt reale Quellen und neue Tools erst nach eigener Entscheidung. |
| Sandbox / Code Mode | Keine Laufzeit für generierten Code. `scripts/aline_l1_runner_guard.py` ist ein Aktivierungsgate, keine Sandbox. | Neue, vom Aline-Prozess getrennte Laufzeit nötig. |
| Control Plane / Governance | `app/main.py` bietet `/health` und `/ready`. `app/lifecycle.py` enthält nur den Lebenszyklusvertrag; Migration `0001_schema_meta.py` legt kein WorkItem-Modell an. `docs/ARCHITECTURE.md`, `docs/IDENTITY_MODEL.md`, `docs/WORKITEM_LIFECYCLE.md` und ADR-0003 verlangen genau eine Assignment Authority. | Pilot darf WorkItem-Zustand, Assignment, Claim, Lease und Fencing weder verwalten noch simuliert als autoritativ ausgeben. |
| Auth und Secrets | Authentisierungsstandard ADR-0008 und Secret-Management ADR-0007 sind `Proposed`; keine produktive Identity-Prüfung im Backend. `app/config.py` liest `DATABASE_URL` als `SecretStr`. GitHub Moderator trennt privilegierte Credentials in `.github/workflows/github-moderator.yml` und ADR-0014. | Für Pilot nur explizit injizierte, attestierte Testidentität. Credential-Trennung des Moderators als Muster, kein Trust auf Agentenbehauptungen. |
| Logs / Audit / Monitoring | `app/request_id.py` und `app/logging_config.py` liefern Request-ID, JSON-Logs und Redaction. Kein Execution-Audit oder persistenter Audit-Store. SLO/Alarmierung in ADR-0010 offen. | Korrelation und Redaction wiederverwenden; separater, strukturierter Pilot-Auditnachweis ohne Eingabe- oder Antwortinhalte. |
| CI | `.github/workflows/ci.yml` prüft PRs mit Markdownlint, Struktur, Gitleaks, Ruff, OpenAPI, Pytest und Image-Smoke; `contents: read`. `scripts/validate_structure.py` erwartet genau drei bestehende Jobs. | Pilotprüfungen in den bestehenden Backend-Job integrieren, keine privilegierten CI-Secrets. |
| ADRs | ADR-0001 bis -0005 und -0012 bis -0015 `Accepted`; -0006 bis -0011 `Proposed` (`docs/adr/README.md`). ADR-0015 begrenzt Aline auf synthetische L1-Tests. | Neue technische Entscheidung als `Proposed`; kein stilles Mandat für Live-Quellen. |

## Dublettenanalyse offener Branches

- `origin/prototype/aline-openai-worker-l1`: Aline-Worker ohne Tools oder Sandbox.
- `origin/feat/aline-notion-readonly-001`: HTTP-GET-Adapter mit Seiten-Allowlist,
  Redirect- und Größenkontrolle; kein MCP, GitHub oder Railway. Policy-Muster
  wiederverwendbar, aber nicht als fertige Bridge.
- `origin/feat/aline-live-001`: Staging-Token und Budget-Ledger, keine isolierte
  Codeausführung. Die Implementierung liegt nicht auf `main`.
- `origin/feat/codex-dispatcher-a-001-offline-handoff`: erzeugt manuelle
  Übergabetexte, führt keinen Code aus.
- `origin/feat/codex-vault-001-aline`, `origin/feat/github-auto-001-pr-triage`
  und `origin/feat/aline-l1-repeatable-runner-20261120`: keine Code-Mode-Bridge.

Es gibt keine Dublette eines Code Mode Executors. Die wiederverwendbaren
Komponenten sind Verträge und Sicherheitsmuster, nicht eine bestehende
Autorisierungs- oder Isolationslaufzeit. Der Read-only-Pilot bleibt deshalb
lokal und fixturebasiert, bis Identitätsnachweis, Tool-Mandat, Credential-
Provisionierung und Betriebsfreigabe eigenständig entschieden sind.
