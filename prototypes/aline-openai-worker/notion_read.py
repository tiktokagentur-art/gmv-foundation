"""ALINE-NOTION-001: bounded Notion page reads; no model calls or Notion writes.

This opt-in adapter is deliberately separate from the L1 worker entrypoint.
Only explicitly allowlisted ticket pages are fetched, with GET only.
"""
import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from urllib import error, request


NOTION_API = "https://api.notion.com/v1/pages/"
NOTION_VERSION = "2026-03-11"
MAX_PAGES = 10
MAX_RESPONSE_BYTES = 262144


class NotionReadError(RuntimeError):
    """Safe, credential-free failure message."""


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise NotionReadError("Notion redirect refused")


def normalize_id(value):
    try:
        return str(uuid.UUID(str(value).strip()))
    except (ValueError, AttributeError, TypeError) as exc:
        raise NotionReadError("Invalid Notion page UUID") from exc


def authorize_read(page_ids, *, confirmed, environment=None):
    """Fail closed before any network call; never expose the token."""
    env = os.environ if environment is None else environment
    if not confirmed:
        raise NotionReadError("Explicit --confirm-notion-read required")
    if not page_ids or len(page_ids) > MAX_PAGES:
        raise NotionReadError("Specify 1 to 10 ticket page IDs")
    requested = [normalize_id(value) for value in page_ids]
    if len(requested) != len(set(requested)):
        raise NotionReadError("Duplicate page IDs refused")
    configured = env.get("NOTION_ALLOWED_PAGE_IDS", "").split(",")
    if not configured or not any(value.strip() for value in configured):
        raise NotionReadError("NOTION_ALLOWED_PAGE_IDS is required")
    allowed = {normalize_id(value) for value in configured if value.strip()}
    if len(allowed) > MAX_PAGES or not set(requested).issubset(allowed):
        raise NotionReadError("Page not in the explicit allowlist")
    token = env.get("NOTION_API_TOKEN", "")
    if not token or token.isspace():
        raise NotionReadError("NOTION_API_TOKEN is required")
    return requested, token


def fetch_page(page_id, token, *, opener=None):
    """Retrieve one allowlisted page through Notion's read-only GET endpoint."""
    page_id = normalize_id(page_id)
    req = request.Request(
        NOTION_API + page_id,
        headers={
            "Authorization": "Bearer " + token,
            "Notion-Version": NOTION_VERSION,
            "Accept": "application/json",
        },
        method="GET",
    )
    client = request.build_opener(NoRedirect()) if opener is None else opener
    try:
        with client.open(req, timeout=10) as response:
            if response.status != 200:
                raise NotionReadError("Unexpected Notion HTTP status")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except error.HTTPError as exc:
        raise NotionReadError("Notion read denied or failed: HTTP " + str(exc.code)) from None
    except (error.URLError, TimeoutError, OSError):
        raise NotionReadError("Notion read failed (transport)") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise NotionReadError("Notion response too large; no partial data used")
    try:
        page = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise NotionReadError("Invalid Notion JSON response") from None
    if not isinstance(page, dict) or page.get("object") != "page":
        raise NotionReadError("Expected Notion page object")
    if normalize_id(page.get("id")) != page_id:
        raise NotionReadError("Notion page ID mismatch")
    if page.get("archived") or page.get("in_trash"):
        raise NotionReadError("Archived or trashed ticket refused")
    if not isinstance(page.get("properties"), dict):
        raise NotionReadError("Notion page has no property map")
    return page


def _property_text(properties, *names):
    """Read only named, structured Notion fields, not page body or children."""
    for name in names:
        field = properties.get(name)
        if not isinstance(field, dict):
            continue
        kind = field.get("type")
        if kind in ("title", "rich_text"):
            chunks = field.get(kind, [])
            if isinstance(chunks, list):
                return "".join(
                    part.get("plain_text", "")
                    for part in chunks
                    if isinstance(part, dict) and isinstance(part.get("plain_text"), str)
                ).strip()[:5000]
        if kind in ("select", "status"):
            item = field.get(kind)
            if isinstance(item, dict):
                return str(item.get("name") or "").strip()[:5000]
        if kind == "formula":
            formula = field.get("formula", {})
            if isinstance(formula, dict) and formula.get("type") == "string":
                return str(formula.get("string") or "").strip()[:5000]
    return ""


