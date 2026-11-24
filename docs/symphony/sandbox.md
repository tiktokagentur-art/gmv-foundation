# Symphony/Codex-Sandbox – erzwungen vs. dokumentiert

Stand 24.11.2026. Geprüft gegen `openai/symphony@be10a1b` und
`codex-cli 0.172.0` auf dem Pilot-Host. Kein Symphony-Lauf und kein
Modellaufruf: Nachweise über `scripts/symphony_host/sandbox-selftest.sh`
(`codex app-server` mit `command/exec` und genau der `sandboxPolicy`, die
Symphony pro Turn sendet). Ausgegeben werden nur Existenz, Größe und
HTTP-Status, keine Inhalte.

## Schichten

1. **bwrap-Namespace (Host, ohne Root)**: `run-symphony.sh` startet
   Symphony in `bwrap`. Credential-Speicher sind mit leerem `tmpfs` bzw.
   `/dev/null` überdeckt (`bwrap-env.sh`). Das Installation-Token wird
   vorher außerhalb erzeugt, weil nur dort der App-Key lesbar ist.
2. **Codex-Sandbox je Turn**: `turn_sandbox_policy` erlaubt Schreiben nur
   im Issue-Workspace, `/tmp` und `$TMPDIR` sind gesperrt, `.git` ist
   schreibgeschützt, `networkAccess: false`.
3. **Netz**: Codex-Netzwerk-Proxy (Profil `gmv_symphony`) mit Allowlist,
   Upstream ist der lokale Allowlist-Egress-Proxy
   (`scripts/symphony_egress_proxy.py`, Nutzerprozess auf `127.0.0.1:18443`).
   Beide prüfen dieselben drei Hosts.

## Ergebnis

| Grenze | Status | Nachweis (Selbsttest) |
| --- | --- | --- |
| App-Key `~/secrets` | **erzwungen** ausgeblendet | außerhalb lesbar (1675 Bytes); im Namespace und in der Codex-Sandbox: fehlt |
| `~/.config/gh` (Admin-Token) | **erzwungen** ausgeblendet | außerhalb lesbar; innen: fehlt |
| `~/.gitconfig` (Credential-Helper), `~/.git-credentials`, `~/.netrc` | **erzwungen** | `.gitconfig` innen leer (`/dev/null`), `git config --global` ohne Einträge; die anderen existieren auf dem Host nicht und werden maskiert, sobald sie existieren |
| `~/.codex` | **erzwungen** bis auf `auth.json` | innen leer und sitzungslokal (Sessions, Historie, Memories, Config fehlen) |
| `~/.codex/auth.json` | **schreibgeschützt, aber lesbar (Restrisiko)** | `--ro-bind`: aus dem Namespace nicht veränderbar oder ersetzbar (Test `BwrapLiveTests`). Lesbar bleibt sie, weil der Codex-Prozess im selben Namespace läuft und die ChatGPT-Anmeldung braucht. Muss Codex das Token erneuern, schlägt das fail-closed fehl; erneuert wird außerhalb per `codex login` |
| Browser-/CLI-Profile, `/cursor`, `/workspace` außer Pilot-Verzeichnis | **erzwungen** ausgeblendet | innen leer bzw. nur `symphony-pilot` sichtbar |
| Schreiben nur im Issue-Workspace | **erzwungen** | eigener Workspace erlaubt; Nachbar-Workspace, `/tmp`, `$HOME` verweigert |
| Netz `github.com`, `api.github.com`, `api.openai.com` | **erzwungen erreichbar** | 200, 200, 401 (ohne Auth, nur Status); dreimal hintereinander stabil |
| Netz `example.com`, `pypi.org` | **erzwungen blockiert** | `000` (Proxy `CONNECT` 403) |
| Doppelte Prüfung | **erzwungen** | Ein in Codex zusätzlich freigegebener Host (Test: `pypi.org`) wird vom Egress-Proxy abgelehnt |

