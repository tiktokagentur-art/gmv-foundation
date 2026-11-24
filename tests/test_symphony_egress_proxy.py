"""Offline tests for the allowlist egress proxy. No outbound connections."""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import symphony_egress_proxy as p  # noqa: E402


class ParseTests(unittest.TestCase):
    def test_parse_connect(self) -> None:
        self.assertEqual(
            p.parse_connect(b"CONNECT API.GitHub.com:443 HTTP/1.1\r\nHost: x\r\n\r\n"),
            ("api.github.com", 443),
        )

    def test_rejects_non_connect_and_garbage(self) -> None:
        for head in (
            b"GET http://github.com/ HTTP/1.1\r\n\r\n",
            b"CONNECT github.com HTTP/1.1\r\n\r\n",
            b"CONNECT 140.82.112.3:443 HTTP/1.1\r\n\r\n",
            b"CONNECT [::1]:443 HTTP/1.1\r\n\r\n",
            b"CONNECT gith\xc3\xbcb.com:443 HTTP/1.1\r\n\r\n",
            b"CONNECT github.com:443 FTP/1.0\r\n\r\n",
        ):
            with self.subTest(head=head), self.assertRaises(ValueError):
                p.parse_connect(head)

    def test_allowlist_is_exact(self) -> None:
        allow = p.DEFAULT_ALLOWLIST
        self.assertEqual(allow, {"github.com", "api.github.com", "api.openai.com"})
        self.assertTrue(p.is_allowed("api.github.com", 443, allow))
        for host, port in (
            ("example.com", 443),
            ("pypi.org", 443),
            ("evil.github.com", 443),
            ("github.com.evil.io", 443),
            ("codeload.github.com", 443),
            ("github.com", 80),
            ("api.openai.com", 22),
        ):
            with self.subTest(host=host, port=port):
                self.assertFalse(p.is_allowed(host, port, allow))


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.server = await asyncio.start_server(
            lambda r, w: p.handle(r, w, p.DEFAULT_ALLOWLIST), host="127.0.0.1", port=0
        )
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self) -> None:
        self.server.close()
        await self.server.wait_closed()

    async def request(self, raw: bytes) -> bytes:
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(raw)
        await writer.drain()
        data = await asyncio.wait_for(reader.read(200), timeout=5)
        writer.close()
        return data

    async def test_denied_host_gets_403(self) -> None:
        for raw in (
            b"CONNECT example.com:443 HTTP/1.1\r\n\r\n",
            b"CONNECT pypi.org:443 HTTP/1.1\r\n\r\n",
            b"CONNECT github.com:80 HTTP/1.1\r\n\r\n",
        ):
            with self.subTest(raw=raw):
                self.assertTrue((await self.request(raw)).startswith(b"HTTP/1.1 403"))

    async def test_plain_http_gets_405(self) -> None:
        data = await self.request(b"GET http://github.com/ HTTP/1.1\r\nHost: github.com\r\n\r\n")
        self.assertTrue(data.startswith(b"HTTP/1.1 405"))


if __name__ == "__main__":
    unittest.main()
