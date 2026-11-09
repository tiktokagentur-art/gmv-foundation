# ADR-0004: Branch Protection und CODEOWNERS

- Status: Proposed
- Datum: 2026-11-09
- Entscheider: offen

## Kontext

[../../CONTRIBUTING.md](../../CONTRIBUTING.md) verlangt: kein direkter Push auf
`main`, Pull Request, mindestens eine unabhängige Freigabe, keine Freigabe der
eigenen Änderung, keine Ausnahme für Administratoren. CI ist in
[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) vorhanden.

[`.github/CODEOWNERS`](../../.github/CODEOWNERS) ist ein Entwurf ohne aktive
Owner, damit nicht versehentlich ein Team gebunden wird, das es noch nicht gibt.
Ob auf `main` bereits Branch Protection oder ein Regelwerk der Organisation
liegt, stellt dieses ADR nicht fest. Es liest die Einstellung nicht.

Diese Baseline ändert keine Repository-Einstellungen. Ein späteres Einschalten
ist ein separater Schritt nach diesem Entscheid, nicht Teil des
Dokumentations-Pull-Requests.

## Entscheidung

Nicht entschieden. Wie Branch Protection, erforderliche Checks und CODEOWNERS technisch eingeschaltet werden, ist offen.

Zu klären ist mindestens:

- geschützte Branches, mindestens `main`
- Anzahl der Freigaben und Durchsetzung der unabhängigen Review, auch für Personen mit eigenem Commit an der Änderung
- Verbot von Self-Approval und von direkten Pushes, einschließlich Force-Push
- ob Administratoren die Regeln umgehen dürfen (die schriftliche Regel sagt nein)
- erforderlicher Status-Check aus `.github/workflows/ci.yml`, Job `lint-and-structure`
- ob Reviews von Code Owners Pflicht werden, und welche realen Teams dann in CODEOWNERS stehen
- Merge-Strategie (Merge-Commit, Squash oder Rebase)

## Konsequenzen

- Bis zum Entscheid bleibt der Schutz eine Arbeitsregel. Ein direkter Push auf `main` verstößt gegen [../../CONTRIBUTING.md](../../CONTRIBUTING.md). Ob GitHub ihn zusätzlich blockiert, ist nicht festgestellt.
- CODEOWNERS erhält keine aktiven Owner, solange dieses ADR `Proposed` ist. Die Strukturprüfung wacht darüber.
- Ein annehmender Pull Request dokumentiert die gewählten Einstellungen. Die Einstellungen selbst werden erst danach gesetzt, in einem Schritt, der als Repository-Änderung sichtbar ist.

## Alternativen

Nicht bewertet. Die schriftlichen Beitragsregeln stehen fest. Offen ist nur
ihre technische Durchsetzung.

## Bezug

- [../../CONTRIBUTING.md](../../CONTRIBUTING.md)
- [../GOVERNANCE.md](../GOVERNANCE.md)
