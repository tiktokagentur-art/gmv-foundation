# Symphony GitHub App – Spezifikation (nicht angelegt)

Status: **Entwurf zur Review durch Petrus.** Die App wird mit diesem PR
**nicht** angelegt, nicht installiert und erhält keinen Private Key.
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

## Anlage-Checkliste für Petrus

- [ ] Rechteliste und Verzichte geprüft
- [ ] App mit obigen Stammdaten angelegt, Webhook aus
- [ ] Installation nur auf `gmv-foundation`
- [ ] Private Key im Host-Secret-Store, nicht im Repo
- [ ] Moderator-Audit nach Installation: `bypass_actors` weiterhin `[]`
- [ ] Persönliches Konto-Token aus dem Pilot widerrufen
