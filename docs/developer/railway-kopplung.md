# Railway-Kopplung an `main` (Audit zu #70)

Stand: Read-only-Beobachtung am 25.11.2026 gegen 23:59 UTC. Dieser Audit ergänzt den am 24.11.2026
gemergten Audit aus PR #136. Keine Railway-, GitHub-Ruleset-, Secret- oder
IAM-Änderung wurde für diesen Nachtrag ausgeführt. Der Zeitstempel stammt aus
der Audit-Sitzung, nicht aus einem `readAt`-Feld der Railway-API.

## Verifizierte Konfiguration

| Scope | Railway-Quelle | CI-Wartefunktion | Deployment-Befund |
| --- | --- | --- | --- |
| GMV-V3 / staging / `backend` | `tiktokagentur-art/gmv-foundation`, Branch `main` | `source.checkSuites=true` | SHA `dd3217d7a2ab9d21ad2955f21427aec7718d943e`, 25.11.2026 03:13 UTC, SUCCESS; 1/1 online. |
| GMV Forge / production / `gmv-foundation` | Dasselbe Repo; `source.branch` fehlt im Connector-Objekt | `source.checkSuites` fehlt im Connector-Objekt | Letzter Versuch zu SHA `3c585c7cf167ade171282a495b7b211284c15778` am 20.11. FAILED. SUCCESS-Deployment zu SHA `eb96d7c714e5557e5c4caeef2e1870faf44c95a7` läuft mit 1/1 Replica. |

Railway meldet für Production keine ausstehenden Änderungen über
`get-staged-changes` und `describe-environment`. `environment-status` meldet
dagegen einen leeren Pending-Patch mit 0 Änderungen. Der Widerspruch muss vor
jedem APPLY im Dashboard aufgelöst werden. Der Production-SUCCESS-Deploy ist
laut Deployment-Liste derzeit rollbackfähig (`canRollback=true`); die
Image-Retention und Datenbank-Kompatibilität sind damit nicht belegt.

## Trigger-Befund und Beweisgrenzen

