# Symphony Operations Playbook V1

Stand: 25.11.2026. Ergänzt [sandbox.md](sandbox.md) (Schichten, Selbsttest,
Dateien) und [../SYMPHONY-GITHUB-V1.md](../SYMPHONY-GITHUB-V1.md) (Grenzen,
Phasen). Was dort steht, wird hier nicht wiederholt. Dieses Playbook beschreibt
den Ablauf eines Pilotlaufs und die bisher beobachteten Fehlerbilder.

## Rollen

| Rolle | Wer | Aufgabe |
| --- | --- | --- |
| Zuweisung | Aline (Control Plane) | Auftrag freigeben, Wellen freigeben, PRs mergen |
| Operator | Aline oder Deniz | Label setzen, Lauf starten, Bericht schreiben |
| Worker | Codex über Symphony | nur Patch und Bericht, keine GitHub-Schreibaktion |
| Schutzmaßnahmen, Rechte, Ausgaben | Petrus | jede Änderung daran |

## Ablauf eines Laufs

1. Issue nach der [Vorlage](../../.github/ISSUE_TEMPLATE/symphony-pilot.yml)
   anlegen. Regeln dafür: [codex-engineering.md](codex-engineering.md).
2. Vorabprüfung: genau ein offenes Issue trägt `gmv-symphony-pilot`, kein
   Symphony- oder Codex-Prozess läuft.
3. Egress-Proxy starten, Selbsttest ausführen. Nicht grün heißt kein Start.
4. Alte Einmal-Sperre `log/pilot-run.once` archivieren
   (`pilot-run.once.used-<Zeit>`), dann genau ein Start über
   `scripts/symphony_host/run-symphony.sh` mit beiden Freigabevariablen für
   diesen einen Aufruf.
5. Der Wächter (`symphony_watchdog.py`) stoppt den Prozessbaum. Danach wird
   das Installation-Token widerrufen.
6. Nachlauf: Stop-Grund und Tokens aus dem Wächter-Log lesen, Patch sichern,
   Label entfernen, Prozesszahl 0 prüfen.
7. Ein Mensch erstellt Branch und Draft-PR mit `Closes #N`. Merge nach grüner
   CI durch Aline oder Deniz.
8. Bericht an Aline, höchstens 5 Zeilen: Issue, PR, Tokens, Stop-Grund,
   Auffälligkeiten.

## Stop-Gründe des Wächters

| Grund | Bedeutung | Erwartet? |
| --- | --- | --- |
| `first_run_finished` | `max_turns` erreicht oder Agent fertig | ja, Normalfall |
| `retry_cycle_scheduled` | Symphony plant einen Fehler-Retry | nein, Ursache im Symphony-Log suchen |
| `second_dispatch`, `second_issue` | zweiter Auftrag im selben Lauf | nein, Label-Vergabe prüfen |
| `loop_sessions` | mehr Codex-Sessions als `max_turns` | nein |
| `token_budget_reached` | 1,7 Mio. Tokens (2 Mio. minus Reserve) | nein |
| `token_readout_missing` | 300 s keine Tokenzahl | nein, Log-Format prüfen |
| `max_runtime` | 1 h überschritten | nein |

Nach `first_run_finished` steht im Symphony-Log
`Retrying … in 1000ms (attempt 1)`. Das ist der normale Fortsetzungs-Retry
laut Symphony-Spezifikation (§8.4), kein Fehler.

## Troubleshooting: beobachtete Fehlerbilder

Quelle: Läufe 1 bis 8 am 24.11.2026 und die zugehörige CI. Issues: Nr. 87,
106, 108, 113, 114, 115, 120 und 123.

| Fehlerbild | Beleg | Ursache | Abhilfe |
| --- | --- | --- | --- |
| `retry_cycle_scheduled` mit `approval_required` im Log | #113, #114 | Codex wollte Tests per Python/subprocess außerhalb der Sandbox starten. Bei `approval_policy: on-request` bricht Symphony den Turn bei jeder Eskalationsanfrage ab. | Im Issue keine Testausführung verlangen („Tests nicht selbst ausführen, nur Patch liefern“, Vorlage seit #119). Akzeptanz „CI grün“ statt „pytest grün“. Der Patch war in beiden Fällen schon fertig: sichern und normal weiterverarbeiten. |
| Viele Dispatches desselben Issues | Vor-Pilot #87 (44 Dispatches, Dashboard 7,6 Mio. Tokens) | Symphony dispatcht erneut, solange das Issue offen und gelabelt ist. | Wächter (`second_dispatch`) und Einmal-Sperre, beide seit #128 im Repo. |
| Denies für `*.oaiusercontent.com` im Proxy-Log | jeder Lauf, 34 bis 136 je Lauf | Host ist nicht auf der Allowlist. | Erwartetes Rauschen, kein Lauf ist daran gescheitert. Allowlist nicht erweitern. |
| CI rot: `gitleaks download failed: The read operation timed out` | PR #124, CI-Versuch 1 | `tests/test_gitleaks_scan.py` lädt gitleaks aus dem Netz (Timeout 60 s). | Job einmal neu starten (Versuch 2 war grün). Kein Codefehler, der Patch bleibt unverändert. |
| CI rot: `bwrap: Can't mkdir /workspace` | PR #128, erster CI-Lauf | bwrap-Live-Test lief auf dem Runner ohne `/workspace`. | Test nur auf dem Pilot-Host (Commit `14ef3d5`). |
| Patch übernimmt veraltete Regeln | #87 → #105 | Codex zitiert, was in der Doku steht („Freigabe von Petrus“). | Doku aktuell halten, Patch vor dem PR lesen. |
| Kleine Formatabweichung | #113 → #116 | ruff-format bricht eine Zeile um. | Vor dem PR `ruff format` auf die geänderten Dateien. |
| Issue bleibt nach dem Merge offen | #106, #108 | PR ohne `Closes #N`. | `Closes #N` im PR-Text. |
| Agent-Abschlussbericht fehlt | Bericht GH-87 | Symphony loggt nur Deltas, `~/.codex/sessions` liegt im bwrap auf tmpfs. | Patch aus dem Workspace sichern. Persistenz offen, siehe unten. |

## Offene Punkte

- Strengere Approval-Einstellung, die Eskalationen ablehnt statt abzubrechen
  (`approval_policy = { granular = { sandbox_approval = false } }`), offline
  gegen die gepinnte Version prüfen. Eine Änderung braucht Petrus' OK.
- Den Agent-Bericht über einen `after_run`-Hook sichern (Spezifikation §5.3.4).
- Den Wächter auf die JSON-API (`/api/v1/state`) oder die absoluten
  Token-Events umstellen statt Logtexte zu lesen.
