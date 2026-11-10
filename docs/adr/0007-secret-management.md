# ADR-0007: Secret-Verwaltung, Rotation, Break-glass

- Status: Proposed
- Datum: 2026-11-09
- Überarbeitet: 2026-11-10 (Vorschlag ergänzt, nicht entschieden)
- Entscheider: offen

## Kontext

[../../SECURITY.md](../../SECURITY.md) verbietet Secrets in Git, Logs, Beispielen
und CI-Ausgaben. Jeder Dienst und jeder Worker hat eine eigene Identität.
Rechte sind auf die Aufgabe begrenzt.

Offen ist, welcher Secret-Provider die Werte hält, wie oft sie rotiert werden
und wie ein Break-glass-Zugang aussieht. Break-glass meint einen kontrollierten
Notfallzugriff: personengebunden, zeitlich begrenzt und im Audit-Trail sichtbar.

### Ist-Stand

- In der Railway-Umgebung `staging` ([ADR-0005](0005-railway-environments.md))
  laufen ein Anwendungsdienst und PostgreSQL. Der Anwendungsdienst erhält die
  Variable `DATABASE_URL`. Werte wurden nicht gelesen. Ob sie gesealt sind und
  welche Datenbankrolle sie nutzt, ist NICHT VERIFIZIERT.
- Der GitHub Moderator legt seinen App-Private-Key laut
  [../github-moderator.md](../github-moderator.md) nur als Environment-Secret ab.
  Ob das die verbindliche Regel ist, hält [ADR-0014](0014-github-moderator-trust-boundary.md)
  offen. Die Environments haben `can_admins_bypass: false`
  ([ADR-0004](0004-branch-protection-codeowners.md)).
- Secret Scanning und Push Protection sind aktiv
  ([ADR-0013](0013-repository-visibility-public.md)). CI scannt die Git-Historie
  mit gepinntem gitleaks ([../../CONTRIBUTING.md](../../CONTRIBUTING.md)).

### Fakten aus Primärquellen

