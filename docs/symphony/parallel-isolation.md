# Symphony parallel: Trennung je Issue und Proxy-Regel

Status: Repo-Stand ab Merge, Host-Umsetzung siehe PR-Text (nicht ausgeführt).
Bezug: Petrus 25.11.2026 (über Aline, 02:03): bis zu 10 parallele Läufe erst
nach Samiras schriftlichem OK. Samira: Bedingung 1 (Tracker-Trennung je Issue)
und Bedingung 2 (Proxy-Stopp in `run-wave.sh`). Die Vorlage
[WORKFLOW.example.txt](WORKFLOW.example.txt) bleibt bei `max_concurrent: 1`
und `enabled: false`. Die Grenze von 10 Läufen zusammen mit `research.sh`
bleibt ([dispatch-gate.md](dispatch-gate.md)).

## Bedingung 1: eigener Zustand je Issue

`run-symphony.sh` legt nach der Einmal-Sperre `runs/issue-<n>/` exklusiv an
(`symphony_dispatch_gate.py prepare-run`, Modus 700). Existiert das
Verzeichnis schon, startet nichts (`run_dir_exists`, fail-closed).

| Pfad in `runs/issue-<n>/` | Inhalt |
| --- | --- |
| `WORKFLOW.md` (600) | aus der Pilot-`WORKFLOW.md` erzeugt: zusätzliches Pflicht-Label `gmv-symphony-issue-<n>`, `workspace.root` = `runs/issue-<n>/workspaces` |
| `workspaces/` | Issue-Workspaces dieses Prozesses (Symphony `rm_rf`/`mkdir_p` nur hier) |
| `log/` | `--logs-root` von Symphony; der Wächter liest nur `log/log` |
| `run.out` | Dashboard-Ausgabe (Wächter `--stdout-file`) |
| `watchdog.log` | Ereignisse des Wächters |

Tracker: `tracker.required_labels` ist bei Symphony eine UND-Bedingung. Jeder
Prozess verlangt `gmv-symphony-pilot` und `gmv-symphony-issue-<n>`; damit
routet er nur sein eigenes Issue, auch wenn mehrere Issues das Pilot-Label
tragen. Das Erzeugen ist zeilenbasiert und fail-closed: fehlt `workspace.root`
oder `tracker.required_labels`, kommt es doppelt vor oder steht schon ein
`gmv-symphony-issue-`-Label darin, wird nichts erzeugt.

In bwrap hängt `run-symphony.sh` an die unveränderten Masken aus
`bwrap-env.sh` an: `--ro-bind <Pilot> <Pilot> --bind runs/issue-<n> runs/issue-<n>`
und startet mit `--chdir runs/issue-<n>`. Das Pilot-Verzeichnis (Binary,
gemeinsame `WORKFLOW.md`, Sperren, andere Läufe) ist für den Symphony-Prozess
nur lesbar; beschreibbar ist dort nur das eigene Lauf-Verzeichnis.

## Schreibpfade (Inventar)

Geprüft: `run-symphony.sh`, `symphony_dispatch_gate.py`, `symphony_watchdog.py`,
`symphony_app_token.py`, `egress-proxy.sh`, `bwrap-env.sh` und die
Symphony-Quellen (Tracker GitHub, Workspace, Logdatei).

| Schreiber | Pfad | geteilt? | Schutz |
| --- | --- | --- | --- |
| Gate `slot-acquire`/`slot-release` | `/workspace/research/state/slots/<pid>` | ja (Zähler) | `flock` auf `/workspace/research/.research.lock` |
| Gate (alle Kommandos mit Lock) | `/workspace/research/.research.lock` | ja (Lock) | Lock-Datei selbst |
| Gate `once-acquire` | `log/once/issue-<n>.once` | nein, je Issue | `O_EXCL` |
| Gate `prepare-run` | `runs/issue-<n>/…` | nein, je Issue | exklusives `mkdir`, `O_EXCL` |
| Gate Alarme (`quota-scan`, `run-verdict`, `release`, `proxy-stop-if-idle`) | `/workspace/research/ALERTS.log` | ja | nur Anhängen, `flock` auf die Datei (neu) |
| Gate Marker | `state/quota-stop`, `state/symphony-stop` | ja, gewollt global | fail-closed für alle; Freigabe nur per `release` |
| `egress-proxy.sh` (über Gate `proxy-start`, `proxy-stop-if-idle`) | `log/egress-proxy.pid`, `log/egress-proxy.log` | ja (ein Proxy für alle) | Start und Stopp nur unter dem Slot-Lock |
| Wächter | `run.out`, `watchdog.log` | nein | im Lauf-Verzeichnis |
| Token-Helfer | eigenes `TemporaryDirectory` je Aufruf | nein | privat, wird gelöscht |
| Symphony/Codex in bwrap | `runs/issue-<n>/`, privates `/tmp`, `~/.codex` als tmpfs | nein | bwrap je Prozess |
| Symphony-Tracker | GitHub (Issue-Status, Kommentare, Labels) | je Issue | Pflicht-Label `gmv-symphony-issue-<n>` |

