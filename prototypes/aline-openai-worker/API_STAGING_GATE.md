# Aline L1 – FastAPI staging gate (Draft)

**Status:** Code-Vorbereitung auf separatem Feature-Branch. Nicht gemergt,
nicht deployt. Der bestehende Aline-Worker in Railway ist lediglich
`staged-create`; die zehn vorhandenen Staging-Änderungen bleiben unangetastet.

## Umfang

Die API ergänzt den bestehenden Worker nur als geschützte, **offline**
ausgeführte Demonstration. Sie verändert weder `worker.py` noch
`Dockerfile`, die Worker-Cron-Konfiguration oder die Control Plane.

- `GET /health`: Prozessstatus, unabhängig von Secrets.
- `GET /ready`: nur bei gesetztem `ALINE_PILOT_TOKEN` mit mindestens
  32 Zeichen bereit; kein Nachweis für Modell- oder Tool-Berechtigungen.
- `POST /v1/offline-analysis`: nur mit `X-Pilot-Token`, nur mit
  unverändertem synthetischem Bundle-Fixture.
- Ausgabe mit `api_requests_made=0` und `writes_performed=0`.
- Kein Modellaufruf, kein MCP, kein Notion/GitHub/Railway-Zugriff, keine
  WorkItem-Änderung. Kein Zugang zu echten Tickets.
- Swagger/OpenAPI-Routen deaktiviert. Kein öffentliches Domain-Setup.
- `Dockerfile.api` und `requirements-api.txt` sind getrennt
  vom bestehenden CLI-Worker.

## Lokale Prüfungen

```bash
python -m pip install -r prototypes/aline-openai-worker/requirements-api.txt
python -m unittest discover -s prototypes/aline-openai-worker/tests -v
```

Der Test der FastAPI-Endpunkte benötigt für `TestClient` auch `httpx`.
`httpx` ist eine Test-Abhängigkeit, keine Produktionsschnittstelle.

## Railway – erst nach gesondertem Staging-Gate

Der bestehende Service `aline-openai-worker-l1` ist für einen
periodischen CLI-Offline-Demolauf mit `Dockerfile`, einem Cron und
einem gepinnten Commit vorgemerkt. Er soll **nicht** stillschweigend
in einen dauerhaft laufenden API-Service umgewandelt werden.

Für eine spätere API-Staging-Instanz wäre getrennt zu prüfen:

1. Unabhängige Review und grüne aktuelle CI für den konkreten PR-Head.
2. Kosten-/Region-/Datenschutzentscheidung, da ein weiterer Railway-Dienst
   Kosten verursachen kann.
3. Eigene isolierte Service-Konfiguration unter
   `/prototypes/aline-openai-worker` mit `Dockerfile.api`.
4. `ALINE_PILOT_TOKEN` ausschließlich als Railway-Secret; niemals ins
   öffentliche Repository, Logs oder Tickets.
5. Keine öffentliche Domain bis Authentifizierung, Limits und
   Sicherheitsprüfung freigegeben sind.
6. Staging-Healthcheck `/ready`, Negativtests und beobachteter
   erfolgreicher Terminalstatus vor Statusmeldung als deployed.
7. Für echten OpenAI-Betrieb: eigene Modell-, Budget-, Datenübermittlungs-,
   IAM-/AuthZ- und CEO-Freigabe. Dieser PR implementiert das nicht.

**Kein Merge, Deployment, API-Key-Setzen oder produktiver Eingriff
durch diesen Entwurf.** Die Assignment Authority bleibt bei der
Control Plane gemäß Accepted ADR-0003.
