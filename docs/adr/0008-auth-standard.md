# ADR-0008: Authentisierungsstandard

- Status: Proposed
- Datum: 2026-11-09
- Entscheider: offen

## Kontext

[../../SECURITY.md](../../SECURITY.md) und [ADR-0003](0003-single-assignment-authority.md)
legen fest, was von einem Standard unabhängig schon gilt:

- eigene Identität je Dienst und je Worker
- Menschen und Workloads sind verschiedene Subjekte
- jede Zustandsänderung wird von der besitzenden Instanz autorisiert
- Anträge ohne passende Identität ändern nichts

Offen ist der Standard, mit dem eine Identität nachgewiesen wird. Ein Standard
wird nicht gewählt, indem ein Protokoll im ersten Dienst hart codiert wird.
[ADR-0002](0002-python-fastapi.md) ist der beschlossene Stack und liefert keine
Authentisierung mit.

## Entscheidung

Nicht entschieden. Der Authentisierungsstandard für Menschen und für Workloads ist offen.

Zu klären ist mindestens:

- Nachweis für Menschen und Nachweis für Dienste und Worker, getrennt
- Aussteller, Prüfer und Lebensdauer der Nachweise
- wo die Prüfung stattfindet (die besitzende Instanz bleibt autorisierend)
- wie ein Nachweis widerrufen wird
- was ein Worker vor der ersten Zuweisung vorzeigen muss

## Konsequenzen

- Es wird kein Token-Format, kein Aussteller und keine Bibliothek als Default eingeführt.
- Autorisierung bleibt serverseitig, auch nachdem ein Standard gewählt ist. Der Standard ersetzt die Assignment Authority nicht.
- Worker teilen sich keinen Nachweis.

## Alternativen

Nicht bewertet. Konkrete Protokolle werden hier nicht als Shortlist genannt,
damit die Nennung nicht wie eine Vorauswahl wirkt.

## Bezug

- [ADR-0002](0002-python-fastapi.md)
- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0007](0007-secret-management.md)
- [../../SECURITY.md](../../SECURITY.md)
