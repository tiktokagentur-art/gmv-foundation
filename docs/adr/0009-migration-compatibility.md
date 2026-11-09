# ADR-0009: Migration und Kompatibilität

- Status: Proposed
- Datum: 2026-11-09
- Entscheider: offen

## Kontext

Daten- und API-Verträge gibt es noch nicht. [../ARCHITECTURE.md](../ARCHITECTURE.md)
reserviert sie für die Foundation: erst der Vertrag, dann die Umsetzung durch
die Infrastructure.

[ADR-0001](0001-postgresql-on-railway.md) legt eine PostgreSQL-Datenbank fest.
[ADR-0003](0003-single-assignment-authority.md) verbietet einen zweiten Eigentümer.
Eine Migration ist eine Änderung dieser einen Datenbank, kein paralleles Schema
mit eigener Wahrheit.

Offen ist, wie Verträge versioniert werden, wie lange eine alte Fassung gilt und
welches Verfahren eine Datenbankänderung ausrollt. Alembic im Skelett hängt am
Vorschlag [ADR-0002](0002-python-fastapi.md) und ist nicht diese Strategie.

## Entscheidung

Nicht entschieden. Die Strategie für API-Versionierung, Datenbankmigration und Kompatibilität ist offen.

Das Skelett (GF-006) nutzt Alembic, um die Infrastrukturtabelle `schema_meta`
anzulegen. Das wählt keine Kompatibilitätsstrategie und nimmt
[ADR-0002](0002-python-fastapi.md) nicht an. Ein Domänenschema bleibt
unzulässig, bis dieses ADR entschieden ist.

Zu klären ist mindestens:

- wo ein Vertrag im Repository liegt und wann er `Accepted` ist
- ob eine API-Fassung kompatibel erweitert oder explizit abgelöst wird, und wie lange die alte Fassung gilt
- in welcher Reihenfolge Schema und Anwendung wechseln, ohne zwei Schreiber zu erzeugen
- wie eine gescheiterte Migration zurückgenommen wird
- ob Alembic das Werkzeug bleibt, wenn der Backend-Vorschlag entschieden wird

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
