# ADR-0016: Temporärer CEO-geführter Holiday Mode

- Status: Proposed
- Datum: 2026-11-26
- Entscheider: CEO

## Kontext

[ADR-0003](0003-single-assignment-authority.md) verlangt genau eine
Assignment Authority. [ARCHITECTURE.md](../ARCHITECTURE.md) und
[DATA_MODEL.md](../DATA_MODEL.md) benennen die Control Plane als Eigentümerin
von WorkItems, Zuweisungen, Claims, Leases, Fencing und Audit. Diese Domänen
sind auf `main` noch nicht implementiert; die API-Endpunkte sind Verträge.
[ADR-0009](0009-migration-compatibility.md) zur Datenbankmigration ist
`Proposed`.

[ADR-0008](0008-auth-standard.md) vertagt Menschen-Authentisierung. Eine
technisch durchsetzbare CEO-Identität besteht daher noch nicht. Derzeit kann
eine CEO-Entscheidung in diesem Chat eine eng begrenzte Entwicklung autorisieren,
aber sie kann weder einen Control-Plane-Claim noch einen Lease oder eine
produktive Berechtigung erzeugen.

Der Holiday Mode soll die manuelle Koordination durch den CEO ermöglichen,
während virtuelle Mitarbeiter abwesend sind. GitHub Issues und Labels sind
laut [SYMPHONY-GITHUB-V1.md](../SYMPHONY-GITHUB-V1.md) keine
Autorisierungsnachweise und dürfen nicht als Dispatcher dienen.

## Entscheidung

Nicht entschieden. Vorgeschlagen wird ein befristeter Betriebsmodus innerhalb
derselben Control Plane und derselben Assignment Authority. Es wird keine
zweite Zuteilungsinstanz geschaffen.

### Betriebsmodi und Zustandsbesitz

- `NORMAL_MODE`: Aline darf zulässige Zuteilungsanträge an die Control Plane
  stellen. Die Assignment Authority allein nimmt sie an oder lehnt sie ab.
- `HOLIDAY_MODE`: Eine authentisierte CEO-Identität darf manuelle
  Zuteilungsanträge an dieselbe Assignment Authority stellen. Die Authority
  vergibt weiterhin Zuweisung, Claim, Lease und Fencing und schreibt den
  WorkItem-Status und Audit.
- Modus und monoton steigende `mode_epoch` liegen in der bestehenden
  autoritativen Control-Plane-Datenbank. Die Modusumschaltung wird von derselben
  Authority atomar ausgeführt. GitHub, ChatGPT, Codex, Labels und Logs halten
  keine Kopie dieses Zustands und dürfen keine Zuweisung autoritativ ändern.
- Codex muss als Worker mit eigener Identität registriert sein. Eine CEO-
  Anweisung ersetzt weder Authentisierung noch Lease, Fencing, Branchschutz,
  CI, Review oder andere technische Sicherheitsgates.
- Höchstens drei aktive Codex-Arbeitspakete insgesamt. Die Grenze umfasst
  angenommene Claims mit aktiver Lease und wird transaktional in der
  Assignment Authority durchgesetzt. Der Aufrufer kann das Limit nicht erhöhen.
- Eine mit einer Assignment verbundene CEO-Entscheidung nennt Arbeitspaket,
  Umfang, betroffene Zustimmung, Gültigkeit und Ergebnisbeleg. Sie ersetzt nur
  ausdrücklich benannte, organisatorisch ersetzbare Freigaben. Gesetzliche,
  vertragliche, sicherheitsbezogene und technische Pflichten sowie unabhängige
  Reviews bleiben bestehen. Welche Mitarbeiterfreigaben ersetzbar sind, muss
  der CEO vor Aktivierung einzeln oder über eine präzise Positivliste festlegen.

### Bootstrap ohne funktionsfähige Assignment Authority

Die Reparatur der Assignment Authority darf nicht selbst einen Claim dieser
Authority voraussetzen. Vorgeschlagen wird dafür genau ein **Bootstrap-
Entwicklungsauftrag**:

- Die CEO-Entscheidung autorisiert ausschließlich den beschriebenen
  Repository-Änderungsumfang auf einem kurzlebigen Branch und als Draft-PR.
  Sie ist eine Governance-Autorisierung für Code-Arbeit, kein Control-Plane-
  WorkItem.
- Das Bootstrap-Paket wird mit eindeutiger Kennung, Basis-SHA, Dateigrenzen,
  Ablaufdatum, Abnahmekriterien und CI-Nachweisen im Issue/PR festgehalten.
  Während dieses Bootstrap-Schritts läuft höchstens eine Codex-Session.
- Issue, ChatGPT und Codex dürfen keine Laufzeitaufträge verteilen, Claims,
  Leases, Fencing oder WIP-Zähler führen, WorkItem-Status schreiben oder
  Dispatch auslösen. GitHub ist hier nur der nachvollziehbare Code- und
  Review-Kanal. Damit entsteht keine zweite Assignment Authority.
- Bootstrap endet nach technischer Prüfung des Draft-PRs. Weitere
  Implementierung, Modusaktivierung und Laufzeitnutzung gehen erst weiter,
  wenn die CEO-Autorisierung für den nächsten Schritt vorliegt und die
  Control Plane ihre einzige Assignment Authority nachweisbar durchsetzt.

### Aktivierung und Rückkehr

- Aktivierung setzt eine authentisierte CEO-Identität, eine erfüllte
  Engineering-Abnahme, funktionsfähige Claims/Leases/Fencing, serverseitige
  WIP-Durchsetzung, vollständigen Audit, aktuelle grüne CI und einen
  dokumentierten Ablaufzeitpunkt voraus.
