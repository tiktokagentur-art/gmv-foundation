# GMV Foundation

Technisches Fundament für GMV, Greenfield V1.

Dieses Repository ist der Neuaufbau. Legacy-Repositories sind historische Referenz.
Es wird kein Legacy-Code importiert.

**Leitsatz:** Build first. Verify everything. Scale after proof.

Das Repository ist öffentlich (CEO-Entscheidung vom 10.11.2026,
[ADR-0013](docs/adr/0013-repository-visibility-public.md)). Keine Secrets, keine
Verbindungsdaten, keine internen Betriebsdetails. Regeln: [SECURITY.md](SECURITY.md).

## Stand

Diese Baseline enthält Architektur, Governance, Sicherheitsregeln, versionierte
Entscheidungen und ein Anwendungsskelett. Sie legt keine Datenbank an, deployt
nicht und ändert Railway nicht.

| Work Package | Inhalt |
| --- | --- |
| GF-001 | Repository-Struktur, Beitragsregeln, CI |
| GF-003 | Architektur, Governance, Sicherheit, ADRs |
| GF-006 | Skelett: FastAPI, Health, Readiness, Alembic, Image |

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
- [ADR-0002](docs/adr/0002-python-fastapi.md) Python / FastAPI, entschieden am 09.11.2026
- [ADR-0003](docs/adr/0003-single-assignment-authority.md) eine Assignment Authority, ein Zustandseigentümer je Domäne
- [ADR-0004](docs/adr/0004-branch-protection-codeowners.md) Branch Protection für `main`, entschieden am 10.11.2026
- [ADR-0005](docs/adr/0005-railway-environments.md) Railway-Projekt GMV-V3, Umgebung staging, entschieden am 10.11.2026
- [ADR-0012](docs/adr/0012-hosting-region-usa.md) Hosting-Region USA, Railway `sfo`, entschieden am 09.11.2026
- [ADR-0013](docs/adr/0013-repository-visibility-public.md) Repository-Sichtbarkeit public, entschieden am 10.11.2026

Offene Punkte stehen im [ADR-Index](docs/adr/README.md).

## Struktur

```text
app/                         FastAPI-Skelett und Lebenszyklus-Vertrag, keine Endpunkte der V1
api/openapi.yaml             OpenAPI 3.1, nicht implementiert
migrations/                  Migrationen, erste Tabelle schema_meta
tests/                       health, ready, Migration, Vertrag gegen den Lebenszyklus
scripts/validate_structure.py
docs/ARCHITECTURE.md
docs/GOVERNANCE.md
docs/adr/                    ADR-Vorlage, Index, Entscheidungen
.github/workflows/ci.yml     Markdown, Struktur, Ruff, Pytest, Image
Dockerfile                   non-root, Healthcheck auf /health
.env.example                 Platzhalter, wird nicht gelesen
```

## Skelett

Konfiguration kommt nur aus der Prozessumgebung. `.env.example` enthält
Platzhalter und wird von der Anwendung nicht gelesen.

```bash
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

`GET /health` prüft den Prozess und öffnet keine Datenbank.
`GET /ready` prüft die Verbindung und antwortet bei Fehler mit 503.

Startbefehl für Railway, Port aus der Umgebung, identisch zum `CMD` im Image:

```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Das Image läuft als Benutzer `app` (uid 10001). Ein Deploy findet in diesem
Stand nicht statt. `DATABASE_URL` wird nicht ins Repository geschrieben.

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) lintet Markdown, prüft die
Struktur, führt Ruff und Pytest gegen PostgreSQL 18 aus und baut das Image.
Die Jobs heißen `lint-and-structure`, `backend` und `image`.

Die Prüfung ist vorhanden. Diese Baseline macht sie nicht zu einem erzwungenen
Merge-Schutz und ändert keine Repository-Einstellung
([ADR-0004](docs/adr/0004-branch-protection-codeowners.md)).

## Mitwirken

Regeln für Branches und Pull Requests: [CONTRIBUTING.md](CONTRIBUTING.md).

Änderungen an `main` nur per Pull Request. Die Review ist unabhängig: wer die
Änderung geschrieben hat, gibt sie nicht frei.