- Railway Sealed Variables: Der Wert geht an Build und Deployment, ist aber in
  UI, API und CLI nicht sichtbar. Ein Seal lässt sich nicht aufheben.
  ([Railway Variables](https://docs.railway.com/variables))
- Railway-Project-Tokens gelten für genau eine Umgebung eines Projekts.
  Account-Tokens reichen über alle Ressourcen.
  ([Railway Public API](https://docs.railway.com/integrations/api))
- Railway-Audit-Logs werden im Plan Free, Trial und Hobby 48 Stunden
  aufbewahrt, bei Pro 30 Tage, bei Enterprise 18 Monate.
  ([Railway Audit Logs](https://docs.railway.com/enterprise/audit-logs))
- Environment RBAC, also der Schutz einer Umgebung vor Nicht-Admins, gibt es
  nur bei Railway Enterprise.
  ([Railway Environments](https://docs.railway.com/environments))
- GitHub Environment-Secrets stehen nur Jobs zur Verfügung, die das Environment
  referenzieren. Mit Required Reviewers sind sie erst nach einer Freigabe zugänglich.
  ([GitHub Environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments))
- Railway beschreibt eine Rotation mit Überlappung: neues Credential ausstellen,
  Variable ändern, deployen, prüfen, erst dann das alte widerrufen.
  ([Railway Guide](https://railway.com/guides/rotate-credentials-zero-downtime.md))

### Annahmen (getrennt von den Fakten)

- A1: Railway läuft im Plan Free. Übermittelt vom Head of Engineering, vom CEO
  nicht bestätigt. NICHT VERIFIZIERT. Folge: Das Audit-Log hält nur 48 Stunden.
  Ein Erzwingen von MFA für alle Mitglieder ist laut Railway erst ab Pro möglich
  ([Railway Security](https://docs.railway.com/enterprise/security)).
- A2: [ADR-0012](0012-hosting-region-usa.md) gilt nur für Railway-Dienste. Ein
  externer Secret-Manager wäre frei wählbar. Übermittelt vom Head of
  Engineering, vom CEO nicht bestätigt. NICHT VERIFIZIERT.

## Entscheidung

Nicht entschieden. Secret-Provider, Rotationsfrist und Break-glass-Verfahren sind offen.

### Vorschlag zur Prüfung (keine Entscheidung)

1. Provider in V1 sind die Plattformen selbst. Laufzeit-Secrets liegen als
   Railway Sealed Variables, CI-Secrets nur als GitHub Environment-Secrets mit
   Required Reviewers, ohne Self-Review und ohne Admin-Bypass. Privilegierte
   Werte liegen nicht als Repository-Secret.
2. Identitäten: je Dienst eine eigene Datenbankrolle, je Umgebung ein eigenes
   Project-Token, keine Account-Tokens in CI. Agenten und Tools sind eigene
   Subjekte mit eigenen, eng begrenzten Tokens.
3. Rotation nach dem Überlappungsmuster. Außerplanmäßig sofort bei Verdacht auf
   ein Leak, beim Austritt einer Person oder bei einem gemeldeten Vorfall eines
   Anbieters. Die planmäßige Frist ist ein Kandidat, keine Entscheidung (z. B.
   90 Tage). In den gelesenen Quellen steht keine verbindliche Frist.
4. Break-glass: ein personengebundener Notfall-Admin mit MFA, befristet
   freigeschaltet. Weil das Railway-Audit bei A1 nur 48 Stunden hält, wird jede
   Nutzung sofort außerhalb von Railway protokolliert. Danach werden alle
   berührten Werte rotiert. Kein gemeinsames Dauerpasswort.
5. Ein externer Manager (z. B. Infisical oder Doppler) kommt auf Wiedervorlage,
   sobald mehr als eine Plattform Secrets braucht oder automatische Rotation
   gefordert ist.

### Zu klären

- ob A1 und A2 gelten (CEO-Bestätigung)
- Rechtetrennung zwischen `staging` und einer späteren `production`: eigenes
  Projekt oder Enterprise ([ADR-0005](0005-railway-environments.md))
- wer Break-glass auslösen darf und wie lange Nachweise aufbewahrt werden
- Rotationsfrist je Secret-Klasse
- welche Rechte Agenten und Connectors bei Railway und GitHub erhalten

## Konsequenzen

- Bis zum Entscheid gilt kein Provider als gewählt. Die bestehende Nutzung von Railway-Variablen und GitHub Environment-Secrets ist Ist-Stand, kein Entscheid.
- Ein Break-glass-Weg, der nicht auditierbar ist oder ein gemeinsames Dauergeheimnis verteilt, widerspricht SECURITY.md und wird nicht ergänzt, um die Lücke zu füllen.
- Beispiele bleiben ohne verwendbare Werte. Die Wegwerf-Zugangsdaten der CI-Datenbank in `ci.yml` sind eine kommentierte Ausnahme dafür.
- Wird der Vorschlag angenommen: Ein Rollback auf ein älteres Deployment stellt
  auch dessen Variablen wieder her ([ADR-0011](0011-release-rollback-authority.md)).
  Nach einer Rotation ist das ein Risiko, das geprüft werden muss.

## Alternativen

| Option | Vorteil | Nachteil |
| --- | --- | --- |
| A: Plattform-Secrets (Vorschlag) | kein zusätzliches Hochwert-Secret, kein neuer Anbieter | Audit-Dauer planabhängig; keine Rechtetrennung im selben Projekt ohne Enterprise |
| B: gehosteter Manager (Infisical, Doppler) | zentrale Rotation und Audit | neues Sync-Token mit hohem Wert, neuer Anbieter (A2) |
| C: Vault selbst betrieben | volle Kontrolle | hoher Betriebsaufwand, eigener Dienst mit Backup ([ADR-0006](0006-backup-retention-rpo-rto.md)) |
| D: Cloud-Secret-Manager (z. B. AWS) | ausgereift | keine Managed Rotation für Railway-Postgres (NICHT VERIFIZIERT), zusätzlicher Cloud-Zugang |

## Bezug

- [../../SECURITY.md](../../SECURITY.md)
- [ADR-0004](0004-branch-protection-codeowners.md)
- [ADR-0005](0005-railway-environments.md)
- [ADR-0006](0006-backup-retention-rpo-rto.md)
- [ADR-0008](0008-auth-standard.md)
- [ADR-0011](0011-release-rollback-authority.md)
- [ADR-0012](0012-hosting-region-usa.md)
- [ADR-0013](0013-repository-visibility-public.md)
- [ADR-0014](0014-github-moderator-trust-boundary.md)
