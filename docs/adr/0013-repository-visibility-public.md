# ADR-0013: Repository-Sichtbarkeit: public

- Status: Accepted
- Datum: 2026-11-10
- Entscheider: CEO

## Kontext

Der Plan „GMV Greenfield V1 – Implementierungsplanung“ empfahl für
`tiktokagentur-art/gmv-foundation` ein privates Repository. Das Repository ist
seit seiner Anlage öffentlich. README, [../../SECURITY.md](../../SECURITY.md),
[../../CONTRIBUTING.md](../../CONTRIBUTING.md) und [../GOVERNANCE.md](../GOVERNANCE.md)
gehen bereits davon aus.

Die CEO-Entscheidung vom 10.11.2026 legt fest, dass das Repository öffentlich bleibt.

Nicht mitentschieden werden Branch Protection und CODEOWNERS
([ADR-0004](0004-branch-protection-codeowners.md)) sowie Railway-Umgebungen
([ADR-0005](0005-railway-environments.md)). Dieses ADR ändert keine
Repository-Einstellung.

## Entscheidung

Entschieden. Das Repository tiktokagentur-art/gmv-foundation ist öffentlich (public) und bleibt es.

Die Empfehlung „privat“ aus dem Plan gilt nicht mehr. Eine Änderung der
Sichtbarkeit braucht ein neues ADR, das dieses auf `Superseded` setzt.

## Konsequenzen

- Keine Secrets, Credentials, Verbindungszeichenfolgen und keine Kundendaten oder personenbezogenen Daten im Repository, in Issues, Pull Requests, Logs oder CI-Ausgaben ([../../SECURITY.md](../../SECURITY.md)).
- Keine internen Infrastrukturdetails mit Sicherheitsrelevanz: keine internen Hostnamen, Kontonummern, Projekt-IDs, Zugangswege oder Netzwerkdetails.
- Secret Scanning und Push Protection bleiben aktiv. Sie sind ein Prüfpunkt für jede Review der Repository-Einstellungen. Am 10.11.2026 waren beide laut GitHub-API aktiv.
- Ein Secret, das trotzdem in die Historie gelangt, gilt als kompromittiert und wird rotiert. Löschen aus der Historie allein reicht nicht.
- Durchsetzung von Reviews und Checks bleibt Gegenstand von [ADR-0004](0004-branch-protection-codeowners.md).

## Alternativen

Nicht in diesem ADR neu bewertet. Ein privates Repository war im Plan empfohlen.
Der Entscheid der CEO vom 10.11.2026 wird dokumentiert.

## Bezug

- [../../SECURITY.md](../../SECURITY.md)
- [../../CONTRIBUTING.md](../../CONTRIBUTING.md)
- [../GOVERNANCE.md](../GOVERNANCE.md)
- [ADR-0004](0004-branch-protection-codeowners.md)
- [ADR-0007](0007-secret-management.md)
