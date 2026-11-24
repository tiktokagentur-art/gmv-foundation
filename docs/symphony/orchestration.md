# Multi-Agent-Orchestrierung und Abteilungsintegration V1

Stand: 25.11.2026. Konzept. Ergänzt [dispatch-gate.md](dispatch-gate.md)
(Gate-Entwurf) und das Verantwortungsmodell in
[../SYMPHONY-GITHUB-V1.md](../SYMPHONY-GITHUB-V1.md). Die einzige
Zuweisungsinstanz bleibt die Control Plane (ADR-0003).

## Heutiger Stand

- Genau ein Worker, `max_concurrent_agents: 1`, ein Lauf je Start.
- Das Dispatch-Gate bleibt **bewusst aus**, solange genau ein Operator steuert
  (siehe dispatch-gate.md). Ersatz: Label nur durch Aline oder Deniz,
  Einmal-Sperre, Wächter.
- Parallele Worker sind nur Konzept. Es gibt dafür keine Freigabe.

## Wellenlogik

| Regel | Inhalt |
| --- | --- |
| Reihenfolge | Unterbau → Standards → Content → Sales → Ergänzungen |
| Gate zwischen Wellen | Die nächste Welle startet erst, wenn alle PRs der vorigen gemergt sind. |
| Innerhalb einer Welle | Läufe nacheinander, je Werkzeug ein Lauf, je Lauf ein Issue. |
| Abhängigkeiten | Ein Werkzeug, das auf einem anderen aufbaut (z. B. Statusmodell auf Prüfgerüst), kommt in eine spätere Welle. |
| Freigabe | Aline gibt das Paket und jede Welle frei. Gesperrte Werkzeuge (interne Daten) laufen nicht. |

Beispiel 24.11.2026: Welle 0 mit SP-E1 (#120 → PR #122) und SP-E2 (#123 →
PR #124, nutzt das Prüfgerüst aus #122). Welle 1 startete nach beiden Merges.

## Gates

| Gate | Wo | Wer |
| --- | --- | --- |
| Auftrag freigegeben | Control Plane | Aline |
| Ticket nach Standard | Issue | Operator ([codex-engineering.md](codex-engineering.md)) |
| Genau ein gelabeltes Issue, kein Prozess | Host | Vorabprüfung |
| Selbsttest grün | Host | `sandbox-selftest.sh` |
| Budget, Dispatch, Laufzeit | Host | Wächter |
| CI grün | GitHub | 3 Checks |
| Merge | GitHub | Aline oder Deniz |
| Fachliche Abnahme des Werkzeugs | Abteilung | jeweilige Leitung |
| Rechtsprüfung vor allem, was nach außen geht | Abteilung | Recht |

## Parallele Worker (Konzept, nicht freigegeben)

Voraussetzungen, bevor mehr als ein Worker laufen darf:

1. Dispatch-Gate an und angebunden: Claim, Lease und Fencing aus der Control
   Plane vor jedem Codex-Start.
2. Die Einmal-Sperre wandert vom Host in die Control Plane, eine Sperre je
   WorkItem.
3. Wächter je Worker statt je Prozess, Budget je Ticket.
4. Workspaces strikt getrennt. Heute bleiben andere Workspaces im
   Pilot-Verzeichnis lesbar (sandbox.md).
5. Keine zwei Tickets mit überlappenden Pfaden in derselben Welle.
6. Nur Tickets der Klassen S und M parallel. L bleibt seriell.

Startwert nach Freigabe: höchstens 2 Worker, eine Welle, danach Auswertung.
Jede dieser Änderungen ist eine Änderung an Schutzmaßnahmen und braucht
Petrus' OK.

## Abteilungsintegration

| Abteilung | Werkzeuge im Repo | Grenze |
| --- | --- | --- |
| Engineering | Prüfgerüst, Statusmodell-Prüfer (Welle 0) | – |
| Geschäftsführungsbüro | Entscheidungsregister ([../governance/decision-register.md](../governance/decision-register.md)), Aufgabenprotokoll, KPI-Schema, Playbook-Vorlage (Welle 1) | nur fiktive Beispiele |
| Content Factory | Briefing-Schema ([../content-factory/briefing.md](../content-factory/briefing.md)) | Veröffentlichung bleibt gesperrt, Publisher offen |
| Sales & Partnerships | Pipeline-Statusmodell (geplant) | interne Händlerkriterien und Deckungsbeitragslogik nicht im öffentlichen Repo |

Regeln für jede Abteilung:

- Symphony baut Werkzeuge (Schemas, Prüfskripte, Vorlagen), keine Inhalte
  mit echten Daten.
- Die Leitung stimmt die fachlichen Regeln vorher ab und nimmt das Werkzeug ab.
- Rechtsgrundlagen und externe Empfänger bleiben Platzhalter, bis sie
  geklärt sind.
- Ein privates Repo wird erst entschieden, wenn ein Werkzeug es braucht.
