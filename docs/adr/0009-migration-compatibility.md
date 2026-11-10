# ADR-0009: Migration und Kompatibilität

- Status: Proposed
- Datum: 2026-11-09
- Überarbeitet: 2026-11-10 (Vorschlag ergänzt, nicht entschieden)
- Entscheider: offen

## Kontext

Die V1-Verträge stehen in [../DATA_MODEL.md](../DATA_MODEL.md) und
[../API_SPECIFICATION.md](../API_SPECIFICATION.md). Die Foundation definiert sie,
bevor die Infrastructure sie umsetzt.

[ADR-0001](0001-postgresql-on-railway.md) legt eine PostgreSQL-Datenbank fest.
[ADR-0003](0003-single-assignment-authority.md) verbietet einen zweiten Eigentümer.
Eine Migration ist eine Änderung dieser einen Datenbank, kein paralleles Schema
mit eigener Wahrheit.

Offen ist, wie Verträge versioniert werden, wie lange eine alte Fassung gilt und
welches Verfahren eine Datenbankänderung ausrollt. Alembic im Skelett ist nicht
diese Strategie. [ADR-0002](0002-python-fastapi.md) entscheidet den Stack, nicht
die Kompatibilität.

### Ist-Stand

- Das Skelett (GF-006) hat eine Alembic-Revision, die `schema_meta` anlegt.
  GF-008 legt zusätzlich die Tabelle `credentials` an. Das Upgrade fügt nur
  diese Tabelle hinzu und lässt `schema_meta` unverändert. Die
  Kompatibilitätsstrategie dieses ADR bleibt davon unberührt.
  `migrations/env.py` setzt weder `lock_timeout` noch `statement_timeout`.
  `tests/test_migration.py` prüft `upgrade head` und dass `credentials`
  additiv ist und auf Revision `0001` zurückgenommen werden kann.
- Migrationen laufen beim Start des Containers nicht (Dockerfile `CMD`).
- [../API_SPECIFICATION.md](../API_SPECIFICATION.md): Pfadpräfix `/v1`, eine
  inkompatible Änderung heißt `/v2`. Innerhalb von `/v1` kommen nur optionale
  Felder hinzu. CI prüft die OpenAPI-Datei auf Gültigkeit, nicht auf Breaking Changes.
- Die Railway-Umgebung `staging` ([ADR-0005](0005-railway-environments.md))
  deployt jeden Commit auf `main` automatisch, ohne auf CI zu warten. Kein
  Pre-Deploy-Command, kein Healthcheck-Pfad, keine Overlap-Einstellung (gelesen
  am 2026-11-10). Ob `schema_meta` in `staging` angelegt ist, ist NICHT VERIFIZIERT.

### Fakten aus Primärquellen

