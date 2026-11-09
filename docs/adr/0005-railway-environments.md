# ADR-0005: Railway-Umgebungen, Regionen, Limits

- Status: Proposed
- Datum: 2026-11-09
- Entscheider: offen

## Kontext

[ADR-0001](0001-postgresql-on-railway.md) legt PostgreSQL direkt auf Railway fest
und erzeugt keine Ressource. Ungeklärt sind die Umgebungen und die Limits der
Dienste. Die Region ist entschieden
([ADR-0012](0012-hosting-region-usa.md)): Railway `sfo` in den USA.

[ADR-0003](0003-single-assignment-authority.md) verbietet einen zweiten Schreiber
für dieselbe Domäne. [ADR-0012](0012-hosting-region-usa.md) legt zusätzlich fest,
dass alle Dienste in `sfo` laufen. Eine weitere Region ist nicht mehr offen.

Es gibt in diesem Repository kein Railway-Projekt, keine Umgebung und keine
Kontonummer. Solche Angaben gehören nicht in ein öffentliches ADR.

## Entscheidung

Nicht entschieden. Namen und Anzahl der Railway-Umgebungen und die Dienstlimits sind offen.

Die Region ist nicht mehr Teil dieser offenen Frage. Sie steht in
[ADR-0012](0012-hosting-region-usa.md).

Zu klären ist mindestens:

- welche Umgebungen es gibt und welche davon autoritativen Zustand halten dürfen
- welche Limits für Verbindungen, Speicher, Rechner und Kosten gelten
- welche Identität je Umgebung eigene Rechte hat

## Konsequenzen

- Es wird keine Umgebung als bereits vorhanden beschrieben.
- Produktion wird nicht nebenbei angelegt, solange Backup ([ADR-0006](0006-backup-retention-rpo-rto.md)), Secrets ([ADR-0007](0007-secret-management.md)) und Release-Autorität ([ADR-0011](0011-release-rollback-authority.md)) offen sind.
- Ein späterer Entscheid, der zwei schreibende Primaries erzeugt, widerspricht ADR-0003 und kann ADR-0001 nicht stillschweigend erweitern.

## Alternativen

Nicht bewertet. Die Region wird hier nicht erneut gewählt.

## Bezug

- [ADR-0001](0001-postgresql-on-railway.md)
- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0006](0006-backup-retention-rpo-rto.md)
- [ADR-0012](0012-hosting-region-usa.md)
