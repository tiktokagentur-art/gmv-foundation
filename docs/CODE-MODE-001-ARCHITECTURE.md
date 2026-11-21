# GMV-CODE-MODE-001: Pilotarchitektur und Sicherheitskonzept

Stand: 2026-11-21. Geltungsbereich ist ein **lokaler Offline-Pilot** mit
synthetischen GitHub- und Railway-Antworten. Die Bestandsaufnahme steht in
[CODE-MODE-001-INVENTORY.md](CODE-MODE-001-INVENTORY.md); die noch offene
Architekturentscheidung steht in [ADR-0016](adr/0016-code-mode-executor.md).
Dieser Pilot erteilt Aline keine neue Berechtigung.

## Datenfluss und Zuständigkeiten

```text
Vertrauenswürdiger Testaufrufer
    | attestierter Testkontext, Code, WorkItem-Referenz
    v
Code Mode Gateway -----> strukturierter Execution-Audit
    | autorisierte Tools, Limits
    +----> MCP Tool Bridge ----> lokale GitHub-/Railway-Fixtures
    |           ^
    v           | nur typisierte Tool-RPCs, niemals Credentials
Isolierter JS-Prozess (bubblewrap, kein Netz, keine Host-Umgebung)
    | bereinigtes, strukturiertes Ergebnis
    v
Gateway
```

Das Gateway validiert den Auftrag vor Prozessstart: eindeutige Agenten-ID,
WorkItem-Referenz, Berechtigungsprofil, Tool-Allowlist, Code- und Parameter-
größen sowie Laufzeitlimits. Es erzeugt eine Execution-ID. Jeder Tool-Aufruf
wird nochmals gegen das Profil und seine typisierten Argumente geprüft. Die
Bridge lässt für den Pilot nur lesende Operationen auf Issues, Pull Requests,
CI-Status, Deployments und Service-Status zu. Sie behandelt Ergebnisse als
untrusted Daten und reicht nur begrenzte, schema-geprüfte Felder in den
Sandbox-Prozess. Freie URLs, beliebige MCP-Methoden und Schreiboperationen
sind keine Schnittstellen des Piloten.

Im Repository existiert noch kein MCP-Client oder Server. Die Pilot-Bridge
bildet eine **MCP-kompatible Tool-Grenze** mit benannten Aufrufen und
strukturierten Ergebnissen gegen Fixtures ab. Ein späterer echter MCP-Adapter
muss dieselbe serverseitige Prüfung beibehalten. Dieser Pilot behauptet keine
Live-Verbindung zu GitHub oder Railway.

Der Executor startet den Node-Prozess als eigenständiges Kind mit
`bubblewrap`-Isolation. Nur die Runtime und ihre nötigen Bibliotheken sind
schreibgeschützt eingebunden. Netzwerk-, Mount-, PID- und User-Namespace
trennen ihn vom Host; die Umgebung wird geleert. CPU, Arbeitsspeicher,
Wandzeit und Ausgabemenge werden zusätzlich vom Supervisor begrenzt.
Importe oder Prozessaufrufe aus generiertem Code bekommen weder Host-Dateien
noch Credentials oder Netzwerk. Ein `vm`-Kontext reduziert die sichtbare
JavaScript-API, ist aber nicht der Isolationsanker. Kann der Supervisor die
OS-Isolation nicht belegen, startet er keinen generierten Code.

## Berechtigung und Governance

Das Testprofil ist explizit und read-only. Die Identität stammt aus dem
vertrauenswürdigen Aufrufer der lokalen Testumgebung; ein `agent_id` im
generierten Code oder in einer Tool-Antwort hat keine Autorität. Für einen
späteren Netzwerkdienst fehlen derzeit ein akzeptierter Auth-Standard
([ADR-0008](adr/0008-auth-standard.md)), ein produktiver Identity-Store und
ein Vertrag zur Delegation eines WorkItem-Mandats. Eine öffentliche
`execute`-Route wäre unter diesen Bedingungen unzulässig.

Die Control Plane bleibt nach
[ADR-0003](adr/0003-single-assignment-authority.md) die einzige Eigentümerin
von WorkItem-State, Assignment, Claim, Lease und Fencing. Der Pilot benutzt
eine synthetische WorkItem-Referenz nur zur Korrelation. Er erstellt oder
ändert keine WorkItems und verlängert keinen Lease. Vor einer späteren
Integration muss die Control Plane einen aktiven, passenden Claim und den
Lease samt Fencing-Token attestieren; der Executor darf diese Werte nur prüfen
und ein Ergebnis über den dafür vorgesehenen Control-Plane-Weg melden.

## Bedrohungsmodell

