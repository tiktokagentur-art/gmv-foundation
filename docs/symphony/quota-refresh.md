# Symphony und Codex: Quota- und Refresh-Regel

Status: Regel ab Merge, Host-Umsetzung siehe PR-Text. Bezug: Petrus
24.11.2026 23:20, Samira 24.11.2026 23:25, Aline 24.11.2026 23:41.

## Ausgangslage

`research.sh` (Codex-Recherchen, nur auf dem Host) und Symphony nutzen
dasselbe Konto: Petrus' ChatGPT-/Codex-Login, eine `~/.codex/auth.json`.
In beiden Hüllen ist `auth.json` per `--ro-bind` nur lesbar eingebunden
([sandbox.md](sandbox.md)). Codex kann ein abgelaufenes Token deshalb nicht
selbst erneuern. Kontingent und Rate-Limits teilen sich alle Läufe.

## Regel: fail-closed

Bei einem dieser Befunde stoppt der Lauf, es gibt keinen automatischen
neuen Versuch:

| Code | Befund |
| --- | --- |
| `quota_exhausted` | Kontingent erschöpft (`usage_limit_reached`, `insufficient_quota`) |
| `rate_limited` | Rate-Limit (`rate_limit_exceeded`, HTTP 429) |
| `auth_failed` | Login ungültig (HTTP 401, `invalid_grant`, `refresh_token_*`, „codex login“) |
| `auth_refresh_blocked` | Erneuerung wollte `auth.json` schreiben (`EROFS`, Read-only file system) |

Folgen:

1. Rückgabewert `9` (`RC_QUOTA_FAIL_CLOSED`) aus `run-symphony.sh`.
2. Eine Zeile in `/workspace/research/ALERTS.log` (dieselbe Datei wie
   `research.sh`, Rechte 600), nur mit Issue und Code, ohne Log-Inhalte.
3. Stopp-Marker `/workspace/research/state/quota-stop`. Solange er existiert,
   verweigert `run-symphony.sh` jeden Start mit rc=9, vor Slot, Proxy und
   Token. Das verhindert einen Retry-Sturm über alle Issues.
4. Kein Schreibzugriff auf `auth.json`, kein `codex login` aus einer Hülle,
   kein Wechsel auf ein anderes Konto oder einen API-Key.

## Wiederaufnahme (nur Mensch)

1. Petrus erneuert den Login außerhalb jeder Hülle (`codex login`) oder
   wartet das Ende des Rate-Limit- bzw. Kontingentfensters ab.
2. Ein Operator prüft `ALERTS.log`, dokumentiert die Ursache und entfernt
   erst dann den Marker.
3. Der nächste Lauf startet normal; die Einmal-Sperre des betroffenen Issues
   bleibt bestehen, ein Neustart dieses Issues braucht ein neues Go.

## Grenzen

- Erkannt wird über Textmuster in den Protokollen des Laufs (Symphony-Logs,
  Dashboard-Ausgabe, Wächter-Log). Ein neues Fehlerformat von Codex oder
  Symphony kann unerkannt bleiben; dann greifen weiter Wächter und Budget.
- `research.sh` erkennt Login-Fehler bereits selbst (Alert, kein Retry).
  Den Marker beachtet es erst nach der Host-Umsetzung.
- Ein eigenes Konto für Symphony würde das geteilte Kontingent auflösen; das
  ist eine Entscheidung von Petrus und nicht Teil dieser Regel.
