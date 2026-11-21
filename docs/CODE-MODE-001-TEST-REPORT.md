# GMV-CODE-MODE-001: Testbericht und offene Grenzen

Stand: 2026-11-21. Alle neuen Tests verwenden synthetische Daten und starten
keine produktiven Modell-, GitHub- oder Railway-Aufrufe.

## Reproduktion und Ergebnis

```bash
python scripts/code_mode_demo.py
pytest -q tests/test_code_mode_gateway.py tests/test_code_mode_sandbox.py tests/test_code_mode_benchmark.py
ruff check app code_mode tests migrations scripts
python scripts/validate_structure.py
openapi-spec-validator api/openapi.yaml
```

Lokaler Lauf auf Linux mit Python 3.12, Node 24.22.3 und `bubblewrap`:

| Prüfung | Ergebnis |
| --- | --- |
| Isolierter Beispielauftrag | Erfolgreich: 2 offene Issues, Issue 101 als Blocker, CI `failure`, Railway-Service `degraded`, Deployment `dep-1` fehlgeschlagen; Audit mit Execution-ID. |
| Neue Gateway-, Sandbox- und Benchmarktests | 20 bestanden. |
| Gesamte lokale Pytest-Suite | 157 bestanden, 2 übersprungen; beide vorhandenen DB-Tests benötigen `DATABASE_URL`. In CI steht eine Wegwerf-Postgres-Instanz bereit. |
| Draft PR #55, GitHub Actions, Lauf `44876283530` | Backend: 159 Tests bestanden, Ruff und OpenAPI grün; Image und Lint/Struktur grün. Keine produktive Bereitstellung. |
| Ruff, Struktur, OpenAPI, Markdownlint, `git diff --check` | Bestanden. |
| Python-Wheel | Lokal gebaut; `code_mode/runner.js` im Wheel enthalten. |
| Bestehendes Docker-Image | Lokaler Build beim Abruf gelockter PyPI-Pakete durch `SSLCertVerificationError` der hiesigen Build-Umgebung blockiert. Kein Image veröffentlicht. Der unabhängige CI-Image-Job bestand. |

Die Tests decken autorisierte Leseläufe, unberechtigte Identität und WorkItem-
Referenz, nicht erlaubte Tools und Schreibversuche, Secret-/Umgebungs- und
Host-Dateizugriffe, Modulimport, direkten Netzversuch, Prozessstart,
Endlosschleife, Wandzeit, RAM-Wächter, Ausgabegröße, Tool-Kontingent,
fehlerhafte Tool-Antworten, Prompt-Injection als Daten, Parallelität,
Cancellation sowie Audit-Klassifikation ab. Ein anfänglich beobachteter
Zombie-Prozessfehler wurde durch `bubblewrap --as-pid-1` und geordnetes Reaping
behoben; danach blieb die Zahl der bereits entstandenen Zombies bei Wiederholungs-
und Abbruchtests konstant. Der Test prüft keine Modellinterpretation von
Prompt-Injection, weil der Pilot kein Modell aufruft.

## Sicherheitsbewertung und Blocker

- Der RAM-Wächter misst RSS periodisch. Kurzzeitige Speicher- und Prozessspitzen
  sind ohne hartes cgroup-/VM-Limit möglich. Die PID-basierte Überwachung und
  Beendigung hat Races. `preexec_fn` ist keine geeignete Service-Strategie für
  einen späteren mehrthreadigen Gateway-Prozess.
- Der Tool-Handler ist im lokalen Fixture endlich. Ein späterer echter MCP-
  Aufruf braucht eine eigene Deadline und abbrechbaren Transport, sonst kann
  er den Supervisor trotz Executor-Timeout blockieren.
- Im Repository gibt es keinen bestehenden MCP-Client für die Pilotquellen.
  Die Bridge hat hier nur einen injizierten Fixture-Client, keine Live-API-
  Verbindung und keine produktiven Credentials.
- Authentisierung, WorkItem-Mandat, Claim-/Lease-/Fencing-Prüfung, Audit-
  Aufbewahrung und Betreiberpflicht sind nicht implementiert. ADR-0015 erteilt
  Aline keinen Zugriff auf reale Quellen oder neue Tools.
- Der Benchmark enthält echte lokale Laufzeitwerte, aber nur simulierte Modell-
  und Netzwerte; Infrastrukturkosten und Live-Qualität sind unbekannt.

**Empfehlung:** Go für die unabhängige Review dieses Offline-Piloten im Draft
PR. No-Go für Aline-Anschluss, Live-MCP, Railway-/Cloudflare-Betrieb und jede
produktive Nutzung, bis die obigen Grenzen und ein eigenes Mandat entschieden
und technisch nachgewiesen sind.
