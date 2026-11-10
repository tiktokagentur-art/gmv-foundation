# ADR-0004: Branch Protection und CODEOWNERS

- Status: Accepted
- Datum: 2026-11-10
- Entscheider: CEO

## Kontext

[../../CONTRIBUTING.md](../../CONTRIBUTING.md) verlangt: kein direkter Push auf
`main`, Pull Request, mindestens eine unabhängige Freigabe, keine Freigabe der
eigenen Änderung, keine Ausnahme für Administratoren. CI ist in
[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) vorhanden.

[`.github/CODEOWNERS`](../../.github/CODEOWNERS) ist ein Entwurf ohne aktive
Owner. Die klassische Branch-Protection-API für `main` liefert keinen Schutz
(HTTP 404). Der technische Schutz liegt auf einem Repository-Ruleset.

Die CEO-Entscheidung vom 10.11.2026 nimmt den an diesem Tag gelesenen Ist-Stand
an. Dieses ADR ändert keine Repository-Einstellungen; es dokumentiert sie.

## Entscheidung

Entschieden. Der Default-Branch `main` wird durch das aktive Repository-Ruleset `main` (ID 26896505) geschützt.

Gültig ist der folgende Ist-Stand, gelesen am 10.11.2026:

- Löschen des Branches und Non-Fast-Forward (Force-Push) sind untersagt.
- Änderungen an `main` nur über Pull Request. Die Zahl der erforderlichen
  Approvals ist 0. Ein Code-Owner-Review ist nicht vorgeschrieben.
  `require_last_push_approval` ist aus.
  `require_extra_approval_for_unattributed_changes` ist an. Zulässige
  Merge-Methoden sind merge, squash und rebase.
- Erforderliche Status-Checks mit strikter Prüfung gegen den aktuellen Head:
  `Lint and structure`, `Backend`, `Image`.
- `bypass_actors` ist leer. Die lesende Identität kann das Ruleset nicht
  umgehen (`current_user_can_bypass: never`).
- [`.github/CODEOWNERS`](../../.github/CODEOWNERS) bleibt Entwurf ohne aktive
  Owner.

GitHub Moderator V1 darf den Sollzustand dieses Rulesets per APPLY schreiben.
Der erfolgreiche APPLY-Lauf 42747852555 am 10.11.2026 bezog den Token über eine
GitHub App (`TOKEN_SOURCE: github-app`). Der anschließende Audit-Lauf
42748296837 meldete den Zustand `aligned`.

Die Environments `github-moderator-apply` und `github-moderator-privileged`
haben `can_admins_bypass: false`. Die Repository-Variable und das
Repository-Secret `GMV_MODERATOR_APPLY_GATE` sind nicht vorhanden.

## Konsequenzen

- Direkter Push und Force-Push auf `main` werden technisch blockiert.
- Ein Merge ohne die drei erforderlichen, aktuellen Checks ist unzulässig.
- [../../CONTRIBUTING.md](../../CONTRIBUTING.md) verlangt weiterhin eine
  unabhängige Review. Das Ruleset erzwingt derzeit keine Approval-Zahl größer
  0. Diese Abweichung ist festgestellt, nicht stillschweigend aufgehoben.
- Aktive CODEOWNERS-Regeln bleiben aus, bis ein späterer Entscheid reale Teams
  einträgt und dieses ADR anpasst.
- Eine numerische GitHub-App-ID und ein öffentlicher App-Slug sind hier nicht
  festgehalten, weil sie über die verfügbare API nicht verifiziert wurden.

## Alternativen

Nicht in diesem ADR neu bewertet. Der Entscheid dokumentiert den gelesenen
Ist-Stand vom 10.11.2026. Eine Änderung der Checks, der Approval-Zahl oder der
CODEOWNERS-Wirkung braucht ein neues oder angepasstes ADR.

## Bezug

- [../../CONTRIBUTING.md](../../CONTRIBUTING.md)
- [../GOVERNANCE.md](../GOVERNANCE.md)
- [../github-moderator.md](../github-moderator.md)
- [ADR-0013](0013-repository-visibility-public.md)
