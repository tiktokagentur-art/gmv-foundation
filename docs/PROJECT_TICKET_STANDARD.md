# GMVGANG-Standard für Tickets und Projekte V1

**Status:** CEO-Auftrag vom 26.11.2026; Einführung über Pull Request.  
**Geltung:** GitHub-Issues und Projekte in `gmv-foundation`. Die Regeln ergänzen die technische WorkItem-Zustandsmaschine; sie ändern keine Zustands-, Zuweisungs-, Review- oder Release-Autorität.

## 1. Verbindliche Grundsätze

1. Ein Ticket beschreibt ein überprüfbares Ergebnis.
2. Nutzen, Umfang, Abhängigkeiten und Risiken sind vor der Umsetzung verständlich.
3. Der Issue-Status entspricht dem belegten Arbeitsstand.
4. Ein Ticket wird erst geschlossen, wenn Ergebnis, Beleg und Abnahme dokumentiert sind.
5. Erst Fertigstellen, dann neue Arbeit beginnen. WIP-Grenzen gelten für alle Teams und Worker.

Dieser Standard verwendet die Begriffe und Zustände aus [WORKITEM_LIFECYCLE.md](WORKITEM_LIFECYCLE.md). GitHub-Issues sind keine zweite Instanz, die den autoritativen `WorkItem.status` schreibt. Zuweisung, Claim, Lease, Fencing und Zustandsübergänge bleiben bei der Control Plane und ihrer Assignment Authority gemäß [ADR-0003](adr/0003-single-assignment-authority.md).

## 2. Arbeitsebenen

| Ebene | Zweck | Regel |
| --- | --- | --- |
| Ziel / Initiative | Geschäftsergebnis oder Quartalsziel | Messbares Ziel, Verantwortungsbereich und Nicht-Ziele festhalten |
| Epic / Projekt | Zusammenhängendes Vorhaben mit mehreren Ergebnissen | In kleine, prüfbare Inkremente teilen; aktive Projekte begrenzen |
| Story / Aufgabe | Eigenständig abnehmbares Ergebnis | Innerhalb von höchstens sieben Kalendertagen abschließbar |
| Subtask | Abgrenzbarer Teilschritt einer Aufgabe | Eigenständiger Nachweis oder klarer Beitrag zum übergeordneten Ergebnis |
| Bug | Abweichung vom erwarteten Verhalten | Erwartung, tatsächliches Verhalten, Auswirkungen und Reproduktion angeben |
| Spike | Zeitlich begrenzte Untersuchung | Frage, Zeitlimit (in der Regel ein bis drei Tage) und Ergebnisbericht festlegen |
| Tech Debt / Chore | Wartung oder technische Verbesserung | Nutzen, Risiko oder vermiedene Folgekosten nennen |

Aufgaben, die voraussichtlich länger als sieben Tage dauern, werden in kleinere Ergebnisse zerlegt. Technische Schichten allein sind kein sinnvoller Zuschnitt, wenn dadurch kein prüfbares Zwischenergebnis entsteht.

## 3. Pflichtangaben eines Tickets

Jedes neue Ticket enthält:

- **Titel:** konkret und handlungsorientiert.
- **Kontext und Nutzen:** Problem, betroffene Rolle und erwarteter Nutzen.
- **Ergebnis und Umfang:** was geliefert wird und was ausdrücklich außerhalb des Umfangs bleibt.
- **Akzeptanzkriterien:** beobachtbare, prüfbare Aussagen.
- **Abhängigkeiten und Risiken:** bekannte Vorarbeiten, externe Dienste, Sicherheit und Datenschutz.
- **Priorität:** P0 bis P3 mit kurzer Begründung.
- **Ergebnisbeleg und Abnahme:** erwartete Nachweisart und zuständige Abnahmerolle.
- **Verantwortung:** benötigte Rolle oder Rückfragenkontakt; die tatsächliche Zuweisung erfolgt über die Assignment Authority.

Bei Bugs kommen Reproduktionsschritte, Version/Umgebung, erwartetes und tatsächliches Verhalten sowie Auswirkungen hinzu. Screenshots und Logs dürfen keine Zugangsdaten oder unnötigen personenbezogenen Daten enthalten.

## 4. Definition of Ready

Ein Ticket ist `ready`, wenn:

- Ziel und Nutzen verständlich sind;
- Akzeptanzkriterien und Ergebnisbeleg feststehen;
- Umfang und Nicht-Ziele klar sind;
- die Aufgabe in höchstens sieben Tagen abschließbar oder passend zerlegt ist;
- Abhängigkeiten und Rückfragen geklärt oder mit Verantwortlichen dokumentiert sind;
- Risiken, Datenschutz- und Sicherheitsbezug benannt sind;
- Priorität und zuständige Abnahmerolle feststehen;
- notwendige Spezifikationen oder Entscheidungen verlinkt sind.

Eine Ausnahme wird vor Beginn mit Grund, Risiko, Entscheiderrolle und Ablaufdatum im Issue dokumentiert. Sie erteilt keine zusätzliche Berechtigung und ändert keine Freigabegates.

## 5. Definition of Done

Ein Ticket ist erst `done`, wenn:

- die Akzeptanzkriterien erfüllt sind;
- das konkrete Ergebnis im Issue oder über einen stabilen Link vorliegt;
- Ergebnisbeleg und Abnahme durch die zuständige Rolle dokumentiert sind;
- verknüpfte PRs, Dokumente, Incidents und Folgeaufgaben aktuell sind;
- bekannte offene Punkte sichtbar sind und keinen unerklärten Widerspruch zum Ticketziel bilden.

