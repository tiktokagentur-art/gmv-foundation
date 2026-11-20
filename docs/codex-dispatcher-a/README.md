# CODEX-DISPATCHER-A-001 – Plus-first Cloud-Handoff V1

Stand: 20.11.2026. Ticket: [#44](https://github.com/tiktokagentur-art/gmv-foundation/issues/44).

## Entscheidung und technisch belegte Grenze

Pizza Club nutzt **zuerst Codex Cloud mit ChatGPT-Login** im Rahmen des
verfügbaren Plus-Kontingents. Das Cloud-Environment muss in Codex Web oder Desktop
mit dem autorisierten GitHub-Repository verbunden und veröffentlicht werden.

**Wichtig:** Ein regulärer programmatischer GitHub-Issue-zu-Codex-Cloud-Start
innerhalb von ChatGPT Plus wurde für diesen Piloten nicht nachgewiesen.
GitHub-PR-Ereignisse können mit ChatGPT Work überwacht werden, sind aber nicht
gleichbedeutend mit der Erzeugung eines Codex-Cloud-Laufs. Die Agents API
verursacht separate Modell-/Sandbox-Kosten und gehört **nicht** zu Variante A.

Daraus folgt: **MANUAL_CODEX_CLOUD** ist der einzig unterstützte Betriebsmodus
dieser V1. Der Dispatcher ruft weder Codex noch GitHub noch die OpenAI API auf.
Er ist kein Scheduler, Queue-Consumer oder autoritativer WorkItem-Service.

Primärquellen:

- [Codex Cloud – Nutzung und Voraussetzungen](https://help.openai.com/en/articles/20001545-using-codex-cloud)
- [Codex im ChatGPT-Tarif](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan)
- [ChatGPT Work Ereignisaufgaben](https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt)
- [Agents API – separate Kosten](https://developers.openai.com/api/docs/guides/agents-api/overview)

## Bestands- und Dublettenprüfung

Die bestehenden CI-Checks, der GitHub Moderator, PR-Triage (#35 / Draft-PR #36),
Aline-L1-Workflows (#38 / gemergter #43), die Coding-Agent-Anleitung (Draft-PR
#30) und die Command-Center-Demo (Draft-PR #37) bleiben Eigentum ihrer
bisherigen Bereiche. Diese V1 fügt **keinen** GitHub-Actions-Trigger hinzu,
beansprucht keine Assignment Authority und aktiviert keine neuen Berechtigungen.

Die Beispiel-Warteliste referenziert vorhandene Quellen statt neue Issues oder
zweite Produkte anzulegen. Sie enthält bewusst nur **Vorschläge**; tatsächliche
Aufgabenannahme, Freigaben und Ausführung werden hier nicht gespeichert.

## Offline-Nutzung

Vom Repository-Root:

~~~bash
python3 scripts/codex_dispatcher_a.py --list
python3 scripts/codex_dispatcher_a.py --task SELLER-HEALTH-001
python3 scripts/codex_dispatcher_a.py --task UI-FOUND-002
python3 scripts/codex_dispatcher_a.py --task WEB-DEPLOY-001
python3 -m unittest tests/test_codex_dispatcher_a.py
~~~

Ein einzelner Handoff wird auf stdout ausgegeben und kann vom autorisierten
Nutzer in einer ausgewählten Codex-Cloud-Sitzung eingefügt werden.
**Der Aufruf startet keine Sitzung**, erzeugt keinen Branch und gibt kein
Berechtigungssignal ab. In Codex ist vor dem Lauf die GitHub-Verbindung und
das veröffentlichte Environment zu prüfen; dies wurde hier nicht eingerichtet.

Die JSON-Datei unter [example-queue.json](example-queue.json) ist ein
synthetischer, manuell kuratierter Übergabeplan mit öffentlichen GitHub-Links.
Nicht direkt GitHub-Issue-Texte oder andere nicht vertrauenswürdige Daten in
diese Datei übernehmen: Sie können manipulierte Instruktionen enthalten.
Der Generator erkennt nur strukturelle Fehler und ersetzt kein Review.

## Sicherheitsgrenzen

1. Fail closed: Exaktes Repository, Schema-Version, genau der manuelle Modus,
   höchstens drei Vorgänge, gültige Issue-/PR-Links und keine Dubletten.
2. Nur `PROPOSED_NOT_STARTED`; keine Fake-Claims, angenommenen Mitarbeiterrollen
   oder simulierten Freigaben. Keine Änderungen an `main` oder WorkItem-Status.
3. Keine Speicherung von Tokens, ChatGPT-Sitzungen, API-Keys oder Secrets.
   Der Generator kennt keine Remote-Zugangsdaten.
4. Codex darf bei späterer manueller Durchführung nur im explizit genehmigten
   Umfang auf Feature-Branches und Draft-PRs arbeiten; keine Merges,
   Deployments oder produktiven Änderungen.
5. Unabhängige Review und die drei bestehenden CI-Checks bleiben erforderlich.
   Ein grüner Check ist keine Freigabe. ADR-0003 (eine Assignment Authority)
   und ADR-0014 (Credential-Isolation) gelten unverändert.
6. Neue Codex-Cloud-Umgebungen, Authentifizierung, Netzwerkrechte oder
   automatische Trigger brauchen getrennte technische Prüfung und Freigabe.

## Weg zur nächsten Stufe

- **Gate A – Cloud:** Ein autorisiertes Codex-Cloud-Environment mit
  Zugriff auf das korrekte Repository ist nachweisbar verbunden.
- **Gate B – Ausführung:** Ein manuell ausgelöster synthetischer Codex-Task
  läuft innerhalb der ChatGPT-Plus-Nutzung; keine Modell-API-Rechnung.
- **Gate C – GitHub:** Derselbe Task dokumentiert Tests und erzeugt nur den
  für ihn erlaubten Draft-PR; kein Merge und kein Deployment.
- **Gate D – Automatik:** Erst wenn eine geeignete offiziell unterstützte
  Abo-basierte Startschnittstelle tatsächlich verifiziert ist, wird die
  automatische Übertragung separat entworfen und getestet. Sonst bleibt
  die Übergabe manuell. Keine inoffizielle Token-Extraktion oder
  Browser-Sitzungsautomatisierung als Ersatz.

## Abnahmeprotokoll

Technische Umsetzung dieses Branches: lesender JSON-Validator, Prompt-Generator,
drei Kurationsbeispiele und automatisierte Negativtests.
Die eigentliche Codex-Cloud-Ausführung ist **nicht** Bestandteil dieses PR.
Review, CI-Resultate und externe Cloud-Gates sind getrennt zu dokumentieren.
