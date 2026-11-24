# Railway-Kopplung an `main` (Audit zu #70)

Read-only-Readback vom 24.11.2026, etwa 23:30 Uhr (Europe/Berlin), über den
Railway-Connector und die GitHub-API. Es wurde nichts an Railway, GitHub-Rulesets,
Environments oder Secrets geändert. Secret-Werte stehen hier nicht.

## Ist-Zustand

| Projekt / Umgebung | Service | Quelle laut Railway | Trigger-Befund | Letztes Deployment |
| --- | --- | --- | --- | --- |
| GMV Forge / production | `gmv-foundation` | Repo verbunden, **kein Branch** gesetzt | Kein Branch-Autodeploy; seit 20.11. kein Production-Deployment trotz vieler Merges auf `main` | 20.11.2026, 10:14 Uhr, `3c585c7`, FAILED |
| GMV-V3 / staging | `backend` | `main`, `checkSuites=true` | Autodeploy bei jedem Merge auf `main`, erst nach grüner CI | 24.11.2026, 21:51 Uhr, `e003041`, SUCCESS |
| GMV-V3 / staging | `aline-openai-worker-l1` | Branch `prototype/aline-openai-worker-l1`, fester Commit | Kein Bezug zu `main`; Neustart-Policy `NEVER` | 20.11.2026, 05:03 Uhr, SUCCESS |

Weitere Befunde:

- Production hat keine Domain, keine TCP-Proxys, keine Volumes und keine
  Service-Variablen. Ein kundenwirksamer Endpunkt ist nicht nachgewiesen.
- In GMV Forge gibt es keine Railway-Webhooks; im Repository gibt es keine
  Repository-Webhooks und keinen Workflow, der nach Railway deployt.
  Deployments löst allein die Railway-GitHub-App aus.
- Die GitHub-Environments `GMV Forge / production` und `GMV-V3 / staging`
  legt Railway an. Sie haben keine Schutzregeln.
- Am 22.11.2026 zeigte Production noch `main` als Quellbranch. Die Entkopplung
  des Triggers erfolgte danach außerhalb des Repositorys; ein leerer
  Railway-Patch in Production ist auf den 24.11.2026, 16:52 Uhr, datiert.

## Bewertung

Ein Merge auf `main` löst derzeit **kein** Production-Deployment aus.
Staging folgt `main` absichtlich und wartet auf grüne CI.
Offen bleiben: Das Repository ist an Production weiterhin angebunden, ein
manuelles Deployment oder Redeploy ist also möglich, und eine Release-Autorität
nach [ADR-0011](../adr/0011-release-rollback-authority.md) ist noch nicht
entschieden.

## Entscheidungsvorlage

Jede Änderung an Railway braucht die ausdrückliche Freigabe des CEO.

1. **Option A – keine Mutation:** Ist-Zustand dokumentieren, regelmäßig
   nachlesen. Kein Risiko für den Betrieb, manuelles Deployment bleibt möglich.
2. **Option B – Production-Quelle trennen:** In GMV Forge die Repo-Verbindung
   lösen. Damit ist kein Deployment aus GitHub mehr möglich, bis ein Release
   nach ADR-0011 sie bewusst wiederherstellt. Kleine, umkehrbare Änderung.
3. **Option C – GMV Forge stilllegen:** Projekt entfernen, weil es weder Domain
   noch Variablen noch ein laufendes Release trägt. Nicht umkehrbar, erst nach
   der Entscheidung zu ADR-0011.

Empfehlung: sofort Option A, Option B als nächster freizugebender Schritt.
Staging unverändert lassen; ein eigener Release-Branch für Staging ist erst
mit ADR-0011 sinnvoll.
