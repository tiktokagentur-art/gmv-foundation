# GITHUB-AUTO-001 · PR-Automatisierung – Pilot

Status: **Draft / nicht produktiv aktiviert**. Auftrag: [GitHub #35](https://github.com/tiktokagentur-art/gmv-foundation/issues/35).

## Bereits vorhanden

`.github/workflows/ci.yml` führt für Pull Requests die drei bestehenden Jobs `Lint and structure`, `Backend` und `Image` aus. Diese bleiben unverändert. `docs/adr/0004-branch-protection-codeowners.md` hält den historischen Ruleset-Stand fest; sein heutiger Istzustand muss vor jeder Rollout-Freigabe unabhängig geprüft werden.

## Neue, rein beratende Triage

`.github/workflows/pr-triage.yml` reagiert auf `pull_request` (opened, reopened, synchronize, edited, ready_for_review), liest PR-Metadaten und geänderte Dateinamen über die GitHub-API und schreibt nur eine Job-Zusammenfassung. Sensible Pfade erhalten eine Warnung. Die Liste ist ein Signal für unabhängige Prüfung, keine vollständige Sicherheitsanalyse.

Sicherheitsgrenzen: `contents: read` und `pull-requests: read`; kein `pull_request_target`, kein Checkout oder Ausführen des PR-Codes, keine gespeicherten Secrets, kein Comment-Bot, keine automatischen Commits, kein Auto-Merge, keine Änderungen an Rulesets oder Deployments. API-Fehler stoppen die Triage; die Ergebnisse werden nicht als erfolgreich erfunden.

GitHub stellt die nativen Workflow- und Check-Benachrichtigungen bereit; externe Alarmierung ist nicht Teil dieses Piloten. Der neue Check wird nicht als Required Check konfiguriert.

## Abnahme / Prüfung

1. Workflow auf dem konkreten PR-Head durch GitHub Actions syntaktisch und technisch prüfen; bisherige drei CI-Jobs müssen grün bleiben.
2. Positivfall: PR ohne sensitive Pfade, lesbare Job Summary; keine Mutation.
3. Negativfall: Workflow- oder ADR-Änderung liefert Warnung ohne Freigabe. Leere PR-Beschreibung wird erwähnt.
4. Fehlerfall: fehlender API-Token, API-Fehler oder ungültige Dateiliste brechen die Triage ab, ohne einen grünen Beleg zu fingieren.
5. Rechte, `pull_request`-Abgrenzung sowie die Risiken von PR-Metadaten und Dateinamen unabhängig prüfen.

## Gesperrte nächste Ausbaustufen

- **KI-Review**: Erst Anbieter/Modell, Kostenobergrenze, Datenfreigabe, Prompt-Injection-Schutz und Reviewer-Unabhängigkeit genehmigen. Der Workflow ruft bewusst kein LLM auf.
- **Korrekturvorschläge**: Nur mit separatem Agenten-/Sandbox-Auftrag und minimalen Schreibrechten; keine Eigenabnahme.
- **Merge / Deployment / GitHub-Ruleset / Runner / Secret-Verwaltung**: Nur nach gesonderter CEO-Freigabe.

Fachliche Verantwortung: Deniz; Koordination: Aline; unabhängiges Sicherheitsreview: Samira. Die Rollenbezeichnung erteilt keine GitHub-Rechte oder Worker-Claims.
