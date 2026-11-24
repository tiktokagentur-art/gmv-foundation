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

Historischer Ist-Snapshot vom 10.11.2026 (heute nicht mehr aktuell):

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
- Zum Snapshot vom 10.11.2026 verlangten [../../CONTRIBUTING.md](../../CONTRIBUTING.md)
  und das Ruleset 0 Approvals; der Live-Readback vom 24.11.2026 weicht davon ab
  und ist unten dokumentiert. Die drei erforderlichen, aktuellen Checks bleiben
  Merge-Voraussetzung. Quelle des historischen Beschlusses: CEO-Auswahl im Chat
  des Head of Engineering, 10.11.2026 05:49 MEZ.
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


## Live Ruleset Readback und Review Governance V2 — 24.11.2026

Die frühere Konfiguration oben ist der am 10.11.2026 dokumentierte Snapshot. Ein
direkter Readback der GitHub Ruleset API am 24.11.2026 zeigt den aktuellen
Istzustand von Ruleset `main` (ID `26896505`):

- Ruleset aktiv, Zielbranch `main`; Pull Request erforderlich.
- Required Approvals: **1**; veraltete Approvals nach neuen Commits verwerfen: **an**.
- Approval des letzten reviewbaren Pushes: **an**; Code-Owner-Review: **aus**.
- Zusätzliche Approval-Regel für nicht zugeordnete Copilot-PRs: **an**.
- Strikte erforderliche Status-Checks: `Lint and structure`, `Backend`,
  `Image`.
- Branch-Löschung und Non-Fast-Forward/Force-Push sind gesperrt.
- Bypass-Liste ist leer; `current_user_can_bypass` ist `never`.
- Die Branch-Einstellungsseite zeigte keine klassische Branch-Protection-Regel.
  Das Repository liegt im persönlichen Account; eine Organisations-Policy ist
  daher keine übergeordnete Regel für dieses Repository.

Die CEO-Entscheidung **Review Governance V2** vom 24.11.2026 setzt als Ziel
`required_approving_review_count=0` und
`require_last_push_approval=false`. PR-Pflicht, die drei strikten Checks,
Force-Push-Sperre, Löschsperre und leerer Bypass bleiben erhalten.
Hochrisiko-Änderungen bleiben risikobasiert review- und freigabepflichtig;
pauschales Auto-Merge ist ausgeschlossen.

**Der Zielzustand ist noch nicht aktiviert.** Vor einer Ruleset-Änderung muss ein
verbindliches automatisiertes Codex-Review- und Risikogate nachweislich aktiv
sein und mit Negativfällen blockieren. Am 24.11.2026 war kein solches Gate auf
`main` belegt: automatische Copilot-Review-Anforderung im Ruleset ist aus;
PR #36 ist ein Draft mit beratender PR-Triage. Das erforderliche Review-Gate
und der Risikogate-Nachweis sind in #35 fortzuführen. Bis zum Gate-Nachweis
bleibt das Ruleset bei 1 Approval. Diese Notiz dokumentiert den Istzustand und
den gesperrten Zielzustand; sie selbst ändert keine GitHub-Einstellung.

Quelle: [Ruleset 26896505](https://github.com/tiktokagentur-art/gmv-foundation/rules/26896505),
[Workflow CI](https://github.com/tiktokagentur-art/gmv-foundation/blob/main/.github/workflows/ci.yml),
[Review-Automation #35](https://github.com/tiktokagentur-art/gmv-foundation/issues/35),
[PR-Triage Draft #36](https://github.com/tiktokagentur-art/gmv-foundation/pull/36),
[CEO-Auftrag #80](https://github.com/tiktokagentur-art/gmv-foundation/issues/80).

**Rückrollgrundlage:** Vorherige Ruleset-Konfiguration vom 24.11.2026:
1 Required Approval; stale approvals an; last-push approval an; Code-Owner-Review
aus; Copilot-unattributed approval an; PR erforderlich; die drei oben genannten
Checks strict; Branch deletion und non-fast-forward gesperrt; Bypass leer.
