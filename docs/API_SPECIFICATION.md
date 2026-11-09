# API-Vertrag

Verbindliche HTTP-API für V1. Die maschinenlesbare Fassung ist
[../api/openapi.yaml](../api/openapi.yaml), OpenAPI 3.1. Bezeichner sind
Englisch, Beschreibungen Deutsch. Die Endpunkte sind hier definiert und noch
nicht implementiert. `/health` und `/ready` gehören zum Skelett und liegen
nicht unter `/v1`.

Der Nachweis der Identity ist nicht gewählt
([ADR-0008](adr/0008-auth-standard.md)). Jeder Endpunkt unter `/v1` verlangt
trotzdem eine von der Control Plane anerkannte Identity. Fehlt sie, ist die
Antwort `401`. Die Rollen stehen in [IDENTITY_MODEL.md](IDENTITY_MODEL.md).

## Versionierung

Der Pfad beginnt mit `/v1`. Eine inkompatible Änderung, die Pflichtfelder
entfernt oder ihre Bedeutung ändert, ist eine neue Hauptversion `/v2`.
Innerhalb von `/v1` dürfen nur optionale Felder hinzukommen. Unbekannte Felder
in einem Request werden abgelehnt (`400`, `validation_error`). Unbekannte
Felder in einer Response derselben `schema_version` ignoriert ein Leser.

Ereignisse und Payloads tragen die Nummern aus [DATA_MODEL.md](DATA_MODEL.md).
Wie die Datenbank migriert wird, bleibt
[ADR-0009](adr/0009-migration-compatibility.md).

## Fehler

Jeder Fehlerkörper hat dieselbe Form. `code` ist stabil und Englisch.
`message` ist Deutsch und darf keine Secrets, Tokens oder
Verbindungsdaten enthalten.

| HTTP | code | Wann |
| --- | --- | --- |
| 400 | validation_error | Form oder unzulässiger Übergang |
| 401 | unauthorized | keine anerkannte Identity |
| 403 | forbidden | Identity ohne die nötige Rolle |
| 404 | not_found | die Ressource gibt es nicht |
| 409 | version_conflict | `If-Match` ist nicht die aktuelle `resource_version` |
| 409 | idempotency_conflict | derselbe Schlüssel, anderer Körper |
| 409 | fencing_rejected | Token fehlt, ist alt oder gehört zu einer beendeten Zuweisung |
| 409 | lease_expired | Lease ist abgelaufen |
| 409 | invalid_state | der Antrag passt nicht zum aktuellen Status |

## Idempotenz und Fassung

`Idempotency-Key` ist Pflicht bei jedem POST, der eine Ressource anlegt oder
einen Übergang beantragt. Der Schlüssel gilt je Identity, Methode und Pfad.
Dieselbe Kombination mit demselben Körper liefert dieselbe Antwort. Ein
anderer Körper mit demselben Schlüssel liefert `409` `idempotency_conflict`.
Heartbeat und GET brauchen keinen Schlüssel.

Ändernde Aufrufe senden `If-Match` mit der aktuellen `resource_version` in
Anführungszeichen, zum Beispiel `"3"`.

## Endpunkte

| Methode und Pfad | Wirkung |
| --- | --- |
| POST `/v1/work-items` | legt ein WorkItem in `created` an |
| GET `/v1/work-items` | Liste, optional nach `status`, Cursor `next_cursor` |
| GET `/v1/work-items/{work_item_id}` | ein WorkItem |
| PATCH `/v1/work-items/{work_item_id}` | nur `payload` und `payload_schema_version`, nur in `created` |
| POST `/v1/work-items/{work_item_id}/transitions` | Übergang außer Claim, Renew, Release und Ergebnis |
| POST `/v1/work-items/{work_item_id}/claims` | Claim; bei Annahme Zuweisung mit `expires_at` und neuem `fencing_token` |
| POST `/v1/workers` | registriert den aufrufenden Worker |
| GET `/v1/workers/{worker_id}` | ein Worker |
| POST `/v1/workers/{worker_id}/heartbeat` | setzt `last_heartbeat_at`, kein Lease, kein Token |
| POST `/v1/workers/{worker_id}/disable` | setzt `disabled` |
| GET `/v1/assignments/{assignment_id}` | eine Zuweisung |
| POST `/v1/assignments/{assignment_id}/renew` | verlängert `expires_at`, Token Pflicht und unverändert |
| POST `/v1/assignments/{assignment_id}/release` | Freigabe, Token Pflicht, WorkItem nach `ready` |
| POST `/v1/assignments/{assignment_id}/result` | Ergebnis, Token Pflicht, nach `submitted` oder `failed` |
| GET `/v1/audit-events` | liest den Audit-Trail, kein Schreiben |

Es gibt kein DELETE. Abbruch ist der Übergang nach `cancelled`.

Claim, Renew, Release und Ergebnis tragen den Fencing-Vertrag aus
[WORKITEM_LIFECYCLE.md](WORKITEM_LIFECYCLE.md). Der Claim-Request enthält
keinen Token. Die Antwort der Annahme enthält ihn. Renew, Release, Start und
Ergebnis müssen ihn senden. Start läuft über `transitions` mit `to_status =
in_progress`.
