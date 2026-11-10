# ADR-0006: Backup-Aufbewahrung, RPO und RTO

- Status: Proposed
- Datum: 2026-11-09
- Entscheider: offen

## Kontext

[ADR-0001](0001-postgresql-on-railway.md) macht PostgreSQL auf Railway zur
Datenbank des autoritativen Zustands. Wie lange Backups aufbewahrt werden, welches
Recovery Point Objective (RPO) und welches Recovery Time Objective (RTO) gelten,
ist nicht entschieden.

Ein Backup ist eine Kopie für Wiederherstellung, kein zweiter Schreiber
([ADR-0003](0003-single-assignment-authority.md)). Zugriff darauf folgt Least
Privilege ([../../SECURITY.md](../../SECURITY.md)).

Der Leitsatz verlangt Nachweis. Ein RPO oder RTO ohne beschriebenen und später
ausgeführten Wiederherstellungstest wäre eine unbelegte Zahl. Deshalb wird hier
keine Zahl eingesetzt.

In der Umgebung `staging` des Projekts GMV-V3 läuft eine PostgreSQL-Datenbank
mit persistentem Volume (Railway-Readback am 10.11.2026, Europe/Berlin).
Ob ein Backup oder PITR eingerichtet ist, ist NICHT VERIFIZIERT.

## Entscheidung

Nicht entschieden. Aufbewahrungsdauer, RPO und RTO sind offen.

Zu klären ist mindestens:

- RPO und RTO als konkrete Ziele, getrennt für die Umgebungen aus [ADR-0005](0005-railway-environments.md)
- Aufbewahrungsdauer und wer Backups löschen darf
- wo die Kopien liegen, ohne daraus einen zweiten Primary zu machen
- wie ein Wiederherstellungstest aussieht und wann er wiederholt wird
- welche Identität ein Backup lesen darf und welche es einspielen darf

## Konsequenzen

- Solange dieses ADR `Proposed` ist, gibt es kein behauptetes Wiederherstellungsziel.
- Autoritative Daten in einer dauerhaften Umgebung setzen einen angenommenen Entscheid und einen bestandenen Wiederherstellungstest voraus. Beides existiert nicht.
- Backup-Zugangsdaten stehen nicht im Git und nicht in diesem ADR.

## Alternativen

Nicht bewertet. Anbieterfunktionen werden nicht als stiller Ersatz für RPO und
RTO gewertet.

## Bezug

- [ADR-0001](0001-postgresql-on-railway.md)
- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0005](0005-railway-environments.md)
- [ADR-0007](0007-secret-management.md)
