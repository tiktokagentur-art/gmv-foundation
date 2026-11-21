# ADR-0016: Isolierter Code Mode Executor für einen Read-only-Pilot

- Status: Proposed
- Datum: 2026-11-21
- Entscheider: offen

## Kontext

Die [Bestandsanalyse](../CODE-MODE-001-INVENTORY.md) findet auf `main` weder
MCP-Bridge noch Sandbox oder produktiven Identitätsnachweis. Die eine
Assignment Authority aus [ADR-0003](0003-single-assignment-authority.md) darf
kein Worker ersetzen. Das bestehende L1-Mandat für Aline in
[ADR-0015](0015-aline-l1-testmandate.md) umfasst keine realen Read-only-Quellen
und keine neuen Tools. Der Auftrag GMV-CODE-MODE-001 erlaubt einen isolierten
Pilot, aber weder kostenpflichtige Ressourcen noch Änderungen an Aline,
Secrets, Infrastruktur oder produktiven APIs.

Cloudflares [Code Mode](https://blog.cloudflare.com/code-mode/) trennt
generierten Code von einem Supervisor: Der Code ruft eine kleine typisierte
Tool-API auf; der Supervisor hält Berechtigungen und Credentials. Dieses
Prinzip wird für den Pilot geprüft, ohne eine Live-Integration zu beschließen.

## Entscheidung

Nicht entschieden. Als technisch begrenzter Vorschlag wird ein lokaler,
fixturebasierter JavaScript-Pilot auf einem separaten Branch erprobt. Ein
Gateway prüft eine von der aufrufenden, vertrauenswürdigen Testumgebung
attestierte Agentenidentität, WorkItem-Referenz, Profil und Tool-Allowlist.
Ein separater Node-Prozess läuft in `bubblewrap` mit leerem Mount-Namespace,
ohne Netzwerk-Namespace-Zugriff, ohne Host-Umgebung und nur mit den für Node
nötigen, schreibgeschützten Runtime-Dateien. Prozesslimits und ein Supervisor-
Timeout begrenzen Ressourcen. Tool-Aufrufe laufen ausschließlich über eine
serverseitige Bridge mit lokalen Testdaten. Die Sandbox erhält weder
Credentials noch einen allgemeinen Netzwerk- oder Dateisystemzugang.

Ein JavaScript-`vm`-Kontext darf die sichtbare API verkleinern, gilt aber
ausdrücklich **nicht** als Sicherheitsgrenze. Fehlt `bubblewrap` oder kann die
Isolation nicht hergestellt werden, wird der Lauf verweigert. Der Pilot ist
kein Dienst in der produktiven FastAPI-Anwendung und wird nicht an den
bestehenden Aline-Runner angeschlossen.

| Option | Sicherheit | Betrieb und Kosten | Bewertung |
| --- | --- | --- | --- |
| Cloudflare Dynamic Workers | Isolates, steuerbare Bindings und Netzwerkzugriff; Supervisor kann Credentials getrennt halten. | [Dynamic Workers](https://developers.cloudflare.com/dynamic-workers/pricing/) benötigen den Paid Plan und werden nutzungsabhängig abgerechnet; [Workers-Limits](https://developers.cloudflare.com/workers/platform/limits/) müssen je Tarif konfiguriert und geprüft werden. | Gute spätere Hosting-Option, im kostenfreien Pilot nicht verfügbar. |
| Railway Sandbox | Eigene VM und konfigurierbare CPU-/RAM-/Zeitlimits. | Laut [Railway-Doku](https://docs.railway.com/sandboxes) hat auch `ISOLATED` ausgehendes Internet. Neue VMs verursachen [nutzungsbasierte Kosten](https://docs.railway.com/reference/pricing/plans). | Ohne zusätzlich verifizierte Egress-Sperre nicht geeignet; keine Instanz anlegen. |
| Lokaler `bubblewrap`-Prozess | Separater User-, Mount-, PID- und Netzwerk-Namespace; nur minimale Read-only-Mounts und kein Secret im Kindprozess. | Keine neue bezahlte Infrastruktur; auf Linux mit erlaubten User-Namespaces ausführbar. Muss je Zielhost geprüft werden und ersetzt keine produktionsreife Orchestrierung. | Für Offline-Pilot gewählt. |

Der Vorschlag entscheidet keine produktive Laufzeit, keinen Auth-Standard,
keinen Secret-Provider, keine Tool-Freigabe für Aline und keinen Betreiber für
den Execution-Audit. Dafür sind eigene Entscheidungen und Nachweise nötig.

## Konsequenzen

- Jeder Pilotlauf bleibt read-only und nutzt ausschließlich lokale Fixtures.
- Eine CLI oder Bibliothek darf einen Testkontext injizieren, aber dessen
  `agent_id` ist kein Beweis für Live-Aufrufe. Eine externe API darf daraus
  keine Authentisierung ableiten.
- Bridge und Gateway prüfen jede Operation erneut. Unbekannte Tools, Schreib-
  verbformen, freie URLs und unzulässige Parameter werden abgewiesen.
- Auditdaten enthalten IDs, Toolnamen, Zeiten, Ressourcen und Fehlerklassen,
  aber keine Secrets, Quelltexte, Tool-Rohantworten oder Prompts.
- Für produktive Nutzung sind eine attestierte Identity nach ADR-0008,
  Mandat/Lease-Prüfung durch die Control Plane, Credential-Isolation,
  Retention/Monitoring sowie ein eigener Betriebsentscheid erforderlich.

## Alternativen

Node `vm` oder `worker_threads` allein wurden als Sicherheitsgrenze verworfen:
Sie teilen Prozessrechte und bieten keine belegte Trennung von Host-Dateien,
Netzwerk und Umgebung. Ein neuer Railway-Sandbox-Dienst und Dynamic Workers
wurden für diesen Auftrag wegen Kosten und fehlender Egress-/Mandatsfreigabe
nicht gestartet.

## Bezug

- [Architektur, Bedrohungsmodell und Betrieb](../CODE-MODE-001-ARCHITECTURE.md)
- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0007](0007-secret-management.md)
- [ADR-0008](0008-auth-standard.md)
- [ADR-0015](0015-aline-l1-testmandate.md)
