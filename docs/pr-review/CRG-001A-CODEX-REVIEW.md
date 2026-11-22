# CRG-001A: Codex Code Review – Integrationsvertrag V1

Status: Implementierungskandidat auf separatem Branch, **keine Produktionsaktivierung**.

## Zweck und Abhängigkeiten

OpenAI Codex Code Review übernimmt die standardmäßige **technische Sichtprüfung**
von GitHub-Pull-Requests. Es ersetzt weder CI noch formale GitHub-Approvals,
Sicherheitsfreigaben oder die Autorität der GMVGANG Control Plane.

Dieser PR baut auf dem `AGENTS.md`-Entwurf in PR #30 auf (Stacked PR).
Die Risikoklassen R0–R4 beziehen sich auf den **nicht gemergten**
APR-005A-Entwurf in PR #62. Hier wird **kein zweiter Klassifikator** eingeführt.
APR-005A bewertet Änderungslisten nach höchstem Risiko und sperrt jede echte
Merge-Ausführung (`DENY`). Dieser Zustand bleibt unangetastet.

## Review-Ablauf

1. Entwickler erstellt einen PR ohne Merge-, Deployment- oder Freigaberechte.
2. Die drei bestehenden CI-Checks laufen: `Lint and structure`, `Backend`, `Image`.
3. Codex prüft den PR-Diff im getrennten Review-Lauf nach `AGENTS.md`.
4. Reviewer-Befunde werden mit PR, Head-SHA, Review-SHA und GitHub-Link erfasst.
5. R0/R1 gelten *nur als Kandidaten* für spätere automatisierte Niedrigrisiko-Gates.
   R2/R3/R4 erfordern zusätzliche Sicherheits- und Freigabeprüfung.
6. Ein autoritativer GitHub-/Control-Plane-Adapter muss Quelle, GitHub-App-Identität,
   SHA, Befunde, Policies und formale Freigaben **serverseitig** prüfen.
7. Ohne diesen Adapter und eine gesonderte CEO-Freigabe ist das Ergebnis
   ausnahmslos **DENY**. Kein produktiver Merge-Operator ist Bestandteil dieses PRs.

## Versioniertes Evidenzformat

`config/code-review/review-evidence-v1.schema.json` definiert ein
maschinenprüfbares *Offline-Format für Beobachtungen*, nicht für Approvals.
`app/codex_review_evidence.py` erkennt insbesondere ungültige Felder,
fehlende CI-Checks, SHA-Veralterung, Selbstprüfung, offene Befunde und höhere
Risikoklassen. Auch fehlerfreie JSON-Dateien können gefälscht sein: Der Prüfer
liefert deshalb **immer** `merge_authorized=false`, `verdict=DENY` und einen
Hinweis auf die nicht authentifizierte GitHub-Quelle; sein CLI endet mit Code 2.

Die bisherige APR-005A-`ReviewEvidence` bleibt davon unabhängig. Eine
zukünftige Integration muss die GitHub-App-Identität und das `head_sha`
verifiziert in ihren separaten Vertrag übersetzen; ein Bot-Kommentar allein
belegt keine GitHub-Approval.

## OpenAI-Code-Review-Aktivierung (außerhalb dieses PRs)

Die Konto-/Repo-Aktivierung erfolgt über die Codex Code Review-Einstellungen.
Ob automatische Reviews für dieses Repository eingeschaltet sind, ist nicht
bestätigt. `@codex review` kann nach bestätigter Verbindung als manueller
Test genutzt werden. Ein Review-Kommentar ist keine signierte Freigabe.

Referenzen:

- <https://developers.openai.com/blog/custom-code-review-rules-for-codex>
- <https://help.openai.com/en/articles/20001552-review-pull-requests-with-codex>
- <https://github.com/tiktokagentur-art/gmv-foundation/pull/30>
- <https://github.com/tiktokagentur-art/gmv-foundation/pull/62>

## Noch gesperrt

- Änderungen an `main`-Ruleset, erforderlicher Approval-Zahl, CODEOWNERS
  oder GitHub-Berechtigungen.
- Automerge, Merge, Deployment, Secret-Erteilung und produktive Modellaufrufe.
- Vertrauen auf selbst eingereichte JSON-Evidenz oder synthetische Reviews.
- Vermischung von CRG-001A mit dem offenen APR-005A-Dateiscope.

## Abnahme

- Differenz gegenüber dem PR-#30-Branch enthält nur die dokumentierten Dateien.
- Ruff, Pytest, Repository-Strukturvalidator, Markdownlint und GitHub-CI geprüft.
- Getrennte Review-Schicht, keine Reviewer-Selbstevaluation, SHA-Bindung.
- No-Go für Live-Gating bis nachweisbarer API-Adapter und expliziter Freigabe.
