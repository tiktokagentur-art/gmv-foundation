# ADR-0007: Secret-Verwaltung, Rotation, Break-glass

- Status: Proposed
- Datum: 2026-11-09
- Entscheider: offen

## Kontext

[../../SECURITY.md](../../SECURITY.md) verbietet Secrets in Git, Logs, Beispielen
und CI-Ausgaben. Jeder Dienst und jeder Worker hat eine eigene Identität.
Rechte sind auf die Aufgabe begrenzt.

Offen ist, welcher Secret-Provider die Werte hält, wie oft sie rotiert werden
und wie ein Break-glass-Zugang aussieht. Break-glass meint einen kontrollierten
Notfallzugriff: personengebunden, zeitlich begrenzt und im Audit-Trail sichtbar.
Das Verfahren selbst ist nicht beschrieben und nicht entschieden.

In `staging` laufen die Dienste `backend` und Postgres (Railway-Readback am
10.11.2026, Europe/Berlin). Der Dienst `backend` hat die Variable
`DATABASE_URL` (nur der Name; der Wert steht nicht in diesem Repository).
Laut [ADR-0004](0004-branch-protection-codeowners.md) bezog ein APPLY-Lauf
des GitHub Moderators V1 den Token über eine GitHub App. Ob in den
Environments `github-moderator-apply` und `github-moderator-privileged`
Environment-Secrets liegen, ist NICHT VERIFIZIERT. Welcher Secret-Provider
verbindlich gilt, ist nicht entschieden.

## Entscheidung

Nicht entschieden. Secret-Provider, Rotationsfrist und Break-glass-Verfahren sind offen.

Zu klären ist mindestens:

- welcher Provider Werte für welche Umgebung hält
- welche Identität Werte lesen darf und welche sie ändern darf
- Rotationsfrist und Auslöser einer außerplanmäßigen Rotation
- wer einen Break-glass-Zugang auslösen darf, wie lange er gilt und wo das Ereignis auditiert wird
- wie ein kompromittierter Wert widerrufen wird, ohne ihn ins Repository zu schreiben

## Konsequenzen

- Bis zum Entscheid wird kein Secret-Provider als bereits gewählt genannt.
  Die Railway-Variable `DATABASE_URL` (nur der Name) ist vorgefunden, nicht
  durch dieses ADR ausgewählt. In diesem Repository liegen keine Secret-Werte.
- Ein Break-glass-Weg, der nicht auditierbar ist oder ein gemeinsames Dauergeheimnis verteilt, widerspricht SECURITY.md und wird nicht ergänzt, um die Lücke zu füllen.
- Beispiele bleiben ohne verwendbare Werte.

## Alternativen

Nicht bewertet. Weder der Secret-Store der Plattform noch ein externer Provider
ist vorausgewählt.

## Bezug

- [../../SECURITY.md](../../SECURITY.md)
- [ADR-0004](0004-branch-protection-codeowners.md)
- [ADR-0005](0005-railway-environments.md)
- [ADR-0006](0006-backup-retention-rpo-rto.md)
- [ADR-0008](0008-auth-standard.md)
- [ADR-0011](0011-release-rollback-authority.md)
- [ADR-0013](0013-repository-visibility-public.md)