`codeload.github.com` und `objects.githubusercontent.com` sind **nicht**
freigegeben: Klon (`hooks.after_create`) und `github_api` laufen außerhalb
der Codex-Sandbox und brauchen keinen Sandbox-Zugang.

## Warum `allow_local_binding`

Der Pilot-Host löst `github.com`, `api.github.com` und `api.openai.com` auf
`198.18.0.1` (Egress-Tunnel) auf. Der lokale/private Schutz des
Codex-Proxys blockiert solche Ziele und verhindert auch den Weg zum lokalen
Upstream. `allow_local_binding=true` hebt nur diesen Schutz auf. Die
Domain-Allowlist bleibt exakt, der Upstream prüft erneut, und
`validate-workflow` lässt die Option nur zusammen mit
`HTTPS_PROXY=http://127.0.0.1:18443` und `allow_upstream_proxy=true` zu.

## Modellverkehr

Der Codex-Prozess selbst (ChatGPT-Anmeldung) spricht `chatgpt.com` und
`auth.openai.com` direkt an (`NO_PROXY` nur für diese Hosts). Aus dem
Namespace sind beide erreichbar (HTTP 200, ohne Auth). In den Pilotläufen
vom 24.11.2026 (Issues #87, #106, #108) lehnte der Egress-Proxy
`*.oaiusercontent.com` jeweils ab. Alle drei Läufe endeten regulär und
lieferten einen Patch (PRs #105, #107, #109). Die Domain bleibt blockiert.

## Wie Symphony die Sandbox setzt

- `thread/start` erhält `sandbox` = `codex.thread_sandbox`, jeder
  `turn/start` erhält `sandboxPolicy` = `codex.turn_sandbox_policy`.
  Ohne eigenen Wert sendet Symphony `workspaceWrite` mit `/tmp`.
  `thread_sandbox: read-only` allein wirkt nicht.
- Weil Symphony immer eine `sandboxPolicy` sendet, wirken Leseregeln aus
  Codex-Profilen nicht. Deshalb übernimmt bwrap das Ausblenden.
- `approval_policy: never` lässt Symphony alle Freigabeanfragen
  automatisch annehmen. Symphonys Standard (`reject`-Map) lehnt
  `codex-cli 0.172.0` ab. Die Vorlage nutzt `on-request` (fail-closed).
- Symphony entfernt das Tracker-Token vor dem Codex-Start (`unset`).

## Betrieb

| Datei (Repo → Host `bin/`) | Zweck |
| --- | --- |
| `scripts/symphony_host/run-symphony.sh` | Einziger Start; ohne `GMV_SYMPHONY_START_APPROVED=yes` Abbruch. Guardrail-Flag nur per Opt-in `GMV_SYMPHONY_GUARDRAIL_FLAG_APPROVED=yes` für genau einen Aufruf (danach `unset`), externer Wächter und Einmal-Sperre `log/pilot-run.once` je Lauf |
| `scripts/symphony_host/symphony_watchdog.py` | Externer Wächter: stoppt den ganzen Prozessbaum (SIGTERM, dann SIGKILL, danach verifiziert) bei 2.000.000 − 300.000 Tokens, zweitem Issue, zweitem Dispatch, Retry-Zyklus, Ende des ersten Laufs, Schleife, Laufzeitlimit oder fehlender Token-Anzeige. Tests: `tests/test_symphony_watchdog.py` |
| `scripts/symphony_host/uds_bridge.py` | Nur Versuch, nicht im Start eingebunden: TCP↔Unix-Socket-Brücke für Netz-Isolation per `bwrap --unshare-net` (siehe unten) |
| `scripts/symphony_host/bwrap-env.sh` | Masken für bwrap |
| `scripts/symphony_host/egress-proxy.sh` | Proxy starten/stoppen (Nutzerprozess, PID und Log unter `log/`) |
| `scripts/symphony_egress_proxy.py` | Allowlist-Proxy, nur `CONNECT` auf Port 443, keine IP-Literale, keine Inhaltsprotokolle |
| `scripts/symphony_host/sandbox-selftest.sh`, `codex_exec_probe.py` | Nachweis ohne Lauf und ohne Modellaufruf; braucht PyYAML (Host: `tools-venv`) |

Fallback, falls der Proxy nicht stabil läuft: `permissions.gmv_symphony.network`
auf `enabled=false` setzen und die Proxy-Variablen entfernen. Dann hat die
Sandbox kein Netz. Klon und `github_api` laufen weiterhin außerhalb.

## Netz per Betriebssystem erzwingen (Versuch 24.11.2026)

Heute erzwingen Codex-Netzwerk-Proxy und Egress-Proxy die Allowlist. Der
bwrap-Namespace teilt aber das Host-Netz: Ein Prozess, der die Proxy-Variablen
ignoriert, käme direkt hinaus. Geprüft wurde in einer Wegwerf-Sandbox auf dem
Pilot-Host (ohne Root, eigene Proxy-Instanz auf einem anderen Port, kein
Eingriff in Pilot-Proxy, Firewall oder laufende Läufe):

| Variante | Ergebnis |
| --- | --- |
| nftables/iptables je UID | **nicht möglich**: kein Root, kein `sudo`, `nft`/`iptables` nicht installiert. Braucht Root auf dem Host |
| veth-Paar + eigener Netz-Namespace | **nicht möglich** ohne Root (`CAP_NET_ADMIN` im Host-Namespace); `slirp4netns`/`pasta` sind nicht installiert |
| `bwrap --unshare-net` | **funktioniert ohne Root**: innen nur `lo`; `github.com`, `example.com` und die Tunnel-IP `198.18.0.1:443` direkt nicht erreichbar |
| `bwrap --unshare-net` + Unix-Socket-Brücke zum Allowlist-Proxy (`uds_bridge.py`) | **funktioniert ohne Root**: über den Proxy `github.com` 200, `api.github.com/zen` 200, `api.openai.com/v1/models` 401, `git ls-remote` ok; `example.com`, `pypi.org`, `chatgpt.com` 000 (abgelehnt); direkt ohne Proxy 000 |

Damit ließe sich die Netzgrenze ohne Root vom Kernel erzwingen: Der einzige
Weg nach außen ist der hineingereichte Unix-Socket des Allowlist-Proxys.
**Noch nicht eingebunden**, weil offen ist:

- Der Modellverkehr von Codex (`chatgpt.com`, `auth.openai.com`) läuft heute
  per `NO_PROXY` direkt. Unter `--unshare-net` braucht er einen Weg über einen
  Proxy, also entweder diese zwei Hosts auf die Allowlist oder eine zweite,
  nur für sie freigegebene Proxy-Instanz. Beides ändert die Allowlist bzw.
  den Betrieb und braucht eine Freigabe. Aus dem Namespace sind beide Hosts
  heute schon erreichbar (Selbsttest Abschnitt 2b).
- Symphony selbst (Tracker-Abfragen an `api.github.com`) und der Klon-Hook
  müssten den Proxy nutzen; für Symphony ist das noch nicht nachgewiesen.
- Ein Pilotlauf mit der Variante ist ein Betriebswechsel und läuft erst nach
  Freigabe.

## Offene Punkte

- `auth.json` aus der Sandbox lesbar (jetzt schreibgeschützt): eigenes
  Codex-Konto bzw. Projekt mit Ausgabenlimit für Symphony oder ein eigener
  Unix-Nutzer (Root). Beides braucht eine Entscheidung (Kosten bzw.
  Root-Zugriff auf dem Host).
- Lesbar bleibt innerhalb des Pilot-Verzeichnisses auch der Inhalt anderer
  Issue-Workspaces und der Logs.
- Netzebene: nftables je UID braucht Root; die rootlose Variante
  `--unshare-net` + Unix-Socket-Brücke ist nachgewiesen, aber nicht
  eingebunden (siehe oben).
