# WorkItem-Lebenszyklus

Verbindliche Zustandsmaschine für V1. Die Bezeichner sind Englisch.
Die Control Plane ist die einzige Instanz, die `WorkItem.status` schreibt
([ADR-0003](adr/0003-single-assignment-authority.md)). Die Assignment Authority
ist das einzige Modul innerhalb dieser Control Plane, das Zuweisung, Lease und
Fencing anwendet. Sie ist kein zweiter Schreiber.

Ein Aufrufer stellt einen Antrag. Die Control Plane prüft Rolle, Zustand,
Lease und Fencing und führt den Übergang aus oder lehnt ihn ab. Eine Ablehnung
ändert den Status nicht und erzeugt kein `AuditEvent`.

Die maschinenlesbare Fassung steht in `app/lifecycle.py`. CI vergleicht die
Tabellen unten mit diesem Modul und mit dem Enum in `api/openapi.yaml`.

## Zustände

- `created`: angelegt, noch nicht zuteilbar
- `ready`: zuteilbar, keine aktive Zuweisung
- `claimed`: eine aktive Zuweisung mit Lease und Fencing-Token
- `in_progress`: der Worker hat die Ausführung begonnen, der Lease gilt
- `submitted`: Ergebnis liegt vor, noch nicht angenommen
- `done`: Ergebnis angenommen, Endzustand
- `failed`: endgültig fehlgeschlagen, Endzustand
- `cancelled`: abgebrochen, Endzustand

Endzustände haben keinen Ausgang.

## Übergänge

`requested_by` ist, wer den Antrag stellen darf. Ausgeführt wird er nur von der
Control Plane. `assignment_authority` in dieser Spalte ist der interne
Lease-Ablauf derselben Authority, kein externer Aufrufer.

| from_status | to_status | requested_by |
| --- | --- | --- |
| created | ready | work_item_editor |
| created | cancelled | work_item_editor |
| ready | claimed | worker |
| ready | cancelled | work_item_editor |
| claimed | in_progress | worker |
| claimed | ready | worker |
| claimed | ready | assignment_authority |
| claimed | cancelled | work_item_editor |
| in_progress | submitted | worker |
| in_progress | failed | worker |
| in_progress | ready | assignment_authority |
| in_progress | cancelled | work_item_editor |
| submitted | done | result_acceptor |
| submitted | failed | result_acceptor |
| submitted | cancelled | work_item_editor |

Bedeutung der Rückkehr nach `ready`:

- `requested_by` `worker`: der Worker gibt die Zuweisung frei (`release`)
- `requested_by` `assignment_authority`: der Lease ist abgelaufen

`claimed` nach `in_progress` ist `start`. `in_progress` nach `submitted` oder
`failed` ist die Ergebnisabgabe (`result`). `ready` nach `claimed` ist `claim`.

## Lease

Ein Lease gehört zur aktiven `Assignment` und hat `expires_at`. Nur die
Assignment Authority setzt und verlängert ihn. Ein Worker verlängert ihn nicht
selbst. `renew` ist ein Antrag.

Regeln:

- `renew` ist nur zulässig, solange `expires_at` in der Zukunft liegt und der
  Fencing-Token der aktiven Zuweisung ist
- `renew` ändert `expires_at` und nicht den Fencing-Token und nicht den
  WorkItem-Status
- ist `expires_at` erreicht und der Status `claimed` oder `in_progress`, setzt
  die Authority den Status auf `ready` und die Zuweisung auf `expired`
- der abgelaufene Lease schreibt kein Ergebnis
- ein Heartbeat des Workers verlängert den Lease nicht

## Fencing

Der Fencing-Token ist eine ganze Zahl, mindestens 1, streng aufsteigend je
WorkItem. Die erste Zuweisung erhält 1, jede spätere Zuweisung desselben
WorkItem erhält den bisherigen Höchstwert plus 1. Der Token ist kein Geheimnis
und kein Authentisierungsnachweis.

| operation | rule |
| --- | --- |
| claim | issued |
| renew | required |
| release | required |
| start | required |
| result | required |
| lease_expiry | invalidated |

`issued` heißt: der Claim enthält keinen Token. Die Authority vergibt ihn mit
der Zuweisung. `required` heißt: der Antrag muss den Token der aktiven
Zuweisung tragen. Ein kleinerer, fremder oder bereits beendeter Token wird mit
`409` und dem Code `fencing_rejected` abgelehnt. Status und Audit bleiben
unverändert. `invalidated` heißt: nach Ablauf oder Freigabe gilt der Token
nicht mehr. Die nächste Zuweisung erhält einen höheren Token. Ein verspäteter
Worker kann damit kein Ergebnis mehr schreiben.
