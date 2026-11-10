# ADR-0006: Backup-Aufbewahrung, RPO und RTO

- Status: Proposed
- Datum: 2026-11-09
- Überarbeitet: 2026-11-10 (Vorschlag ergänzt, nicht entschieden)
- Entscheider: offen

## Kontext

[ADR-0001](0001-postgresql-on-railway.md) macht PostgreSQL auf Railway zur
Datenbank des autoritativen Zustands. Wie lange Backups aufbewahrt werden, welches
Recovery Point Objective (RPO) und welches Recovery Time Objective (RTO) gelten,
ist nicht entschieden.

Ein Backup ist eine Kopie für Wiederherstellung, kein zweiter Schreiber
([ADR-0003](0003-single-assignment-authority.md)). Zugriff darauf folgt Least
Privilege ([../../SECURITY.md](../../SECURITY.md)).

Der Leitsatz verlangt Nachweis. Ein RPO oder RTO ohne ausgeführten
Wiederherstellungstest wäre eine unbelegte Zahl. Zahlen stehen hier deshalb nur
als Kandidaten.

In der Umgebung `staging` des Projekts GMV-V3 läuft eine PostgreSQL-Datenbank
mit persistentem Volume (Railway-Readback am 10.11.2026, Europe/Berlin).
Ob ein Backup oder PITR eingerichtet ist, ist NICHT VERIFIZIERT.

### Ist-Stand

- [ADR-0005](0005-railway-environments.md) (Accepted): Eine Umgebung
  `production` gibt es nicht.
- Welche Umgebung autoritativen Zustand halten darf, ist offen (ADR-0005).

### Fakten aus Primärquellen

