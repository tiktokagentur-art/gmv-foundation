# ADR-0015: Dauerhaftes L1-Testmandat für Aline

- Status: Accepted
- Datum: 2026-11-20
- Entscheider: CEO, Pizza Club
- Geltungsbereich: GMV-VE-001 (Aline), isolierte nichtproduktive Tests

## Kontext

Der bisherige OpenAI-Pilot ist auf einzelne manuell freizugebende Tests
ausgelegt. Der CEO hat am 20.11.2026 entschieden, dass Aline wiederkehrende
L1-Tests eigenständig durchführen darf, ohne für jeden Test eine weitere
CEO-Freigabe anzufordern. Damit wird **kein** Produktionsrecht verliehen.

Die bestehenden Draft-PRs #31 (Worker), #33 (Notion read-only) und #38
(einmaliger Actions-Test) enthalten eigene Gates und werden durch dieses
ADR weder gemergt noch automatisch entsperrt. Das zu #38 gehörige
Einmaligkeits-Gate darf nicht stillschweigend umgangen oder umgebaut werden.

[ADR-0003](0003-single-assignment-authority.md) legt weiterhin genau eine
Assignment Authority fest; [ADR-0004](0004-branch-protection-codeowners.md)
schützt `main`. Die Secret- und Release-Fragen bleiben in
[ADR-0007](0007-secret-management.md) und
[ADR-0011](0011-release-rollback-authority.md) offen.

## Entscheidung

Entschieden. Aline (GMV-VE-001) erhält ein **dauerhaftes,
widerrufbares L1-Testmandat** für isolierte, synthetische Offline- und
OpenAI-API-Tests innerhalb eines vorab technisch freigegebenen
Testkorridors. Nach einmaliger Aktivierungsabnahme entfällt die
**einzelne CEO-Freigabe für jeden konformen L1-Test**.

### Erlaubter Korridor

- Nur dedizierte Nichtproduktionsumgebung und fest geprüfte
  synthetische Testdaten. Keine echten Tickets, personenbezogenen
  Daten, Drittanbieterinhalte oder ungeprüfte Netzwerkquellen.
- Nur bereits geprüfte Worker-Versionen und freigegebene Modelle.
  Änderungen an Modell, Prompt mit höherem Risikoprofil, Eingabedaten,
  Tools oder Laufzeit benötigen erneute Korridorabnahme.
- Pro Test höchstens **ein** Modellaufruf, maximal **2 USD**
  kalkulierte Kosten, keine automatischen API-Retries und höchstens
  ein gleichzeitig laufender Test. Ein Verlust der Antwort ist kein
  Freibrief für einen erneuten Aufruf.
- Maximal **10 USD pro Kalendermonat** für das ausschließlich Aline-L1
  zugeordnete OpenAI-Projekt. Das Projekt benötigt ein nachweislich
  **durchgesetztes Hard-Limit** von höchstens 10 USD; reine Warnungen
  gelten nicht. Wegen möglicher verzögerter Abrechnung ist dies keine
  Garantie auf centgenaue Kostenbegrenzung.
- Ein vorgeschalteter Kontingent-Guard prüft vor dem Aufruf den
  verbleibenden lokalen Korridor, schätzt Kosten konservativ anhand
  der aktuellen offiziellen Modellpreise und verweigert bei
  Ungewissheit den Aufruf. Nur ein Modellturn und begrenzte
  Input-/Output-Tokens, Laufzeit und Netzwerkziele.
- Minimaler revisionsfähiger Audit-Nachweis pro Lauf: eindeutige
  Run-ID, attestierte Worker-Identität, Commit/SHA, Modell,
  synthetische Fixture-ID, Ergebnisstatus, Anzahl Aufrufe,
  Usage/Kosten soweit verfügbar und Fehler. Keine Prompts,
  Secrets oder Antwortinhalte in öffentlichen CI-Logs.
