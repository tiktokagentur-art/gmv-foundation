#!/usr/bin/env python3
"""Lesender Nachweis der Live-Rechte der GitHub App gmv-symphony-worker (ENG-003).

Ruft per App-JWT (RS256, < 10 min) nur ``GET /app`` und ``GET /app/installations``
auf und gibt ausschließlich Slug, Sichtbarkeitshinweis, App-Rechte, Events und je
Installation Konto, Repository-Auswahl und Rechte aus. Es wird kein
Installation-Token erzeugt; JWT- und Key-Werte erscheinen nie in der Ausgabe.

Warum nicht ``GET /apps/<slug>``? Der öffentliche Endpunkt liefert für private
Apps (nur im Owner-Konto installierbar) ohne Authentifizierung 404. ``GET /app``
mit App-JWT ist der vorgesehene Weg, die eigene App zu lesen.

Die Liste der Repositories je Installation braucht ein Installation-Token; dafür
gibt es ``symphony_app_token.py selftest`` (holt Token, liest, widerruft sofort).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import symphony_app_token as sat  # noqa: E402


def summarize_app(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise sat.TokenError("GET /app returned no object")
    return {
        "slug": data.get("slug"),
        "owner": (data.get("owner") or {}).get("login"),
        "permissions": data.get("permissions"),
        "events": data.get("events"),
        "installations_count": data.get("installations_count"),
    }


def summarize_installations(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise sat.TokenError("GET /app/installations returned no list")
    return [
        {
            "id": i.get("id"),
            "account": (i.get("account") or {}).get("login"),
            "repository_selection": i.get("repository_selection"),
            "permissions": i.get("permissions"),
            "events": i.get("events"),
            "suspended_at": i.get("suspended_at"),
        }
        for i in data
    ]


def audit(key_path: Path, http: sat.Http | None = None) -> dict[str, Any]:
    http = http or sat.urllib_http
    jwt = sat.build_jwt(sat.APP_ID, key_path)
    headers = sat._headers(jwt)
    status_app, app = http("GET", f"{sat.API}/app", headers, None)
    if status_app != 200:
        raise sat.TokenError(f"GET /app failed (HTTP {status_app})")
    status_inst, inst = http("GET", f"{sat.API}/app/installations", headers, None)
    if status_inst != 200:
        raise sat.TokenError(f"GET /app/installations failed (HTTP {status_inst})")
    status_public, _ = http("GET", f"{sat.API}/apps/{app.get('slug')}", {
        "Accept": "application/vnd.github+json", "User-Agent": "gmv-symphony-worker"}, None)
    return {
        "app": summarize_app(app),
        "public_apps_slug_http": status_public,
        "installations": summarize_installations(inst),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--key", type=Path, default=Path(
        os.environ.get("GMV_SYMPHONY_APP_KEY_PATH", str(sat.DEFAULT_KEY_PATH))))
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(args.key), indent=2, sort_keys=True))
    except sat.TokenError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
