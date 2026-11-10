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
Die Trust-Boundary liegt in `scripts/github_moderator_security.py` und in
workflow-nativen `github.event_name`-Gates.

## Dateien

| Pfad | Rolle |
| --- | --- |
| `.github/workflows/github-moderator.yml` | Workflow mit AUDIT / DRY_RUN / APPLY |
| `config/github/repos.yml` | Explizite Allowlist verwalteter Repositories |
| `config/github/settings-config.yml` | Sollzustand und Selektor |
| `config/github/rulesets/main-branch-protection.json` | Versioniertes Ruleset für `main` |
| `scripts/github_moderator_validate.py` | Konfigurationsvalidierung |
| `scripts/github_moderator_audit.py` | Live-Audit und Readback |
| `scripts/github_moderator_security.py` | Trust-Boundary und APPLY-Gate |
| `docs/github-moderator-security-review.md` | Sicherheits- und Testnachweis |

## Betriebsmodi

Der Standardmodus ist immer `AUDIT`.

| Modus | Wirkung |
| --- | --- |
| `AUDIT` | Konfiguration prüfen, Istzustand lesen, Abweichungen dokumentieren. Keine Schreiboperation. |
| `DRY_RUN` | Geplante Änderungen über die Sync-Action mit `dry-run: true` anzeigen. Keine Schreiboperation. |
| `APPLY` | Änderungen durchführen, danach Readback. Nur mit Environment-Freigabe und Apply-Gate. |

Auslöser:

- `pull_request`: nur Konfigurationsvalidierung und Unit-/Security-Tests, **keine** App-Secrets
- `push` auf `main` / wöchentlicher Cron: `AUDIT` auf privilegiertem Pfad
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
- Client-ID: Variable `GMV_GITHUB_MODERATOR_APP_CLIENT_ID`
- Private Key: Secret `GMV_GITHUB_MODERATOR_APP_PRIVATE_KEY` **nur als Environment-Secret**
  auf `github-moderator-privileged` und `github-moderator-apply`
- Keine Repository-Secrets für den App-Private-Key (sonst wären Same-Repo-PRs gefährdet)

### Trust-Boundary (P0)

- `pull_request` erhält grundsätzlich keine GitHub-App-Secrets
- Same-Repo-PRs gelten **nicht** als vertrauenswürdig
- Privilege wird im Workflow über `github.event_name != 'pull_request'` entschieden,
  nicht über ausgecheckten PR-Python-Code
- `pull_request_target` wird nicht verwendet
- Tokens werden nicht in `GITHUB_OUTPUT`, Logs, Artefakte oder Job-Summaries geschrieben
- App-Token-Minting ist auf Repository `gmv-foundation` beschränkt

### Benötigte GitHub-App-Berechtigungen

Minimal für V1:

| Permission | Zugriff | Grund |
| --- | --- | --- |
| Administration | Read and write | Repository-Settings und Rulesets lesen/schreiben |
| Metadata | Read | Standard für GitHub Apps |

Hinweis: Das Workflow-`GITHUB_TOKEN` hat keinen `administration`-Scope.
Live-AUDIT, DRY_RUN und APPLY brauchen deshalb die GitHub App. Fehlt sie,
meldet der Audit-Schritt `BLOCKED` statt stiller Umgehung.

AUDIT bleibt lesend (Vergleich Ist/Soll, keine Writes).
DRY_RUN setzt `dry-run: true` und führt keine Schreiboperationen aus.
APPLY schreibt erst nach expliziter Freigabe.

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
4. Repository-Variable `GMV_MODERATOR_APPLY_GATE=enabled`
5. Vorhandene GitHub-App-Credentials (Environment-Secrets)
6. Vorher-Audit und anschließender Readback (`--expect-aligned`)

Fehlt eine Bedingung, endet der Lauf mit `BLOCKED`.

### Pull Requests

- Same-Repo- und Fork-PRs erhalten keine App-Secrets
- Live-Audit / DRY_RUN / APPLY mit App-Token laufen nicht auf `pull_request`
- Konfigurationsvalidierung und Unit-/Negativtests laufen ohne privilegierte Zugangsdaten

## Bedienung

### Lokal

```bash
python3 scripts/github_moderator_validate.py
python3 scripts/github_moderator_security.py check-workflow
GITHUB_TOKEN=… python3 scripts/github_moderator_audit.py --repo tiktokagentur-art/gmv-foundation
```

### In GitHub Actions

1. Workflow `GitHub Moderator` öffnen
2. `Run workflow` wählen
3. Modus `AUDIT` oder `DRY_RUN` setzen
4. `APPLY` nur nach CEO-Freigabe der Environment und des Apply-Gates

## CEO-Checkliste vor dem ersten APPLY

1. GitHub App anlegen mit Administration read/write, nur dieses Repository
2. Environment `github-moderator-privileged` anlegen
   - Deployment Branch Policy: nur `main`
   - Environment-Secret `GMV_GITHUB_MODERATOR_APP_PRIVATE_KEY`
   - Environment- oder Repository-Variable `GMV_GITHUB_MODERATOR_APP_CLIENT_ID`
   - Keine Required Reviewers (nur Credential-Isolation)
3. Environment `github-moderator-apply` anlegen
   - Required Reviewers setzen
   - Deployment Branch Policy: nur `main`
   - denselben App-Private-Key als Environment-Secret
4. Repository-Secret für den App-Private-Key **entfernen**, falls vorhanden
5. `GMV_MODERATOR_APPLY_GATE=enabled` setzen
6. Zuerst `AUDIT`, dann `DRY_RUN`, erst danach `APPLY`

## Bekannte Einschränkungen

- Ohne GitHub App sind DRY_RUN und APPLY blockiert.
- Ohne Environment-Reviewer ist die Freigabekette unvollständig; das Apply-Gate bleibt aus.
- Die Sync-Action pinnt auf einen Commit-SHA; Updates brauchen eine bewusste Prüfung.
- ADR-0004 bleibt `Proposed`. Dieses Modul setzt den CEO-Pilot-Sollzustand um, ersetzt aber keinen ADR-Statuswechsel.
- Solange der App-Private-Key als Repository-Secret liegt, kann ein Same-Repo-PR den
  Workflow umschreiben und Secrets lesen. Environment-Secrets mit Branch-Policy sind Pflicht.