- Parallel Change (Expand/Contract) zerlegt eine inkompatible Änderung in
  expand, migrate und contract.
  ([Fowler: ParallelChange](https://martinfowler.com/bliki/ParallelChange.html))
- Alembic Autogenerate erkennt keine Umbenennungen und nicht alle Constraints.
  Kandidaten sind manuell zu prüfen.
  ([Alembic Autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html))
  DDL außerhalb einer Transaktion geht mit `autocommit_block()`
  ([Alembic Runtime](https://alembic.sqlalchemy.org/en/latest/api/runtime.html)).
- `CREATE INDEX CONCURRENTLY` darf nicht in einem Transaktionsblock laufen.
  ([PostgreSQL CREATE INDEX](https://www.postgresql.org/docs/current/sql-createindex.html))
  `lock_timeout` ist standardmäßig aus.
  ([PostgreSQL Client Config](https://www.postgresql.org/docs/current/runtime-config-client.html))
  `ADD CONSTRAINT … NOT VALID` überspringt den Scan bestehender Zeilen.
  ([PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html))
- Railway Pre-Deploy-Command: eigener Container zwischen Build und Deploy, kein
  Retry, standardmäßig ohne Zeitlimit, Timeout von 1 bis 3600 s einstellbar.
  ([Railway Pre-Deploy](https://docs.railway.com/deployments/pre-deploy-command))
- Railway Healthcheck schaltet erst nach einer 2xx-Antwort um (Default 300 s).
  ([Railway Healthchecks](https://docs.railway.com/deployments/healthchecks))
  Overlap und Draining sind einstellbar.
  ([Railway Teardown](https://docs.railway.com/deployments/deployment-teardown))
- Railway „Wait for CI“ hält Deployments, bis die Workflows fertig sind. Für
  Pflichtschritte wie Migrationen rät Railway, sich nicht allein darauf zu verlassen.
  ([Railway Autodeploys](https://docs.railway.com/deployments/github-autodeploys))
- Ein Railway-Rollback stellt Image und Variablen wieder her, nicht die Datenbank.
  ([Railway Deployment Actions](https://docs.railway.com/deployments/deployment-actions))
- `Deprecation`-Header ([RFC 9745](https://www.rfc-editor.org/rfc/rfc9745)) und
  `Sunset`-Header ([RFC 8594](https://www.rfc-editor.org/rfc/rfc8594)). Der
  Sunset-Zeitpunkt darf nicht vor dem Deprecation-Zeitpunkt liegen.
- oasdiff meldet Breaking Changes zwischen zwei OpenAPI-Fassungen als ERR oder WARN.
  ([oasdiff](https://github.com/oasdiff/oasdiff))

### Annahmen (getrennt von den Fakten)

- A1: Railway läuft im Plan Free (höchstens 1 Replica je Service, Image-Retention
  24 h laut [Railway Plans](https://docs.railway.com/pricing/plans)). Übermittelt
  vom Head of Engineering, vom CEO nicht bestätigt. NICHT VERIFIZIERT. Ob Overlap
  mit dem Replica-Limit des Plans Free funktioniert, ist NICHT VERIFIZIERT.
- A2: Kurze Downtime bei Schemaänderungen ist in V1 tragbar. NICHT VERIFIZIERT.

## Entscheidung

Nicht entschieden. Die Strategie für API-Versionierung, Datenbankmigration und Kompatibilität ist offen.

Das Skelett (GF-006) nutzt Alembic, um die Infrastrukturtabelle `schema_meta`
anzulegen. Das wählt keine Kompatibilitätsstrategie. Ein Domänenschema bleibt
unzulässig, bis dieses ADR entschieden ist.

### Vorschlag zur Prüfung (keine Entscheidung)

1. Datenbank: nur Expand/Contract. Jede Revision ist mit der vorherigen
   Anwendungsversion kompatibel. Roll-forward-only: Eine gescheiterte Änderung
   wird durch eine neue Revision behoben. Datenverlust behebt nur ein Restore
   ([ADR-0006](0006-backup-retention-rpo-rto.md)).
2. Ausführung: `alembic upgrade head` als Railway-Pre-Deploy-Command mit
   gesetztem Timeout. In jeder Migration gilt ein `lock_timeout`. Indizes werden
   per `CONCURRENTLY` im `autocommit_block()` angelegt, Constraints mit
   `NOT VALID` und späterer Validierung. Wer eine Migration auslösen darf, regelt
   [ADR-0011](0011-release-rollback-authority.md).
3. Umschalten: Healthcheck-Pfad `/ready`, dazu Overlap und Draining, soweit der
   Plan es erlaubt (A1).
4. API: Bei `/v1` und `/v2` bleibt es. Eine abgelöste Fassung sendet
   `Deprecation` und `Sunset`. Die Frist bis zum Sunset ist ein Kandidat, z. B.
   mindestens 90 Tage, keine Entscheidung.
5. CI: oasdiff als gepinntes CLI vergleicht `api/openapi.yaml` mit `main`. ERR
   blockiert. Es werden keine Daten an externe Dienste hochgeladen.
6. Tests: Ein Test prüft die vorherige Anwendungsversion gegen das neue Schema.

### Zu klären

- ob Migrationen automatisch per Pre-Deploy laufen dürfen oder nur nach Freigabe ([ADR-0011](0011-release-rollback-authority.md))
- wie lange eine abgelöste API-Fassung weiterläuft und wer den Sunset-Termin setzt
- ob Roll-forward-only plus Restore genügt oder getestete Downgrades verlangt werden
- ob in V1 kurze Downtime tragbar ist (A2)
- Obergrenzen für `lock_timeout` und den Pre-Deploy-Timeout

## Konsequenzen

- `schema_meta` ist ein Infrastrukturmarker der einen Datenbank, kein fachlicher Vertrag.
- Ein Domänenschema oder ein zweites Migrationswerkzeug neben dem Skelett ist ohne dieses ADR nicht zulässig.
- Kompatibilität ist eine Eigenschaft des Vertrags, nicht ein Verhalten, das jeder Client für sich definiert.
- Wird der Vorschlag angenommen: Ein App-Rollback
  ([ADR-0011](0011-release-rollback-authority.md)) bleibt sicher, weil die
  Vorversion zum aktuellen Schema passt. Während Overlap laufen alte und neue
  Version kurz parallel gegen dieselbe Datenbank. Das ist kein zweiter
  Eigentümer, verlangt aber datenbankseitige Absicherung der Zuweisungen
  ([ADR-0003](0003-single-assignment-authority.md)).

## Alternativen

| Option | Vorteil | Nachteil |
| --- | --- | --- |
| Expand/Contract, Roll-forward-only (Vorschlag) | Rollback der App sicher, keine Downgrade-Pflege | mehr Schritte je Änderung |
| Downgrade-Skripte je Revision | scheinbar einfacher Rückweg | Datenverlust bei Drop, selten getestet |
| Migration beim Containerstart | keine Plattformfunktion nötig | jede Replica migriert, Abbruch blockiert den Start |
| API-Version per Header statt Pfad | feinere Steuerung | widerspricht dem bestehenden `/v1`-Vertrag |

## Bezug

- [ADR-0001](0001-postgresql-on-railway.md)
- [ADR-0002](0002-python-fastapi.md)
- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0005](0005-railway-environments.md)
- [ADR-0006](0006-backup-retention-rpo-rto.md)
- [ADR-0010](0010-slo-alerting-incident.md)
- [ADR-0011](0011-release-rollback-authority.md)
