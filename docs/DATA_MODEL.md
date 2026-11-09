# Datenmodell

Verbindliche Kernentitäten für V1. Das sind Verträge, keine Datenbankmigration.
Ein Domänenschema in PostgreSQL bleibt unzulässig, bis
[ADR-0009](adr/0009-migration-compatibility.md) entschieden ist.
Die Assignment Authority ist genau eine
([ADR-0003](adr/0003-single-assignment-authority.md)).

Bezeichner und Typen sind Englisch. Zeiten sind RFC 3339 in UTC
(`format: date-time`). Identifikatoren sind UUID. `resource_version` beginnt
bei 1 und steigt bei jeder angenommenen Änderung der jeweiligen Entität um 1.

## Eigentümer

| Entität | Eigentümer | Schreibt nicht |
| --- | --- | --- |
| WorkItem | Control Plane | Worker, Client, Cache |
| Worker | Control Plane | der Worker selbst, andere Worker |
| Claim | Assignment Authority | der antragstellende Worker |
| Assignment | Assignment Authority | Worker, Client, Cache |
| AuditEvent | Control Plane | jeder Aufrufer |

Die Assignment Authority ist das einzige Modul der Control Plane für Claim,
Assignment, Lease und Fencing. Sie ist keine zweite Control Plane.

## WorkItem

Einheit der Arbeit. Der Status folgt [WORKITEM_LIFECYCLE.md](WORKITEM_LIFECYCLE.md).

| Feld | Typ | Constraints |
| --- | --- | --- |
| id | uuid | von der Control Plane vergeben, unveränderlich |
| status | WorkItemStatus | einer der Lebenszyklus-Zustände |
| work_type | string | Länge 1 bis 128, nach dem Anlegen unveränderlich |
| payload | object | JSON-Objekt, darf leer sein, keine Secrets |
| payload_schema_version | integer | mindestens 1 |
| resource_version | integer | mindestens 1, steigt nur bei angenommener Änderung |
| created_by | uuid | Identity, die den Anlegeantrag gestellt hat |
| created_at | date-time | unveränderlich |
| updated_at | date-time | Zeitpunkt der letzten angenommenen Änderung |

Constraints:

- höchstens eine `Assignment` mit `status = active` je WorkItem
- `status` ändert sich nur entlang der dokumentierten Übergänge
- `payload` und `payload_schema_version` sind nur in `created` änderbar
- physikalisch löschen ist nicht zulässig; Abbruch ist der Übergang nach `cancelled`

## Worker

Registrierte Ausführungskapazität mit eigener Identität.

| Feld | Typ | Constraints |
| --- | --- | --- |
| id | uuid | von der Control Plane vergeben, unveränderlich |
| identity_id | uuid | genau eine Identity mit `kind = worker`, eindeutig |
| status | string | `registered` oder `disabled` |
| registered_at | date-time | unveränderlich |
| last_heartbeat_at | date-time oder null | nur die Control Plane setzt den Wert |
| resource_version | integer | mindestens 1 |

Constraints:

- eine Identity gehört höchstens einem Worker
- ein `disabled` Worker erhält keine neue Zuweisung
- ein Heartbeat setzt nur `last_heartbeat_at` und verlängert keinen Lease

## Claim

Antrag eines Workers, ein `ready` WorkItem zu übernehmen. Der Antrag ändert
nichts, solange die Assignment Authority ihn nicht annimmt.

| Feld | Typ | Constraints |
| --- | --- | --- |
| id | uuid | unveränderlich |
| work_item_id | uuid | muss existieren |
| worker_id | uuid | Worker mit `status = registered` |
| idempotency_key | string | Länge 1 bis 128, eindeutig je Identity und Operation |
| requested_at | date-time | unveränderlich |
| decision | string | `accepted` oder `rejected`, nur die Authority setzt es |
| assignment_id | uuid oder null | gesetzt genau dann, wenn `decision = accepted` |
| decided_at | date-time | Zeitpunkt der Entscheidung |

## Assignment

Angenommene Zuweisung. Sie trägt Lease und Fencing-Token.

| Feld | Typ | Constraints |
| --- | --- | --- |
| id | uuid | unveränderlich |
| claim_id | uuid | genau ein angenommener Claim |
| work_item_id | uuid | unveränderlich |
| worker_id | uuid | unveränderlich, derselbe Worker wie im Claim |
| status | string | `active`, `expired`, `released` oder `superseded` |
| expires_at | date-time | Pflicht, bei Vergabe in der Zukunft |
| fencing_token | integer | mindestens 1, je WorkItem streng aufsteigend |
| granted_at | date-time | unveränderlich |
| ended_at | date-time oder null | gesetzt, wenn der Status nicht mehr `active` ist |
| resource_version | integer | mindestens 1 |

Constraints:

- je WorkItem höchstens eine Zeile mit `status = active`
- `fencing_token` wird bei `renew` nicht geändert
- ein beendeter Token wird nicht wiederverwendet
- `expires_at` darf nur durch ein angenommenes `renew` nach hinten gesetzt werden

## AuditEvent

Anhängend. Angenommene Zustandsänderungen erzeugen genau ein Ereignis.
Korrekturen sind neue Ereignisse. Es gibt kein Update und kein Delete.

| Feld | Typ | Constraints |
| --- | --- | --- |
| id | uuid | unveränderlich |
| schema_version | integer | mindestens 1, siehe Versionierung unten |
| occurred_at | date-time | Zeitpunkt der Annahme |
| actor_id | uuid | Identity, die den Antrag gestellt hat; beim Lease-Ablauf die Authority |
| action | string | Ereignisname, siehe unten |
| entity_type | string | `work_item`, `worker`, `claim` oder `assignment` |
| entity_id | uuid | betroffene Entität |
| resource_version | integer | `resource_version` der Entität nach der Änderung |
| from_status | string oder null | leer, wenn der Übergang keinen Status hat |
| to_status | string oder null | leer, wenn der Übergang keinen Status hat |
| fencing_token | integer oder null | Token der Zuweisung, wenn die Änderung eine betrifft |
| details | object | JSON ohne Secrets und ohne Verbindungsdaten |

Ereignisnamen in V1:

- `work_item.created`
- `work_item.transitioned`
- `work_item.lease_expired`
- `worker.registered`
- `worker.heartbeat`
- `worker.disabled`
- `assignment.granted`
- `assignment.renewed`
- `assignment.released`
- `assignment.expired`

## Versionierung der Ereignisse und Payloads

`payload_schema_version` und `AuditEvent.schema_version` sind ganze Zahlen ab 1.
Innerhalb derselben Nummer dürfen nur optionale Felder hinzukommen. Ein neues
Pflichtfeld oder eine geänderte Bedeutung erhöht die Nummer. Leser ignorieren
unbekannte Felder derselben Nummer. Sie müssen eine höhere Nummer nicht
verstehen.

Diese Konvention ist der V1-Vertrag. Sie entscheidet nicht
[ADR-0009](adr/0009-migration-compatibility.md): wie eine Änderung in
PostgreSQL ausgerollt und zurückgenommen wird, bleibt offen. Bis dahin wird
kein Domänenschema migriert.
