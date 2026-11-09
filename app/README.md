# Anwendung

Skelett des Control-Plane-Dienstes. Kein Domänenmodell.

Python / FastAPI ist ein Vorschlag und nicht beschlossen
([ADR-0002](../docs/adr/0002-python-fastapi.md)). GF-006 baut dieses Skelett auf
dem Vorschlag. Der Status bleibt `Proposed`, bis die CEO entscheidet.

| Modul | Aufgabe |
| --- | --- |
| `main.py` | `GET /health`, `GET /ready` |
| `config.py` | `DATABASE_URL` nur aus der Prozessumgebung |
| `db.py` | Verbindung und Infrastrukturtabelle `schema_meta` |
| `logging_config.py` | JSON-Logs, Secrets werden geschwärzt |

`GET /health` öffnet keine Datenbank. `GET /ready` antwortet mit 503, wenn die
Verbindung fehlt oder scheitert. Die Antwort enthält keine Verbindungsdaten.

Alembic liest dieselbe Variable. Ein Fehler auf der Konsole von `alembic` kann
die URL trotzdem enthalten, weil das der Traceback des Werkzeugs ist. Die
Anwendungslogger schreiben sie nicht.
