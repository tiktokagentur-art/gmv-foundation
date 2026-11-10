# Anwendung

Skelett des Control-Plane-Dienstes. Kein Domänenmodell.

Python / FastAPI ist beschlossen
([ADR-0002](../docs/adr/0002-python-fastapi.md)), CEO-Entscheidung vom 09.11.2026.

| Modul | Aufgabe |
| --- | --- |
| `main.py` | `GET /health`, `GET /ready`, `GET /v1/whoami` |
| `auth.py` | FastAPI-Dependency für `Authorization: Bearer` |
| `credentials.py` | Workload-Keys, SHA-256, CLI `python -m app.credentials` |
| `errors.py` | V1-`ErrorBody` unter `/v1` |
| `request_id.py` | `X-Request-ID` prüfen oder erzeugen, an Antwort und Logs hängen |
| `config.py` | `DATABASE_URL` nur aus der Prozessumgebung, gehalten als `SecretStr` |
| `db.py` | Verbindung und Infrastrukturtabelle `schema_meta` |
| `logging_config.py` | JSON-Logs, Feld `request_id`, Secrets und Keys werden geschwärzt |

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

`GET /health` und `GET /ready` behalten Statuscode und JSON-Körper. Nur der
Header kommt hinzu. Sie verlangen keinen API-Key.

Eine unbehandelte Exception wird als JSON-Log mit `request_id` und
`error_type` geschrieben. Unter `/v1` ist die Antwort dann ein `ErrorBody`
mit Code `internal`. Außerhalb von `/v1`, also auch bei `/health` und
`/ready`, bleibt der Text `Internal Server Error`. Die Ursache steht in
beiden Fällen nicht in der Antwort.

`GET /v1/whoami` verlangt einen Workload-API-Key. `401`, `403` und `404`
unter `/v1` nutzen denselben `ErrorBody`, einschließlich `error.request_id`.
Schlüssel werden über das CLI ausgegeben und widerrufen:

```bash
python -m app.credentials issue --kind worker
python -m app.credentials revoke --credential-id <uuid>
```

Der Klartext erscheint einmal auf der Standardausgabe und wird nicht geloggt.
Einen HTTP-Endpunkt zum Ausstellen gibt es nicht.

Alembic liest dieselbe Variable. Ein Fehler auf der Konsole von `alembic` kann
die URL trotzdem enthalten, weil das der Traceback des Werkzeugs ist. Die
Anwendungslogger schreiben sie nicht.
