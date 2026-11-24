# ADR-0003: Eine Assignment Authority

- Status: Accepted
- Datum: 2026-11-09
- Entscheider: Architekturvorgabe Greenfield V1

## Kontext

Greenfield V1 verteilt Arbeit an Worker. Ohne eine einzelne Zuweisungsinstanz
entstehen doppelte Ausführung und zwei Schreiber für denselben Zustand.

Die Zielarchitektur vom 09.11.2026 verlangt genau eine Assignment Authority und
genau eine autoritative Instanz je Zustandsdomäne. Die Foundation definiert die
Verträge. Die Infrastructure implementiert sie und weist sie durch Tests nach.

Begriffe und der Ablauf einer Arbeit stehen in [../ARCHITECTURE.md](../ARCHITECTURE.md).
Dieses ADR macht die Regel verbindlich. Es spezifiziert kein Protokoll.

## Entscheidung

Entschieden. Es gibt genau eine Assignment Authority und genau eine autoritative Instanz je Zustandsdomäne.

Die Assignment Authority ist die einzige Instanz, die eine Zuweisung vergibt
oder zurücknimmt. Worker, Clients und Caches sind keine Eigentümer dieses
Zustands. Ein Claim, ein Heartbeat oder eine Ergebnisabgabe ist ein Antrag.
Nur die besitzende Instanz nimmt ihn an.

Eine zweite Instanz, die denselben Zustand schreibt, ist unzulässig. Das gilt
auch für eine Replik, einen Cache, ein Log und einen Worker. Skalierung darf
diese Regel nicht aufweichen. Zwei Domänen mit je einem Eigentümer sind zulässig.
Zwei Eigentümer einer Domäne sind es nicht.

## Konsequenzen

- Verträge nennen für jede Domäne genau einen Eigentümer, bevor sie implementiert werden.
- Die Worker Runtime schreibt den WorkItem-Status nicht selbst.
- Jede angenommene Zustandsänderung ist serverseitig autorisiert und auditierbar ([../../SECURITY.md](../../SECURITY.md)).
- Lease und Fencing bleiben Eigenschaften der Authority. Ein Worker kann sie nicht selbst verlängern oder ersetzen.
- Failover ist nur zulässig, wenn dabei weiterhin genau eine Instanz schreibt. Wie das betrieblich aussieht, ist kein Freibrief für einen zweiten Primary und ist mit [ADR-0005](0005-railway-environments.md) offen.
- Der Authentisierungsstandard für Workloads steht in [ADR-0008](0008-auth-standard.md). Die Regel, dass autorisiert wird, ist davon unabhängig schon gültig.

## Alternativen

Eine Zuweisung durch den Worker selbst oder durch mehrere gleichberechtigte
Instanzen widerspricht der Zielarchitektur und ist abgelehnt. Andere Formen,
die die eine schreibende Instanz erhalten, sind damit nicht vorentschieden.
Sie brauchen ein eigenes ADR, wenn sie über diese Regel hinausgehen.

## Bezug

- [ADR-0001](0001-postgresql-on-railway.md)
- [ADR-0008](0008-auth-standard.md)
- [../ARCHITECTURE.md](../ARCHITECTURE.md)
- [../../SECURITY.md](../../SECURITY.md)