- Railway hat einen **separaten Autodeploy-Schalter**. Der verfügbare Connector
  exponiert ihn nicht. `source.branch` ohne Wert beweist keine Abschaltung;
  laut Railway-Source-Dokumentation kann dann der GitHub-Default-Branch gelten.
  Die Aussage des früheren Audittexts, dass deshalb kein Branch-Autodeploy
  möglich sei, wird zurückgenommen. Ein Dashboard-Readback vom 24.11. meldete
  zwar „Auto deploy is disabled“ (Issue #70), dieser Schalter konnte am
  25.11. mit dem verfügbaren Zugriff nicht erneut gelesen werden.
- Dass seit dem 20.11. kein neues Production-Deployment in der abgefragten
  Historie erscheint, obwohl `main` weiterlief, ist **Beobachtung**, kein
  Nachweis der Ursache und kein Test aller künftigen Trigger. Ein Merge nach
  `main` kann deshalb gegenwärtig nicht belastbar als ungefährlich abgenommen
  werden.
- Staging ist mit `main` und `checkSuites=true` verbunden. Die erfolgreiche
  Deploy-Historie ist mit einem Railway-GitHub-Trigger vereinbar. `Wait for CI`
  ist keine Release-Freigabe; Railway behandelt bestimmte neutrale oder
  übersprungene Check-Suites als nicht blockierend.
- Im aktuellen Repository gibt es keinen Railway-Deployment-Workflow. Beide
  Railway-Projekte melden keine Railway-Webhooks. Die GitHub Environments
  `GMV Forge / production` und `GMV-V3 / staging` haben aktuell keine
  Schutzregeln oder Branch-Policy. Ein manuelles Railway-Deploy oder ein
  externer API-Trigger ist damit nicht ausgeschlossen. Ein aktueller Readback
  der Repository-Webhooks und GitHub-Actions-Berechtigungen scheiterte mit
  HTTP 403 (`Resource not accessible by integration`).
- Production meldet keine Domain; Staging `backend` hat eine Railway-Domain.
  Daraus folgt keine bestätigte
  Kundenwirkung oder fehlende interne Abhängigkeit; beides ist vor APPLY zu
  prüfen.

## GitHub- und Architektur-Gates

`main` stand beim Preflight auf
`dd3217d7a2ab9d21ad2955f21427aec7718d943e` und hatte erfolgreiche
Pflicht-CI ([Run 45538437087](https://github.com/tiktokagentur-art/gmv-foundation/actions/runs/45538437087)). Das aktive [Ruleset #26896505](https://github.com/tiktokagentur-art/gmv-foundation/rules/26896505) verlangt Pull Requests und die
strikten Checks `Lint and structure`, `Backend`, `Image`, jedoch 0 formale
Approvals. Auto-Merge ist aus. ADR-0011 zur Production-Release-/Rollback-
Autorität ist weiterhin `Proposed`. Symphony besitzt kein implementiertes
Control-Plane-Release-Gate. #68 bleibt vor Aktivierung autonomer Merges
abhängig von diesem P0-Gate.

Die direkte CEO-Auftragsnachricht benennt Codex als Ausführenden, Deniz als
technisch Verantwortlichen und Aline als Koordinatorin. Issue #70 hat keinen
sichtbaren GitHub-Assignee. GitHub Project-V2-Einträge und damit die aktuelle
WIP-Kapazität konnten wegen HTTP 403 nicht gelesen werden. Es gab beim
Preflight 29 offene Pull Requests, darunter den Draft #69 zu #68. Der frühere
Der Audit-PR #136 zu Issue #70 ist gemergt. Dies sind Zugriffs- und Kapazitätsgrenzen,
keine Bestätigung einer Control-Plane-Claim- oder Lease-Zuteilung.

## Zielarchitektur und Freigabegrenze

GitHub bleibt Codequelle; Codex arbeitet nur auf Feature-Branches und reicht
Änderungen per Pull Request mit exakter Head-SHA und den geltenden strikten
CI-Checks ein. Staging darf einen gesondert abgenommenen `main`-Korridor mit
CI-Wartefunktion haben. Für Production bleibt Railway-Autodeploy aus. Eine
separate, serverseitig überprüfbare Release-Autorisierung muss vor jedem
Production-Deploy an die in ADR-0011 erst noch zu benennende Rolle und die
bestehende Control Plane gebunden werden. Die Prüfungen verwenden exakte
Commit-SHA und, bei Images, Digest; fehlende oder widersprüchliche Evidenz
sperrt. Doppelte Anfragen werden offline gegen Railway-Deployment-Readback
geprüft. Parallele Rennen erfordern später atomare Claims, Leases und Fencing
der bestehenden Control Plane. Rollback benötigt eine bekannte,
zuvor freigegebene Deployment-ID und einen Schema-/Datenbank-Plan.

Die Repository-Policy und ihre Mock-Tests sind ausschließlich offline
auswertbar. Ohne beschlossene ADR-0011, geschütztes Production-Environment,
geprüfte Railway-Einstellungen und authentifizierte Control-Plane-Integration
gibt es keinen aktivierten Production-Release-Pfad. Die bestehenden GitHub
Environments ohne Schutzregeln dürfen nicht als Freigabe ausgegeben werden.

## Abnahmestand

| Kriterium | Stand am Audit-Tag |
| --- | --- |
| Railway-Projekte, Service-Quelle, Deployments | `LIVE_VERIFIED` für die oben genannten API-Felder; Autodeploy-Schalter offen |
| Tatsächlicher Production-Push-Trigger | `BLOCKED` bis Dashboard-Readback; historische `main`-Deployments belegt |
| Staging/Production-Korridore | Getrennte Projekte belegt; wirksame Release-Trennung offen |
| Unkontrollierte Production-Deployments ausgeschlossen | Offen: keine Live-Abnahme |
| Release-Autorität | Offen: ADR-0011 `Proposed` |
| PR-Head-CI und Negativtests | Nach Erstellung des Draft-PR separat zu belegen |
| Rollback | Frühere Deployment-ID und Railway-Option belegt; reproduzierbarer Betriebsablauf offen |
| Keine redundante Infrastruktur | Repository-Vorbereitung nutzt bestehende CI und Control Plane |

## Nächster Schritt

Den aktuellen Autodeploy-Schalter beider exakten Service-Scopes im Railway-
Dashboard mit Zeitstempel und prüfbarem Nachweis auslesen. Externe Trigger,
aktive Revision, Rollback, Berechtigungen und den leeren Pending-Patch prüfen.
Der [separate APPLY-Plan](railway-isolation-apply-plan.md) beschreibt den
bedingten kleinsten Production-Diff und die erforderliche CEO-Freigabe. Bis
zur Live-Abnahme bleibt der Status dieses Triggers **nicht LIVE_VERIFIED**.
