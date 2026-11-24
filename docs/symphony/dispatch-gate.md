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
4. Token-Budget konfiguriert und im Rahmen (1 bis 200.000), sonst
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
Für mehrere Hosts muss die Sperre in die Control Plane wandern
(z. B. Unique-Constraint auf aktive Dispatches je WorkItem in PostgreSQL);
das gehört in den CP-002-Vertrag (PR #63) und ist hier nicht entschieden.

## Token-Budget pro Lauf

`TokenBudget` ist ein hartes, kumulatives Limit für genau einen Lauf:

- Vorlage: `gmv.token_budget.max_tokens_per_run: 150000`,
  `reserve_per_turn: 25000` (6 Turns × 25.000).
- Vor jedem Turn: passt die Reserve nicht mehr, wird gestoppt.
- Unbekannter, negativer oder nicht ganzzahliger Verbrauch zählt als erschöpft.
- Überschritten bleibt überschritten (sticky); der Lauf endet, kein Retry
  im selben Lauf.
- Konfigurationsobergrenze im Code: 200.000. Höhere Werte brauchen eine
  Code-Änderung mit Review.

Annahme, vor Phase B gegen `openai/symphony@be10a1b` zu prüfen: Symphony
selbst kennt nur `agent.max_turns`, kein Token-Limit. Der Verbrauch muss aus
den Codex-Nutzungsereignissen an das Gate gemeldet werden; fehlt diese
Meldung, greift `token_usage_unknown`.

## Repo-Klon-Hook

`hooks.after_create` in `WORKFLOW.example.txt` klont `main` per HTTPS ohne
Token (`--depth 1 --single-branch --no-tags`) in den leeren Workspace,
setzt `core.hooksPath` auf `/dev/null` und prüft einen sauberen Baum.
`validate-workflow` lehnt Tokens, Credentials in URLs, Pipes in Shells,
`git push`, `gh` und fehlende Timeouts ab.

```text
python3 scripts/symphony_dispatch_gate.py validate-workflow docs/symphony/WORKFLOW.example.txt
```

## Anbindung (Phase B, nicht aktiv)

- `hooks.before_run` ruft das Gate auf (in der Vorlage auskommentiert).
  Exit-Code ungleich 0 bricht den Lauf ab.
- Die Authority-Anbindung (`ClaimAuthority.active_claim`) kommt mit dem
  Control-Plane-Vertrag CP-002.
- Stopp ohne Statusübergang: Gate-Flag entfernen. Ab dem nächsten Dispatch
  startet nichts mehr.

## Offene Entscheidungen

- Budgetwert: Der Pilot brauchte ca. 480.000 Token für einen README-Absatz.
  Mit 150.000 wäre er gestoppt worden. Wert und Obergrenze freigeben.
- Ort der dauerhaften Sperre (Host vs. Control Plane).
- Aktivierung des Flags nur mit separatem CEO-Go.
