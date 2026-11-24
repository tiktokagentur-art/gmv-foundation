# Symphony Dispatch-Gate – Entwurf

Status: **Entwurf, standardmäßig aus.** Code-Skelett:
`scripts/symphony_dispatch_gate.py`, Tests: `tests/test_symphony_dispatch_gate.py`.
Bezug: Notion ENG-003, Issue #74, PR #66, Review-Befunde 3, 4 und 6.

## Zweck

Symphony dispatcht erneut, solange ein Issue `open` ist. Labels sind keine
Autorisierung. Das Gate sitzt deshalb **vor** jedem Codex-Start auf dem
Orchestrator-Host (nicht im Prompt, nicht im Codex-Workspace) und lehnt
jeden Lauf ab, der nicht nachweislich zugewiesen ist.

Das Gate ist keine zweite Assignment Authority (ADR-0003). Es vergibt und
verlängert keine Claims, es liest sie bei der Control Plane und prüft sie.

## Flag

| Variable | Wert | Wirkung |
| --- | --- | --- |
| `GMV_SYMPHONY_DISPATCH_GATE` | nicht gesetzt (Standard) | Jeder Dispatch: `gate_disabled` |
| `GMV_SYMPHONY_DISPATCH_GATE` | exakt `enabled` | Prüfungen unten laufen |

Andere Werte (`true`, `1`, `ENABLED`) gelten als aus. „Aus“ heißt nicht
„ungeprüft starten“, sondern „nichts starten“. Auch mit Flag liefert der
Entwurf ohne angebundene Authority `authority_unavailable`.

## Prüfreihenfolge (fail-closed)

1. Flag an, sonst `gate_disabled`.
2. Authority erreichbar, sonst `authority_unavailable`.
3. Anfrage formal gültig: Repository auf Allowlist, Issue-Nummer, Worker-ID,
   Claim-ID, Fencing-Token positiv.
4. Token-Budget konfiguriert und im Rahmen (1 bis 5.000.000), sonst
   `token_budget_missing_or_invalid` bzw. `token_budget_out_of_range`.
5. Aktiver Claim der Control Plane passt zu Worker, Claim-ID und Fencing,
   Lease nicht abgelaufen.
6. Sperre gegen Doppelvergabe erworben.

Erst danach darf der Orchestrator Codex starten.

## Sperre gegen Doppelvergabe

`DispatchLock` hält je Ticket genau einen Halter, atomar unter einem
exklusiven `flock` auf dem Host:

- freies Ticket: erste Anfrage gewinnt,
- gleicher Worker, gleicher Claim, gleiches Fencing: idempotent (Re-Dispatch, Restart),
- anderer Worker bei gültigem Lease: `already_dispatched_to_other_worker`,
- Übernahme nach Lease-Ablauf nur mit streng höherem Fencing-Token,
- gleiches oder niedrigeres Fencing: `stale_fencing_token`,
- unlesbarer Sperrzustand: `lock_state_unreadable`, kein Start.

Die Sperre ergänzt die Authority. Selbst wenn sie fälschlich zwei Claims
ausstellt oder zwei Orchestrator-Prozesse laufen, startet nur einer.

