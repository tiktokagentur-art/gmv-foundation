# ADR-0002: Python / FastAPI

- Status: Accepted
- Datum: 2026-11-09
- Entscheider: CEO

## Kontext

Der Control-Plane-Dienst braucht eine Implementierungssprache und ein
HTTP-Framework. Dafür lag der Vorschlag Python und FastAPI vor.

GF-006 hat darauf ein Skelett gebaut: FastAPI, Konfiguration nur aus
Umgebungsvariablen, SQLAlchemy 2 und Alembic. Das Skelett hat den Vorschlag
prüfbar gemacht. Angenommen hat ihn die CEO-Entscheidung vom 09.11.2026.

[ADR-0001](0001-postgresql-on-railway.md) bleibt unabhängig davon gültig.

## Entscheidung

Entschieden. Python und FastAPI sind der Stack für den Control-Plane-Dienst.

Die CEO hat das am 09.11.2026 entschieden. Authentisierung und Betrieb sind
damit nicht gewählt.

## Konsequenzen

- Das Skelett aus GF-006 steht auf dem beschlossenen Stack.
- Domänenmodelle, Authentisierung und ein Deployment folgen aus diesem ADR nicht.
- Eine andere Sprache oder ein anderes Framework braucht ein neues ADR, das dieses auf `Superseded` setzt.
- [ADR-0003](0003-single-assignment-authority.md) und [../../SECURITY.md](../../SECURITY.md) gelten unabhängig von der Sprache.

## Alternativen

Nicht in diesem ADR verglichen. Der Entscheid der CEO vom 09.11.2026 wird
dokumentiert. Eine Auswahlliste wird nicht nachträglich behauptet.

## Bezug

- [ADR-0001](0001-postgresql-on-railway.md)
- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0008](0008-auth-standard.md)
- [ADR-0009](0009-migration-compatibility.md)
