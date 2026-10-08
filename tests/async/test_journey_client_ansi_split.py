#!/usr/bin/env python3
"""Journey clients strip an ANSI escape that the end of a socket read cuts in two."""

import socket

import test_account_recovery_journey as recovery
import test_flatfile_combat_journey as journey

# The generated NPC journey once read "Cha:  87[0;1;33m ( 87)" from `stat mob`: a
# read ended between the escape's ESC byte and the rest of it.
for client_class in (journey.MudClient, recovery.MudClient):
    server, peer = socket.socketpair()
    client = client_class.__new__(client_class)
    client.socket, client.pending, client.transcript = peer, bytearray(), bytearray()
    for part in (b"Cha:  87\x1b", b"[0;1;33m ( 87)\x1b[", b"0m done"):
        server.sendall(part)
        assert client._receive()
    assert bytes(client.pending) == b"Cha:  87 ( 87) done", bytes(client.pending)
    assert bytes(client.transcript) == b"Cha:  87 ( 87) done", bytes(client.transcript)
    server.close()
    peer.close()

print("journey clients strip ANSI escapes split across reads")