def ticket_from_page(page):
    """Normalize one canonical ticket; missing critical fields are NOT guessed."""
    props = page["properties"]
    ticket_id = _property_text(props, "Fach-ID", "Aufgaben-ID")
    title = _property_text(props, "Aufgabe", "Name", "Titel")
    priority = _property_text(props, "Priorität", "Prioritaet")
    status = _property_text(props, "Status")
    if not ticket_id or not title or priority not in {"P0", "P1", "P2", "P3"} or not status:
        raise NotionReadError("Missing/invalid canonical ticket ID, title, priority or status")
    return {
        "page_id": normalize_id(page["id"]),
        "ticket_id": ticket_id,
        "title": title,
        "priority": priority,
        "status": status,
        "department": _property_text(props, "Abteilung") or "unknown",
        "owner": _property_text(props, "Verantwortlich") or None,
        "blocker": _property_text(props, "Blocker") or None,
        "acceptance_criteria_present": bool(_property_text(props, "Abnahmekriterien")),
        "last_edited_time": page.get("last_edited_time"),
        # Canonical URL is constructed from validated UUID, not untrusted content.
        "source_url": "https://www.notion.so/" + uuid.UUID(page["id"]).hex,
    }


def analyze_tickets(tickets):
    """Use the existing deterministic advisory algorithm; never invoke Runner.run."""
    from worker import Snapshot, WorkItem, offline_demo

    work_items = [
        WorkItem(
            ticket_id=t["ticket_id"],
            department=t["department"],
            title=t["title"],
            priority=t["priority"],
            status=t["status"],
            owner=t["owner"],
            blocker=t["blocker"],
            evidence=[],
        )
        for t in tickets
    ]
    snapshot = Snapshot(
        snapshot_id="NOTION-READONLY-ONDEMAND",
        captured_at=datetime.now(timezone.utc).isoformat(),
        synthetic=False,
        work_items=work_items,
    )
    result = offline_demo(snapshot)
    records = {t["ticket_id"]: t for t in tickets}
    # Never print ticket bodies, owner, blocker text, tokens or model prompts.
    return {
        "work_item_source": "notion_allowlisted_page_metadata",
        "execution_mode": "offline_deterministic_advisory",
        "notion_requests": len(tickets),
        "openai_requests": 0,
        "writes_performed": 0,
        "evidence_verified": False,
        "ticket_findings": [
            {
                "ticket_id": f.ticket_id,
                "priority": records[f.ticket_id]["priority"],
                "status": records[f.ticket_id]["status"],
                "severity": f.severity,
                "blocker_present": bool(records[f.ticket_id]["blocker"]),
                "acceptance_criteria_present": records[f.ticket_id]["acceptance_criteria_present"],
                "evidence_status": "unknown",
                "source_url": records[f.ticket_id]["source_url"],
                "next_readonly_check": f.next_readonly_check,
                "ceo_decision_required": f.ceo_decision_required,
            }
            for f in result.findings
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Aline bounded read-only Notion ticket pilot")
    parser.add_argument("--page-id", action="append", required=True)
    parser.add_argument("--confirm-notion-read", action="store_true")
    args = parser.parse_args()
    requested, token = authorize_read(args.page_id, confirmed=args.confirm_notion_read)
    tickets = [ticket_from_page(fetch_page(page_id, token)) for page_id in requested]
    if len({ticket["ticket_id"] for ticket in tickets}) != len(tickets):
        raise NotionReadError("Duplicate canonical ticket ID")
    print(json.dumps(analyze_tickets(tickets), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except NotionReadError as exc:
        raise SystemExit("Notion read aborted: " + str(exc)) from None