Für Codeänderungen gelten zusätzlich die Regeln aus [CONTRIBUTING.md](../CONTRIBUTING.md): PR gegen `main`, drei erforderliche grüne Checks und kein Direkt- oder Force-Push. Erforderliche Reviewer werden nicht durch diesen Standard neu festgelegt.

Ticketabschluss, Release und Wirkungsmessung sind getrennte Aussagen:

- **Done:** Ergebnis angenommen und belegt.
- **Released:** in der ausdrücklich freigegebenen Zielumgebung verfügbar.
- **Validated:** Wirkung am vereinbarten Erfolgsmaß geprüft.

Ein Ticketabschluss ist keine Produktionsfreigabe. Deployment, Release und Änderungen an Berechtigungen benötigen die jeweils geltenden Freigaben.

## 6. Priorisierung und WIP

Die Reihenfolge des Backlogs ist sichtbar und begründet. Priorität wird nach Wirkung, Risiko, Dringlichkeit und Abhängigkeiten bestimmt, nicht nach Lautstärke. RICE oder andere Schätzverfahren können bei ausreichenden Daten zur Entscheidungshilfe dienen; sie ersetzen keine Entscheidung durch die zuständige Autorität.

| Priorität | Richtlinie |
| --- | --- |
| P0 | Produktionsausfall, Datenverlust oder akute Sicherheitslücke; sofort über den Incident-/Security-Prozess behandeln |
| P1 | Kritische Kernfunktion oder wichtiger freigegebener Termin erheblich gefährdet |
| P2 | Begrenzt beeinträchtigt, mit vertretbarem Workaround; geordnet einplanen |
| P3 | Geringe Auswirkung oder Verbesserung; Backlog und regelmäßige Neubewertung |

Bestehende WIP-Grenzen bleiben maßgeblich: höchstens drei aktive Gruppenprojekte und höchstens drei aktive Projekte je Venture; ein Projektumfang darf sieben Tage nicht überschreiten, bevor er in kleinere Inkremente aufgeteilt wird. Auf Worker-Ebene gilt als Startregel höchstens ein aktives Ticket je Worker. Abweichungen werden mit Grund und Ablaufdatum dokumentiert und dürfen die höheren Projektgrenzen nicht überschreiten.

## 7. Ablauf und Statuspflege

Die technische Statusmaschine bleibt unverändert:

`created → ready → claimed → in_progress → submitted → done`

`failed` und `cancelled` bleiben die definierten Endzustände. Die Schritte „Refined/Ready“, „In Progress“, „Review“ und „Test/Validation“ aus dem allgemeinen Prozess beschreiben fachliche Arbeit; sie werden nicht als zusätzliche `WorkItem.status`-Werte eingeführt. Review und Test werden über PR, CI, Abnahmebeleg und verknüpfte Artefakte nachgewiesen.

- Blockaden erhalten einen sichtbaren Grund, eine verantwortliche Rolle und den nächsten Klärungsschritt.
- Arbeitsstand wird mindestens einmal pro Arbeitstag aktualisiert.
- Issue, Branch, Commit und PR werden über die Ticketnummer verknüpft.
- Vorhandene Issues werden vor der Anlage ähnlicher Tickets auf Duplikate und Abhängigkeiten geprüft.
- Veraltete Tickets werden im regelmäßigen Backlog-Review neu bewertet oder mit Begründung geschlossen.
- Sensible Sicherheits- oder Datenschutzdetails gehören nicht in öffentliche Issues; dort steht nur ein Verweis auf den zugriffsbeschränkten Nachweis.

## 8. Projektstart, Steuerung und Abschluss

Ein Projektstart hält mindestens fest: Ziel und Nutzen, Erfolgsmaß, Nicht-Ziele, Owner-Rolle, Entscheiderrolle, Abhängigkeiten, Risiken, erste Inkremente und Meilensteine. Kein Inkrement überschreitet die Sieben-Tage-Grenze.

Wöchentlich wird ein schriftlicher Status gepflegt:

```markdown
## Projektstatus <Projekt> – <Datum>

**Gesamtstatus:** grün / gelb / rot

**Erreicht:**
- ...

**Als Nächstes:**
- ...

**Risiken und Blocker:**
- ... (Gegenmaßnahme, verantwortliche Rolle, Termin)

**Entscheidungsbedarf:**
- ... (Entscheiderrolle, benötigt bis)
```

Änderungen an Umfang, Termin oder Budget werden mit Grund, Auswirkung, Entscheidung und Datum protokolliert. Beim Abschluss werden Übergabe, Betrieb, Ergebnisbelege und Abgleich mit dem Erfolgsmaß festgehalten.

## 9. Kennzahlen und Pflege

Durchlaufzeit, Durchsatz, Blockierzeit, Anteil ungeplanter Arbeit, Wiedereröffnungen und Alter des Backlogs dienen der Prozessverbesserung. Sie werden nicht zur individuellen Leistungsbewertung verwendet.

Backlog-Refinement, Duplikatprüfung, einheitliche Labels und Verknüpfungen sind regelmäßig durchzuführen. Für Codex-/Symphony-Aufträge gelten zusätzlich die engeren Regeln im [Codex Engineering Playbook](symphony/codex-engineering.md) und in der [Symphony-Pilotvorlage](../.github/ISSUE_TEMPLATE/symphony-pilot.yml).
