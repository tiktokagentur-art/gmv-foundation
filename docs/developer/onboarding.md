# Getting Started

Die [Repository-README](../../README.md) enthält den Startbefehl.
Für die lokale Entwicklung gilt Python 3.12; in CI wird PostgreSQL 18
für Datenbanktests bereitgestellt. Konfiguration kommt aus der Umgebung;
echte Credentials gehören nie in Git.

## Entwicklungsprüfungen

```bash
npx --yes markdownlint-cli2@0.24.0
python3 scripts/validate_structure.py
python3 scripts/check_docs.py
ruff check app tests migrations scripts
pytest
```

Abhängigkeiten werden nach [CONTRIBUTING.md](../../CONTRIBUTING.md)
installiert. Ohne `DATABASE_URL` werden Datenbanktests lokal
übersprungen, in CI nicht.

## Code finden

- [Anwendung](../../app/README.md)
- [API-Vertrag](../../api/openapi.yaml)
- [Tests](../../tests/README.md)
- [CI](../../.github/workflows/ci.yml)

Änderungen werden über einen Branch und einen PR eingereicht.
Unabhängige Prüfung und Freigaberegeln gelten unverändert.
