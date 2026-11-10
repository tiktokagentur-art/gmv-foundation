# Anwendung

Skelett des Control-Plane-Dienstes. Kein Domänenmodell.

Python / FastAPI ist beschlossen
([ADR-0002](../docs/adr/0002-python-fastapi.md)), CEO-Entscheidung vom 09.11.2026.

| Modul | Aufgabe |
| --- | --- |
| `main.py` | `GET /health`, `GET /ready` |
| `config.py` | `DATABASE_URL` nur aus der Prozessumgebung, gehalten als `SecretStr` |
| `db.py` | Verbindung und Infrastrukturtabelle `schema_meta` |
| `logging_config.py` | JSON-Logs, Secrets werden geschwärzt |

`GET /health` öffnet keine Datenbank. `GET /ready` antwortet mit 503, wenn die
Verbindung fehlt oder scheitert. Die Antwort enthält keine Verbindungsdaten.

`DATABASE_URL` wird als `SecretStr` gehalten. `str` und `repr` der Settings
zeigen den Wert nicht. Der Klartext wird nur gelesen, wenn eine Verbindung
geöffnet wird. Die Schwärzung in `logging_config.py` bleibt zusätzlich wirksam.

Alembic liest dieselbe Variable. Ein Fehler auf der Konsole von `alembic` kann
die URL trotzdem enthalten, weil das der Traceback des Werkzeugs ist. Die
Anwendungslogger schreiben sie nicht.
