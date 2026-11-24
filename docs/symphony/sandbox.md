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
| `~/.codex/auth.json` | **nicht ausgeblendet (Restrisiko)** | bleibt aus der Codex-Sandbox lesbar, weil der Codex-Prozess im selben Namespace läuft und die ChatGPT-Anmeldung braucht |
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
Namespace sind beide erreichbar (HTTP 200, ohne Auth). Ein Modellaufruf
wurde nicht getestet. Beim Start versuchte Codex zusätzlich
`*.oaiusercontent.com`; der Egress-Proxy lehnt das ab. Ob das den
Modellbetrieb stört, ist erst beim ersten freigegebenen Lauf prüfbar.

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
| `scripts/symphony_host/run-symphony.sh` | Einziger Start; ohne `GMV_SYMPHONY_START_APPROVED=yes` Abbruch, ohne Guardrail-Flag |
| `scripts/symphony_host/bwrap-env.sh` | Masken für bwrap |
| `scripts/symphony_host/egress-proxy.sh` | Proxy starten/stoppen (Nutzerprozess, PID und Log unter `log/`) |
| `scripts/symphony_egress_proxy.py` | Allowlist-Proxy, nur `CONNECT` auf Port 443, keine IP-Literale, keine Inhaltsprotokolle |
| `scripts/symphony_host/sandbox-selftest.sh`, `codex_exec_probe.py` | Nachweis ohne Lauf und ohne Modellaufruf; braucht PyYAML (Host: `tools-venv`) |

Fallback, falls der Proxy nicht stabil läuft: `permissions.gmv_symphony.network`
auf `enabled=false` setzen und die Proxy-Variablen entfernen. Dann hat die
Sandbox kein Netz. Klon und `github_api` laufen weiterhin außerhalb.

## Offene Punkte

- `auth.json` aus der Sandbox lesbar: eigenes Codex-Konto bzw. Projekt mit
  Ausgabenlimit für Symphony oder ein eigener Unix-Nutzer (Root).
- Lesbar bleibt innerhalb des Pilot-Verzeichnisses auch der Inhalt anderer
  Issue-Workspaces und der Logs.
- Netzebene unabhängig von Codex (nftables je UID) braucht Root.
