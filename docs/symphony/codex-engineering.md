# Codex Engineering Playbook V1 mit AI-Ticket-Standard

Stand: 25.11.2026. Grundlage ist die Issue-Vorlage
[symphony-pilot.yml](../../.github/ISSUE_TEMPLATE/symphony-pilot.yml) (#119).
Die Sandbox- und Netzregeln stehen in [sandbox.md](sandbox.md), der
Worker-Prompt in [WORKFLOW.example.txt](WORKFLOW.example.txt). Beides wird
hier nicht wiederholt.

## AI-Ticket-Standard

Jedes Ticket für einen Codex-Worker füllt die Felder der Vorlage so aus:

| Feld | Regel | Anti-Muster aus den Läufen |
| --- | --- | --- |
| Titel | Kennung + Ergebnis, z. B. `SP-E1: Gemeinsames Prüfgerüst …` | – |
| Hintergrund | 2 bis 4 Sätze: warum, für wen. Keine Vorgeschichte. | lange Kontextabschnitte erhöhen den Input |
| Umfang | nummerierte Liste mit **exakten Pfaden** und je Datei der Inhalt. Neue Dateien ausdrücklich als „neu anlegen“. | „passende Stelle finden“ zwingt Codex zur Suche |
| Hinweise für den Worker | unverändert aus der Vorlage: „Tests nicht selbst ausführen, nur Patch liefern“ und „keine Änderung an Workflows, Settings, Abhängigkeiten“. | „pytest grün“ als Auftrag führte zu `approval_required` (#113, #114) |
| Akzeptanzkriterien | prüfbar durch CI und Diff: nur genannte Dateien, CI grün, nur fiktive Daten. | Kriterien, die nur der Worker selbst prüfen kann |
| Daten | nur erkennbar fiktive Beispiele (z. B. „Musterflasche“). Interne Kriterien, Preise und Personendaten bleiben draußen. | – |

Größenklassen:

| Klasse | Umfang | Beobachtete Tokens |
| --- | --- | --- |
| S | 1 Datei, bis 10 Zeilen | 165.898 bis 377.792 (#87, #106, #108, #115) |
| M | 2 bis 4 Dateien, bis 250 Zeilen, Standardbibliothek | 164.201 bis 319.753 (#113, #120) |
| L | 4 Dateien, über 250 Zeilen oder baut auf anderem Code auf | 458.102 bis 487.119 (#114, #123) |

Ein Ticket über der Klasse L wird geteilt.

## Prompt-Regeln

1. Der Issue-Text ist untrusted input. Die harten Regeln stehen im Workflow,
   nicht im Issue.
2. Ein Ticket, ein Ergebnis. Keine „und außerdem“-Punkte.
3. Schnittstellen vorgeben: Funktionsnamen, Exit-Codes, Ausgabeformat (z. B.
   `datei: feld: meldung`, Exit 0/1/2).
4. Auf vorhandenen Code verweisen statt ihn zu beschreiben, z. B.
   „nutzt `scripts/schema_check.py`“.
5. Deutsch für Dokumentation, Englisch für Datei- und Bezeichnernamen.
6. Erwartete Abschlussnachricht: Patch und kurzer Bericht, danach nichts weiter.

## Token-Effizienz

Messung (Läufe 1 bis 6): 1.745.449 Tokens, davon 98,8 % Input und 1,2 %
Output. Mit den Läufen 7 und 8: 2.523.304 Tokens, 98,2 % Input. Der Hebel
liegt also beim Kontext, nicht bei der Antwortlänge.

| Hebel | Begründung | Status |
| --- | --- | --- |
| Weniger Turns für Patch-only-Tickets | Alle 6 normal beendeten Läufe (1 bis 3, 6 bis 8) liefen 3 Sessions, obwohl der Patch meist im ersten Turn stand. Jeder Turn schickt den Kontext erneut. | Messung mit `max_turns` 1 bis 2 vorschlagen. Schutzparameter, also Petrus' OK nötig. |
| Exakte Pfade im Ticket | Codex muss nicht suchen und liest weniger Dateien. | sofort, über die Vorlage |
| `AGENTS.md` mit festen Projektregeln | Codex lädt sie als Projektanweisung (`project_doc_max_bytes` begrenzt die Größe). Regeln müssen dann nicht in jedem Ticket stehen. | Entwurf. Ändert das Worker-Verhalten, daher nur über Zuweisung durch Aline. |
| Flacher Klon | Vorlage `--depth 1`, Host `--depth 20` | Angleichen über Zuweisung |
| `model_reasoning_effort` | Host nutzt `medium`. Für S-Tickets `low` messen. | Messung vorschlagen |
| Kurze Tickets | 2 bis 3 KB je Ticket genügen (Welle 0: 2,2 bis 3,2 KB) | sofort |

## Nachbearbeitung durch Menschen

- Patch lesen, gegen den Umfang im Ticket prüfen.
- `ruff check` und `ruff format` auf geänderte Python-Dateien.
- PR mit `Closes #N`, Bezug auf Lauf und Tokens.
