# Sicherheits- und Testnachweis GitHub Moderator V1

Nachweis zur Action-Prüfung, zu Negativtests und zu offenen BLOCKED-Punkten.
Kein produktives APPLY ohne CEO-Freigabe.

## Action-Prüfung

Geprüfte Action: `joshjohanning/bulk-github-repo-settings-sync-action`

| Prüfpunkt | Ergebnis |
| --- | --- |
| Lizenz | MIT |
| Release | `v2.12.4` (veröffentlichter Immutable Release) |
| Commit-SHA | `40134e844f292d0dcdc88c24fde06f085d191a35` (Commit-Verifikation: gültig) |
| Pinning | Workflow nutzt nur den Commit-SHA, nicht `@v2` / `@main` |
| Funktionsumfang | Repository-Settings, Rulesets, Dry-Run, Before/After-Logging |
| Abhängigkeiten (Runtime) | `@actions/core`, `@octokit/rest`, `js-yaml`, `ignore` |
| Offene Issues | Feature-/Wartungsissues, kein bekanntes aktives Security-Advisory über die zugängliche GraphQL-Abfrage |
| Passende V1-Nutzung | Ruleset-Sync + Dry-Run; keine Datei-Syncs im Pilot |

## Sicherheitsregeln im Workflow

- Standardmodus `AUDIT`
- Keine persönlichen Tokens
- GitHub App als einzige Schreibidentität
- APPLY nur hinter Environment + Apply-Gate + `main`
- Fork-PRs ohne Secrets / ohne App-Token
- Allowlist erzwingt Pilot-Repository
- `delete-unmanaged-rulesets: false`
- Vorher-/Nachher-Audit als Artifact und Job Summary

## Testergebnisse

### Konfiguration und Unit-Tests

Ausgeführt lokal im Agentenlauf:

1. `python3 scripts/github_moderator_validate.py` → ok
2. `pytest tests/test_github_moderator_validate.py tests/test_github_moderator_audit.py` → ok
3. Negativtests abgedeckt:
   - Repository außerhalb der Allowlist
   - Settings-Ziel außerhalb der Allowlist
   - `all: true` Selektor
   - verpflichtende Reviews
   - fehlender CI-Check
   - ungültiges Ruleset-JSON
   - Audit ohne Token → `BLOCKED`
   - Audit mit HTTP 403 → `BLOCKED`
   - Audit gegen nicht allowlistetes Repo → `BLOCKED`

### Live-Audit gegen den Pilot

Mit vorhandenem Lesezugriff auf Rulesets ausgeführt:

- Istzustand Ruleset `main`: `deletion`, `non_fast_forward`, `pull_request` (0 Reviews)
- Fehlend gegenüber Soll: `required_status_checks` für `Lint and structure`, `Backend`, `Image`
- Status: `drift` (erwartet)
- Keine produktive Korrektur in diesem Lauf

### DRY_RUN / APPLY gegen die Sync-Action

Status: **BLOCKED**

Ursache: GitHub App Credentials und Environment-Freigabe sind im Repository noch nicht eingerichtet.
Kein PAT-Fallback. Keine produktive Ruleset-Änderung durch diesen Pull Request.

### Freigabeprozess APPLY

Status: **BLOCKED bis CEO-Setup**

Technisch vorbereitet:

- Environment-Name `github-moderator-apply`
- Gate-Variable `GMV_MODERATOR_APPLY_GATE`
- Ref-Zwang auf `refs/heads/main`
- Readback mit `--expect-aligned`

## Governance-Grenzen

- Keine Ausweitung auf weitere Repositories
- Keine Änderung der bestehenden CI-Jobs
- Kein APPLY aus diesem Implementierungs-PR
- Bestehende Ruleset-Regeln werden erst nach CEO-Freigabe geschrieben
- Fehlende Voraussetzung wird als `BLOCKED` gemeldet, nicht umgangen

## Offene Risiken

1. Environment ohne Required Reviewers wäre unsicher, falls jemand das Apply-Gate früh setzt.
2. `administration: write` der App ist mächtig; Installation muss auf ein Repo begrenzt bleiben.
3. Status-Check-Namen müssen exakt den Job-`name`-Werten in `ci.yml` entsprechen.
4. ADR-0004 ist weiterhin `Proposed`; schriftliche Beitragsregeln und technisches Ruleset können auseinanderlaufen, bis ein ADR entschieden ist.
