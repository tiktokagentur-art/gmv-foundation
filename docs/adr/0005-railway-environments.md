# ADR-0005: Railway-Umgebungen, Regionen, Limits

- Status: Accepted
- Datum: 2026-11-10
- Entscheider: CEO

## Kontext

[ADR-0001](0001-postgresql-on-railway.md) legt PostgreSQL direkt auf Railway fest.
Die Region ist entschieden ([ADR-0012](0012-hosting-region-usa.md)): Railway
`sfo` in den USA. [ADR-0003](0003-single-assignment-authority.md) verbietet einen
zweiten Schreiber für dieselbe Domäne. Alle Dienste laufen in `sfo`. Eine
weitere Region ist nicht offen.

Interne Projekt-IDs, Kontonummern und Dienstedomains gehören nicht in dieses
öffentliche Repository ([ADR-0013](0013-repository-visibility-public.md)). Der
Name des Projekts und der Umgebungen darf beschrieben werden.

Die CEO-Entscheidung vom 10.11.2026 nimmt den an diesem Tag gelesenen Ist-Stand
der Umgebungen an. Dienstlimits wurden dabei nicht als festgelegter Wert
gelesen.

## Entscheidung

Entschieden. Das Greenfield-Railway-Projekt heißt GMV-V3. Alle Dienste laufen in der Region sfo (USA). In diesem Projekt gibt es die Umgebung staging. Eine Umgebung production gibt es in diesem Projekt nicht.

Dienstlimits, welche Umgebung autoritativen Zustand halten darf und welche
Identität je Umgebung eigene Rechte hat, sind durch diesen Entscheid nicht
festgelegt.

## Konsequenzen

- Production wird durch diesen Entscheid nicht angelegt. Backup
  ([ADR-0006](0006-backup-retention-rpo-rto.md)), Secrets
  ([ADR-0007](0007-secret-management.md)) und Release-Autorität
  ([ADR-0011](0011-release-rollback-authority.md)) bleiben eigene offene Punkte.
- Eine zweite schreibende Primary widerspricht weiter ADR-0003 und kann
  ADR-0001 nicht stillschweigend erweitern.
- Limits bleiben offen, bis ein späterer Entscheid sie festlegt.

## Alternativen

Nicht in diesem ADR neu bewertet. Der Entscheid dokumentiert den gelesenen
Ist-Stand der Umgebungen. Die Region wird hier nicht erneut gewählt.

## Bezug

- [ADR-0001](0001-postgresql-on-railway.md)
- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0006](0006-backup-retention-rpo-rto.md)
- [ADR-0007](0007-secret-management.md)
- [ADR-0011](0011-release-rollback-authority.md)
- [ADR-0012](0012-hosting-region-usa.md)
- [ADR-0013](0013-repository-visibility-public.md)