| Bedrohung | Sicherheitsgrenze im Pilot | Verbleibendes Risiko |
| --- | --- | --- |
| Generierter Code liest Host-Dateien, Umgebung oder Secrets | Leer aufgebauter Mount-Namespace, `--clearenv`, keine Secret-Übergabe; nur minimale Runtime-Mounts. | Fehlerhafte Mount-Liste oder Kernel-/Runtime-Lücke; auf Zielhost erneut prüfen. |
| Code greift direkt auf Internet, Metadaten oder Railway-Netz zu | Separater Netzwerk-Namespace ohne Egress; Tool-RPC ist der einzige Datenweg. | Tool-Bridge selbst braucht später eigene Netz- und Credential-Policy. |
| Code startet Prozesse oder lädt Module nach | Keine Shell/Tools/Module im Sandbox-Dateisystem; API-Oberfläche begrenzt; Ressourcenlimits und Abbruch. | JS-`vm` ist keine harte Grenze. Auch bei `vm`-Escape muss die OS-Sandbox halten. |
| Tool-Ergebnis enthält Prompt-Injection | Antworten sind Daten, nie Instruktionen des Gateways; Schema- und Größenprüfung; keine dynamische Tool- oder Rechtevergabe. | Ein KI-Modell kann später Inhalte in seiner Zusammenfassung falsch gewichten; Evidenz und Quellen erhalten. |
| Versteckter Schreibaufruf oder Parametertrick | Feste Toolnamen, lesende Methoden und Parameter-Schemata; Prüfung pro Aufruf. | Echte MCP-Server müssen später zusätzlich selbst Least Privilege erzwingen. |
| Endlosschleife, Speicher- oder Ausgabeflut | CPU-/RAM-/Wandzeit- und Ausgabelimits, Abbruch des Prozessbaums, begrenzte Parallelität. | Limits von `bubblewrap` allein genügen nicht; Supervisor und Host-Kapazität bleiben relevant. |
| Wiederholung oder gefälschter Auftrag | Einmalige Execution-ID und Testkontext-Bindung; kein Live-Auftragsrecht. | Authentisierung, Idempotenz und Lease-Bindung für Live-Betrieb sind offen. |
| Secret im Audit oder Fehlertext | Nur Metadaten und klassifizierte Fehler; keine Code-, Prompt- oder Rohdatenfelder; Redaction-Muster aus `app/logging_config.py`. | Secret-ähnliche Inhalte in künftig freigegebenen Tool-Antworten brauchen zusätzliche Inhaltsprüfung. |

Der lokale RAM-Wächter misst den Prozessbaum periodisch. Er ist kein hartes
cgroup-Limit; kurzzeitige Spitzen und Prozess-Races bleiben möglich. Ein
späterer MCP-Client darf zudem nicht synchron ohne eigene Deadline im
Supervisor laufen, weil ein blockierter Tool-Aufruf sonst Wandzeitabbruch und
Cancellation verzögert. Diese beiden Punkte sind vor Live-Betrieb zu beheben.
Der Prompt-Injection-Test belegt nur, dass Tool-Daten keine zusätzlichen
Rechte vergeben; er prüft keine spätere Modellzusammenfassung.

## Audit und Ergebnis

Für jeden Startversuch wird ein maschinenlesbarer Nachweis mit Execution-ID,
Agenten-ID, synthetischer WorkItem-ID, Profil, UTC-Zeitstempeln, aufgerufenen
Toolnamen, Laufzeit, gemessenen Ressourcen soweit vom Host verfügbar,
Ergebnisstatus und Fehlerklasse erzeugt. Erfolgreiche Antworten enthalten
nur die strukturierten, relevanten Befunde. Fehler geben eine sichere Klasse
und Execution-ID zurück, keine ungefilterten Exception-Texte. Der Pilot-Audit
ist ein Nachweis des Executors und **nicht** der autoritative Control-Plane-
Audit für WorkItem-Zustandsänderungen. Eine produktive Aufbewahrungsfrist ist
in [ADR-0010](adr/0010-slo-alerting-incident.md) noch offen.

## Betrieb und Rückbau

Der Pilot wird ausschließlich lokal oder in einer isolierten CI-Testumgebung
mit Fixtures gestartet. Er erhält keine produktiven Credentials. Ein fehlendes
`bubblewrap`, nicht verfügbare User-Namespaces oder unerwartete Runtime-Dateien
führen zu `deny`, nicht zu einem unisolierten Fallback. CI führt nur Offline-
Sicherheitstests aus. Es gibt weder Deployment noch Datenmigration; ein
Rollback besteht im Stoppen der lokalen Ausführung und Zurücknehmen des
Pilot-Branches. Offene Ausführungen werden bei Abbruch beendet und als
abgebrochen auditiert.

Für einen späteren Betrieb sind vorab zu entscheiden und nachzuweisen:

1. Eigenes Mandat für reale Read-only-Quellen und neue Tools; das aktuelle
   [Aline-L1-Mandat](adr/0015-aline-l1-testmandate.md) deckt beides nicht ab.
2. Verifizierter Workload-Identitätsnachweis und serverseitige Bindung an
   Auftrag, Claim, Lease, Fencing und konkretes Toolprofil.
3. GitHub-/Railway-Credentials mit ausschließlich benötigten Leserechten,
   außerhalb der Sandbox und mit eigener Rotation und Widerrufbarkeit.
4. Zielruntime mit belegtem Egress-Deny, Ressourcenlimits, Isolationstests,
   Audit-Store, Retention, Monitoring und Incident-/Rollback-Verfahren.
5. Unabhängige Sicherheitsreview und Entscheidung über ADR-0016 sowie eine
   eigene Aktivierung; kein stiller Anschluss an bestehende Aline-Workflows.

## Späterer Aline-Anschluss

Aline sollte nach Freigabe einen strukturierten Auftrag an die Control Plane
stellen. Diese prüft und bescheinigt Identität, Mandat und aktiven Lease.
Erst danach kann ein separates Gateway den Executor mit einem auf diesen
Auftrag und eine kurze Laufzeit begrenzten Read-only-Profil aufrufen. Der
Executor meldet Ergebnis oder Fehler zurück; ausschließlich die Control Plane
entscheidet über WorkItem-Übergänge. Ein Modellaufruf für Code-Erzeugung und
seine Kosten würden außerhalb dieses Offline-Piloten separat begrenzt und
auditiert.
