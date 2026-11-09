# Architecture Decision Records

Versionierte Entscheidungen der Foundation. Die Vorlage ist [template.md](template.md).
Das Verfahren steht in [../GOVERNANCE.md](../GOVERNANCE.md).

`Proposed` ist keine Entscheidung. Ein Skelett, das ein ADR ausdrücklich als
Prüfung des Vorschlags erlaubt, nimmt den Vorschlag nicht an.
`Accepted` gilt, bis ein neueres ADR es auf `Superseded` setzt.

## Bestand

| ADR | Titel | Status |
| --- | --- | --- |
| [0001](0001-postgresql-on-railway.md) | PostgreSQL auf Railway | Accepted |
| [0002](0002-python-fastapi.md) | Python / FastAPI | Proposed |
| [0003](0003-single-assignment-authority.md) | Eine Assignment Authority, ein Eigentümer je Domäne | Accepted |
| [0004](0004-branch-protection-codeowners.md) | Branch Protection und CODEOWNERS | Proposed |
| [0005](0005-railway-environments.md) | Railway-Umgebungen, Regionen, Limits | Proposed |
| [0006](0006-backup-retention-rpo-rto.md) | Backup-Aufbewahrung, RPO, RTO | Proposed |
| [0007](0007-secret-management.md) | Secret-Verwaltung, Rotation, Break-glass | Proposed |
| [0008](0008-auth-standard.md) | Authentisierungsstandard | Proposed |
| [0009](0009-migration-compatibility.md) | API- und Datenbankmigration, Kompatibilität | Proposed |
| [0010](0010-slo-alerting-incident.md) | SLOs, Alarmierung, Incident-Prozess | Proposed |
| [0011](0011-release-rollback-authority.md) | Release- und Rollback-Autorität | Proposed |
| [0012](0012-hosting-region-usa.md) | Hosting-Region USA (Railway sfo) | Accepted |

## Offene Entscheidungen

Die folgenden Punkte sind bewusst nicht entschieden. Sie haben keinen stillen
Default. Jede Zeile verweist auf das ADR, das die Frage festhält.

| Thema | ADR |
| --- | --- |
| Branch Protection, erforderliche Checks, aktive CODEOWNERS | [0004](0004-branch-protection-codeowners.md) |
| Railway-Umgebungen und Limits (Region entschieden, ADR-0012) | [0005](0005-railway-environments.md) |
| Backup-Aufbewahrung, RPO, RTO | [0006](0006-backup-retention-rpo-rto.md) |
| Secret-Provider, Rotation, Break-glass | [0007](0007-secret-management.md) |
| Authentisierungsstandard | [0008](0008-auth-standard.md) |
| Strategie für API- und Datenbankmigration und Kompatibilität | [0009](0009-migration-compatibility.md) |
| SLOs, Alarmierung, Incident-Prozess | [0010](0010-slo-alerting-incident.md) |
| Autorität für Produktionsrelease und Rollback | [0011](0011-release-rollback-authority.md) |

Python / FastAPI ([0002](0002-python-fastapi.md)) ist ebenfalls `Proposed`.
GF-006 baut das Skelett darauf, ohne den Status zu ändern.

Die Hosting-Region USA, Railway `sfo`, ist [0012](0012-hosting-region-usa.md)
(Accepted, CEO 09.11.2026). Im Arbeitsauftrag heißt sie ADR-0004. Diese Nummer
ist im Repository Branch Protection
([0004](0004-branch-protection-codeowners.md)).
