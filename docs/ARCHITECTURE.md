# Architektur

Landkarte von Greenfield V1. Dieses Dokument legt Grenzen und Begriffe fest.
Es ist kein Schnittstellenvertrag, kein Schema und keine Betriebsanleitung.

Legacy-Systeme werden nicht abgebildet und nicht importiert. Sie sind historische
Referenz außerhalb dieses Repository.

## Leitsatz

Build first. Verify everything. Scale after proof.

Zuerst eine nachprüfbare Instanz je Zustandsdomäne. Skalierung, zusätzliche
Regionen und zusätzliche Laufzeiten erst, wenn diese Instanz nachgewiesen ist.
Ein zweiter Schreiber ist keine Skalierung.

## Schichten

Die fünf Schichten haben getrennte Verantwortungen. Eine Schicht ersetzt die
andere nicht.

### Foundation

Die Foundation definiert, was gilt:

- Architektur und Grenzen, dieses Dokument
- Governance, [GOVERNANCE.md](GOVERNANCE.md)
- Sicherheitsregeln, [../SECURITY.md](../SECURITY.md)
- Daten- und API-Verträge, sobald sie geschrieben sind
- das Identitätsmodell, soweit es entschieden ist
- versionierte Entscheidungen unter [adr/](adr/README.md)

Die Foundation betreibt keinen Dienst und hält keinen Laufzeitzustand.

### Infrastructure

Die Infrastructure implementiert die Verträge der Foundation und weist sie durch
Tests nach. Dazu gehören Railway-Dienste, PostgreSQL direkt auf Railway, Backups,
Secrets, Deployments, Monitoring und Wiederherstellung.

Sie führt keine zweite fachliche Wahrheit ein. Eine Datenbankmigration ändert das
Schema der einen Datenbank. Sie ist kein zweiter Eigentümer des Zustands.

In `staging` des Railway-Projekts GMV-V3 laufen die Dienste `backend` und
Postgres (Railway-Readback am 10.11.2026, Europe/Berlin).
[ADR-0005](adr/0005-railway-environments.md) dokumentiert Projekt und Umgebung.
Backup, Production und Limits bleiben offene Punkte.

### Control Plane

Die Control Plane besitzt die fachlichen Zustandsdomänen der Arbeitsverteilung:

- WorkItems und ihren Status
- die Assignment Authority
- die Registrierung von Workern
- Authentisierung und Autorisierung an der Grenze dieser Domänen
- Claims, Leases und Fencing
- den Audit-Trail dieser Zustandsänderungen

Worker und Clients senden Anträge. Die Control Plane nimmt sie an oder lehnt sie ab.

### Worker Runtime

Die Worker Runtime führt Arbeit aus, die an eine Identität gebunden ist.
Sie sendet Heartbeats und gibt Ergebnis oder Fehler ab. Sie besitzt den
WorkItem-Status nicht und schreibt die Datenbank der Control Plane nicht direkt.

Fehlerbehandlung des Workers endet bei der Meldung. Ob die Arbeit erneut
vergeben, beendet oder angehalten wird, entscheidet die Instanz, der die Domäne
gehört. Eine Wiederholungsrichtlinie ist noch nicht festgelegt.

### Software Factory

Die Software Factory ändert das System kontrolliert: Änderung, Test, CI, Pull
Request, unabhängige Review, gesteuertes Release.

Ein Merge nach `main` ist noch kein Produktionsrelease. Wer ein Release oder
einen Rollback auslösen darf, ist offen
([ADR-0011](adr/0011-release-rollback-authority.md)).

## Zustandsregel

Je Zustandsdomäne gibt es genau eine autoritative Instanz. Die Regel ist
[ADR-0003](adr/0003-single-assignment-authority.md) und gilt für jede spätere
Schicht.

Die Foundation definiert die Verträge dieser Domänen. Die Infrastructure
implementiert genau diese Verträge und testet sie. Ein Test, ein Cache, ein Log
oder ein Worker darf den Zustand nicht abweichend festlegen.

Eine Domäne zu teilen heißt: zwei Domänen mit je einem Eigentümer benennen.
Es heißt nicht: zwei Schreiber für dieselbe Domäne.

## Zustandsdomänen

Die Domänen sind benannt, damit später niemand eine zweite Quelle anlegt.
Felder und Endpunkte der V1 stehen in [DATA_MODEL.md](DATA_MODEL.md) und
[API_SPECIFICATION.md](API_SPECIFICATION.md). Eine Datenbanktabelle dafür gibt
es nicht.

