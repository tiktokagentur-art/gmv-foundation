# ADR-0016: Atomic Work Package Standard V1

- Status: Accepted
- Datum: 2026-11-26
- Entscheider: CEO

## Kontext

Große, mehrdeutige Engineering-Aufträge erhöhen Kontextverbrauch und
Abnahmerisiko. Der Symphony-Pilot zeigte zusätzlich Doppelvergabe und hohen
Kontextverbrauch. Kleinere Pakete ersetzen keine Claim-/Lease-Sicherheit.

## Entscheidung

Entschieden. Neue Codex-Aufträge werden nach dem Atomic Work Package
Standard V1 geplant und vor Vergabe auf Ausführungsreife geprüft.

Ein Paket liefert genau ein überprüfbares Ergebnis, ein GitHub-Issue und
bei Codeänderungen möglichst einen PR. Planungs-, Implementierungs- und
unabhängige Abnahmeaufträge bleiben getrennt. Ergebnisbezogene Tests und
notwendige Dokumentation gehören zum jeweiligen Implementierungspaket.

### Größenklassen

| Klasse | Geschätzte aktive Bearbeitungszeit | Regel |
| --- | --- | --- |
| XS | 5–15 Minuten | Kleine Korrektur |
| S | 15–30 Minuten | Standard |
| M | 30–60 Minuten | Standard |
| L | 60–120 Minuten | Zerlegung prüfen und begründen |
| XL | Über 120 Minuten | Vor Vergabe zerlegen |

Die Zeiten sind initiale Planungswerte, keine garantierten Laufzeiten und
keine Ausgabenfreigabe. Im Zweifel größer einstufen. Tests und notwendige
Kontextaufnahme zählen zur Schätzung; Wartezeiten werden separat erfasst.

### Task Readiness Check

Vor jedem neuen Handoff (direkt, manuell oder über Symphony) prüft die
zuständige Planung/Assignment Authority folgende Informationen:

- Eindeutiges Ergebnis, Issue-ID und ggf. Parent-Issue.
- Größenklasse, Schätzung, expliziter In-Scope und Out-of-Scope.
- Betroffene Pfade, zulässige Schnittstellen und relevante Referenzen.
- Abhängigkeiten erfüllt und durch konkrete Evidenz belegt.
- Keine offene Architekturentscheidung oder widersprüchliche Anforderung.
- Akzeptanzkriterien, Testbefehle, Ergebnisbelege und Abnahmerolle.
- Risiko, nötige Rechte, erlaubte Umgebung, Rückrollweg.
- Genehmigte Token-, Kosten- und Laufzeitgrenzen; technisch nicht
  durchsetzbare erforderliche Grenzen blockieren einen Live-Start.
- Gültiges Assignment, WIP-Prüfung und Ausschluss von Doppelvergabe;
  für Symphony zusätzlich bestehende Claim-/Lease-/Fencing-Gates.

Fehlende, unbekannte oder widersprüchliche Pflichtinformationen blockieren
den Handoff. Eine Issue-Markierung ist kein Assignment. Der Check begründet
keinen neuen WorkItem-Status und keine zweite Zustandsautorität.
Bei fehlender Zuweisung bleibt das Paket im Backlog/Hold.

### Ausführung und Abschluss

Codex erhält nur den für das Ergebnis erforderlichen Kontext und prüft
gezielt die betroffenen Dateien. Keine eigenmächtige Scope-Erweiterung.
Bei größerem Aufwand, fehlender Abhängigkeit oder Budgetgrenze stoppen,
Evidenz sichern und der Assignment Authority melden. Kein automatischer
Retry ohne gültige Autorisierung. Ein neuer Versuch verwendet die
bestehende WorkItem-Identität.

Abschluss erfordert Ergebnis, reproduzierbare Tests, PR/Head-SHA soweit
zutreffend, erforderliche grüne CI und risikogerechte technische Abnahme.
Merge und Deployment bleiben getrennt autorisiert.

### Einführung und Messung

Der manuelle Standard gilt ab CEO-Entscheidung für neue Handoffs.
Bestehende laufende Arbeit nicht ungeprüft abbrechen; offene Pakete vor
der nächsten Vergabe überprüfen und nötigenfalls versioniert zerlegen.
Keine automatische Aktivierung von Symphony oder Änderung an Produktion.

Die technische Durchsetzung wird separat innerhalb bestehender Control-Plane-
und Symphony-Gates geplant, zunächst offline mit synthetischen Fixtures.
Für die ersten zehn autorisierten Pakete erfassen: Schätzung, aktive
Laufzeit, Input-/Output-Tokens, tatsächlich belegte Kosten, Versuche,
Doppelstarts, Scope-Abweichungen und Erstabnahme. Fehlende Messwerte als
unbekannt kennzeichnen. Danach Größenklassen anhand der Evidenz kalibrieren.

## Konsequenzen

Mehr kleine Issues und explizite Abhängigkeiten, dafür gezieltere
Kontextaufnahme und klarere Abnahme. Keine künstliche Zerlegung eng
gekoppelter Änderungen zulasten der Konsistenz. Die bestehende
Assignment Authority und sämtliche Freigaberegeln bleiben unverändert.

## Alternativen

Die bisherige Vergabe umfangreicher Sammelaufträge bleibt nur für die
Planung als Parent-Issue geeignet, nicht als direkter Codex-Handoff.
Ein zusätzliches Aufgabenregister oder ein zweiter Scheduler wird verworfen.

## Bezug

- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0004](0004-branch-protection-codeowners.md)
- [Governance](../GOVERNANCE.md)
- [Symphony-Integration](../SYMPHONY-GITHUB-V1.md)
