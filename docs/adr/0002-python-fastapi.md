# ADR-0002: Python / FastAPI

- Status: Proposed
- Datum: 2026-11-09
- Entscheider: offen

## Kontext

Der Control-Plane-Dienst braucht später eine Implementierungssprache und ein
HTTP-Framework. Dafür liegt ein Vorschlag vor: Python und FastAPI.

Der Vorschlag ist nicht final. Die CEO-Entscheidung vom 09.11.2026 legt das
Programm und PostgreSQL auf Railway fest, nicht den Anwendungstack.
[ADR-0001](0001-postgresql-on-railway.md) ist davon unabhängig: die Datenbank
gilt auch, wenn dieser Vorschlag abgelehnt wird.

In `app/` liegt bewusst kein Code. Ein Framework im Repository wäre ein
vorweggenommener Beschluss.

## Entscheidung

Nicht entschieden. Python und FastAPI sind der Vorschlag für den Control-Plane-Dienst, nicht der Beschluss.

Der Vorschlag umfasst die Sprache Python und FastAPI als HTTP-Schicht der
Control Plane, einschließlich der Grenze zu den Workern. Er wählt keine
Bibliothek für Migrationen, keine Authentisierung und keinen Betrieb.

## Konsequenzen

- Solange der Status `Proposed` ist, wird kein Anwendungscode und keine Laufzeitabhängigkeit hinzugefügt.
- Ein annehmender Pull Request setzt den Status auf `Accepted`, nennt die entscheidende Rolle und hält fest, welche Alternativen verglichen wurden.
- Eine Ablehnung setzt den Status auf `Rejected` oder ersetzt dieses ADR. Beides ist ein eigener Pull Request.
- [ADR-0003](0003-single-assignment-authority.md) und [../../SECURITY.md](../../SECURITY.md) gelten unabhängig von der Sprache.

## Alternativen

Nicht verglichen. Andere Sprachen und Frameworks bleiben möglich.
Ein Vergleich wäre Teil eines annehmenden Pull Requests, nicht dieser Baseline.
Namen von Alternativen werden hier nicht als Auswahlliste geführt.

## Bezug

- [ADR-0001](0001-postgresql-on-railway.md)
- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0008](0008-auth-standard.md)
- [ADR-0009](0009-migration-compatibility.md)
