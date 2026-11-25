# GMV-AUTO-001 – Autonomie und Freigaben V1

Status: CEO-Politik beschlossen, **technisch nicht aktiviert**.

[ADR-0016](../adr/0016-risk-based-autonomy-mandate.md) ist die verbindliche
Grundsatzentscheidung. Der aktuelle GitHub-Istzustand ist getrennt davon in
[ADR-0004](../adr/0004-branch-protection-codeowners.md) dokumentiert.

## Architektur und Trust Boundaries

1. Die Control Plane ist die einzige Assignment Authority und prüft
   Identität, Lease, Fencing, Zustandsrechte und Budget vor jedem Dispatch.
2. Der noch ungemergte APR-005A-Klassifikator (PR #62) liefert R0–R4.
   Unbekannte, gemischte und kritische Änderungen dürfen nicht
   herabgestuft werden.
3. Eine unabhängig ausgeführte Review (Codex / andere Engine) liefert
   technische Findings. Erst ein separates formales, authentifiziertes
   GitHub-Approval zählt als erzwungener Review-Nachweis.
4. GitHub erzwingt PR-Grenze, aktuelle Required Checks, mindestens ein
   unabhängiges Approval und Bypass-Verbot. Die Control Plane darf diese
   GitHub-Regeln nicht simulieren oder umgehen.
5. Railway-Staging ist ein eigener Release-Korridor, getrennt von einem
   Merge nach main. Nur genehmigte Artefakte, Budgetgrenzen und
   nachvollziehbares Rollback.
6. Production, Rechte, Secrets und Ruleset-Änderungen bleiben manuell
   freigegebene geschützte Vorgänge.

## Testbarer Offline-Kontrakt

- Versionierte, deaktivierte Policy:
  [mandate-v1.json](../../config/autonomy/mandate-v1.json)
- Reiner Prüfer: [decision.py](../../app/autonomy/decision.py)
- Negative Tests: [test_autonomy_decision.py](../../tests/test_autonomy_decision.py)

Der Prüfer validiert exemplarische Angaben über Head-/Review-/CI-/Risk-SHA,
formal getrennte Reviewer, drei GitHub-Checks, GitHub-Ruleset, Control-Plane-
Lease, Status der Deployment-Trennung, Limits, Audit und Kill Switch.
Die Angaben sind **untrusted** und werden nicht selbst über GitHub oder
Railway attestiert. Das Modul darf nicht direkt in einer privilegierten
Workflow-Stufe verwendet werden. CANDIDATE_ONLY ist keine Autorisierung.

## Rollout und Abnahmekriterien

| Phase | Inhalt | Erfolg |
| --- | --- | --- |
| 0 – Offline | ADR, Policy, Tests, Draft-PR | CI + unabhängiger Review |
| 1 – Sicherheitsbasis | APR-005A, Review-Gates, eigene IDs, GitHub-Approval erzwingen | Live-Readback, Negativtests, Ruleset ohne Bypass |
| 2 – Release-Trennung | Railway-Autodeploy und Wait-for-CI auditieren, Staging-Korridor isolieren | Nachweis: Merge allein ist kein unerwarteter Deploy |
| 3 – Pilot R0/R1 | Nur genehmigte Pfade, max. ein Pilotjob parallel, harte Limits, Kill Switch | Sieben Tage störungsfreier Audit mit Rollback-Übung |
| 4 – Produktion | Separates ADR-0011, Release-Berechtigte, Notfallkonzept | Erst danach neuer Aktivierungsbeschluss |

Freigabe- und Kill-Switch-Prüfungen müssen gegen die serverseitigen
Istzustände laufen. Aktivierung nicht über PR-Beschreibung, Issue-Label,
Agent-Selbstbewertung oder einen bloßen lokalen Policy-Schalter.

## Live-Readback 22.11.2026 – P0-Abhängigkeit

[Issue #70](https://github.com/tiktokagentur-art/gmv-foundation/issues/70)
hält die notwendige Prüfung der Railway-/GitHub-Kopplung fest.
In `GMV-V3/staging/backend` sowie `GMV Forge/production/gmv-foundation`
ist dieselbe Quelle `tiktokagentur-art/gmv-foundation:main` konfiguriert.
Beide Konfigurationen melden `checkSuites=false`. Die zuletzt
beobachteten Deployments vom 20.11.2026 sind auf denselben main-SHA
`3c585c7` bezogen: Staging erfolgreich, Production fehlgeschlagen;
ein früherer Production-Deploy war erfolgreich.

Das beweist noch nicht den aktuellen Live-Traffic oder den exakten
GitHub-Push-Trigger. Die operative Entkopplung ist aber **nicht
nachgewiesen** und muss als P0-Sperre vor Auto-Merge behandelt werden.
Ein `production_deploy_enabled=false` in unserer inaktiven Policy
blockiert **keine** extern konfigurierte Railway-Autodeploy-Verbindung.
Nur überprüfte Plattform-Gates und dokumentierte Readbacks
schließen diese Lücke.

## Vor der ersten Aktivierung

- [ ] PR #62, #64, #65 unabhängig prüfen und konfliktfrei integrieren;
      keine Stacked-PR-Abhängigkeit verdecken
- [ ] Getrennte, nachweislich kontrollierte Worker-/Reviewer-Identitäten
- [ ] GitHub-Ruleset mit mindestens einem erforderlichen Approval,
      veraltete Reviews entwerten, Reviewer-Trennung und kein Bypass
- [ ] Required Checks am aktuellen PR-Head und vollständiger Status-Readback
- [ ] Verbindlicher Control-Plane-Admission- und Lease-/Fencing-Nachweis
- [ ] Railway-Staging-Auslöser und unveränderliches Artefakt verifizieren
- [ ] Hard Limits, Audit, sofortige Deaktivierung, Rollback testen
- [ ] Security-Review, Abnahmebericht und dokumentierte Korridor-Aktivierung

**Bis dahin:** nur Offline-Auswertung. Kein Auto-Merge, kein
Produktionsdeployment, keine Änderungen an Rechten, Rulesets oder Secrets.
