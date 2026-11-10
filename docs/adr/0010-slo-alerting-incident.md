# ADR-0010: SLOs, Alarmierung, Incident-Prozess

- Status: Proposed
- Datum: 2026-11-09
- Überarbeitet: 2026-11-10 (Vorschlag ergänzt, nicht entschieden)
- Entscheider: offen

## Kontext

Es gibt kein gemessenes Service Level Objective (SLO). Zahlen ohne Messpfad
würden den Leitsatz verletzen: Verify everything. Deshalb setzt dieses ADR keine
Verfügbarkeit, keine Latenz und keine Fehlerquote fest. Zahlen stehen hier nur
als Kandidaten.

Ebenfalls offen sind Alarmierung und der Incident-Prozess: wer informiert wird,
welche Stufen es gibt und wie ein Incident beendet wird.

### Ist-Stand

- [ADR-0005](0005-railway-environments.md) (Accepted): Es gibt die Umgebung
  `staging`, keine `production`. In `staging` läuft der Anwendungsdienst
  öffentlich erreichbar. Laut Railway gab es in den 7 Tagen bis 2026-11-10
  7 HTTP-Requests. Für Produktion existiert damit kein Messobjekt.
- `/health` antwortet ohne Datenbankprüfung. `/ready` prüft die Datenbank und
  antwortet sonst mit 503 ([../../app/main.py](../../app/main.py)).
- Die JSON-Logs haben keine Felder für Request-ID, Dauer oder Statuscode
  ([../../app/logging_config.py](../../app/logging_config.py)).
- [../../SECURITY.md](../../SECURITY.md) nennt noch keinen vertraulichen
  Meldeweg für Schwachstellen.

### Fakten aus Primärquellen