- Wechsel zwischen Modi ist nur möglich, wenn die bisherige Authority
  Zuteilungen stoppt und aktive Assignments abgearbeitet oder abgelaufen sind.
  Ein atomarer Moduswechsel erhöht `mode_epoch`; alte Requests und Leases
  können damit keine neue Zuweisung legitimieren. Bei Unsicherheit wird kein
  Dispatch angenommen.
- Deaktivierung nutzt denselben Übergang zurück zu `NORMAL_MODE`. Die
  Rückkehr ist nur zulässig, wenn Aline/Control Plane betriebsbereit ist und
  die Authority den Moduswechsel bestätigt. Bei Nichterreichbarkeit bleiben
  Zuteilungen gesperrt; es gibt keinen lokalen oder GitHub-basierten
  Fallback-Dispatcher.
- Ablaufzeitpunkt, CEO-Widerruf oder ein Sicherheits-/Auditfehler sperren
  weitere Holiday-Zuteilungen. Die bereits laufenden Assignments werden durch
  dieselbe Authority beendet, freigegeben oder auslaufen gelassen.

### Audit

Der append-only Audit-Trail der Control Plane soll Moduswechsel und
`mode_epoch`, CEO-Entscheidungsreferenz, Autorisierer, Zielidentität,
WorkItem/Assignment, Claim, Lease, Fencing, WIP-Zählerstand, Zeitpunkte und
Ergebnisbelege enthalten. Secrets und vertrauliche Payloads gehören nicht in
Events.

Der aktuelle Vertrag beschreibt Audit-Ereignisse für angenommene
Zustandsänderungen; abgelehnte Anträge erzeugen derzeit kein `AuditEvent`.
Für den geforderten vollständigen Holiday-Audit muss vor Implementierung
entschieden werden, wie abgelehnte Autorisierungs- und WIP-Anträge sicher und
anhängend protokolliert werden, ohne den fachlichen Zustand zu ändern.

### Reproduzierbare Abnahme

Nach Annahme dieses ADR soll eine isolierte Umsetzung mindestens folgende
Tests gegen dieselbe Control-Plane-Authority enthalten:

1. `NORMAL_MODE` nimmt nur Aline-Anträge an; `HOLIDAY_MODE` nur
   CEO-autorisierte Anträge. Fremde Rollen werden abgelehnt.
2. In beiden Modi schreibt ausschließlich die Assignment Authority; Claims,
   Leases, Fencing und Statusänderungen folgen den bestehenden Verträgen.
3. Parallele Claims überschreiten auch bei konkurrierenden Datenbanktransaktionen
   nie drei aktive Codex-Arbeitspakete.
4. Moduswechsel wird bei aktiven Assignments abgelehnt oder wartet auf deren
   kontrolliertes Ende; nach dem Wechsel werden veraltete Epochs und Fencing-
   Tokens abgelehnt.
5. Audit ist append-only und verbindet Modus, CEO-Entscheidung,
   Zuweisung/Claim/Lease, Ergebnis sowie Ablehnungsgrund; ein abgelehnter
   Request verändert keinen WorkItem-Zustand.
6. Abgelaufener oder widerrufener Modus, fehlende CEO-Identität,
   Datenbankfehler und unvollständiger Audit führen fail-closed zu keinem
   Dispatch.
7. Tests laufen reproduzierbar mit den bestehenden CI-Befehlen und einer
   ephemeren PostgreSQL-18-Testdatenbank; sie benötigen weder Railway noch
   Produktionszugang.

## Konsequenzen

- Dieses ADR ist ein Vorschlag und erteilt keine Laufzeitberechtigung. Wegen
  `Proposed` darf der Holiday Mode noch nicht implementiert oder aktiviert
  werden.
- Die Control Plane muss vor Holiday Mode erst die WorkItem-, Assignment-,
  Claim-, Lease-, Fencing- und Audit-Verträge implementieren.
- Menschen-Authentisierung, Datenbankmigration und Audit für Ablehnungen
  bleiben explizite Vorbedingungen. [ADR-0009](0009-migration-compatibility.md)
  bleibt unentschieden; dieses ADR entscheidet keine Migrationsstrategie.
- Der Bootstrap-Pfad autorisiert nur die Reparatur des Authority-Mechanismus.
  Er ist kein dauerhafter Ersatz für Assignment, Claim oder Lease.
- Merge, Deployment und produktive Aktivierung brauchen weiterhin ihre
  separaten Freigaben und vorhandenen Sicherheitsgates.

## Alternativen

- Eine lokale ChatGPT-/Codex-Warteschlange oder GitHub-Labels als Dispatcher:
  verworfen, weil dadurch neben der Control Plane ein zweiter Owner für
  Zuteilung, Status und WIP entstünde.
- CEO oder Codex schreiben WorkItems, Claims oder Leases direkt in die
  Datenbank: verworfen, weil das ADR-0003 verletzt und die serverseitige
  Autorisierung umgeht.
- Holiday Mode als separates Control-Plane-System: verworfen, weil zwei
  Assignment Authorities konkurrieren könnten.

## Bezug

- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0008](0008-auth-standard.md)
- [ADR-0009](0009-migration-compatibility.md)
- [ADR-0014](0014-github-moderator-trust-boundary.md)
- [../ARCHITECTURE.md](../ARCHITECTURE.md)
- [../DATA_MODEL.md](../DATA_MODEL.md)
- [../WORKITEM_LIFECYCLE.md](../WORKITEM_LIFECYCLE.md)
- [../SYMPHONY-GITHUB-V1.md](../SYMPHONY-GITHUB-V1.md)
- [../../SECURITY.md](../../SECURITY.md)
