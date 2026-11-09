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

In dieser Baseline wird kein Secret gebraucht. Es gibt keinen laufenden Dienst.

## Entscheidung

Nicht entschieden. Secret-Provider, Rotationsfrist und Break-glass-Verfahren sind offen.

Zu klären ist mindestens:

- welcher Provider Werte für welche Umgebung hält
- welche Identität Werte lesen darf und welche sie ändern darf
- Rotationsfrist und Auslöser einer außerplanmäßigen Rotation
- wer einen Break-glass-Zugang auslösen darf, wie lange er gilt und wo das Ereignis auditiert wird
- wie ein kompromittierter Wert widerrufen wird, ohne ihn ins Repository zu schreiben

## Konsequenzen

- Bis zum Entscheid wird kein Provider als bereits gewählt genannt und keiner im Repository konfiguriert.
- Ein Break-glass-Weg, der nicht auditierbar ist oder ein gemeinsames Dauergeheimnis verteilt, widerspricht SECURITY.md und wird nicht ergänzt, um die Lücke zu füllen.
- Beispiele bleiben ohne verwendbare Werte.

## Alternativen

Nicht bewertet. Weder der Secret-Store der Plattform noch ein externer Provider
ist vorausgewählt.

## Bezug

- [../../SECURITY.md](../../SECURITY.md)
- [ADR-0005](0005-railway-environments.md)
- [ADR-0008](0008-auth-standard.md)
