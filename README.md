# GMV Foundation

Technisches Fundament für GMV, Greenfield V1.

Dieses Repository ist der Neuaufbau. Legacy-Repositories sind historische Referenz.
Es wird kein Legacy-Code importiert.

**Leitsatz:** Build first. Verify everything. Scale after proof.

Das Repository ist öffentlich. Keine Secrets, keine Verbindungsdaten, keine internen
Betriebsdetails. Regeln: [SECURITY.md](SECURITY.md).

## Stand

Diese Baseline enthält Architektur, Governance, Sicherheitsregeln und versionierte
Entscheidungen. Sie enthält keine Anwendung, legt keine Datenbank an, deployt nicht
und ändert Railway nicht.

| Work Package | Inhalt |
| --- | --- |
| GF-001 | Repository-Struktur, Beitragsregeln, CI |
| GF-003 | Architektur, Governance, Sicherheit, ADRs |

## Schichten

| Schicht | Verantwortung |
| --- | --- |
| Foundation | Architektur, Governance, Sicherheitsregeln, Daten- und API-Verträge, Identitätsmodell, versionierte Entscheidungen |
| Infrastructure | Railway-Dienste, PostgreSQL direkt auf Railway, Backups, Secrets, Deployments, Monitoring, Wiederherstellung |
| Control Plane | WorkItems, genau eine Assignment Authority, Worker-Registrierung, AuthN/AuthZ, Claims, Leases, Fencing, Status, Audit-Trail |
| Worker Runtime | Identitätsgebundene Ausführung, Heartbeats, Abgabe von Ergebnis und Fehler |
| Software Factory | Änderungen, Tests, CI, Pull Requests, unabhängige Reviews, gesteuerte Releases |

Je Zustandsdomäne gibt es genau eine autoritative Instanz. Die Foundation definiert
die Verträge. Die Infrastructure implementiert sie und weist sie durch Tests nach.

Die Landkarte steht in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Verbindlich ist nur, was ein ADR mit Status `Accepted` sagt.
[docs/GOVERNANCE.md](docs/GOVERNANCE.md) beschreibt, wie Entscheidungen entstehen.

## Entscheidungen

Der Index liegt unter [docs/adr/README.md](docs/adr/README.md).

Gültig:

- [ADR-0001](docs/adr/0001-postgresql-on-railway.md) PostgreSQL auf Railway, entschieden am 09.11.2026
- [ADR-0003](docs/adr/0003-single-assignment-authority.md) eine Assignment Authority, ein Zustandseigentümer je Domäne

Vorschlag, nicht beschlossen:

- [ADR-0002](docs/adr/0002-python-fastapi.md) Python / FastAPI

Weitere offene Punkte sind ADR-0004 bis ADR-0011. Sie sind Vorschläge ohne Beschluss.

## Struktur

```text
app/                         Platzhalter, kein Anwendungscode
tests/                       Platzhalter, noch keine Vertragstests
scripts/validate_structure.py
docs/ARCHITECTURE.md
docs/GOVERNANCE.md
docs/adr/                    ADR-Vorlage, Index, Entscheidungen
.github/workflows/ci.yml     Markdown-Lint und Strukturprüfung
.github/CODEOWNERS           Entwurf, keine aktiven Owner
SECURITY.md
CONTRIBUTING.md
```

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) lintet Markdown und prüft die
Struktur. Der Job heißt `lint-and-structure`.

Die Prüfung ist vorhanden. Diese Baseline macht sie nicht zu einem erzwungenen
Merge-Schutz und ändert keine Repository-Einstellung
([ADR-0004](docs/adr/0004-branch-protection-codeowners.md)).

## Mitwirken

Regeln für Branches und Pull Requests: [CONTRIBUTING.md](CONTRIBUTING.md).

Änderungen an `main` nur per Pull Request. Die Review ist unabhängig: wer die
Änderung geschrieben hat, gibt sie nicht frei.
