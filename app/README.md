# Anwendung

Skelett des Control-Plane-Dienstes. Kein Domänenmodell.

Python / FastAPI ist beschlossen
([ADR-0002](../docs/adr/0002-python-fastapi.md)), CEO-Entscheidung vom 09.11.2026.

| Modul | Aufgabe |
| --- | --- |
| `main.py` | `GET /health`, `GET /ready` |
| `request_id.py` | `X-Request-ID` prüfen oder erzeugen, an Antwort und Logs hängen |
| `config.py` | `DATABASE_URL` nur aus der Prozessumgebung, gehalten als `SecretStr` |
| `db.py` | Verbindung und Infrastrukturtabelle `schema_meta` |
| `logging_config.py` | JSON-Logs, Feld `request_id`, Secrets werden geschwärzt |

`GET /health` öffnet keine Datenbank. `GET /ready` antwortet mit 503, wenn die
Verbindung fehlt oder scheitert. Die Antwort enthält keine Verbindungsdaten.

`DATABASE_URL` wird als `SecretStr` gehalten. `str` und `repr` der Settings
zeigen den Wert nicht. Der Klartext wird nur gelesen, wenn eine Verbindung
geöffnet wird. Die Schwärzung in `logging_config.py` bleibt zusätzlich wirksam.

Jeder HTTP-Request erhält eine Request-ID. Ein einzelner Header `X-Request-ID`
wird übernommen, wenn der Wert eine UUID der Form `8-4-4-4-12` ist. Fehlt der
Header, liegt er mehrfach vor oder ist der Wert keine solche UUID, erzeugt das
Skelett eine neue. So gelangen keine Zeilenumbrüche oder fremden Zeichen in die
Logs. Dieselbe ID steht im Antwort-Header `X-Request-ID`. Ein Logging-Filter
schreibt sie während des Requests als Feld `request_id` in jede JSON-Zeile.
Nachricht und Traceback werden weiterhin geschwärzt.

Die Access-Logzeile von Uvicorn (`uvicorn.access`) nutzt denselben
JSON-Formatter und dieselbe Schwärzung. Auch sie trägt die `request_id` des
Requests. Uvicorn setzt vor dem Import eigene Handler. `configure_logging`
entfernt sie, damit diese Zeile denselben Formatter erreicht.

`GET /health` und `GET /ready` behalten Statuscode und JSON-Körper. Nur der
Header kommt hinzu. Eine unbehandelte Exception erzeugt genau eine
JSON-Fehlerzeile mit `request_id`, `error_type`, `path` und `method`. `path`
ist der URL-Pfad ohne Query. Pfad und Methode werden wie die Nachricht
geschwärzt, bevor die Zeile geschrieben wird. Die Antwort ist der bisherige
Text `Internal Server Error` und nennt die Ursache nicht. Einen Metrik- oder
Fehler-Endpunkt gibt es nicht. V1-Fehlerkörper sind im Skelett nicht
implementiert und gehören zu GF-008. `error.request_id` bleibt das optionale
Feld in `api/openapi.yaml`.

Alembic liest dieselbe Variable. Ein Fehler auf der Konsole von `alembic` kann
die URL trotzdem enthalten, weil das der Traceback des Werkzeugs ist. Die
Anwendungslogger schreiben sie nicht.
