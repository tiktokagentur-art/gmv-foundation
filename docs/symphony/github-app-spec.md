# Symphony GitHub App – Spezifikation

Status: **App angelegt und installiert** (App-ID `5899252`, Installation
`185263574`, beides keine Secrets). Dieser PR legt nichts an und enthält keinen
Private Key. Seit 24.11.2026 bezieht Symphony sein Token nur noch über diese
App; **das persönliche Admin-Token wird nicht mehr verwendet.**
Bezug: Notion ENG-003, Issue #74, PR #66, Review-Befund 5
(`github_api` lief im Pilot hostseitig mit den Rechten eines persönlichen
Kontos).

Vorbild ist die App `gmv-github-moderator` ([../github-moderator.md](../github-moderator.md)):
eigene technische Identität, Installation nur auf einem Repository,
Private Key nur außerhalb des Repositorys, kein Bypass in Rulesets.

## Zweck

Symphony liest über diese App ausschließlich Issues des Pilot-Repositorys
(Polling des Trackers, Kontext für den Prompt). Zuweisung, Claim, Lease und
Fencing bleiben bei der Control Plane (ADR-0003). Die App schreibt nichts.

## Stammdaten

| Feld | Sollwert |
| --- | --- |
| Name | `gmv-symphony-worker` |
| Eigentümer | Konto `tiktokagentur-art` |
| Sichtbarkeit | Nur dieses Konto (*Only on this account*), keine öffentliche App |
| Installation | *Only select repositories*: genau `tiktokagentur-art/gmv-foundation` |
| Webhook | Deaktiviert (*Active* aus), keine Webhook-URL, kein Webhook-Secret |
| Callback-URL / OAuth bei Installation | Keine / aus |
| Device Flow | Aus |
| User-to-Server-Tokens | Nicht genutzt; Symphony arbeitet nur mit Installation-Tokens |

## Rechteliste (Phase B, read-only)

Alle nicht genannten Permissions bleiben **No access**.

| Permission | Level | Begründung |
| --- | --- | --- |
| Repository: Metadata | Read | Pflicht für jede GitHub App; Repository-Grunddaten |
| Repository: Issues | Read | Tracker-Polling: offene Issues mit Label `gmv-symphony-pilot`, Titel, Beschreibung, Zustand |

Bewusst **nicht** vergeben:

| Permission | Level | Begründung für den Verzicht |
| --- | --- | --- |
| Repository: Contents | No access | Repo ist öffentlich; der Klon im Hook `after_create` läuft ohne Token |
| Repository: Issues | kein Write | Statusübergänge besitzt die Control Plane, nicht Symphony |
| Repository: Pull requests | No access | Erst Phase C (Draft-PRs) nach separatem CEO-Go |
| Repository: Administration | No access | Settings/Rulesets sind Sache von `gmv-github-moderator` |
| Repository: Actions, Workflows, Secrets, Variables, Environments | No access | Keine CI-, Secret- oder Deploy-Wirkung |
| Repository: Checks, Commit statuses, Deployments | No access | Kein Einfluss auf Merge-Gates |
| Organization- und Account-Permissions | No access | Kein Org-Zugriff (im Pilot hatte das Konto `admin:org`) |

## Events

Keine Webhook-Events abonniert. Symphony pollt den Tracker. Damit gibt es
keinen eingehenden Endpunkt und kein Webhook-Secret. Sollte später ein
Event-Pfad nötig sein (`issues`, `issue_comment`), gehört er an die Control
Plane und braucht eine eigene Review.

## Token-Ausgabe

- Installation-Token nur hostseitig im Dispatch-Gate bzw. Orchestrator erzeugen,
  nie im Codex-Workspace, nie in Logs, `GITHUB_OUTPUT`, Artefakten oder Prompts.
- Bei jeder Token-Anforderung zusätzlich herunterskalieren:
  `repositories: ["gmv-foundation"]`, `permissions: {"issues": "read", "metadata": "read"}`.
- Lebensdauer: GitHub-Standard (1 Stunde), kein Caching über den Lauf hinaus.
- In der Workflow-Vorlage bleibt `token: "$GITHUB_TOKEN"` eine Env-Referenz.

Umsetzung: `scripts/symphony_app_token.py` (Tests ohne echten Key:
`tests/test_symphony_app_token.py`).

- Pro Lauf ein JWT (RS256, `exp` 9 Minuten nach Ausstellung, `iat` 60 Sekunden
  zurückdatiert, also unter 10 Minuten). Signiert wird per `openssl`; der Key
  wird nicht in den Prozess geladen. Key-Datei muss `600` und dem Nutzer gehören.
- Die Token-Antwort muss exakt `issues: read`, `metadata: read` und genau
  `tiktokagentur-art/gmv-foundation` enthalten, sonst Widerruf und Abbruch.
