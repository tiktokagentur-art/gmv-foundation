"""ALINE-NOTION-001 negative and happy-path tests: no outbound traffic."""

import importlib.util
import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1] / "prototypes" / "aline-openai-worker"
SPEC = importlib.util.spec_from_file_location("aline_notion_read", ROOT / "notion_read.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Notion reader not found")
notion = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(notion)

PAGE_ID = "41776c68-17ac-81cc-aeb0-c055a9ee0e1f"
OTHER_ID = "41676c68-17ac-8168-8b40-f1f2d8dc00ba"
TOKEN = "fake-unit-test-secret"


def text_field(kind, value):
    if kind in {"title", "rich_text"}:
        return {"type": kind, kind: [{"plain_text": value}]}
    return {"type": kind, kind: {"name": value}}


def fixture_page(page_id=PAGE_ID):
    return {
        "object": "page",
        "id": page_id,
        "last_edited_time": "2026-11-19T18:35:49.000Z",
        "archived": False,
        "properties": {
            "Fach-ID": text_field("rich_text", "HR-013"),
            "Aufgabe": text_field("title", "Ticket SOP"),
            "Priorität": text_field("select", "P0"),
            "Status": text_field("status", "In Arbeit"),
            "Verantwortlich": text_field("rich_text", "Test owner"),
            "Blocker": text_field("rich_text", "Open review"),
            "Abnahmekriterien": text_field("rich_text", "External approval"),
        },
    }


class Response:
    status = 200

    def __init__(self, payload):
        self._payload = BytesIO(payload)

    def read(self, size):
        return self._payload.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self._payload.close()


class FakeOpener:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def open(self, req, timeout):
        self.calls.append((req, timeout))
        return Response(json.dumps(self.data).encode("utf-8"))


class TestNotionReader(unittest.TestCase):
    def env(self, **overrides):
        values = {
            "NOTION_API_TOKEN": TOKEN,
            "NOTION_ALLOWED_PAGE_IDS": PAGE_ID,
        }
        values.update(overrides)
        return values

    def test_requires_confirm_before_credentials_or_network(self):
        with self.assertRaisesRegex(notion.NotionReadError, "confirm-notion-read"):
            notion.authorize_read([PAGE_ID], confirmed=False, environment={})

    def test_missing_allowlist_blocks(self):
        with self.assertRaisesRegex(notion.NotionReadError, "ALLOW"):
            notion.authorize_read(
                [PAGE_ID], confirmed=True, environment=self.env(NOTION_ALLOWED_PAGE_IDS="")
            )

    def test_missing_token_blocks(self):
        with self.assertRaisesRegex(notion.NotionReadError, "NOTION_API_TOKEN"):
            notion.authorize_read(
                [PAGE_ID], confirmed=True, environment=self.env(NOTION_API_TOKEN="")
            )

    def test_out_of_scope_and_duplicate_blocks(self):
        with self.assertRaisesRegex(notion.NotionReadError, "allowlist"):
            notion.authorize_read([OTHER_ID], confirmed=True, environment=self.env())
        with self.assertRaisesRegex(notion.NotionReadError, "Duplicate"):
            notion.authorize_read(
                [PAGE_ID, PAGE_ID], confirmed=True, environment=self.env()
            )

    def test_invalid_uuid_blocks(self):
        with self.assertRaisesRegex(notion.NotionReadError, "UUID"):
            notion.authorize_read(["../../token"], confirmed=True, environment=self.env())

    def test_get_only_fixed_notions_api_no_redirects(self):
        client = FakeOpener(fixture_page())
        page = notion.fetch_page(PAGE_ID, TOKEN, opener=client)
        req, timeout = client.calls[0]
        self.assertEqual(page["id"], PAGE_ID)
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(
            req.full_url, "https://api.notion.com/v1/pages/" + PAGE_ID
        )
        self.assertEqual(req.get_header("Notion-version"), notion.NOTION_VERSION)
        self.assertEqual(timeout, 10)
        self.assertEqual(len(client.calls), 1)

    def test_mismatched_id_fails_closed(self):
        with self.assertRaisesRegex(notion.NotionReadError, "mismatch"):
            notion.fetch_page(PAGE_ID, TOKEN, opener=FakeOpener(fixture_page(OTHER_ID)))

    def test_archived_page_fails_closed(self):
        payload = fixture_page()
        payload["archived"] = True
        with self.assertRaisesRegex(notion.NotionReadError, "Archived"):
            notion.fetch_page(PAGE_ID, TOKEN, opener=FakeOpener(payload))

    def test_missing_priority_fails_closed(self):
        payload = fixture_page()
        del payload["properties"]["Priorität"]
        with self.assertRaisesRegex(notion.NotionReadError, "Missing/invalid"):
            notion.ticket_from_page(payload)

    def test_normalization_and_no_raw_blocker_in_report(self):
        ticket = notion.ticket_from_page(fixture_page())
        self.assertEqual(ticket["ticket_id"], "HR-013")
        self.assertEqual(ticket["priority"], "P0")
        self.assertEqual(ticket["status"], "In Arbeit")
        self.assertTrue(ticket["acceptance_criteria_present"])
        with patch.dict(sys.modules, {}, clear=False):
            sys.path.insert(0, str(ROOT))
            try:
                report = notion.analyze_tickets([ticket])
            finally:
                sys.path.remove(str(ROOT))
        self.assertEqual(report["notion_requests"], 1)
        self.assertEqual(report["openai_requests"], 0)
        self.assertEqual(report["writes_performed"], 0)
        self.assertEqual(report["ticket_findings"][0]["evidence_status"], "unknown")
        serialized = json.dumps(report)
        self.assertNotIn(TOKEN, serialized)
        self.assertNotIn("Open review", serialized)
        self.assertNotIn("Test owner", serialized)

    def test_rejects_non_json_or_oversized_response(self):
        class BadOpener:
            def __init__(self, payload):
                self.payload = payload

            def open(self, _req, _timeout=None, **_kwargs):
                return Response(self.payload)

        with self.assertRaisesRegex(notion.NotionReadError, "Invalid Notion JSON"):
            notion.fetch_page(PAGE_ID, TOKEN, opener=BadOpener(b"not json"))
        with self.assertRaisesRegex(notion.NotionReadError, "too large"):
            notion.fetch_page(
                PAGE_ID,
                TOKEN,
                opener=BadOpener(b"x" * (notion.MAX_RESPONSE_BYTES + 1)),
            )


if __name__ == "__main__":
    unittest.main()
