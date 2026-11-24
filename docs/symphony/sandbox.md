# Symphony/Codex-Sandbox – erzwungen vs. dokumentiert

Stand 24.11.2026. Geprüft gegen `openai/symphony@be10a1b` und
`codex-cli 0.172.0` auf dem Pilot-Host. Kein Symphony-Lauf und kein
Modellaufruf: Die Nachweise stammen aus `codex sandbox` und
`codex app-server` (`thread/start` plus `command/exec` mit genau der
`sandboxPolicy`, die Symphony pro Turn sendet).

## Wie Symphony die Sandbox setzt

- `thread/start` erhält `sandbox` = `codex.thread_sandbox`.
- Jeder `turn/start` erhält `sandboxPolicy` = `codex.turn_sandbox_policy`.
  Fehlt der Wert, sendet Symphony selbst
  `workspaceWrite` mit dem Issue-Workspace, `/tmp`, `$TMPDIR` und
  `networkAccess: false`.
- Folge: `thread_sandbox: read-only` allein wirkt nicht. Die frühere
  Vorlage war deshalb faktisch `workspaceWrite` inklusive `/tmp`.
- `approval_policy: never` lässt Symphony alle Freigabeanfragen automatisch
  annehmen (`auto_approve_requests`). Symphonys Standard (`reject`-Map) lehnt
  `codex-cli 0.172.0` beim `thread/start` ab (`unknown variant reject`).
  Die Vorlage nutzt `on-request`: Jede Eskalationsanfrage beendet den Turn
  mit `approval_required` (fail-closed).
- Symphony entfernt das Tracker-Token vor dem Codex-Start aus der Umgebung
  (`unset`), Codex sieht `GITHUB_TOKEN` nicht.

## Ergebnis

| Grenze | Status | Mittel | Nachweis |
| --- | --- | --- | --- |
| Schreiben nur im Workspace des Issues | **erzwungen** | `turn_sandbox_policy` mit `writableRoots: []`; cwd ist der Issue-Workspace | Schreiben in `../GH-2`, `/tmp`, `$HOME`: verweigert; im eigenen Workspace: erlaubt |
| `/tmp` und `$TMPDIR` | **erzwungen** gesperrt | `excludeSlashTmp`, `excludeTmpdirEnvVar` | `/tmp`-Schreiben verweigert |
| `.git` im Workspace | **erzwungen** schreibgeschützt (Codex-Standard) | Codex-Sandbox | `git commit` scheitert mit `Read-only file system` |
| Netz nur GitHub und OpenAI | **erzwungen, mit Einschränkung** | `networkAccess: false` plus Codex-Netzwerk-Proxy (`features.network_proxy`, Profil `gmv_symphony` mit Domain-Allowlist) | `codeload.github.com` 301, `objects.githubusercontent.com` 404 (erreicht); `example.com`, `pypi.org` blockiert |
| Erreichbarkeit `github.com`, `api.github.com`, `api.openai.com` aus der Sandbox | **auf diesem Host nicht gegeben** | – | Diese Namen lösen auf dem Host auf `198.18.0.1` (Egress-Tunnel) auf. Der Codex-Proxy blockiert nicht-öffentliche Ziele (`CONNECT` 403) |
| Lesezugriff (z. B. App-Key, `gh`-Konfiguration) | **nicht erzwungen** | – | Mit Symphonys Turn-Policy ist Lesen vollständig erlaubt. Ein Profil mit `deny` wirkt nur ohne `sandboxPolicy`, die Symphony aber immer sendet |
| Kein Netz ohne aktiven Proxy | **erzwungen** (fail-closed) | `networkAccess: false` | Ohne Proxy-Konfiguration sind alle Ziele blockiert |

Hinweis: Der Modellverkehr von Codex zu `api.openai.com` läuft im
App-Server-Prozess, nicht in der Sandbox, und ist davon nicht betroffen.
Klon (`hooks.after_create`) und `github_api` laufen hostseitig außerhalb der
Codex-Sandbox. Der Klon nutzt kein Token.

## Prüfung im Repository

`python3 scripts/symphony_dispatch_gate.py validate-workflow <datei>` lehnt ab:
fehlende oder weitere Turn-Policy-Rechte, `networkAccess: true`, beschreibbares
`/tmp`, zusätzliche `writableRoots`, Workspace unter `/tmp`,
`approval_policy: never`, fehlenden Proxy, Allowlist ungleich GitHub/OpenAI,
Wildcards sowie `danger`/`bypass`-Flags.

## Host-Lösungen (Vorschlag, nicht umgesetzt)

1. **Lesezugriff auf Secrets** (ohne Root möglich): Symphony über den
   bestehenden Wrapper in `bwrap` starten, nachdem das Installation-Token
   erzeugt ist, und `~/secrets`, `~/.config/gh` sowie `~/.codex/sessions`
   per `--tmpfs` ausblenden. Codex selbst braucht nur `~/.codex/auth.json`.
   Sauberer, aber mit Root: eigener Unix-Nutzer `gmv-symphony` ohne Zugriff
   auf diese Pfade.
2. **Netz auf diesem Host**: Ein Egress-Proxy auf `127.0.0.1` (z. B. Squid
   oder tinyproxy als Nutzerprozess) mit derselben Allowlist als einziger
   Ausgang, im Codex-Proxy als Upstream. Alternativ die Sandbox auf einem Host
   betreiben, dessen DNS öffentliche Adressen liefert. Keine Aufweichung des
   Codex-Schutzes für private Adressbereiche.
3. **Durchsetzung auf Netzebene unabhängig von Codex** (Root): nftables-Regeln
   je Nutzer-ID, nur Ziel-Port 443 zu den Allowlist-Domains.

Bis eine dieser Lösungen umgesetzt ist, gilt: Die Lesegrenze ist nur
dokumentiert, nicht erzwungen.
