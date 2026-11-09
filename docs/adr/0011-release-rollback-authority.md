# ADR-0011: Release- und Rollback-Autorität

- Status: Proposed
- Datum: 2026-11-09
- Entscheider: offen

## Kontext

Die Software Factory führt Änderungen über Test, CI, Pull Request und
unabhängige Review. [../ARCHITECTURE.md](../ARCHITECTURE.md) hält fest: ein
Merge nach `main` ist noch kein Produktionsrelease.

Offen ist, welche Rolle ein Release in Produktion auslösen darf und welche
Rolle einen Rollback auslösen darf. Das können verschiedene Rollen sein.
Sie sind nicht besetzt. Eine Person wird hier nicht genannt, weil keine
benannt entschieden wurde.

Es gibt kein Deployment in diesem Repository.

## Entscheidung

Nicht entschieden. Wer ein Produktionsrelease und wer einen Rollback auslösen darf, ist offen.

Zu klären ist mindestens:

- ob Release und Rollback dieselbe Rolle sind
- ob die Rolle von der Review-Freigabe getrennt ist
- welcher Nachweis vor einem Release vorliegt (CI, Review, und die dann geltenden ADR-0006 und ADR-0010)
- wie ein Rollback ausgelöst wird, ohne eine zweite schreibende Instanz zu erzeugen
- wo Release und Rollback im Audit-Trail sichtbar werden

## Konsequenzen

- Ein Merge darf nicht als Produktionsfreigabe gelesen werden.
- Es wird keine Pipeline angelegt, die bei Merge deployt.
- Die unabhängige Review aus [../../CONTRIBUTING.md](../../CONTRIBUTING.md) bleibt bestehen. Sie allein beantwortet dieses ADR nicht.
- Ein Rollback ist eine Entscheidung der dafür vorgesehenen Rolle, kein stilles Überschreiben durch einen Worker.

## Alternativen

Nicht bewertet. Automatisches Deploy bei Merge wäre bereits eine Wahl der
Autorität und ist deshalb nicht der Default.

## Bezug

- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0004](0004-branch-protection-codeowners.md)
- [ADR-0006](0006-backup-retention-rpo-rto.md)
- [ADR-0010](0010-slo-alerting-incident.md)
- [../../CONTRIBUTING.md](../../CONTRIBUTING.md)
