#!/usr/bin/env python3
"""Byte-Brücke zwischen TCP und Unix-Socket (ENG-003, Netz-Isolation ohne Root).

Zweck: Unter ``bwrap --unshare-net`` hat der Namespace nur Loopback. Der einzige
Weg nach außen ist ein Unix-Socket, der per bind-mount hineingereicht wird und
außen beim Allowlist-Egress-Proxy endet. Damit ist die Netzgrenze vom
Betriebssystem erzwungen (eigener Netz-Namespace), nicht nur von Codex.

  außen:  uds_bridge.py uds-to-tcp SOCK 127.0.0.1:PROXYPORT
  innen:  uds_bridge.py tcp-to-uds 127.0.0.1:18443 SOCK

Es wird nichts protokolliert außer Fehlern ohne Inhalt.
"""

from __future__ import annotations

import os
import socket
import sys
import threading


def _pipe(src: socket.socket, dst: socket.socket) -> None:
    try:
        while data := src.recv(65536):
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def _serve(listener: socket.socket, connect) -> None:
    while True:
        client, _ = listener.accept()
        try:
            upstream = connect()
        except OSError:
            client.close()
            continue
        for a, b in ((client, upstream), (upstream, client)):
            threading.Thread(target=_pipe, args=(a, b), daemon=True).start()


def _hostport(value: str) -> tuple[str, int]:
    host, _, port = value.rpartition(":")
    if host not in ("127.0.0.1", "localhost"):
        raise SystemExit("only loopback addresses are allowed")
    return "127.0.0.1", int(port)


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] not in ("uds-to-tcp", "tcp-to-uds"):
        print("usage: uds_bridge.py uds-to-tcp SOCK HOST:PORT | tcp-to-uds HOST:PORT SOCK",
              file=sys.stderr)
        return 2
    mode, a, b = argv
    if mode == "uds-to-tcp":
        if os.path.exists(a):
            os.unlink(a)
        lst = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        old = os.umask(0o077)
        lst.bind(a)
        os.umask(old)
        target = _hostport(b)
        connect = lambda: socket.create_connection(target, timeout=10)  # noqa: E731
    else:
        lst = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lst.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lst.bind(_hostport(a))

        def connect() -> socket.socket:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(b)
            return s
    lst.listen(64)
    _serve(lst, connect)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
