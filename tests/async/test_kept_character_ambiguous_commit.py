#!/usr/bin/env python3
"""Drop a real disposable MariaDB COMMIT acknowledgment after creation lands."""
import argparse
from contextlib import contextmanager
from pathlib import Path
import socket
import threading

import test_account_recovery_journey as account
import test_creation_prompt_journey as creation
from test_character_stat_choice_journey import WebSocketClient
from test_kept_character_journey import persistence, login, character_choices, saved_character


def packet(stream):
    def read(size):
        result = bytearray()
        while len(result) < size:
            chunk = stream.recv(size - len(result))
            if not chunk:
                raise EOFError
            result.extend(chunk)
        return bytes(result)
    header = read(4)
    return header + read(int.from_bytes(header[:3], "little"))


@contextmanager
def commit_ack_proxy(port):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    armed = threading.Event()
    committed = threading.Event()
    release = threading.Event()
    stopped = threading.Event()
    sockets = []

    def close(stream):
        try:
            stream.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        stream.close()

    def connection(client):
        upstream = socket.create_connection(("127.0.0.1", port))
        for stream in (client, upstream):
            stream.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sockets.extend((client, upstream))
        drop = threading.Event()
        saw_creation = False

        def replies():
            try:
                while True:
                    data = packet(upstream)
                    if drop.is_set():
                        assert data[4] == 0, "the intercepted commit did not succeed"
                        committed.set()
                        release.wait(30)
                        return
                    client.sendall(data)
            except (OSError, EOFError):
                pass
            finally:
                close(client)
                close(upstream)
        threading.Thread(target=replies, daemon=True).start()
        try:
            while True:
                data = packet(client)
                if data[4:5] == b"\x03":
                    query = data[5:].strip().upper()
                    if armed.is_set() and b"INSERT INTO PLAYER_DATA" in query and b"TAVEREK" in query:
                        saw_creation = True
                    if saw_creation and query == b"COMMIT" and armed.is_set():
                        armed.clear()
                        drop.set()
                upstream.sendall(data)
        except (OSError, EOFError):
            pass
        finally:
            close(client)
            close(upstream)

    def accept():
        listener.settimeout(0.2)
        while not stopped.is_set():
            try:
                client, _ = listener.accept()
                threading.Thread(target=connection, args=(client,), daemon=True).start()
            except socket.timeout:
                pass
            except OSError:
                break
    threading.Thread(target=accept, daemon=True).start()
    try:
        yield listener.getsockname()[1], armed, committed, release
    finally:
        release.set()
        stopped.set()
        listener.close()
        for stream in sockets:
            close(stream)


def run(binary):
    with persistence("mariadb") as (environment, sql):
        with commit_ack_proxy(int(environment["DB_PORT"])) as (port, armed, committed, release):
            with account.IsolatedServer(binary, dict(environment, DB_PORT=str(port), DURIS_WEBSOCKET="TRUE")) as server:
                client = account.MudClient(server.plain_port)
                try:
                    account.create_account(client, account.OLD_PASSWORD)
                    character_choices(client)
                    armed.set()
                    creation.reply(client, "y", "Saving your character")
                    assert committed.wait(10), "creation COMMIT acknowledgment was not intercepted"
                    before = saved_character(server, sql, None)
                    assert before[1] == 0
                    client.close()
                    probe = WebSocketClient(server.websocket_port)
                    assert probe.command("validate_name", {"name": "tAvErEk"})["valid"] is False
                    probe.close()
                    release.set()  # The server loses the success reply and must reconcile.
                    client = login(server)
                    creation.reply(client, "1", "Taverek")
                    creation.reply(client, "1", "(Y/N)")
                    creation.reply(client, "y", "PRESS RETURN")
                    assert saved_character(server, sql, None) == before
                    client.close()
                    server.shutdown()
                    creation.reboot(server)
                    client = login(server)
                    creation.reply(client, "1", "Taverek")
                    creation.reply(client, "1", "(Y/N)")
                    creation.reply(client, "y", "PRESS RETURN")
                    client.send("")
                    client.expect("Your starter kit is ready", timeout=30)
                    client.expect("Pos: standing >")
                    creation.reply(client, "save", "Saving Taverek.")
                    assert saved_character(server, sql, None) == (before[0], 1, before[2])
                    assert sql(f"SELECT COUNT(*) FROM account_characters WHERE pid={before[0]} AND deleted_at IS NULL") == "1"
                    server.shutdown()
                    print("PASS real ambiguous creation COMMIT, lost descriptor, reservation, reconciliation and cold entry", flush=True)
                finally:
                    release.set()
                    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    args = parser.parse_args()
    run(args.server.resolve())
