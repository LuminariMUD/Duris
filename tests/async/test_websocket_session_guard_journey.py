#!/usr/bin/env python3
"""WebSocket session commands against held bodies and fenced accounts, over real sockets."""
import argparse
import json
from pathlib import Path
import subprocess
import time

import test_account_recovery_journey as account
import test_creation_prompt_journey as creation
from test_character_stat_choice_journey import WebSocketClient
from test_flatfile_combat_journey import make_overlord
from test_kept_character_approval_journey import STAFF, OWNER, enter_staff
from test_kept_character_journey import (
    character_choices, kept_journey_binary, login, persistence, websocket_character,
)

INSPECTOR = account.ROOT / "bin/tests/kept-character-inspector"
OTHER = "Otheracct"


def send(client, command, data=None):
    client.send_frame(1, json.dumps({"type": "cmd", "cmd": command, "data": data or {}}).encode())


def drain(client, seconds, until=None):
    """Messages for up to `seconds`, stopping early once `until` appears."""
    messages = []
    client.socket.settimeout(0.2)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            messages.append(client.receive())
        except TimeoutError:
            continue
        if until and until in json.dumps(messages[-1]):
            break
    client.socket.settimeout(5)
    return messages


def register(server, name):
    client = WebSocketClient(server.websocket_port)
    client.command("register", {"account": name, "password": account.OLD_PASSWORD,
                                "email": name + "@example.invalid"}, "auth")
    return client


def websocket_login(server, name):
    client = WebSocketClient(server.websocket_port)
    return client, client.command("login", {"account": name, "password": account.OLD_PASSWORD}, "auth")


def save(client):
    send(client, "game", "save")
    assert "Saving Taverek." in json.dumps(drain(client, 10, "Saving Taverek.")), "save failed"


def in_game_commands(server):
    """Duplicate enter is ignored; in-game login/logout leave the live body attached."""
    other = register(server, OTHER)
    other.close()
    client = register(server, account.ACCOUNT)
    websocket_character(client)
    drain(client, 1)
    send(client, "enter", {"character": "Taverek"})
    drain(client, 5, "Loading character")
    send(client, "enter", {"character": "Taverek"})
    entered = drain(client, 15, "Your starter kit is ready")
    assert "Your starter kit is ready" in json.dumps(entered), entered
    assert "couldn't load" not in json.dumps(entered), entered
    save(client)
    refused = client.command("login", {"account": OTHER, "password": account.OLD_PASSWORD}, "auth")
    assert refused["status"] == "failed", refused
    refused = client.command("login", {"account": account.ACCOUNT, "password": "wrong-password-1"}, "auth")
    assert refused["status"] == "failed", refused
    # The refused logins kept this session's account and body.
    assert client.command("rested_bonus", expected="account")["action"] == "rested_bonus"
    refused = client.command("logout", expected="account")
    assert refused["action"] == "error" and "Leave the game" in refused["error"], refused
    save(client)
    client.close()
    # A freed body could not be reattached; the old server crashed here instead.
    client, resumed = websocket_login(server, account.ACCOUNT)
    assert resumed["status"] == "reconnected", resumed
    save(client)
    client.close()
    assert server.process.poll() is None


def delete_at_first_play(server):
    """The body a Telnet session holds at its first-Play MOTD cannot be deleted."""
    telnet = account.MudClient(server.plain_port)
    account.create_account(telnet, account.OLD_PASSWORD)
    character_choices(telnet)
    creation.reply(telnet, "y", creation.MENU)
    creation.play_saved_character(telnet)
    client, _ = websocket_login(server, account.ACCOUNT)
    refused = client.command("delete_character", {"name": "Taverek", "confirm": True}, "account")
    assert refused["action"] == "error" and "in the game" in refused["error"], refused
    client.close()
    creation.reply(telnet, "", "Your starter kit is ready")
    telnet.expect("Pos: standing >")
    creation.reply(telnet, "save", "Saving Taverek.")
    telnet.close()