Gemeinsam beschreibbar zwischen parallelen Slots bleiben damit nur der
Slot-Zähler, die Locks, die Sperr- und Markerdateien, `ALERTS.log` (nur
Anhängen unter Lock) und die Proxy-PID-Datei (nur unter dem Slot-Lock).
Test: `WrapperFlowTests.test_two_parallel_slots_have_separate_tracker_and_state`
startet zwei Läufe gleichzeitig (Stubs, ohne Modellaufruf) und prüft, dass jede
geschriebene Datei im eigenen `runs/issue-<n>/` liegt oder zu dieser Liste gehört.

## Bedingung 2: Proxy-Stopp in run-wave.sh

Vorlage: `scripts/symphony_host/run-wave.sh` (Host: `run-wave.sh` im
Pilot-Verzeichnis). Ablauf: Issue-Nummer prüfen, `runs/issue-<n>` darf nicht
existieren, Labels `gmv-symphony-pilot` und `gmv-symphony-issue-<n>` setzen,
`pilot-one-run.sh`, Issue-Label wieder entfernen, dann
`symphony_dispatch_gate.py proxy-stop-if-idle`.

- Unter dem `flock` des Slot-Zählers: lebt kein Symphony-Slot mehr (tote PIDs
  zählen nicht, Codex-Slots von `research.sh` zählen nicht), wird der Proxy
  gestoppt; rc = rc des Laufs.
- Lebt noch ein Symphony-Slot: kein Stopp, `ALERT run-wave issue=<n>
  proxy_stop_refused live_symphony_slots=<k> issues=<…>` in `ALERTS.log`,
  `run-wave.sh` endet mit **rc=14**. Den Proxy stoppt der zuletzt endende Lauf.
- Der Start (`proxy-start`) läuft ebenfalls unter dem Lock, so kann kein
  Stopp zwischen Prüfung und Start eines anderen Laufs fallen.
- Weitere rc: 20 (Eingabe, `runs/issue-<n>` vorhanden), 21 (Labels nicht gesetzt).

Tests: `RunWaveTests` (Stubs für `gh`, `pilot-one-run.sh` und Proxy) und
`IssueIsolationTests` in `tests/test_symphony_dispatch_gate.py`.

## Restrisiken

- **Restrisiko 4 bleibt:** Alle Agenten laufen als UID `box`. Zähler, Locks,
  Sperren, Marker und `ALERTS.log` synchronisieren kooperierende Skripte; gegen
  einen entglittenen Prozess unter `box` außerhalb der Hülle schützen sie nicht.
- Die Sandbox bleibt unverändert (`--dev-bind / /` mit Masken). Außerhalb des
  Pilot-Verzeichnisses kann der Symphony-Prozess technisch weiterhin schreiben,
  was `box` schreiben darf (z. B. `/workspace/research`). Die Codex-Turns selbst
  schreiben nur im Workspace ([sandbox.md](sandbox.md)).
- `ALERTS.log` sperrt per `flock` nur kooperierende Schreiber. Schreiber ohne
  `flock` (Host-Skripte außerhalb des Repos) hängen weiter mit `O_APPEND` an.
- Der Host-Stand (`pilot-one-run.sh`, `run-wave.sh`, Labels
  `gmv-symphony-issue-<n>` auf GitHub) ist nicht umgestellt; siehe PR-Text.
