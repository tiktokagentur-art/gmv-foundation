# ADR-0011: Release- und Rollback-Autorität

- Status: Proposed
- Datum: 2026-11-09
- Überarbeitet: 2026-11-10 (Vorschlag ergänzt, nicht entschieden)
- Entscheider: offen

## Kontext

Die Software Factory führt Änderungen über Test, CI, Pull Request und
unabhängige Review. [../ARCHITECTURE.md](../ARCHITECTURE.md) hält fest: ein
Merge nach `main` ist noch kein Produktionsrelease.

Offen ist, welche Rolle ein Release in Produktion auslösen darf und welche
Rolle einen Rollback auslösen darf. Das können verschiedene Rollen sein.
Sie sind nicht besetzt. Eine Person wird hier nicht genannt, weil keine
benannt entschieden wurde.

In `staging` gibt es ein laufendes Deployment der Dienste `backend` und
Postgres (Railway-Readback am 10.11.2026, Europe/Berlin). Ein
Produktionsdeployment gibt es nicht. Der genaue Auslöser eines Staging-Deploys
wird hier nicht festgehalten.

### Ist-Stand

- [ADR-0004](0004-branch-protection-codeowners.md) (Accepted): `main` ist per
  Ruleset geschützt, mit drei Pflicht-Checks und ohne Bypass. Die Zahl
  erforderlicher Approvals ist 0. Das weicht von
  [../../CONTRIBUTING.md](../../CONTRIBUTING.md) ab (mindestens eine
  unabhängige Freigabe).
- Beobachtung als Entscheidungsgrundlage, gelesen am 2026-11-10: Die
  Staging-Deployments gehörten jeweils zu einem Commit auf `main`, und
  „Wait for CI“ war aus. Eine verbindliche Feststellung des Auslösers ist das
  nicht (siehe oben). Railway meldet diese Deployments als
  GitHub-Deployments (Environment „GMV-V3 / staging“, nicht als Produktion
  markiert). Ein Merge setzt grüne Pflicht-Checks des Pull Requests voraus.
- Das Environment `github-moderator-apply` hat einen Required Reviewer, erlaubt
  aber Self-Review (`prevent_self_review: false`, gelesen am 2026-11-10).
- Es gibt keine Git-Tags, keine GitHub Releases und kein Changelog.
- Der Domänen-Audit-Trail ([../DATA_MODEL.md](../DATA_MODEL.md)) kennt keine
  Release- oder Rollback-Ereignisse.

### Fakten aus Primärquellen

- GitHub Environments: bis zu 6 Required Reviewers, einer genügt. Prevent
  self-review verhindert, dass der Auslöser selbst freigibt. Deployments lassen
  sich auf Branches oder Tags begrenzen. Admin-Bypass ist abschaltbar.
  ([GitHub Environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments))
- Tag-Rulesets beschränken Erstellen, Ändern und Löschen von Tags.
  ([GitHub Rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets))
