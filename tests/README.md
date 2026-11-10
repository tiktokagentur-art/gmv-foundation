# Tests

Prüfungen des Skeletts. Sie sind keine zweite Quelle für fachlichen Zustand.

| Test | Was belegt wird |
| --- | --- |
| `test_gitleaks_scan.py` | gepinntes gitleaks erkennt ein synthetisches Secret außerhalb des Repos |
| `test_health.py` | `/health` ohne Datenbank, keine Dotenv-Datei, Settings ohne Klartext |
| `test_ready.py` | `/ready` gegen PostgreSQL, 503 ohne brauchbare Verbindung, keine Secrets in Antwort oder Log |
| `test_migration.py` | `alembic upgrade head` legt `schema_meta` an |
| `test_logging.py` | JSON-Logs ohne Zugangsdaten, auch beim Loggen der Settings |
| `test_request_id.py` | `X-Request-ID` erzeugt, gültig übernommen, ungültig ersetzt; Logzeilen eines Requests enthalten die ID; unbehandelte Exception als eine JSON-Zeile mit `request_id`, `error_type`, `path` und `method`; Schwärzung bleibt; `/health` und `/ready` unverändert |
| `test_access_log.py` | Access-Zeile von Uvicorn ist JSON, trägt die `request_id` dieses Requests und schwärzt `DATABASE_URL` |
| `test_lifecycle_contract.py` | Lebenszyklus und OpenAPI-Enum gegen `app/lifecycle.py` |

Ohne `DATABASE_URL` werden die Tests übersprungen, die eine Datenbank brauchen.
In CI ist das keine Option: dort zeigt die Variable auf PostgreSQL 18.
