# ADR-0014: GitHub Moderator V1, Betriebsmodi und Credential-Isolation

- Status: Accepted
- Datum: 2026-11-10
- Entscheider: CEO

## Kontext

PR [#5](https://github.com/tiktokagentur-art/gmv-foundation/pull/5) hat den
GitHub Moderator V1 auf `main` gebracht: einen Actions-Workflow mit den
Modi AUDIT, DRY_RUN und APPLY sowie einer Trust-Boundary für privilegierte
Zugangsdaten. Der Pull Request nannte ausdrücklich kein ADR
(„ADR: keins“; ADR-0004 war damals `Proposed`).

[ADR-0004](0004-branch-protection-codeowners.md) ist seit PR
[#9](https://github.com/tiktokagentur-art/gmv-foundation/pull/9)
(Merge `230c07b`) `Accepted`. Es dokumentiert den Ruleset-Ist-Stand für
`main` und hält fest, dass der Moderator den Sollzustand dieses Rulesets
per APPLY schreiben darf, einschließlich der gelesenen APPLY- und
Audit-Läufe sowie der Environment-Einstellung `can_admins_bypass: false`.
Diese Punkte sind damit entschieden.

Nicht Teil von ADR-0004 und nicht Teil von
[ADR-0005](0005-railway-environments.md) (Railway-Umgebungen) sind die
Betriebsmodi und die Credential-Isolation selbst. Sie stehen in
[../github-moderator.md](../github-moderator.md) als Beschreibung der
Implementierung. Eine Beschreibung im Betriebsdokument ist kein
angenommener ADR-Entscheid.

In diesem ADR stehen keine App-ID, kein App-Slug und keine Secret-Werte.

## Entscheidung

Entschieden. Die Betriebsmodi AUDIT, DRY_RUN und APPLY und die
Credential-Isolation des GitHub Moderators V1 gelten als verbindliche Regel.

- AUDIT ist der Standardmodus und führt keine Schreiboperation aus.
- DRY_RUN zeigt geplante Änderungen nur an und schreibt nicht.
- APPLY schreibt nur nach expliziter Freigabe (Lauf von `main`,
  Environment-Freigabe, Apply-Gate), nicht schon durch die Wahl eines
  Workflow-Parameters.
- `pull_request`-Läufe, einschließlich Same-Repo-PRs, erhalten keine
  privilegierten Zugangsdaten.
- Privilege wird über das Workflow-Ereignis entschieden, nicht über
  ausgecheckten PR-Code.
- `pull_request_target` ist unzulässig.
- Tokens werden nicht in Ausgaben, Logs oder Artefakte geschrieben.
- Der App-Schlüssel liegt nur als Environment-Secret, nicht als
  Repository-Secret.

Quelle: CEO-Auswahl im Chat des Head of Engineering, 10.11.2026 05:49 MEZ.

Tatsache, nicht Annahme: Die Implementierung und die Beschreibung in
`docs/github-moderator.md` liegen auf `main`. Annahme, nicht Tatsache:
Dass der vorliegende Code unverändert die endgültige Regel bleibt.

## Konsequenzen

- Die in PR #5 gemergte Implementierung ist der angenommene
  Architekturentscheid für Modi und Credential-Isolation, soweit sie diesen
  Regeln entspricht.
- ADR-0004 bleibt gültig für den Ruleset-Schutz und für die Feststellung,
  dass der Moderator den Sollzustand per APPLY schreiben darf.
- Dieses ADR setzt keine Secrets und nennt keine App-ID.

## Alternativen

Nicht bewertet. Es wird kein anderer Moderator-Zuschnitt als stiller
Default eingeführt.

## Bezug

- [ADR-0004](0004-branch-protection-codeowners.md)
- [ADR-0005](0005-railway-environments.md)
- [../github-moderator.md](../github-moderator.md)
- [../../SECURITY.md](../../SECURITY.md)
- PR [#5](https://github.com/tiktokagentur-art/gmv-foundation/pull/5)
- PR [#9](https://github.com/tiktokagentur-art/gmv-foundation/pull/9)