- Railway Autodeploy lässt sich abschalten. Dann gibt es „Deploy Latest Commit“
  manuell. „Wait for CI“ hält Deployments, bis die Workflows fertig sind.
  ([Railway Autodeploys](https://docs.railway.com/deployments/github-autodeploys))
- Ein Railway-Rollback stellt Image und Variablen eines früheren Deployments
  wieder her, nicht die Datenbank. Er ist nur innerhalb der Image-Retention des
  Plans möglich: Free und Trial 24 h, Hobby 72 h, Pro 120 h, Enterprise 360 h.
  Danach bleibt nur ein Redeploy mit neuem Build.
  ([Railway Deployment Actions](https://docs.railway.com/deployments/deployment-actions),
  [Railway Plans](https://docs.railway.com/pricing/plans))
- Railway Environments: `Sync` übernimmt Konfiguration aus einer anderen
  Umgebung als Staged Changes zur Freigabe. Environment RBAC gibt es nur bei
  Enterprise. Auch dort können Nicht-Admins per Git-Push deployen.
  ([Railway Environments](https://docs.railway.com/environments))
- Railway-Rollen: Admin, Member und Deployer dürfen automatische
  GitHub-Deployments. Audit-Logs sieht nur Admin.
  ([Railway Workspaces](https://docs.railway.com/projects/workspaces))
  Audit-Log-Aufbewahrung im Plan Free: 48 h.
  ([Railway Audit Logs](https://docs.railway.com/enterprise/audit-logs))
- Ein Service kann aus einem Docker-Image deployen, z. B. aus der GitHub
  Container Registry.
  ([Railway Services](https://docs.railway.com/services))
- [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html) und
  [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) beschreiben
  Versionsnummern und ein Änderungsprotokoll je Version.

### Annahmen (getrennt von den Fakten)

- A1: Railway läuft im Plan Free. Übermittelt vom Head of Engineering, vom CEO
  nicht bestätigt. NICHT VERIFIZIERT. Folge: Rollback-Fenster 24 h nach dem
  Entfernen eines Deployments, Audit-Log 48 h.
- A2: Das Team ist sehr klein. Pull Requests von Agenten und Freigaben laufen
  möglicherweise über dasselbe GitHub-Konto, dann wäre eine Freigabe technisch
  Self-Review. NICHT VERIFIZIERT.
- A3: Wie eine Image-Promotion zwischen Umgebungen auf Railway im Detail abläuft
  (Staging der Updates), ist NICHT VERIFIZIERT.

## Entscheidung

Nicht entschieden. Wer ein Produktionsrelease und wer einen Rollback auslösen darf, ist offen.

### Vorschlag zur Prüfung (keine Entscheidung)

1. Rollen: Ein vom CEO benannter Release Manager (RM) gibt jedes Release in
   Produktion frei. Der Autor einer Änderung ist nicht der RM. Agenten erhalten
   eine eigene GitHub-Identität, damit die Trennung prüfbar ist (A2).
2. Notfall-Rollback: RM oder Incident Commander
   ([ADR-0010](0010-slo-alerting-incident.md)) dürfen ohne vorherige Freigabe
   auf ein früheres, bereits freigegebenes Deployment zurückgehen, nie auf einen
   neuen Build. Dokumentation und Postmortem folgen danach. Einen
   Datenbank-Restore ([ADR-0006](0006-backup-retention-rpo-rto.md)) ordnet nur
   der CEO an.
3. Gate: In `production` ist Railway-Autodeploy aus. Deployt wird nur über einen
   GitHub-Actions-Job mit Environment `production`: Required Reviewer = RM,
   Prevent self-review an, kein Admin-Bypass, nur Tags `v*`. Das Token gilt nur
   für diese Umgebung ([ADR-0007](0007-secret-management.md)). Das in `staging`
   getestete Image wird unverändert promotet (A3).
4. `staging`: Autodeploy ist kein Release. Wait for CI wird eingeschaltet, oder
   Autodeploy wird bewusst abgeschaltet.
5. Nachweis je Release: grüne CI, Review, Migrationsplan
   ([ADR-0009](0009-migration-compatibility.md)), aktueller Backup-Stand
   (ADR-0006) und Fehlerbudget (ADR-0010). Dazu kommen ein SemVer-Tag mit
   Tag-Ruleset, ein GitHub Release und ein Changelog-Eintrag.
6. Audit: GitHub-Deployments und Freigaben sind der Release-Nachweis. Das
   Railway-Audit-Log wird bei A1 innerhalb von 48 h exportiert.

### Zu klären

- wer RM ist und wer ihn vertritt, und ob „Agent schreibt, Mensch gibt frei“ als Vier-Augen gilt (A2)
- ob ein Notfall-Rollback ohne Freigabe erlaubt ist und wer einen Datenbank-Restore anordnet
- ob `staging` weiter automatisch deployt
- ob das Ruleset aus [ADR-0004](0004-branch-protection-codeowners.md) auf mindestens eine Freigabe angehoben wird
- eigene Railway-Umgebung oder eigenes Projekt für Produktion ([ADR-0005](0005-railway-environments.md))
- Versionierung, Changelog und Aufbewahrungsdauer der Nachweise

## Konsequenzen

- Ein Merge darf nicht als Produktionsfreigabe gelesen werden.
- Es wird keine Pipeline angelegt, die bei Merge in Produktion deployt. Das automatische Deploy nach `staging` ist Ist-Stand und kein Release. Seine Zulässigkeit ist Teil dieses Entscheids.
- Die unabhängige Review aus [../../CONTRIBUTING.md](../../CONTRIBUTING.md) bleibt bestehen. Sie allein beantwortet dieses ADR nicht.
- Ein Rollback ist eine Entscheidung der dafür vorgesehenen Rolle, kein stilles Überschreiben durch einen Worker.
- Ein Rollback der Anwendung setzt die Datenbank nicht zurück. Er ist nur sicher, wenn das Schema zur Vorversion passt ([ADR-0009](0009-migration-compatibility.md)).
- Ein Restore darf keine zweite schreibende Instanz erzeugen. Die Anwendung schreibt nie parallel in alte und wiederhergestellte Datenbank ([ADR-0003](0003-single-assignment-authority.md)).
- Ein Rollback stellt alte Variablen wieder her. Nach einer Rotation ([ADR-0007](0007-secret-management.md)) muss das geprüft werden.

## Alternativen

| Option | Vorteil | Nachteil |
| --- | --- | --- |
| Railway-Autodeploy von eigenem Release-Branch | wenig Aufwand | Autorität liegt bei Merge-Rechten auf den Branch; neuer Build je Umgebung |
| Manuelles Deploy im Railway-Dashboard | keine CI-Credentials | keine durchgesetzte Freigabe; Audit planabhängig kurz |
| GitHub Environment `production` plus Image-Promotion (Vorschlag) | serverseitige Freigabe, gleiches Artefakt, GitHub-Audit | Prod-Token in GitHub; mit einer Person und Prevent self-review deployt niemand |
| Vier-Augen auch für Rollback | maximale Kontrolle | verzögert die Behebung; mit einer Person nicht durchführbar |

Automatisches Deploy bei Merge in Produktion wäre bereits eine Wahl der
Autorität und ist deshalb nicht der Default.

## Bezug

- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0004](0004-branch-protection-codeowners.md)
- [ADR-0005](0005-railway-environments.md)
- [ADR-0006](0006-backup-retention-rpo-rto.md)
- [ADR-0007](0007-secret-management.md)
- [ADR-0009](0009-migration-compatibility.md)
- [ADR-0010](0010-slo-alerting-incident.md)
- [../../CONTRIBUTING.md](../../CONTRIBUTING.md)