- Railway-Volume-Backups: manuell oder nach Zeitplan. Daily wird 6 Tage,
  Weekly 27 Tage und Monthly 89 Tage aufbewahrt. Ein Restore geht nur ins
  selbe Projekt und dieselbe Umgebung. Wird ein Volume gewiped, werden alle
  seine Backups gelöscht.
  ([Railway Backups](https://docs.railway.com/reference/backups))
- Railway-PITR für PostgreSQL archiviert WAL per pgBackRest in einen
  Railway-Bucket. Das Restore-Fenster beträgt etwa 4 Wochen. Ein Restore legt
  einen neuen Nachbardienst an, das Umschalten ist manuell.
  ([Railway PITR](https://docs.railway.com/volumes/point-in-time-recovery))
- Railway-Plan Free: 0,5 GB Volume-Speicher je Service und 1 Replica.
  ([Railway Plans](https://docs.railway.com/pricing/plans))
- `pg_dump` erzeugt eine konsistente logische Sicherung einer Datenbank, auch
  bei laufendem Betrieb.
  ([PostgreSQL: SQL Dump](https://www.postgresql.org/docs/current/backup-dump.html))
- Art. 32 Abs. 1 lit. c und d DSGVO verlangen die Fähigkeit zur raschen
  Wiederherstellung und ein Verfahren zur regelmäßigen Überprüfung.
  ([Art. 32 DSGVO](https://dsgvo-gesetz.de/art-32-dsgvo/))

### Annahmen (getrennt von den Fakten)

- A1: Railway läuft im Plan Free. Übermittelt vom Head of Engineering, vom CEO
  nicht bestätigt. NICHT VERIFIZIERT.
- A2: [ADR-0012](0012-hosting-region-usa.md) gilt nur für Railway-Dienste.
  Externe Anbieter, auch für Backup-Kopien, sind frei wählbar. Übermittelt vom
  Head of Engineering, vom CEO nicht bestätigt. NICHT VERIFIZIERT.
- A3: Volume-Backups sind laut Antworten von Railway-Mitarbeitern im
  Community-Forum nur im Plan Pro verfügbar. In der offiziellen Backup-Doku
  steht keine Plangrenze.
  ([Forum](https://station.railway.com/questions/volume-back-ups-and-cold-starts-adf65411))
  NICHT VERIFIZIERT.
- A4: Ob PITR im Plan Free verfügbar ist, ist NICHT VERIFIZIERT.

## Entscheidung

Nicht entschieden. Aufbewahrungsdauer, RPO und RTO sind offen.

### Vorschlag zur Prüfung (keine Entscheidung)

Grundlage sind A1 und A2. Gelten sie nicht, ist der Vorschlag neu zu prüfen.

1. Primäre Sicherung ist ein regelmäßiger `pg_dump` an ein Ziel außerhalb des
   Railway-Projekts (offsite), verschlüsselt vor dem Upload. Plattform-Backups
   und PITR sind optional zusätzlich, falls der Plan sie erlaubt (A3, A4).
2. Der Dump-Job läuft als eigener Dienst mit eigener, nur lesender
   Datenbankrolle. Das Ziel wird nur beschrieben, nicht gelesen.
   Zugangsdaten verwaltet [ADR-0007](0007-secret-management.md).
3. Ein Restore-Test spielt einen Dump in eine leere Instanz ein und misst Dauer
   und Datenalter. Erst danach werden RPO und RTO eingetragen.
4. Ein Restore ist keine zweite Schreibinstanz. Die Anwendung wird erst nach dem
   Umschalten auf die wiederhergestellte Datenbank gerichtet, nie auf beide
   ([ADR-0003](0003-single-assignment-authority.md),
   [ADR-0011](0011-release-rollback-authority.md)).

Kandidaten, nicht entschieden und erst nach dem Restore-Test belastbar:

| Größe | Kandidat | Messpfad |
| --- | --- | --- |
| RPO (Produktion, nur Dump) | 24 h bei täglichem Dump | Zeitstempel des letzten erfolgreichen Uploads |
| RTO (Produktion) | kein Kandidat vor dem Test | Dauer des Restore-Tests |
| Aufbewahrung offsite | z. B. 30 Tagesstände | Lebenszyklusregel des Ziels |
| Restore-Test | vor `Accepted`, danach regelmäßig | Testprotokoll |

### Zu klären

- ob A1 und A2 gelten (CEO-Bestätigung)
- Offsite-Ziel, dessen Region und ob Unveränderlichkeit (Object Lock) verlangt ist
- welcher Datenverlust und welche Ausfallzeit geschäftlich tragbar sind
- Aufbewahrungsdauer, Löschpflichten und wer Backups löschen darf
- wer den Restore-Test ausführt und abnimmt und in welchem Intervall

## Konsequenzen

- Solange dieses ADR `Proposed` ist, gibt es kein behauptetes Wiederherstellungsziel.
- Autoritative Daten in einer dauerhaften Umgebung setzen einen angenommenen Entscheid und einen bestandenen Wiederherstellungstest voraus. Beides existiert nicht.
- Backup-Zugangsdaten stehen nicht im Git und nicht in diesem ADR.
- Wird der Vorschlag angenommen: Ein Rollback der Anwendung setzt die Datenbank
  nicht zurück ([ADR-0011](0011-release-rollback-authority.md)). Ein Restore aus
  dem Dump verliert alle Änderungen seit dem Dump.
- Ein Dump-Job braucht einen Netzweg zur Datenbank. Eine öffentliche Freigabe
  der Datenbank nur dafür wäre ein neues Risiko und wird vermieden.

## Alternativen

| Option | Vorteil | Nachteil |
| --- | --- | --- |
| A: nur Railway-Volume-Backups | kein eigener Code | laut A3 nicht im Plan Free; Wipe löscht Backups; Restore nur im selben Projekt |
| B: Railway-PITR | feine Granularität, etwa 4 Wochen | Plan-Verfügbarkeit offen (A4); neuer Nachbardienst beim Restore |
| C: `pg_dump` offsite (Vorschlag) | planunabhängig, portabel, testbar | eigener Job und Zugangsdaten; RPO so grob wie das Dump-Intervall |
| D: eigenes pgBackRest oder WAL-G | volle Kontrolle | hoher Betriebsaufwand für V1 |

## Bezug

- [ADR-0001](0001-postgresql-on-railway.md)
- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0005](0005-railway-environments.md)
- [ADR-0007](0007-secret-management.md)
- [ADR-0009](0009-migration-compatibility.md)
- [ADR-0010](0010-slo-alerting-incident.md)
- [ADR-0011](0011-release-rollback-authority.md)
- [ADR-0012](0012-hosting-region-usa.md)
