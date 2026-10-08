#!/usr/bin/env python3
"""Connections that have not logged in to an account, per address, on a real server.

One isolated flat-file server, with the WebSocket listener on and 127.0.0.9 as its
trusted proxy. Eight telnet connections from 127.0.0.1 reach the account name prompt and
the ninth is refused, and so is a ninth from 127.0.0.5 after eight that each entered a
name, while a login from 127.0.0.2 still gets in; TLS connections still negotiating
count too. Behind the proxy, two client addresses its PROXY headers name are
counted apart, the proxy's own address, shared by every client it forwards, is not
capped, and two website logins with different X-Forwarded-For addresses do not close each
other, even when the second client writes the first one's address in front of its own. A connection silent at the account name prompt, and one silent at the password
prompt, are closed after two minutes. A connection from a banned address is told so and closed, and the server stays up. A full
server refuses TLS connections without growing.
"""

from __future__ import annotations

import socket
import tempfile
import time
from pathlib import Path

from test_account_recovery_journey import (
    ACCOUNT, OLD_PASSWORD, IsolatedServer, MudClient, build_flatfile_server, create_account, require,
)

LIMIT = 8
PROXY = "127.0.0.9"
BANNED = "127.0.0.23"
REFUSAL = b"Too many connections from your address."


class BoundClient(MudClient):
    """A telnet client whose socket leaves from a given loopback address."""

    def __init__(self, port: int, source: str) -> None:
        self.socket = socket.create_connection(("127.0.0.1", port), timeout=5,
                                               source_address=(source, 0))
        self.socket.settimeout(0.25)
        self.pending = bytearray()
        self.transcript = bytearray()


def closed_within(sock: socket.socket, timeout: float) -> bytes | None:
    """Everything the server sent before closing, or None if it is still open."""
    received = bytearray()
    deadline = time.monotonic() + timeout
    sock.settimeout(0.25)
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            continue
        except ConnectionResetError:
            return bytes(received)
        if not chunk:
            return bytes(received)
        received.extend(chunk)
    return None


def proxied(port: int, client: str) -> socket.socket:
    """A WebSocket-port connection from the proxy carrying a PROXY header for client."""
    sock = socket.create_connection(("127.0.0.1", port), timeout=5, source_address=(PROXY, 0))
    sock.sendall(f"PROXY TCP4 {client} 127.0.0.1 40000 4050\r\n".encode("ascii"))
    return sock


