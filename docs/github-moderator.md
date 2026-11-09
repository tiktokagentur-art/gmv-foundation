# GitHub Moderator

Architektur, Bedienung und Berechtigungen des GMV GitHub Moderators V1.
Der Moderator steuert Repository-Einstellungen und Rulesets als GitHub-Actions-Workflow.
Er ändert nichts produktiv, solange der CEO die Freigabeinfrastruktur nicht einschaltet.

## Architekturentscheidung

V1 ist ein GitHub-Actions-Workflow, kein eigener Dienst.

Begründung:

- Die Soll-Konfiguration liegt versioniert im Repository.
- Änderungen an Settings und Rulesets sind nachvollziehbar über Workflow-Läufe.
- Freigaben können über GitHub Environments serverseitig erzwungen werden.
- Der Pilot bleibt auf ein Repository begrenzt.

Genutzte Open-Source-Action:

- Repository: [joshjohanning/bulk-github-repo-settings-sync-action](https://github.com/joshjohanning/bulk-github-repo-settings-sync-action)
- Lizenz: MIT
- Geprüfte Version: `v2.12.4`
- Commit-SHA: `40134e844f292d0dcdc88c24fde06f085d191a35`
- Kein beweglicher `@v2`- oder `@main`-Tag

Ergänzend liest `scripts/github_moderator_audit.py` den Istzustand über die GitHub API
und vergleicht ihn mit dem Sollzustand. Das deckt AUDIT und den Readback nach APPLY ab.

## Dateien

| Pfad | Rolle |
| --- | --- |
| `.github/workflows/github-moderator.yml` | Workflow mit AUDIT / DRY_RUN / APPLY |
| `config/github/repos.yml` | Explizite Allowlist verwalteter Repositories |
| `config/github/settings-config.yml` | Sollzustand und Selektor |
| `config/github/rulesets/main-branch-protection.json` | Versioniertes Ruleset für `main` |
| `scripts/github_moderator_validate.py` | Konfigurationsvalidierung |
| `scripts/github_moderator_audit.py` | Live-Audit und Readback |
| `docs/github-moderator-security-review.md` | Sicherheits- und Testnachweis |

## Betriebsmodi

Der Standardmodus ist immer `AUDIT`.

| Modus | Wirkung |
| --- | --- |
| `AUDIT` | Konfiguration prüfen, Istzustand lesen, Abweichungen dokumentieren. Keine Schreiboperation. |
| `DRY_RUN` | Geplante Änderungen über die Sync-Action mit `dry-run: true` anzeigen. Keine Schreiboperation. |
| `APPLY` | Änderungen durchführen, danach Readback. Nur mit Environment-Freigabe und Apply-Gate. |

Auslöser:

- `pull_request` / `push` auf relevante Pfade / wöchentlicher Cron: immer `AUDIT`
- `workflow_dispatch`: Modus wählbar, Standard `AUDIT`

## Pilotumfang

Nur `tiktokagentur-art/gmv-foundation`.

Sollzustand des Rulesets `main`:

- Schutz des Default-Branches
- Pull Request als verpflichtender Merge-Weg
- Keine verpflichtenden Reviews (`required_approving_review_count: 0`)
- Schutz vor Force-Push und Löschen
- Verpflichtende CI-Checks: `Lint and structure`, `Backend`, `Image`

Die bestehende CI-Workflow-Datei wird nicht verändert oder abgeschwächt.
`delete-unmanaged-rulesets` bleibt `false`.

## Sicherheitsarchitektur

### Identität

- Technische Identität: GitHub App, keine persönlichen Passwörter oder PATs
- Installation zunächst ausschließlich auf `tiktokagentur-art/gmv-foundation`
- Repository-Variable: `GMV_GITHUB_MODERATOR_APP_CLIENT_ID`
- Repository-Secret: `GMV_GITHUB_MODERATOR_APP_PRIVATE_KEY`

### Benötigte GitHub-App-Berechtigungen

Minimal für V1:

| Permission | Zugriff | Grund |
| --- | --- | --- |
| Administration | Read and write | Repository-Settings und Rulesets lesen/schreiben |
| Metadata | Read | Standard für GitHub Apps |

Nicht erforderlich im Pilot, solange keine Datei-Syncs (CODEOWNERS, Workflows, Dependabot) aktiviert sind:

- Contents: write
- Pull requests: write
- Issues: write
- Organization custom properties

Die App vergibt sich keine Rechte selbst. Rechteerweiterungen sind ein eigener CEO-Schritt.

### Freigabe für APPLY

Ein Workflow-Parameter wie `mode=APPLY` ist keine Freigabe.

APPLY verlangt alle Bedingungen gleichzeitig:

1. `workflow_dispatch` mit `mode=APPLY`
2. Lauf von `refs/heads/main`
3. GitHub Environment `github-moderator-apply` mit erforderlichen Reviewern
4. Repository-Variable `GITHUB_MODERATOR_APPLY_GATE=enabled`
5. Vorhandene GitHub-App-Credentials

Fehlt eine Bedingung, endet der Lauf mit `BLOCKED`.

### Pull Requests und Forks

- Fork-PRs erhalten keine Secrets.
- Live-Audit mit App-Token läuft nicht für untrusted Fork-PRs.
- Konfigurationsvalidierung und Unit-Tests laufen trotzdem.

## Bedienung

### Lokal

```bash
python3 scripts/github_moderator_validate.py
GITHUB_TOKEN=… python3 scripts/github_moderator_audit.py --repo tiktokagentur-art/gmv-foundation
```

### In GitHub Actions

1. Workflow `GitHub Moderator` öffnen
2. `Run workflow` wählen
3. Modus `AUDIT` oder `DRY_RUN` setzen
4. `APPLY` nur nach CEO-Freigabe der Environment und des Apply-Gates

## CEO-Checkliste vor dem ersten APPLY

1. GitHub App anlegen mit Administration read/write, nur dieses Repository
2. `GMV_GITHUB_MODERATOR_APP_CLIENT_ID` und `GMV_GITHUB_MODERATOR_APP_PRIVATE_KEY` setzen
3. Environment `github-moderator-apply` anlegen und Required Reviewers setzen
4. Optional: Deployment Branch Policy auf `main` beschränken
5. `GITHUB_MODERATOR_APPLY_GATE=enabled` setzen
6. Zuerst `AUDIT`, dann `DRY_RUN`, erst danach `APPLY`

## Bekannte Einschränkungen

- Ohne GitHub App sind DRY_RUN und APPLY blockiert.
- Ohne Environment-Reviewer ist die Freigabekette unvollständig; das Apply-Gate bleibt aus.
- Die Sync-Action pinnt auf einen Commit-SHA; Updates brauchen eine bewusste Prüfung.
- ADR-0004 bleibt `Proposed`. Dieses Modul setzt den CEO-Pilot-Sollzustand um, ersetzt aber keinen ADR-Statuswechsel.
