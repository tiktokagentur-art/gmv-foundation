#!/usr/bin/env python3
"""Allowlist egress proxy for the Symphony/Codex sandbox (ENG-003).

Unprivileged user process, listens on 127.0.0.1 only. Supports HTTP CONNECT
(HTTPS tunnels) to port 443 of exactly the allowlisted hosts. Everything else
gets 403. No TLS interception, no payload logging, no auth headers read or
stored: only the CONNECT line and the response status are inspected.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import re
import sys
import time

DEFAULT_ALLOWLIST = frozenset({"github.com", "api.github.com", "api.openai.com"})
ALLOWED_PORTS = frozenset({443})
MAX_HEADER_BYTES = 8192
_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
HOST_RE = re.compile(rf"^{_LABEL}(?:\.{_LABEL})+$")


def parse_connect(head: bytes) -> tuple[str, int]:
    """Return (host, port) of a CONNECT request or raise ValueError."""
    try:
        first = head.split(b"\r\n", 1)[0].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("non-ascii request line") from exc
    parts = first.split(" ")
    if len(parts) != 3 or parts[0] != "CONNECT" or not parts[2].startswith("HTTP/1."):
        raise ValueError("only CONNECT is supported")
    target = parts[1]
    host, sep, port_s = target.rpartition(":")
    if not sep or not port_s.isdigit():
        raise ValueError("target must be host:port")
    host = host.lower().rstrip(".")
    if not HOST_RE.fullmatch(host) or host.rsplit(".", 1)[-1].isdigit():
        raise ValueError("invalid host (IP literals are not allowed)")
    return host, int(port_s)


def is_allowed(host: str, port: int, allowlist: frozenset[str]) -> bool:
    # Exakter Hostname, keine Wildcards, keine IP-Literale, nur Port 443.
    return host in allowlist and port in ALLOWED_PORTS


def log(event: str, **fields: object) -> None:
    print(json.dumps({"ts": round(time.time(), 3), "event": event, **fields}), flush=True)


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        with contextlib.suppress(Exception):
            writer.close()


async def handle(reader, writer, allowlist: frozenset[str]) -> None:
    try:
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, TimeoutError):
        writer.close()
        return
    try:
        host, port = parse_connect(head[:MAX_HEADER_BYTES])
    except ValueError as exc:
        log("deny", reason=str(exc))
        writer.write(b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        writer.close()
        return
    if not is_allowed(host, port, allowlist):
        log("deny", host=host, port=port)
        writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        writer.close()
        return
    try:
        up_reader, up_writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=10
        )
    except (OSError, TimeoutError):
        log("upstream_error", host=host, port=port)
        writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        writer.close()
        return
    log("allow", host=host, port=port)
    writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
    await writer.drain()
    await asyncio.gather(_pipe(reader, up_writer), _pipe(up_reader, writer))


async def serve(port: int, allowlist: frozenset[str]) -> None:
    server = await asyncio.start_server(
        lambda r, w: handle(r, w, allowlist), host="127.0.0.1", port=port, limit=MAX_HEADER_BYTES
    )
    log("listening", addr=f"127.0.0.1:{port}", allowlist=sorted(allowlist))
    async with server:
        await server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=18443)
    parser.add_argument("--allow", action="append", default=None,
                        help="exact hostname; repeatable; default: GitHub + OpenAI")
    args = parser.parse_args(argv)
    allowlist = frozenset(h.lower() for h in args.allow) if args.allow else DEFAULT_ALLOWLIST
    for host in allowlist:
        if not HOST_RE.fullmatch(host):
            print(f"invalid host in allowlist: {host}", file=sys.stderr)
            return 2
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(serve(args.port, allowlist))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
