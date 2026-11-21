# GMV-CODE-MODE-001: Benchmarkbericht

Stand: 2026-11-21. Reproduktion ohne Modell- oder Live-API-Aufrufe:

```bash
python scripts/code_mode_benchmark.py --runs 100 --local-e2e-runs 10
pytest tests/test_code_mode_benchmark.py
```

Es gibt zwei getrennte Messklassen. Der **lokale E2E-Test** misst echte
Programmlaufzeit gegen `code_mode.fixtures.PILOT_RESPONSES`, ohne Netzwerk.
Der **Protokollvergleich** simuliert Modellturns, Tokens, Modellpreise und
Netzwerkzeiten. Seine Werte sind keine Messungen eines Modells oder MCP-Servers.

## Identische Aufgabe und Testdaten

Beide Wege prüfen dieselben fünf synthetischen Tool-Antworten: zwei offene
GitHub-Issues, einen offenen PR, einen fehlgeschlagenen CI-Status, ein
fehlgeschlagenes Railway-Deployment und einen degradierten Railway-Service.
Die strukturierte Referenz enthält `open_issue_count=2`, Issue-Blocker `101`,
`open_pr_count=1`, `ci_conclusion=failure`, `staging_service=degraded` und
`failed_deployments=["dep-1"]`. Der klassische Weg ruft fünf Tools nacheinander
über die Bridge auf. Code Mode führt `PILOT_CODE` im Gateway und der isolierten
JS-Laufzeit aus und ruft dieselben fünf Tools über die Bridge auf.

## Echte lokale E2E-Messung

Ein Lauf am 2026-11-21 in der `/workspace`-Umgebung (Python 3.12,
Node 24.22.3, Linux/bubblewrap) mit zehn Wiederholungen ergab:

| Kennzahl | Klassische Bridge-Aufrufe | Code Mode Gateway und Executor |
| --- | ---: | ---: |
| Tool-Aufrufe pro Lauf | 5 | 5 |
| Erfolgreiche Läufe | 10/10 | 10/10 |
| Fehler | 0/10 | 0/10 |
| Ergebnisvollständigkeit gegen Fixture | 10/10 | 10/10 |
| Lokale Latenz, Median | 0,050 ms | 52,990 ms |
| Lokale Latenz, P95 (Nearest Rank) | 0,162 ms | 75,830 ms |

Rohwerte in ms, klassisch: `0.162, 0.058, 0.050, 0.049, 0.048, 0.047,
0.046, 0.047, 0.159, 0.058`.

Rohwerte in ms, Code Mode: `46.562, 73.977, 51.602, 64.675, 52.749,
75.830, 56.187, 48.457, 46.608, 53.232`.

Diese Messung enthält weder Modell- noch Remote-Tool-Latenz. Der klassische
Weg bleibt im Python-Prozess; Code Mode enthält Gateway, Audit-Schreiben,
bubblewrap und Node-Prozessstart. Die lokale Mehrzeit ist daher erwartbar;
aus ihr lässt sich keine Gesamtlatenz bei echten Modellen ableiten.

## Simulierter Modell- und Netzwerkschritt

Das Skript serialisiert dieselben fünf Fixture-Antworten als Modellkontext.
Beim klassischen Ablauf wird nach jedem Tool-Ergebnis ein neuer Modellturn
angenommen; Code Mode gibt das vollständige `PILOT_CODE` und danach eine
abschließende Antwort aus. Der Token-Proxy ist je Nachricht
`ceil(UTF-8-Bytes / 4)` und **kein Provider-Tokenizer**.

| Kennzahl, 100 simulierte Läufe | Klassisch | Code Mode | Einordnung |
| --- | ---: | ---: | --- |
| Modell-Roundtrips | 6 | 2 | Ablaufannahme |
| Eingabetokens | 1.224 | 348 | Byte-Proxy |
| Ausgabetokens | 108 | 227 | Byte-Proxy |
| Gesamtlatenz | ca. 1.700 ms | ca. 725 ms | Szenariorechnung |
| Modellkosten | 0,001656 USD | 0,001256 USD | Illustrativer Tarif |
| Executor-/Infrastrukturkosten | unbekannt | unbekannt | Keine Abrechnung erhoben |
| Erfolgsquote / Fehlerrate | 100 % / 0 % | 100 % / 0 % | Deterministischer Fixture-Auswerter |
| Ergebnisvollständigkeit | 6/6 Referenzfelder | 6/6 Referenzfelder | Fixture-Prüfung |

Szenarioannahmen: 250 ms je Modellturn, 40 ms je Tool-Aufruf,
25 ms Executor-Start; illustrativer Tarif 1 USD je Million Eingabetokens und
4 USD je Million Ausgabetokens. Das Skript addiert die gemessene lokale
Python-Simulationszeit zur Szenariolatenz; diese ist für Modellbetrieb nicht
repräsentativ. Parameter lassen sich per CLI variieren.

Der feste Auswerter kann keine Modellfehler, falsche Tool-Wahl oder generierten
fehlerhaften Code abbilden. Die Kostenrechnung lässt Sandbox- und
Infrastrukturkosten offen. Für einen belastbaren Live-Vergleich sind ein
genehmigter Modell-Testkorridor, echte Usage-Zähler, Remote-Tool-Latenzen,
gemessene Infrastrukturkosten und verblindete Qualitätsbewertung nötig.
Aus den simulierten Zahlen folgt kein Einsparungsversprechen.
