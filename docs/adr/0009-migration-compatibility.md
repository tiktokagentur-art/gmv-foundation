# ADR-0009: Migration und Kompatibilität

- Status: Proposed
- Datum: 2026-11-09
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

## Entscheidung

Nicht entschieden. Die Strategie für API-Versionierung, Datenbankmigration und Kompatibilität ist offen.

Das Skelett (GF-006) nutzt Alembic, um die Infrastrukturtabelle `schema_meta`
anzulegen. Das wählt keine Kompatibilitätsstrategie. Ein Domänenschema bleibt
unzulässig, bis dieses ADR entschieden ist.

Zu klären ist mindestens:

- wie lange eine abgelöste API-Fassung gilt, über die V1-Regel hinaus
- in welcher Reihenfolge Schema und Anwendung wechseln, ohne zwei Schreiber zu erzeugen
- wie eine gescheiterte Migration zurückgenommen wird
- ob Alembic das Werkzeug bleibt. Der Stack ist in [ADR-0002](0002-python-fastapi.md) entschieden

## Konsequenzen

- `schema_meta` ist ein Infrastrukturmarker der einen Datenbank, kein fachlicher Vertrag.
- Ein Domänenschema oder ein zweites Migrationswerkzeug neben dem Skelett ist ohne dieses ADR nicht zulässig.
- Kompatibilität ist eine Eigenschaft des Vertrags, nicht ein Verhalten, das jeder Client für sich definiert.

## Alternativen

Nicht bewertet. Expand/Contract, Versionspräfixe und einzelne Werkzeuge sind
mögliche spätere Antworten, hier aber keine Auswahl.

## Bezug

- [ADR-0001](0001-postgresql-on-railway.md)
- [ADR-0002](0002-python-fastapi.md)
- [ADR-0003](0003-single-assignment-authority.md)
