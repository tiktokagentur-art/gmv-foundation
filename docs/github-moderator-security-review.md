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

## Geschlossene Sicherheitslücken (P0 Hardening)

| Lücke | Vorher | Nachher |
| --- | --- | --- |
| Same-Repo-PR als trusted | `head.repo == repository` → App-Token | PRs nie privilegiert; `privileged=false` |
| Privilege via Checkout-Code | Trust-Logik hätte durch PR-Python umgangen werden können | YAML-Gate `github.event_name != 'pull_request'` |
| Repo-Secrets auf PR-Workflows | App-Key als Repository-Secret möglich | Pflicht: Environment-Secrets auf `github-moderator-privileged` / `github-moderator-apply` |
| Token in Outputs | `echo token=… >> GITHUB_OUTPUT` | Token nur in Step-Env; Leak-Detektor + statische Analyse |
| `pull_request_target` | nicht genutzt, aber nicht geprüft | explizit verboten + Negativtest |
| APPLY-Gate nur Bash | verstreute Checks | zentral in `github_moderator_security.py` + Workflow |

## Sicherheitsregeln im Workflow

- Standardmodus `AUDIT`
- Keine persönlichen Tokens
- GitHub App als einzige Schreibidentität
- APPLY nur hinter Environment + Apply-Gate + `main`
- **Alle** PRs (Same-Repo und Fork) ohne App-Secrets
- Privilege nur für `workflow_dispatch` / `schedule` / `push`
- Allowlist erzwingt Pilot-Repository
- `delete-unmanaged-rulesets: false`
- Vorher-/Nachher-Audit als Artifact und Job Summary (ohne Token-Werte)
- App-Token nur mit `repositories: gmv-foundation`

## Testergebnisse

### Konfiguration und Unit-Tests

1. `python3 scripts/github_moderator_validate.py` → ok
2. `python3 scripts/github_moderator_security.py check-workflow` → ok
3. `pytest tests/test_github_moderator_*.py` → ok

### Negativtests (müssen BLOCKED / Fail ergeben)

| Szenario | Test | Erwartung |
| --- | --- | --- |
| PR aus eigenem Repository ohne privilegierte Secrets | `test_same_repo_pull_request_has_no_privileged_secrets` | `BLOCKED` |
| PR aus Fork ohne privilegierte Secrets | `test_fork_pull_request_has_no_privileged_secrets` | `BLOCKED` |
| Manipulierte Workflow-Konfiguration (`pull_request_target`, Token-Echo, ohne Event-Gate) | `test_manipulated_workflow_*` | Validierungsfehler |
| Versuch, privilegierte Tokens aus PR-Code zu verwenden | `test_refuse_privileged_token_use_from_*_pr_code` | `BLOCKED` |
| APPLY von einem anderen Branch | `test_apply_blocked_from_non_main_branch` | `BLOCKED` |
| APPLY ohne Environment-Freigabe | `test_apply_blocked_without_environment_approval` | `BLOCKED` |
| APPLY ohne aktiviertes CEO-Gate | `test_apply_blocked_without_ceo_gate` | `BLOCKED` |
| Repository außerhalb der Allowlist | `test_apply_blocked_for_repo_outside_allowlist` + Validate-Tests | `BLOCKED` / Fehler |
| Fehlende oder falsche Status-Checks | `test_validate_rejects_missing_or_wrong_status_checks` / `…_wrong_status_check_name` | Fehler |

Weitere bestehende Negativtests bleiben aktiv (Allowlist, `all: true`, Reviews, Audit ohne Token, HTTP 403).

### Live-Audit gegen den Pilot

Status abhängig von Environment-/App-Setup. Ohne Credentials: erwartetes `BLOCKED` oder Fallback-`GITHUB_TOKEN` mit begrenzten Rechten.
Kein produktives APPLY in diesem Auftrag.

### DRY_RUN / APPLY gegen die Sync-Action

Status: **BLOCKED** bis CEO-Setup (App + Environments + Gate).
Kein PAT-Fallback. Keine produktive Ruleset-Änderung durch diesen Pull Request.

### Freigabeprozess APPLY

Status: **BLOCKED bis CEO-Setup**

Technisch vorbereitet:

- Environment-Name `github-moderator-apply`
- Privilege-Environment `github-moderator-privileged`
- Gate-Variable `GMV_MODERATOR_APPLY_GATE`
- Ref-Zwang auf `refs/heads/main`
- Readback mit `--expect-aligned`
- Zentrale Gate-Evaluation in `scripts/github_moderator_security.py`

## Governance-Grenzen

- Keine Ausweitung auf weitere Repositories
- Keine Änderung der bestehenden CI-Jobs
- Kein APPLY aus diesem Implementierungs-PR
- Bestehende Ruleset-Regeln werden erst nach CEO-Freigabe geschrieben
- Fehlende Voraussetzung wird als `BLOCKED` gemeldet, nicht umgangen
- Keine produktive Änderung an Branch-Schutzregeln, Railway oder anderen Infrastrukturen
- Keine Erstellung/Aktivierung einer GitHub App ohne CEO-Freigabe

## Offene Risiken / BLOCKED

1. Environment `github-moderator-apply` ohne Required Reviewers wäre unsicher, falls jemand das Apply-Gate früh setzt.
2. Environment `github-moderator-privileged` muss Deployment Branches auf `main` beschränken; sonst greift die Secret-Isolation nicht.
3. Solange der App-Private-Key noch als **Repository-Secret** existiert, kann ein Same-Repo-PR den Workflow umschreiben und den Key lesen. CEO muss auf Environment-Secrets umstellen und das Repository-Secret entfernen.
4. `administration: write` der App ist mächtig; Installation muss auf ein Repo begrenzt bleiben.
5. Status-Check-Namen müssen exakt den Job-`name`-Werten in `ci.yml` entsprechen.
6. ADR-0004 ist weiterhin `Proposed`; schriftliche Beitragsregeln und technisches Ruleset können auseinanderlaufen, bis ein ADR entschieden ist.
7. Mit `required_approving_review_count: 0` bleibt Review-Disziplin organisatorisch; technische Secret-Isolation über Environments ist deshalb bindend.
