# ADR-0010: SLOs, Alarmierung, Incident-Prozess

- Status: Proposed
- Datum: 2026-11-09
- Entscheider: offen

## Kontext

Es gibt noch kein gemessenes Service Level Objective (SLO). In `staging`
laufen die Dienste `backend` und Postgres (Railway-Readback am 10.11.2026,
Europe/Berlin). Zahlen ohne Messpfad würden den Leitsatz verletzen: Verify
everything. Deshalb setzt dieses ADR keine Verfügbarkeit, keine Latenz und
keine Fehlerquote.

Ebenfalls offen sind Alarmierung und der Incident-Prozess: wer informiert wird,
welche Stufen es gibt und wie ein Incident beendet wird. Ein Werkzeug dafür
ist nicht gewählt. [ADR-0005](0005-railway-environments.md) dokumentiert die
Umgebung `staging`. Ein SLO für `staging` oder production ist nicht festgelegt.

## Entscheidung

Nicht entschieden. SLO-Ziele, Alarmierungswege und der Incident-Prozess sind offen.

Zu klären ist mindestens:

- welche Nutzerpfade ein SLO haben, sobald ein Dienst existiert
- Zielwert und Messfenster je SLO, plus die konkrete Messung
- wohin ein Alarm geht und wer handelt
- Stufen eines Incidents, Kommunikationsweg und Abschluss
- wie ein Alarm von einem fehlgeschlagenen CI-Lauf unterschieden wird

## Konsequenzen

- Diese Baseline behauptet kein Verfügbarkeitsziel.
- Ein Dashboard oder ein Alarm ohne angenommenes ADR ist kein SLO.
- Produktionsbetrieb setzt neben diesem Entscheid auch [ADR-0006](0006-backup-retention-rpo-rto.md) und [ADR-0011](0011-release-rollback-authority.md) voraus.

## Alternativen

Nicht bewertet. Es wird kein Beobachtungswerkzeug vorgeschlagen.

## Bezug

- [ADR-0005](0005-railway-environments.md)
- [ADR-0006](0006-backup-retention-rpo-rto.md)
- [ADR-0011](0011-release-rollback-authority.md)