- `exec -- <befehl>` übergibt das Token nur als `GITHUB_TOKEN` in der
  Prozessumgebung des Kindes. Geerbte `GITHUB_TOKEN`/`GH_TOKEN`, die
  `gh`-Konfiguration (`GH_CONFIG_DIR` leer) und der globale
  Git-Credential-Helper (`GIT_CONFIG_GLOBAL` leer) werden ausgeblendet.
  Wichtig, weil Symphony bei fehlender Variable auf `GITHUB_TOKEN` zurückfällt
  und der Host-Git-Helper sonst das Admin-Token liefert.
- Nach Ende des Kindprozesses (auch bei Absturz) `DELETE /installation/token`
  mit Wiederholung.
- `selftest` erzeugt ein Token, prüft `GET /installation/repositories`,
  widerruft und prüft danach `401`. Ausgegeben werden nur Länge, Ablaufzeit,
  Rechte und Repository-Namen.

Ein Symphony-Start auf dem Host läuft nur über einen Wrapper, der diesen
Helfer aufruft und ohne ausdrückliche Startfreigabe abbricht.

## Live-Rechte lesend nachweisen

`scripts/symphony_app_audit.py` ruft per App-JWT (RS256, unter 10 Minuten)
nur `GET /app` und `GET /app/installations` auf. Ausgegeben werden Slug,
Owner, App-Rechte, Events und je Installation Konto, `repository_selection`,
Rechte und `suspended_at`. Es entsteht kein Installation-Token, JWT und Key
erscheinen nie in der Ausgabe. Die Repository-Liste je Installation liefert
`symphony_app_token.py selftest` (Token holen, lesen, sofort widerrufen).

```text
python3 scripts/symphony_app_audit.py
python3 scripts/symphony_app_token.py selftest
```

Stand 24.11.2026 (Host, lesend): Slug `gmv-symphony-worker`, Owner
`tiktokagentur-art`, App-Rechte und Installationsrechte jeweils
`issues: read`, `metadata: read`, keine Events, eine Installation
(`185263574`, `repository_selection: selected`, nicht suspendiert).
Selbsttest: Repositories `tiktokagentur-art/gmv-foundation`,
`revoked: true`, `after_revoke_http: 401`.

**Warum `GET /apps/gmv-symphony-worker` 404 liefert:** Der Slug stimmt. Die
App ist privat (nur im Owner-Konto installierbar). Der öffentliche Endpunkt
`GET /apps/{slug}` liefert für private Apps ohne passende Authentifizierung
404. Lesbar ist die App über `GET /app` mit App-JWT; genau das macht das
Audit-Skript und meldet den 404 zusätzlich als `public_apps_slug_http`.
Für Prüfende ohne Key: App-Einstellungen in der GitHub-Oberfläche unter
Organisation → Settings → Developer settings → GitHub Apps →
`gmv-symphony-worker` → Permissions & events.

## Private Key und Ablage

- Private Key nur im Secret Store des Orchestrator-Hosts (ADR-0007 offen),
  nicht im Repository, nicht als Repository-Secret, nicht im Codex-Workspace.
- Client-ID ist kein Secret und darf als Variable abgelegt werden.
- Rotation: bei Verdacht sofort, sonst mit dem Moderator-Rhythmus.

## Rulesets und Bypass

Die App wird **nicht** in `bypass_actors` aufgenommen. Der Moderator-Audit
erwartet `bypass_actors` exakt `[]` und meldet jede App als Drift.

## Phase C (nur nach separatem CEO-Go, nicht beantragt)

Für kontrollierte Draft-PRs kämen hinzu: Contents Read and write (nur
Feature-Branches, `main` bleibt durch Ruleset geschützt) und Pull requests
Read and write. Das ist eine Rechteerweiterung und braucht eine eigene
Freigabe.

## Anlage-Checkliste

- [ ] Rechteliste und Verzichte geprüft (Petrus)
- [x] App angelegt (App-ID `5899252`)
- [x] Installation nur auf `gmv-foundation` (Selbsttest 24.11.2026,
  `GET /installation/repositories` liefert genau dieses Repo)
- [x] Token-Rechte exakt `issues: read`, `metadata: read` (Selbsttest 24.11.2026)
- [x] Private Key in der Host-Secret-Ablage (Rechte `600`), nicht im Repo
- [ ] Webhook aus und Stammdaten in den App-Einstellungen bestätigen (Petrus)
- [ ] Moderator-Audit nach Installation: `bypass_actors` weiterhin `[]`
- [ ] Persönliches `gh`-Token des Hosts (Stand 24.11.2026: Scopes `gist`,
  `read:org`, `repo`, `workflow`, kein `admin:org` mehr): Symphony nutzt es
  nicht (im Namespace ausgeblendet). Es dient nur dem Operator auf dem Host
  (Label-Prüfung und -Entfernung, Branches und PRs). Widerruf oder Ersatz ist
  eine separate Entscheidung.
