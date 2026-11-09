# Tests

Prüfungen des Skeletts. Sie sind keine zweite Quelle für fachlichen Zustand.

| Test | Was belegt wird |
| --- | --- |
| `test_health.py` | `/health` ohne Datenbank, keine Dotenv-Datei |
| `test_ready.py` | `/ready` gegen PostgreSQL, 503 ohne brauchbare Verbindung, keine Secrets in der Antwort |
| `test_migration.py` | `alembic upgrade head` legt `schema_meta` an |
| `test_logging.py` | JSON-Logs ohne Zugangsdaten |
| `test_lifecycle_contract.py` | Lebenszyklus und OpenAPI-Enum gegen `app/lifecycle.py` |

Ohne `DATABASE_URL` werden die Tests übersprungen, die eine Datenbank brauchen.
In CI ist das keine Option: dort zeigt die Variable auf PostgreSQL 18.
