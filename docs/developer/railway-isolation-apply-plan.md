# Railway Deployment Isolation V1: separater APPLY-Plan (#70)

Status: **VORLAGE, NICHT FREIGEGEBEN**. Dieser Plan autorisiert weder eine
Railway-Änderung noch einen Deploy. Vor Ausführung sind die unten genannten
Live-Gates und eine gesonderte CEO-Freigabe für den exakten Diff nötig.

## Scope und Ziel

| Korridor | Projekt | Umgebung | Service | Soll |
| --- | --- | --- | --- | --- |
| Staging | GMV-V3 | `staging` | `backend` | `main` nur mit nachweislich erfolgreicher CI; keine Production-Autorität |
| Production | GMV Forge | `production` | `gmv-foundation` | GitHub-Autodeploy ausdrücklich **aus**; Release nur nach gesondert beschlossener Autorität |

Der kleinste mögliche Railway-Diff ist ausschließlich das Abschalten des
GitHub-Autodeploy-Schalters für den **Production-Service**, sofern ein frischer
UI-/API-Readback ihn als eingeschaltet nachweist. Ist er bereits aus, entfällt
dieser APPLY. Ein fehlendes `source.branch`-Feld im API-Objekt ist kein Ersatz
für diesen Nachweis: Railway kann dann den GitHub-Default-Branch verwenden.
Repo-Verbindung, Branch, Staging, laufende Instanzen, Variablen, Secrets,
Volumes, Domains und Datenbank gehören nicht zu diesem Diff.

## Voraussetzungen und Stop-Kriterien

1. Aline/Deniz bestätigen aktuelle Zuteilung und WIP-Kapazität in der
   bestehenden Control Plane; GitHub-Issue-Zuweisung allein ersetzt diese nicht.
2. Railway-Admin gleicht im Dashboard für **beide exakten Scopes** die
   internen Projekt-/Service-IDs mit dem privaten Betriebsnachweis ab und
   liest Autodeploy-Schalter, Quellbranch/Default-Branch, Wait for CI, weitere
   Deployment-Trigger, laufende Revision, letzte erfolgreiche Revision,
   Rollback-Verfügbarkeit und ausstehende Änderungen mit UTC-Zeitstempel aus.
   `source.checkSuites` belegt nur Wait for CI, nicht Autodeploy.
3. Betriebsverantwortliche klären Kundenwirkung, Abhängigkeiten, benötigte
   Release-Frequenz und Bereitschaft zur Fehlerbeobachtung. Secret-Werte werden
   weder kopiert noch veröffentlicht.
4. CEO genehmigt den **konkreten** Production-Service-Diff und ein
   Ausführungsfenster gesondert. Unklare Trigger, widersprüchlicher Readback,
   fehlender Rollback-Nachweis oder fehlende Freigabe bedeuten STOP.

## Bedingter APPLY

1. Vorher-Zustand mit Service-ID, UI-Screenshot oder API-Antwort,
   Zeitstempel und Bearbeiter im privaten Betriebsnachweis sichern.
2. Nur wenn `Auto deploy` **enabled** ist: In GMV Forge / production /
   `gmv-foundation` den Schalter auf **disabled** setzen. Kein `Deploy Latest
   Commit`, `Redeploy`, Repository-Disconnect oder `Accept staged changes`.
3. Den Schalter unmittelbar am gleichen Service erneut lesen. Prüfen, dass
   sich weder Deployment-ID noch aktive Revision noch Replica-Zustand
   unerwartet geändert haben. Railway-Audit-Eintrag erfassen, soweit die
   Kontoberechtigung dies erlaubt.
4. Staging separat read-only prüfen; dessen Konfiguration bleibt in diesem
   APPLY unverändert. Einen Test-Push nach `main` ausdrücklich unterlassen.

Falls der Schalter bereits disabled ist: `NO_OP` protokollieren und
Vorher-/Nachher-Readback ohne Mutation belegen.

## Auswirkungen und Risiken

- Bei abgeschaltetem Autodeploy erreicht neuer Code Production nicht über
  diesen Railway-GitHub-Push-Trigger. Manuelle Railway-Aktionen oder externe
  CI-/API-Trigger müssen gesondert inventarisiert und berechtigt werden.
- Das Abschalten kann eine bisher verwendete Release-Routine unterbrechen.
  Deshalb Betriebsowner vorab benennen. Ein Konfigurationswechsel kann in
  Railway unerwartete Pending Changes erzeugen; nichts pauschal übernehmen.
- Der aktuelle Repository-Stand enthält keinen Production-Release-Workflow.
  ADR-0011 ist `Proposed`; dieser APPLY schafft keine Production-Freigabe.

## Rückroll- und Incident-Verfahren

**Konfigurationsrücknahme:** Autodeploy nicht automatisch wieder einschalten.
Bei einem unerwarteten Betriebsproblem zuerst Zustand, Deployment-ID und
Konfigurationsdiff sichern; Deniz und CEO entscheiden über einen neuen,
gesondert autorisierten Änderungsplan. Das Wiedereinschalten würde die
ungeprüfte Kopplung an GitHub wiederherstellen.

**Anwendungs-Rollback:** Vor jeder späteren Production-Freigabe sind exakter
Commit-SHA und, bei Images, Digest des zuvor erfolgreichen Releases sowie
Railway-Deployment-ID und Schema-/Datenbank-Kompatibilität festzuhalten. Ein
Railway-Rollback ist nur möglich, solange das frühere Image verfügbar ist;
seine Retention hängt vom Plan ab. Er stellt keine Datenbank wieder her und
kann frühere Variablen zurückbringen. Ist das Image abgelaufen, braucht es
einen neu gebauten, gesondert autorisierten Release-Pfad; ein beliebiger
`main`-Build ist kein reproduzierbarer Rollback. Für Datenbank-Restore gilt
ADR-0006 und eine eigene CEO-Entscheidung.

## Abnahme und Evidenz

Die ausführende Person protokolliert vor/nach: Projekt-, Environment- und
Service-ID; Autodeploy und Wait for CI; Quellbranch; ausstehende Änderungen;
aktive und letzte erfolgreiche Deployment-ID samt SHA/Digest, soweit verfügbar;
UTC-Zeit; Autorisierungsnachweis; unerwartete Deployments/Restarts; und
GitHub-/Railway-Audit-Referenzen. Der Production-Trigger gilt erst nach
Readback und Prüfung anderer Trigger als `LIVE_VERIFIED`. Offline-Tests der
Repository-Policy sind nur `OFFLINE_VERIFIED`. Bis zur Entscheidung von
ADR-0011 und Prüfung von #68 bleiben autonome Merges und Production-Releases
gesperrt.