Entschieden (24.11.2026): Die Sperre bleibt vorerst auf dem Host.
Die Verlagerung in die Control Plane (z. B. Unique-Constraint auf aktive
Dispatches je WorkItem in PostgreSQL, Bezug CP-002 / PR #63) kommt später
als eigenes Ticket. Bis dahin ist der Betrieb auf einen Orchestrator-Host
begrenzt.

## Token-Budget pro Lauf

`TokenBudget` ist ein hartes, kumulatives Limit für genau einen Lauf:

- Vorlage: `gmv.token_budget.max_tokens_per_run: 5000000`,
  `reserve_per_turn: 300000` (6 Turns × 300.000 = 1.800.000).
  Der Pilot brauchte ca. 160.000 Token je Turn, die Reserve hat also knapp
  Faktor 2 Puffer. `validate-workflow` lehnt Reserve × Turns über dem Budget ab.
- Erreicht der kumulierte Verbrauch 5.000.000, bricht der Lauf hart ab.
  Zweck: Schutz gegen hängende oder sich wiederholende Läufe.
- Vor jedem Turn: passt die Reserve nicht mehr, wird gestoppt.
- Unbekannter, negativer oder nicht ganzzahliger Verbrauch zählt als erschöpft.
- Überschritten bleibt überschritten (sticky); der Lauf endet, kein Retry
  im selben Lauf.
- Konfigurationsobergrenze im Code: 5.000.000 (`MAX_TOKENS_PER_RUN_CEILING`,
  Petrus 24.11.2026 23:20). Sie ändert sich nur zusammen mit dem
  Wächter-Standard (`symphony_watchdog.py`, `DEFAULT_BUDGET`) und
  `--budget` in `run-symphony.sh`; ein Test prüft die Gleichheit.
  Höhere Werte brauchen eine Code-Änderung mit Review.

Annahme, vor Phase B gegen `openai/symphony@be10a1b` zu prüfen: Symphony
selbst kennt nur `agent.max_turns`, kein Token-Limit. Der Verbrauch muss aus
den Codex-Nutzungsereignissen an das Gate gemeldet werden; fehlt diese
Meldung, greift `token_usage_unknown`.

## Parallelität und gemeinsamer Slot-Zähler

Petrus 24.11.2026 23:20: höchstens 10 Läufe gleichzeitig, Codex-Recherchen
(`research.sh`, nur auf dem Host) und Symphony zusammen. Samira 23:25:
Symphony belegt denselben Zähler wie `research.sh`.

- Ein Symphony-Prozess bearbeitet genau ein Issue
  (`agent.max_concurrent_agents: 1`); der Wächter stoppt bei einem zweiten
  Dispatch (unverändert). Parallelität heißt: mehrere `run-symphony.sh`-Aufrufe
  mit je eigenem `GMV_SYMPHONY_ISSUE`.
- `gmv.dispatch_gate.max_concurrent` (1 bis 10, Vorlage 1) begrenzt die
  Symphony-Prozesse. `validate-workflow` lehnt Werte außerhalb und
  `max_concurrent_agents` ungleich 1 ab.
- Zähler: `flock` auf `/workspace/research/.research.lock` (derselbe Meta-Lock
  wie `research.sh`), je laufendem Prozess eine Datei
  `/workspace/research/state/slots/<pid>`. Symphony schreibt
  `pid=<pid> reserved=0 id=symphony-issue-<n> kind=symphony issue=<n>`.
  Tote PIDs zählen nicht; tote Symphony-Slots räumt das Gate, Codex-Slots
  `research.sh` selbst (wegen der Tagesreservierung).
- Abgelehnt wird unter dem Lock, wenn alle Slots ≥ 10 (`shared_limit_reached`,
  rc=5), Symphony-Slots ≥ `max_concurrent` (`symphony_limit_reached`, rc=5)
  oder dasselbe Issue schon einen Slot hat (`issue_already_running`).
  `GMV_MAX_TOTAL_RUNS` darf nur senken.
- Einmal-Sperre pro Issue: `log/once/issue-<n>.once`, angelegt mit `O_EXCL`.
  Bei einem Race gewinnt genau ein Aufruf; jeder weitere Start desselben Issues
  endet mit `BLOCKED` (rc=2). Andere Issues sind nicht betroffen.
- Reihenfolge in `run-symphony.sh`: Freigabe → Issue → Einmal-Sperre vorhanden?
  → Quota-Stopp → Slot → Einmal-Sperre anlegen → Proxy → Token → Wächter →
  Quota-Prüfung → Slot frei (`trap … EXIT`).
- Protokolle je Issue: `log/issue-<n>/` (Symphony-Logs, die der Wächter liest),
  `log/run-issue<n>-<ts>.out`, `log/watchdog-issue<n>-<ts>.log`. So sieht ein
  Wächter nie die Dispatches eines anderen Prozesses.

Quota-, Rate-Limit- und Login-Regel: [quota-refresh.md](quota-refresh.md).

## Sandbox

Schreib- und Netzwerkgrenzen der Codex-Turns: [sandbox.md](sandbox.md).

## Repo-Klon-Hook

`hooks.after_create` in `WORKFLOW.example.txt` klont `main` per HTTPS ohne
Token (`--depth 1 --single-branch --no-tags`) in den leeren Workspace,
setzt `core.hooksPath` auf `/dev/null` und prüft einen sauberen Baum.
`validate-workflow` lehnt Tokens, Credentials in URLs, Pipes in Shells,
`git push`, `gh` und fehlende Timeouts ab.

```text
python3 scripts/symphony_dispatch_gate.py validate-workflow docs/symphony/WORKFLOW.example.txt
```

## Authentifizierung

Symphony nutzt nur noch das Installation-Token der App `gmv-symphony-worker`
(siehe [github-app-spec.md](github-app-spec.md)), erzeugt pro Lauf von
`scripts/symphony_app_token.py exec`. **Das persönliche Admin-Token
(`repo`, `admin:org`, `workflow`) wird nicht mehr verwendet.** Das Gate darf
einen Dispatch nur in einem Prozess zulassen, dessen `GITHUB_TOKEN` von diesem
Helfer stammt.

## Anbindung (Phase B, nicht aktiv)

- `hooks.before_run` ruft das Gate auf (in der Vorlage auskommentiert).
  Exit-Code ungleich 0 bricht den Lauf ab.
- Die Authority-Anbindung (`ClaimAuthority.active_claim`) kommt mit dem
  Control-Plane-Vertrag CP-002.
- Stopp ohne Statusübergang: Gate-Flag entfernen. Ab dem nächsten Dispatch
  startet nichts mehr.

## Entscheidungen und offene Punkte

- Budget: 5.000.000 Token pro Lauf (bis 24.11.2026 2.000.000), harter Abbruch bei Erreichen
  (Pilotwert ca. 480.000 für einen README-Absatz; ein hängender Lauf
  verbrauchte ohne Gate über 7,5 Mio.).
- Sperre: vorerst auf dem Host; Control-Plane-Verlagerung als eigenes Ticket.
- Offen: Aktivierung des Flags nur mit separatem CEO-Go.
- Stand 24.11.2026: Das Gate bleibt **bewusst aus**, solange genau ein
  Operator auf genau einem Host steuert und Pilotläufe nur einzeln startet.
  Ersatzweise greifen auf dem Host: Startfreigabe je Aufruf
  (`GMV_SYMPHONY_START_APPROVED`), Einmal-Sperre pro Issue
  `log/once/issue-<n>.once` (bis 24.11.2026 global `log/pilot-run.once`), genau
  ein gelabeltes offenes Issue (Vorabprüfung), externer Wächter (ein Issue,
  ein Dispatch, kein Retry, Tokenbudget, Laufzeit) und Widerruf des
  Installation-Tokens nach jedem Lauf. Das ersetzt keine Claim-, Lease- oder
  Fencing-Prüfung. Sobald ein zweiter Operator, ein zweiter Host oder
  Dauerbetrieb dazukommt, ist das Gate Voraussetzung (CP-002).
