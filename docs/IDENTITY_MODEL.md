# Identitätsmodell

Vertrag für V1. Die Prüfung ist serverseitig. Der Client, der Worker und ein
Proxy entscheiden keine Zustandsänderung. Workloads weisen sich mit einem
API-Key je Identität aus
([ADR-0008](adr/0008-auth-standard.md), Accepted für Workloads). Menschen-Logins
sind zurückgestellt. Die Autorisierung einer Zustandsänderung bleibt in der
besitzenden Instanz.

## Arten

Eine Identity hat genau eine Art. Menschen und Workloads sind verschiedene
Subjekte. Eine Identität wird nicht geteilt.

| kind | Bedeutung | Constraints |
| --- | --- | --- |
| human | Mensch | darf nicht `kind = worker` tragen und keinen Worker registrieren |
| service | Dienst | eigene Identität je Dienst, nicht je Instanz geteilt mit einem Worker |
| worker | Worker | genau eine Identity je Worker, `Worker.identity_id` ist eindeutig |

Felder der Identity:

| Feld | Typ | Constraints |
| --- | --- | --- |
| id | uuid | unveränderlich |
| kind | string | `human`, `service` oder `worker` |
| subject | string | opak, eindeutig, Länge 1 bis 256, kein Geheimnis im Klartext des Vertrags |
| status | string | `active` oder `disabled` |
| roles | array of string | Menge der Rollen unten, keine Duplikate |

`subject` ist für Workloads der von der Control Plane vergebene `identity_id`.
Einen externen Aussteller für Menschen gibt es nicht, solange kein IdP
freigegeben ist. Ein Aufruf ohne von der Control Plane anerkannte Identity
endet mit `401`. Eine bekannte Identity ohne die nötige Rolle endet mit `403`.
Ein `disabled` Subjekt wird wie fehlende Berechtigung behandelt.

## Rollen

| Rolle | Darf beantragen |
| --- | --- |
| work_item_editor | WorkItem anlegen, Payload in `created` ändern, Übergänge mit `requested_by = work_item_editor`, Worker deaktivieren |
| worker | sich selbst registrieren, eigenen Heartbeat, Claim, Renew, Release, Start, Ergebnis |
| result_acceptor | `submitted` nach `done` oder `failed` |
| auditor | Audit lesen |
| assignment_authority | kein externer Aufrufer; der interne Lease-Ablauf der einen Authority |

Eine Worker-Identity trägt die Rolle `worker` und keine der Redaktionsrollen.
Die ausführende Worker-Identity ist nicht `result_acceptor` für dasselbe
WorkItem. Sie kann das eigene Ergebnis nicht selbst als `done` annehmen.

## Autorisierung jeder Zustandsänderung

Die Control Plane führt vor dem Schreiben aus:

1. Identity liegt vor und ist `active`
2. die Rolle ist die `requested_by`-Rolle des Übergangs in
   [WORKITEM_LIFECYCLE.md](WORKITEM_LIFECYCLE.md), oder die Operation unten
3. bei Worker-Operationen ist `identity_id` die Identity des Aufrufers
4. bei `start`, `renew`, `release` und `result` stimmen Lease und
   Fencing-Token
5. `If-Match` ist die aktuelle `resource_version`, sonst `409` `version_conflict`

Operationen, die keinen WorkItem-Übergang sind:

| Operation | Rolle | Wirkung |
| --- | --- | --- |
| Worker registrieren | worker | legt den eigenen Worker an, Status `registered` |
| Heartbeat | worker | setzt nur `last_heartbeat_at` des eigenen Workers |
| Renew | worker | verlängert `expires_at`, Token unverändert |
| Worker deaktivieren | work_item_editor | setzt Worker auf `disabled` und beendet eine aktive Zuweisung nicht |
| Audit lesen | auditor oder work_item_editor | kein Schreiben |

Eine deaktivierte Zuweisung entsteht nicht durch den Heartbeat. Läuft ein
Lease ab, gilt der Lebenszyklus, auch wenn der Worker noch Heartbeats sendet.

GF-008 setzt den Workload-Nachweis um: Präfix `gmv_wk_`, SHA-256-Hash,
einzelner Widerruf und optionales Ablaufdatum. Die Rollenregeln dieses
Vertrags bleiben die Autorisierung der besitzenden Instanz. Diesen Code
enthält der Vertrag nicht.