- Ein SLO ist ein Zielwert für einen SLI. Das Fehlerbudget steuert
  Release-Entscheidungen. 100 % ist kein sinnvolles Ziel.
  ([Google SRE Book: SLOs](https://sre.google/sre-book/service-level-objectives/))
- Multiwindow-Multi-Burn-Rate-Alarme, z. B. Page bei 14,4-facher Burn-Rate über
  1 h und 5 min. Bei wenig Traffic empfiehlt das Workbook synthetischen Traffic.
  ([SRE Workbook: Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/))
- Beispiel-Fehlerbudget-Policy: Ist das Budget erschöpft, werden Releases außer
  P0- und Security-Fixes gestoppt.
  ([SRE Workbook: Error Budget Policy](https://sre.google/workbook/error-budget-policy/))
- Rollen Incident Commander (IC), Communications Lead und Ops Lead. Bei kleinen
  Incidents kann der IC die Kommunikation übernehmen.
  ([SRE Workbook: Incident Response](https://sre.google/workbook/incident-response/))
  Postmortems sind blameless, ihre Auslöser werden vorab festgelegt.
  ([SRE Book: Postmortem Culture](https://sre.google/sre-book/postmortem-culture/))
- Railway sammelt Ressourcenmetriken, keine Anwendungsmetriken wie Latenz oder
  Fehlerrate. Edge-HTTP-Logs enthalten Status, Dauer, Pfad und Client-IP.
  ([Railway Logs](https://docs.railway.com/observability/logs))
  Log-Aufbewahrung im Plan Free: 3 Tage.
  ([Railway Plans](https://docs.railway.com/pricing/plans))
- Railway Monitors (Ressourcen-Alarme) erfordern den Plan Pro.
  ([Railway Observability](https://docs.railway.com/observability))
  Healthchecks laufen nur beim Deploy, nicht dauerhaft.
  ([Railway Healthchecks](https://docs.railway.com/deployments/healthchecks))
- Externe Uptime-Dienste, Beispiele: Better Stack mit Prüfungen von mehreren
  Standorten ([Better Stack](https://betterstack.com/docs/uptime/working-with-incidents/)),
  UptimeRobot mit Datenhaltung primär in der EU
  ([UptimeRobot DPA](https://uptimerobot.com/dpa/)).

### Annahmen (getrennt von den Fakten)

- A1: Railway läuft im Plan Free. Übermittelt vom Head of Engineering, vom CEO
  nicht bestätigt. NICHT VERIFIZIERT. Folge: keine Railway Monitors, 3 Tage Logs.
- A2: [ADR-0012](0012-hosting-region-usa.md) gilt nur für Railway-Dienste. Ein
  externer Uptime-Monitor ist frei wählbar. Übermittelt vom Head of Engineering,
  vom CEO nicht bestätigt. NICHT VERIFIZIERT.
- A3: Das Team ist sehr klein und hat keine Rufbereitschaft rund um die Uhr.
  NICHT VERIFIZIERT.
- A4: Edge-Logs enthalten personenbezogene Daten (Client-IP). Ein Export an
  Drittanbieter braucht eine Datenschutzprüfung. NICHT VERIFIZIERT im Detail.

## Entscheidung

Nicht entschieden. SLO-Ziele, Alarmierungswege und der Incident-Prozess sind offen.

### Vorschlag zur Prüfung (keine Entscheidung)

1. Erst die Messpfade, dann die Zahlen. Ein externer Uptime-Monitor (A2) prüft
   `/ready` und einen synthetischen `/v1`-Pfad von mehreren Standorten. Dazu
   kommen der 5xx-Anteil aus den Railway-Edge-Logs und die Quote abgelaufener
   Leases aus dem Audit.
2. Nach einer Messphase (Kandidat: 4 Wochen) werden Ziel, Fenster und
   Fehlerbudget beschlossen. Kandidaten, nicht entschieden:

   | SLI | Kandidat | Messpfad |
   | --- | --- | --- |
   | Verfügbarkeit `/ready` (extern) | 99,5 % über 28 Tage | externer Uptime-Monitor |
   | Erfolgsquote `/v1` | 99,5 % über 28 Tage | Edge-Logs bzw. synthetische Probe |
   | Latenz `/v1` | p95 nach Messphase festlegen | Edge-Logs `@totalDuration` |

3. Alarmierung: Ausfall von `/ready` an mehreren Standorten löst einen Page aus,
   ein Burn-Rate-Ticket erst bei genügend Traffic. Ein fehlgeschlagener CI-Lauf
   ist nie ein Page. Kanal und Erreichbarkeit legt der CEO fest.
4. Incident-Prozess mit drei Stufen: SEV1 (Ausfall oder Integritätsverletzung,
   z. B. doppelte Zuweisung), SEV2 (Teilausfall), SEV3 (Beeinträchtigung ohne
   Nutzerwirkung). Integritätsverletzungen sind immer SEV1. Eine Person ist IC
   und übernimmt die Kommunikation. Ein Rollback richtet sich nach
   [ADR-0011](0011-release-rollback-authority.md). Ein Postmortem ist Pflicht
   bei SEV1, Datenverlust, Restore ([ADR-0006](0006-backup-retention-rpo-rto.md))
   und Rollback.
5. Ein erschöpftes Fehlerbudget stoppt Releases außer Fixes. Das ist ein
   Kandidat, die Freigabe regelt ADR-0011.

### Zu klären

- ob A1 und A2 gelten (CEO-Bestätigung) und welcher Uptime-Dienst
- wer IC ist, über welchen Kanal alarmiert wird und mit welcher Erreichbarkeit
- ob die Messphase akzeptiert wird oder ein vorläufiges SLO gesetzt wird
- ob ein erschöpftes Fehlerbudget Releases stoppen darf
- ob es eine Statusseite oder externe Kommunikation gibt
- wie Logs mit Client-IPs aufbewahrt und weitergegeben werden (A4)

## Konsequenzen

- Diese Baseline behauptet kein Verfügbarkeitsziel.
- Ein Dashboard oder ein Alarm ohne angenommenes ADR ist kein SLO.
- Produktionsbetrieb setzt neben diesem Entscheid auch [ADR-0006](0006-backup-retention-rpo-rto.md) und [ADR-0011](0011-release-rollback-authority.md) voraus.
- Wird der Vorschlag angenommen: Logs brauchen Request-ID, Dauer und Status als
  eigene Felder. Bei A1 halten Railway-Logs nur 3 Tage. Für Postmortems ist ein
  Export nötig. Ein Security-Incident braucht einen Meldeweg in SECURITY.md.

## Alternativen

| Option | Vorteil | Nachteil |
| --- | --- | --- |
| Nur Railway-Bordmittel | kein Drittanbieter | keine Anwendungsmetriken, Monitors erst ab Pro, Healthcheck nur beim Deploy |
| Railway plus externer Uptime-Monitor (Vorschlag) | unabhängige Sicht von außen, geringer Aufwand | neuer Anbieter (A2), nur Black-Box-Sicht |
| Volle Observability (z. B. Grafana Cloud, Sentry, OpenTelemetry) | Metriken, Traces, Fehler | höherer Aufwand und Datenschutzprüfung (A4) |
| Uptime Kuma selbst auf Railway | bleibt in `sfo` | beobachtet sich auf derselben Plattform selbst |

## Bezug

- [ADR-0005](0005-railway-environments.md)
- [ADR-0006](0006-backup-retention-rpo-rto.md)
- [ADR-0009](0009-migration-compatibility.md)
- [ADR-0011](0011-release-rollback-authority.md)
- [ADR-0012](0012-hosting-region-usa.md)
- [../ARCHITECTURE.md](../ARCHITECTURE.md)
- [../../SECURITY.md](../../SECURITY.md)
