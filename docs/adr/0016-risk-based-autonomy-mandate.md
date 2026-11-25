# ADR-0016: Risikobasiertes Autonomiemandat

- Status: Accepted
- Datum: 2026-11-22
- Entscheider: CEO, GMVGANG
- Geltungsbereich: Software Factory und Control Plane, risikobegrenzter Pilot

## Kontext

Der CEO will autonome Ausführung innerhalb vordefinierter Grenzen statt
individueller Freigaben je Routineaktion. Die bestehenden Schutzmechanismen
verbieten direkte Writes auf main; das aktive Ruleset verlangt derzeit 0 formale
Approvals, aber drei aktuelle grüne Checks. Autonomes Mergen ist im Repository
nicht aktiviert. Ein unabhängiger technischer Review durch Codex ersetzt keinen
formalen GitHub-Review.

ADR-0003 schützt die einzige Assignment Authority. ADR-0004 dokumentiert den
aktuellen GitHub-Schutz; ADR-0011 bleibt für Production Release/Rollback
Proposed. Ein Live-Readback am 22.11.2026 zeigt zusätzlich eine als
`production` benannte Railway-Umgebung in `GMV Forge`, deren Service
`gmv-foundation` ebenso wie `GMV-V3/staging/backend` aus
`tiktokagentur-art/gmv-foundation:main` konfiguriert ist. In beiden
Source-Konfigurationen steht `checkSuites=false`. In der
Production-Umgebung gab es bereits ein erfolgreiches Deployment am
20.11.2026, während das neueste Deployment fehlgeschlagen ist.
Damit ist eine echte operative Release-Trennung ausdrücklich **nicht**
nachgewiesen; ein möglicher automatischer Deploy nach einem Merge
muss vor Freigabe überprüft und entkoppelt werden (Issue #70). Der ungemergte PR #62 (APR-005A) enthält den Kandidatenklassifikator
R0–R4, PR #64 den Codex-Review-Vertrag und PR #65 die Offline-Fix-Schleife.
Diese Änderungen dürfen nicht als bereits aktive Infrastruktur gelten.

## Entscheidung

Entschieden. GMVGANG verwendet ein dauerhaftes, widerrufbares, risikobasiertes
Delegationsmandat. Der CEO genehmigt die nachstehende Delegationspolitik,
nicht den sofortigen technischen Vollzug. Nur explizit aktivierte und
nachgewiesene, eng begrenzte Korridore dürfen später Routineaktionen ohne
erneute individuelle CEO-Freigabe durchführen.

### Risikoklassen und Maßnahmen

| Klasse | Beispiele | Delegation im V1-Pilot |
| --- | --- | --- |
| R0 | Abgegrenzte Guides/Tutorials gemäß APR-005A | Merge-Kandidat |
| R1 | Isolierte Tests/Fixtures/Mocks gemäß APR-005A | Merge-Kandidat |
| R2 | Sonstige Dokumentation | Manuelle Freigabe |
| R3 | Anwendung, CI, Governance, Security, Abhängigkeiten, Löschungen | Manuelle Freigabe |
| R4 | Unklar, ungültig, unbekannt | Blockiert bis geklärt |

Bei gemischten Änderungen gilt immer das höchste Risiko. Der Klassifikator
muss Pfad-, Rename- und Löschrisiken prüfen. Eine ungesicherte oder fehlende
Klassifikation ist niemals eine Merge-Erlaubnis.

### Delegationsgrenzen

- Autonomer PR-Entwurf, Tests, technische Reviews und isolierte Offline-Fixes
  bleiben innerhalb existierender Identitäts-, Kosten- und Sandbox-Grenzen möglich.
- Autonomer Merge nach main: erst nach nachgewiesener Aktivierung für R0/R1,
  gültigem Control-Plane-Mandat, aktuellem formalen GitHub-Approval einer
  unabhängig authentifizierten Identität, mindestens einem von GitHub
  erzwungenen Approval, unveränderter Bypass-Sperre und allen drei aktuellen,
  erforderlichen grünen Checks. Codex-Kommentare oder synthetische Reports
  sind kein GitHub-Approval.
- Staging-Deployment: nur als separater, explizit aktivierter Korridor mit
  unveränderlichem Artefakt, Staging-Umgebung, überprüfter Deployment-Trennung,
  Budget-/Laufzeitgrenzen, Health-Checks, Rollback und Audit.
- Ein Merge ist **kein** Produktionsrelease. Der produktive Release-Korridor
  bleibt deaktiviert, solange ADR-0011, Owner, technische Environment-Gates,
  Backup-/Rollback-Nachweise und Release-Sicherheitsabnahme offen sind.
- Berechtigungen, Secrets, Rulesets, Produktionsdaten, Datenbankmigrationen,
  kritische Infrastruktur und neue Vertrauensgrenzen bleiben ausdrücklich
  außerhalb des delegierten Mandats.
- Die Control Plane bleibt einzige Assignment Authority; GitHub Labels,
  Agentenentscheidungen und Audit-Berichte verleihen keine eigenen
  Claims/Leases/Fencing-Rechte.

### Durchsetzung

Jede privilegierte Entscheidung muss serverseitig erfolgen: gebundene
Workload-Identität, aktuell gültiger Lease/Fencing-Nachweis, Commit- und
Review-SHA, unverändertes Ruleset, geschützte GitHub-API-Checks,
Policy-Version, harte Limits, Audit und jederzeitiger Widerruf.

Fehlt ein Nachweis, ist das Ergebnis BLOCKED. Fail-open, Selbstfreigaben,
Admin-Bypass, stiller Rechtezuwachs und Reviews auf veralteten SHAs sind verboten.

Die Version 1 in config/autonomy/mandate-v1.json ist bewusst
enabled=false. Der reine Offline-Prüfer kann höchstens CANDIDATE_ONLY
zurückgeben und darf weder Merge, Deployment noch Rechteänderung auslösen.
Seine Eingaben sind keine attestierten Autorisierungsnachweise.

Die fachliche Zustimmung ersetzt nicht die separate technische
Aktivierungsabnahme des konkreten Korridors. Danach benötigt jede konforme
Routineaktion keine erneute CEO-Einzelfreigabe. Eine Erweiterung des Korridors
bedarf einer neuen Entscheidung.

## Konsequenzen

- Erstes Inkrement: versionierte Policy, Offline-Auswertung, Negativtests,
  Review-fähiger Draft-PR. Keine Regel-, Rechte- oder Deploy-Änderungen.
- Vor Merge-Automation: unabhängige GitHub-Reviewer-Identitäten, enforcebare
  Approval-Regel, sichere Control-Plane-Integration und Readback.
- Vor Staging-Automation: GitHub/Railway-Trigger entkoppeln und verifizieren,
  Rollback testen, Kill Switch und Budgetgrenzen nachweisen.
- Für Production bleibt ADR-0011 offen. Keine Aktivierung bis zur
  separaten Freigabe.
- Bestehende Accepted ADRs und GitHub-Regeln gelten, bis sie formal geändert
  und technisch überprüft wurden.

## Alternativen

Eine einzelne CEO-Freigabe für jede Routineaktion bremst den Dauerbetrieb.
Ein uneingeschränktes Autonomie-Mandat wäre wegen Review-, Identitäts- und
Produktionsrisiken nicht vertretbar. Gewählt wird ein stufenweiser,
widerrufbarer Korridor.

## Bezug

- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0004](0004-branch-protection-codeowners.md)
- [ADR-0011](0011-release-rollback-authority.md)
- [GOVERNANCE.md](../GOVERNANCE.md)
- [GMV-AUTO-001](../autonomy/README.md)