- Abweichungen, fehlende Kostendaten, fehlende Identität,
  ausstehende CI, unklare frühere API-Aufrufe oder verletzte
  Grenzen bedeuten **Fail Closed** und Anhalten weiterer Tests.

### Voraussetzungen der einmaligen Aktivierung

1. Eigene Worker-/Service-Identität mit Least Privilege und
   dediziertem OpenAI-Projekt samt isoliertem Secret; kein
   Benutzerkonto-Sharing oder Secret-Export in Chat, Git oder Logs.
2. Modellzugriff und Hard-Limit im konkreten Projekt überprüft;
   getrennte Nutzungsauswertung nachvollziehbar.
3. Ein wiederholbar nutzbarer, eigenständig geprüfter L1-Runner mit
   serverseitigen Grenzen, sicherem Konto- und Run-Gate, aktuellen
   grünen CI-Checks, Negativtests und ohne automatische Umgehung
   der bestehenden Einmal-Testregeln. Workflow-Änderungen über PR.
4. Einmalige technische Sicherheits-/Engineering-Abnahme des
   exakt abgegrenzten Korridors und dokumentierte CEO-Aktivierung.
   Nachfolgende konforme L1-Ausführungen brauchen keine neue
   CEO-Freigabe, solange der Korridor unverändert ist.

### Unverändert verboten

Aline darf aus diesem Mandat keine Produktionsdeployments,
`main`-Merges, Secrets oder Rechte verändern, keine
Arbeitsaufträge eigenmächtig zuteilen, keine echten WorkItems
aktualisieren, keine Claims/Leases/Fencing vergeben und keine
neuen Schreibzugriffe erhalten. Read-only-Zugriff auf reale
Quellen ist eine getrennte Entscheidung. Review-, CI-,
Branchschutz- und Secret-Vorgaben bleiben bestehen.

Die am 20.11.2026 temporär genehmigte Self-Review-Ausnahme
für `aline-l1-staging` wird **nicht** verstetigt. Sie endet
gemäß der ursprünglichen Ausnahme; anschließend ist
Self-Review wieder auszuschließen. Dieses ADR hebt keinen
Admin-Bypass-Schutz auf und erteilt keine GitHub-
Environment-Freigabe.

## Konsequenzen

- Dauerhaft ist **die CEO-Policy**; die technische Berechtigung
  startet erst bei erfüllten Aktivierungsbedingungen.
- Der bisherige PR #38 bleibt ein einmaliger Test und wird nicht
  automatisch zum wiederholten L1-Runner.
- Engineering implementiert den separaten wiederholbaren Korridor
  und belegt negative Fälle (Budget, Identität, Parallelität,
  falscher Datensatz, falscher SHA, fehlende Usage, Fehler).
- Ein neuer oder erweiterter Toolzugriff, L2-Aufgabenannahme oder
  produktiver Einsatz erfordert ein separates Mandat.
- Der CEO kann dieses Mandat jederzeit widerrufen. Bei einem
  Sicherheitsvorfall sind Schlüssel/Zugriff zu sperren und
  noch nicht abgeschlossene Läufe zu untersuchen.
- Das praktische Freigabe- und Aktivierungsprotokoll steht in
  [../ALINE-L1-MANDATE.md](../ALINE-L1-MANDATE.md).

## Alternativen

Der bisherige Einzeltest mit separater CEO-Freigabe wurde
für den Dauerbetrieb als unnötig langsam verworfen.
Ein unbeschränktes autonomes Mandat wurde wegen
Kosten-, Secret- und Produktionsrisiken nicht erteilt.

## Bezug

- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0004](0004-branch-protection-codeowners.md)
- [ADR-0007](0007-secret-management.md)
- [ADR-0011](0011-release-rollback-authority.md)
- [GOVERNANCE.md](../GOVERNANCE.md)
- [ALINE-L1-MANDATE.md](../ALINE-L1-MANDATE.md)
