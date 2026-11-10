# Tests

Prüfungen des Skeletts. Sie sind keine zweite Quelle für fachlichen Zustand.

| Test | Was belegt wird |
| --- | --- |
| `test_gitleaks_scan.py` | gepinntes gitleaks erkennt ein synthetisches Secret außerhalb des Repos |
| `test_health.py` | `/health` ohne Datenbank, keine Dotenv-Datei, Settings ohne Klartext |
| `test_ready.py` | `/ready` gegen PostgreSQL, 503 ohne brauchbare Verbindung, keine Secrets in Antwort oder Log |
| `test_migration.py` | `alembic upgrade head` legt `schema_meta` an; `credentials` kommt additiv dazu und lässt sich auf `0001` zurücknehmen |
| `test_credentials.py` | gültiger, fehlender, falscher, widerrufener und abgelaufener Key; kein Key und kein Hash in Log oder Antwort; `ErrorBody` mit `request_id` |
| `test_logging.py` | JSON-Logs ohne Zugangsdaten, auch beim Loggen der Settings |
| `test_request_id.py` | `X-Request-ID` erzeugt, gültig übernommen, ungültig ersetzt; Logzeilen eines Requests enthalten die ID; Schwärzung bleibt; `/health` und `/ready` unverändert |
| `test_lifecycle_contract.py` | Lebenszyklus und OpenAPI-Enum gegen `app/lifecycle.py` |

Ohne `DATABASE_URL` werden die Tests übersprungen, die eine Datenbank brauchen.
In CI ist das keine Option: dort zeigt die Variable auf PostgreSQL 18.