def handshake(port: int, client: str) -> socket.socket:
    """A WebSocket upgrade through the proxy naming client in X-Forwarded-For."""
    sock = socket.create_connection(("127.0.0.1", port), timeout=5, source_address=(PROXY, 0))
    sock.sendall(("GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n"
                  "Connection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                  f"Sec-WebSocket-Version: 13\r\nX-Forwarded-For: {client}\r\n\r\n").encode("ascii"))
    sock.settimeout(5)
    require(b" 101 " in sock.recv(4096), f"the handshake for {client} was not accepted")
    return sock


def rss_kib(server: IsolatedServer) -> int:
    for line in Path(f"/proc/{server.process.pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    raise AssertionError("the server has no VmRSS line")


def ban(run_root: Path) -> None:
    """A ban entry for BANNED, as the server's ban command saves one."""
    (run_root / "lib/misc/ban_sites").write_text(f"Journey\n60\n{BANNED}\n")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="duris-connection-limit-build-") as build:
        binary = build_flatfile_server(Path(build))
        with IsolatedServer(binary, {"DURIS_WEBSOCKET": "TRUE",
                                     "DURIS_TRUSTED_PROXY_IP": PROXY}, ban) as server:
            port = server.plain_port
            tls_port, websocket_port = port + 1, port + 2
            held = []
            try:
                # Silent from the start at the account name prompt: closed after 120 s.
                silent = BoundClient(port, "127.0.0.3")
                silent.expect("account name")
                silent_since = time.monotonic()

                # A TLS connection counts while it negotiates (GnuTLS ends a silent one
                # after 40 s).
                for _ in range(LIMIT):
                    held.append(socket.create_connection(("127.0.0.1", tls_port), timeout=5,
                                                         source_address=("127.0.0.4", 0)))
                time.sleep(1)
                excess_tls = socket.create_connection(("127.0.0.1", tls_port), timeout=5,
                                                      source_address=("127.0.0.4", 0))
                require(closed_within(excess_tls, 10) is not None,
                        "a ninth connection from an address with eight in TLS negotiation was kept")

                for _ in range(LIMIT):
                    client = BoundClient(port, "127.0.0.1")
                    client.expect("account name")
                    held.append(client)
                refused = socket.create_connection(("127.0.0.1", port), timeout=5)
                text = closed_within(refused, 10)
                require(text is not None and REFUSAL in text,
                        f"the ninth connection from one address was not refused: {text!r}")
                debug = (server.run_root / "logs/log/debug").read_text(errors="replace")
                require("Refused connection from 127.0.0.1" in debug,
                        "the refusal left no debug-log line:\n" + debug[-4000:])

                # Any name takes a connection past the account name prompt; it still counts.
                for letter in "abcdefgh":
                    client = BoundClient(port, "127.0.0.5")
                    client.expect("account name")
                    client.send(f"Limit{letter}")
                    client.expect("is this correct?")
                    held.append(client)
                refused = socket.create_connection(("127.0.0.1", port), timeout=5,
                                                   source_address=("127.0.0.5", 0))
                text = closed_within(refused, 10)
                require(text is not None and REFUSAL in text,
                        f"a ninth connection after eight named ones was not refused: {text!r}")

                banned = socket.create_connection(("127.0.0.1", port), timeout=5,
                                                  source_address=(BANNED, 0))
                text = closed_within(banned, 10)
                require(text is not None and b"banned" in text,
                        f"a connection from a banned address was not closed: {text!r}")
                require(server.process.poll() is None, "a banned address stopped the server")

                # Another address still logs in.
                other = BoundClient(port, "127.0.0.2")
                create_account(other, OLD_PASSWORD)
                held.append(other)

                # Silent at the password prompt: closed after 120 s as well.
                waiting = BoundClient(port, "127.0.0.6")
                waiting.expect("account name")
                waiting.send(ACCOUNT)
                waiting.expect("password")
                waiting_since = time.monotonic()

                # Behind the proxy each PROXY-named client is counted on its own, and the
                # proxy's own address is shared by its clients, so it is never capped.
                for _ in range(LIMIT):
                    held.append(proxied(websocket_port, "198.51.100.1"))
                time.sleep(1)
                excess = proxied(websocket_port, "198.51.100.1")
                require(closed_within(excess, 10) is not None,
                        "the ninth proxied connection from one client address was kept")
                second = proxied(websocket_port, "198.51.100.2")
                require(closed_within(second, 2) is None,
                        "a proxied client was refused for another client's connections")
                held.append(second)
                for _ in range(LIMIT + 1):
                    client = BoundClient(port, PROXY)
                    client.expect("account name")
                    held.append(client)
                # The proxy appends the real client to whatever X-Forwarded-For it was sent.
                first = handshake(websocket_port, "198.51.100.3")
                held.append(first)
                held.append(handshake(websocket_port, "198.51.100.3, 198.51.100.4"))
                require(closed_within(first, 2) is None,
                        "a website login closed another client's as a stale one from its address")

                for client, since, prompt in ((silent, silent_since, "account name"),
                                              (waiting, waiting_since, "password")):
                    remaining = 120 - (time.monotonic() - since)
                    text = closed_within(client.socket, remaining + 15)
                    require(text is not None and b"Idle Timeout" in text,
                            f"a connection silent at the {prompt} prompt was kept")
                    require(time.monotonic() - since >= 115,
                            f"the connection silent at the {prompt} prompt was closed early")

                # Fill the server: a TLS connection it refuses keeps no GnuTLS session
                # (about 8 KiB each before).
                for octet in range(40, 72):
                    for _ in range(LIMIT):
                        held.append(socket.create_connection(
                            ("127.0.0.1", port), timeout=5, source_address=(f"127.0.0.{octet}", 0)))
                full = socket.create_connection(("127.0.0.1", port), timeout=5,
                                                source_address=("127.0.0.39", 0))
                require(closed_within(full, 10) is not None, "the server never filled up")
                before = rss_kib(server)
                for _ in range(1000):
                    socket.create_connection(("127.0.0.1", tls_port), timeout=5,
                                             source_address=("127.0.0.38", 0)).close()
                time.sleep(1)
                growth = rss_kib(server) - before
                require(growth < 3072,
                        f"a full server grew {growth} KiB over 1000 refused TLS connections")
            finally:
                for client in held:
                    (client.socket if isinstance(client, MudClient) else client).close()
            server.shutdown()
    print("connection limit journey passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