| Domäne | Eigentümer | Nicht Eigentümer |
| --- | --- | --- |
| WorkItem-Lebenszyklus und Status | Control Plane | Worker, Client, Cache |
| Zuweisung, Lease, Fencing | Assignment Authority innerhalb der Control Plane | Worker Runtime |
| Worker-Registrierung und Identität des Workers | Control Plane | der Worker selbst |
| Audit-Trail der angenommenen Zustandsänderungen | Control Plane | Logs der Aufrufer |
| Datenbankschema | die eine PostgreSQL-Datenbank auf Railway | eine zweite Datenbank oder ein zweites führendes Schema |

Die Assignment Authority ist die einzige Instanz, die Arbeit zuteilt und eine
Zuteilung zurücknimmt. Es gibt sie einmal im System, nicht einmal pro Worker.

## Identität

Für Workloads entschieden
([ADR-0008](adr/0008-auth-standard.md), [../SECURITY.md](../SECURITY.md)):

- Jeder Dienst und jeder Worker hat eine eigene Identität und eigene API-Keys.
- Menschen und Workloads sind verschiedene Subjekte. Menschen-Logins sind zurückgestellt.
- Jede Zustandsänderung wird von der besitzenden Instanz autorisiert.
- Ein Antrag ohne passende Identität, ohne gültigen Lease oder ohne gültiges
  Fencing ändert nichts.

Der Nachweis eines Workloads ist ein API-Key mit dem Präfix `gmv_wk_`. Die
Control Plane speichert nur den SHA-256-Hash. OAuth Client Credentials mit
`private_key_jwt` folgt, sobald externe Worker hinzukommen. Ein IdP für
Menschen braucht die Freigabe der CEO.

## Verträge

Die V1-Verträge stehen in [DATA_MODEL.md](DATA_MODEL.md),
[WORKITEM_LIFECYCLE.md](WORKITEM_LIFECYCLE.md),
[IDENTITY_MODEL.md](IDENTITY_MODEL.md) und
[API_SPECIFICATION.md](API_SPECIFICATION.md). Die Endpunkte sind nicht
implementiert. Kompatibilität der Datenbankmigration bleibt offen
([ADR-0009](adr/0009-migration-compatibility.md)).

## Ablauf einer Arbeit

Der Ablauf bleibt die Regel. Pfade, Felder und der Fencing-Token als Zahl stehen
im V1-Vertrag. Eine Datenbanktabelle dafür gibt es nicht.

1. Ein WorkItem entsteht nur bei der Instanz, die diese Domäne besitzt.
2. Die Assignment Authority vergibt höchstens eine aktive Zuweisung.
3. Der Worker weist seine Identität nach. Die Authority legt einen Lease an und
   versieht ihn mit einem Fencing-Merkmal.
4. Ein Heartbeat meldet, dass der Worker lebt. Die Verlängerung des Lease ist
   ein eigener Antrag. Die Authority entscheidet und ändert dabei den
   Fencing-Token nicht.
5. Ergebnis oder Fehler wird nur angenommen, wenn Identität, Lease und Fencing
   noch zur selben Zuweisung gehören.
6. Jede Annahme schreibt einen Audit-Eintrag. Eine Ablehnung ändert den
   fachlichen Status nicht.
7. Ein abgelaufener oder ersetzter Lease schreibt nicht mehr.

`Claim` ist der Antrag des Workers, eine Zuweisung anzunehmen oder fortzusetzen.
`Lease` ist das zeitlich begrenzte Ausführungsrecht, das nur die Authority
vergibt. `Fencing` ist das Merkmal, ohne das ein verspäteter Worker nach Verlust
des Lease nicht mehr schreiben kann.

## Was diese Baseline nicht ist

Nicht enthalten und nicht nebenbei angelegt:

- Domänenmodell und fachliche API außer dem Workload-Nachweis `GET /v1/whoami`; Tabellen für WorkItem, Worker, Claim, Assignment und AuditEvent (die Tabelle `credentials` ist der Nachweis aus ADR-0008)
- Dienstlimits und eine Umgebung production (`staging` in GMV-V3 existiert, siehe [adr/0005-railway-environments.md](adr/0005-railway-environments.md); Region siehe [adr/0012-hosting-region-usa.md](adr/0012-hosting-region-usa.md))
- Backup-Lauf, konkrete RPO- oder RTO-Zahlen
- festgelegter Secret-Provider, Rotation, Break-glass-Verfahren
- Produktions-Deployment, Release, Rollback
- SLO-Zahlen, Alarmierungswege, Incident-Betrieb

Diese Punkte sind als offene ADRs geführt, nicht als stiller Default.
Siehe [adr/README.md](adr/README.md).