def waiting_application(server, sql):
    """Enter and delete leave a pending application in the queue and approvable."""
    staff = account.MudClient(server.plain_port)
    account.create_account(staff, account.OLD_PASSWORD)
    character_choices(staff, STAFF)
    creation.reply(staff, "y", creation.MENU)
    creation.play_saved_character(staff, STAFF)
    creation.reply(staff, "", "Your starter kit is ready")
    staff.expect("Pos: standing >")
    creation.reply(staff, "save", f"Saving {STAFF}.")
    server.shutdown()
    staff.close()
    if sql:
        sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{STAFF}'")
    else:
        make_overlord(server.state_root, STAFF)
    for directory in ("Players/Accepted/t", "Players/Declined/v"):
        (server.run_root / directory).mkdir(parents=True, exist_ok=True)
    creation.reboot(server)
    staff = enter_staff(server)
    creation.reply(staff, "approve on", "Pos: standing >")
    client = register(server, OWNER)
    kept = websocket_character(client)
    assert kept["waitingForApproval"], kept
    drain(client, 1)
    send(client, "enter", {"character": "Taverek"})
    assert "couldn't load" not in json.dumps(drain(client, 2)), "enter disturbed the application"
    refused = client.command("delete_character", {"name": "Taverek", "confirm": True}, "account")
    assert refused["action"] == "error" and "in the game" in refused["error"], refused
    assert "Taverek" in creation.reply(staff, "approve", "Pos: standing >")
    staff.send("approve Taverek")
    approved = drain(client, 15, "has been approved")
    assert "has been approved" in json.dumps(approved), approved
    listed = [message for message in approved if message.get("type") == "auth"]
    assert listed and listed[-1]["data"]["characters"][0]["name"] == "Taverek", approved
    send(client, "enter", {"character": "Taverek"})
    assert "Your starter kit is ready" in json.dumps(drain(client, 15, "Your starter kit is ready"))
    client.close()
    staff.close()


def fenced_login(server, sql):
    """A deletion-fenced account gets no WebSocket session; Telnet still confirms it."""
    client = register(server, account.ACCOUNT)
    websocket_character(client)
    client.close()
    time.sleep(1)
    server.shutdown()
    if sql:
        sql(f"UPDATE accounts SET blocked=2 WHERE account_name='{account.ACCOUNT}'")
    else:
        subprocess.run([str(INSPECTOR), str(server.state_root), "block-account", account.ACCOUNT, "2"],
                       check=True)
    creation.reboot(server)
    client, denied = websocket_login(server, account.ACCOUNT)
    assert denied["status"] == "failed" and "being deleted" in denied["error"], denied
    send(client, "enter", {"character": "Taverek"})
    assert "Your starter kit" not in json.dumps(drain(client, 3))
    client.close()
    telnet = account.MudClient(server.plain_port)
    account.enter_account_name(telnet)
    telnet.expect("Please enter your password:")
    telnet.send(account.OLD_PASSWORD)
    telnet.expect("Account deletion is already in progress.")
    telnet.close()


def chaos_change(binary):
    """First entry follows the server's current mode, not the mode at Keep."""
    for kept_mode, played_mode, expected in (
            ("TRUE", "FALSE", "Your starter kit is ready"),
            ("FALSE", "TRUE", "Your Chaos Equipment has been prepared!!")):
        # Chaos kits need the full world's objects.
        with account.IsolatedServer(binary, {"DURIS_WEBSOCKET": "TRUE", "CHAOS_MUD": kept_mode},
                                    full_world=played_mode == "TRUE") as server:
            client = account.MudClient(server.plain_port)
            account.create_account(client, account.OLD_PASSWORD)
            character_choices(client, chaos=kept_mode == "TRUE")
            creation.reply(client, "y", creation.MENU)
            client.close()
            server.shutdown()
            server.environment["CHAOS_MUD"] = played_mode
            creation.reboot(server)
            client = login(server)
            creation.play_saved_character(client)
            client.send("")
            client.expect(expected, timeout=300)
            client.close()
            server.shutdown()


def run(binary, backend):
    if backend == "flatfile":
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                        "--build-inspector", str(INSPECTOR)], cwd=account.ROOT, check=True)
    for journey in (in_game_commands, delete_at_first_play, waiting_application, fenced_login):
        with persistence(backend) as (environment, sql):
            fixture = account.IsolatedServer(binary, dict(environment, DURIS_WEBSOCKET="TRUE"))
            if backend == "flatfile":
                # Commissioned native authorities, which real deletion requires.
                subprocess.run([str(INSPECTOR), str(fixture.state_root), "empty-authorities"], check=True)
            with fixture as server:
                try:
                    journey(*((server, sql) if journey in (waiting_application, fenced_login) else (server,)))
                except Exception:
                    print(server.server_output()[-2000:])
                    print(server.runtime_logs()[-3000:])
                    raise
        print(f"PASS {backend} {journey.__name__}", flush=True)
    if backend == "flatfile":
        chaos_change(binary)
        print("PASS flatfile chaos_change", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("mariadb", "flatfile"), default="flatfile")
    parser.add_argument("--server", type=Path)
    args = parser.parse_args()
    with kept_journey_binary(args.server, args.backend) as binary:
        run(binary, args.backend)
