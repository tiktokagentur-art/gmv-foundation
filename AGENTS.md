# Coding-Agent-Anweisungen

Diese Datei beschreibt nur den Einstieg für Coding-Agenten. Sie erteilt
keine Berechtigungen und ersetzt weder die Governance noch eine Zuweisung.

## Verbindliche Quellen

- [Governance](docs/GOVERNANCE.md): Ein `Accepted`-ADR ist verbindlich.
  Ein `Proposed`-ADR ist noch keine Implementierungsfreigabe.
- [Beitragsregeln](CONTRIBUTING.md): Branches, Pull Requests, CI.
- [Sicherheit](SECURITY.md): Keine Secrets oder internen Betriebsdetails.
- [Architektur](docs/ARCHITECTURE.md): Komponenten und Verantwortung.
- [WorkItem-Lebenszyklus](docs/WORKITEM_LIFECYCLE.md): Zustände und Verträge.
- [ADR-0003](docs/adr/0003-single-assignment-authority.md): Genau eine
  Assignment Authority und ein Zustandseigentümer je Domäne.
- [ADR-0004](docs/adr/0004-branch-protection-codeowners.md): Regeln für
  `main` und die erforderlichen CI-Prüfungen.

Bei einem Widerspruch hat ein `Accepted`-ADR Vorrang. Keine neue
Architektur-, Sicherheits- oder Betriebsentscheidung ohne ADR-Verfahren.

## Arbeitsweise

1. Auftrag, Nicht-Ziele, Akzeptanzkriterien und Risikoklasse lesen.
2. Bestehenden Code, Tests und maßgebliche ADRs prüfen.
3. Eine kleine, begrenzte Änderung auf einem Feature-Branch erstellen.
4. Passende Tests ausführen und Ergebnisse nachprüfbar dokumentieren.
5. Pull Request mit Auftragsbezug, Risiken und Nachweisen vorbereiten.
6. Unabhängige fachliche Prüfung anfordern; nicht selbst abnehmen.

Ein GitHub-Issue ist kein autoritativer Worker-Claim. Die Control Plane
bleibt alleinige Eigentümerin von `WorkItem.status`. Worker vergeben
keine Leases, Fencing-Tokens oder Zuweisungen an sich selbst.

## Prüfungen

Die aktuellen Befehle und Voraussetzungen stehen in
[CONTRIBUTING.md](CONTRIBUTING.md). Insbesondere:

```bash
npx --yes markdownlint-cli2@0.24.0
python3 scripts/validate_structure.py
python3 scripts/gitleaks_scan.py
ruff check app tests migrations scripts
pytest
```

Vor dem Merge müssen die CI-Checks `Lint and structure`, `Backend` und
`Image` am aktuellen PR-Head grün sein. Ein lokal übersprungener
Datenbanktest ist keine positive Testevidenz.

## Sicherheits- und Freigabegrenzen

- Kein direkter Push auf `main`, kein Force-Push und kein Bypass.
- Keine produktiven Deployments, Secrets- oder Ruleset-Änderungen ohne
  ausdrückliche zuständige Freigabe.
- Keine Änderungen an `Accepted`-ADRs oder geltenden Gates ohne das
  bestehende Entscheidungsverfahren.
- Keine zweite Assignment Authority oder zweite Statusschreibinstanz.
- Keine Credentials, internen Adressen oder sensiblen Logs im öffentlichen
  Repository, in Issues oder Pull Requests.
- Bei blockierten Tests, unklarer Autorität oder Konflikten: stoppen,
  den Befund dokumentieren und keine grüne Abnahme behaupten.

## Definition of Done für den Weiterbau-V2-Pilot

Ein Ergebnis ist erst abnahmefähig, wenn der Pull Request die konkret
vereinbarten Akzeptanzkriterien erfüllt, die relevanten Tests belegt sind,
die drei erforderlichen CI-Checks grün sind und eine unabhängige
fachliche Prüfung dokumentiert ist. Das ist eine Pilot-Arbeitsweise;
sie erhöht nicht die in ADR-0004 festgelegte GitHub-Approval-Zahl von 0.
Merge oder Deployment sind nicht Teil der automatischen Abnahme.

## Code Review Rules (CRG-001A)

Diese drei Prüfschwerpunkte gelten für Codex Code Review. Findings sollen
einen konkreten Pfad, die betroffene Änderung, das Risiko und eine sichere
Korrekturmöglichkeit nennen. Ein Review-Kommentar ist keine GitHub-Approval.

### Autoritativer Zustand und Zuweisungen

Bei Änderungen an WorkItem-, Scheduler-, Claim-, Lease- oder
Fencing-Verträgen prüfen, ob eine zweite Assignment Authority,
ein zweiter Statusschreiber oder eine Selbstzuweisung eingeführt würde.
Solche Änderungen verletzen ADR-0003; die bestehende eindeutige
Autorität und Lebenszyklusgrenzen müssen erhalten bleiben.

### Schnittstellen- und Datenvertrags-Kompatibilität

Bei Änderungen an `api/openapi.yaml`, Authentisierung, Identitäts-,
Lifecycle- oder versionierten Schemas auf inkompatible Feldänderungen,
entfallene Fehlerfälle und stillschweigende Formatänderungen prüfen.
Bestehende Verträge erhalten oder Migration und gesonderte
Freigabe nachweisen; ein erfolgreicher Einzeltest allein genügt nicht.

### Privilegien, Evidenz und Merge-Grenzen

Bei GitHub Actions, Secrets, Berechtigungen, Produktiv-APIs und
Release-Pfaden prüfen, ob neue Schreibrechte, Secret-Zugriffe,
Bypasses oder ungeprüfte Deployment-Auslöser entstehen. Auf aktuelle
Head-SHA, unabhängige Reviewer-Identität, echte CI-Nachweise und
fehlende offene Befunde achten. Synthetische oder selbst gemeldete
Reviews niemals als formelle Freigabe, Merge- oder Deploymentrecht
interpretieren; siehe `docs/pr-review/CRG-001A-CODEX-REVIEW.md`.
