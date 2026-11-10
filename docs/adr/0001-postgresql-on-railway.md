# ADR-0001: PostgreSQL auf Railway

- Status: Accepted
- Datum: 2026-11-09
- Entscheider: CEO

## Kontext

Greenfield V1 braucht für autoritativen Zustand genau eine Datenbank.
Die CEO-Entscheidung vom 09.11.2026 legt PostgreSQL direkt auf Railway fest.

Dieses Repository ist öffentlich
([ADR-0013](0013-repository-visibility-public.md)) und legt mit diesem ADR keine
Railway-Ressource an. Es gibt hier kein Schema, keinen Benutzer und keine
Verbindungsdaten.

## Entscheidung

Entschieden. PostgreSQL direkt auf Railway ist die Datenbank für autoritativen Zustand.

PostgreSQL läuft als Datenbank auf Railway. Ein anderer Betreiber und eine
zwischengeschaltete zweite Datenbankplattform sind für diesen Zustand nicht
zulässig. Eine zweite Datenbank für denselben Zustand ist ausgeschlossen.

## Konsequenzen

- Verträge dürfen später PostgreSQL als einzige Datenbank dieses Zustands annehmen.
- Backup, Wiederherstellung und Betrieb beziehen sich auf diese eine Datenbank.
- Region, Umgebungen, Limits, Aufbewahrung, RPO und RTO sind nicht Teil dieses Entscheids ([ADR-0005](0005-railway-environments.md), [ADR-0006](0006-backup-retention-rpo-rto.md)).
- Dieses ADR erzeugt keine Instanz. Infrastruktur bleibt ein späterer, eigener Schritt.
- Verbindungsdaten stehen nicht im Git ([../../SECURITY.md](../../SECURITY.md)).

## Alternativen

Nicht bewertet. Dieses ADR dokumentiert die CEO-Entscheidung vom 09.11.2026.
Es rekonstruiert keine verworfene Auswahl. Eine andere Datenbank braucht ein
neues ADR, das dieses auf `Superseded` setzt, und einen neuen Entscheid.

## Bezug

- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0005](0005-railway-environments.md)
- [ADR-0006](0006-backup-retention-rpo-rto.md)
- [ADR-0009](0009-migration-compatibility.md)
- [ADR-0013](0013-repository-visibility-public.md)
