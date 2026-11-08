#!/usr/bin/env python3
"""Full-world first kits, restart with a lost callback, and exact grant replay."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys

import test_account_recovery_journey as account
import test_creation_prompt_journey as creation
from test_character_stat_choice_journey import WebSocketClient
from test_kept_character_journey import kept_journey_binary, persistence, login, character_choices, websocket_character, websocket_text, saved_character
from test_flatfile_chaos_new_character_kit import read_item_ownership

sys.path.insert(0, str(account.ROOT / "scripts"))
from build_restore_qualifier import build as build_restore_qualifier



def run(binary, backend, chaos, transport):
    inspector = account.ROOT / "bin/tests/kept-character-inspector"
    if backend == "flatfile":
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                        "--build-inspector", str(inspector)], cwd=account.ROOT, check=True)
    with persistence(backend) as (environment, sql):
        environment.update(DURIS_WEBSOCKET="TRUE", CHAOS_MUD="TRUE" if chaos else "FALSE")
        with account.IsolatedServer(binary, environment, full_world=True) as server:
            qualifier = build_restore_qualifier(server.run_root / "bin/qualify_flatfile_restore")
            client = None
            try:
                if transport == "websocket":
                    client = WebSocketClient(server.websocket_port)
                    client.command("register", {"account": account.ACCOUNT,
                                   "password": account.OLD_PASSWORD,
                                   "email": "kept@example.invalid"}, "auth")
                    websocket_character(client)
                    client.command("enter", {"character": "Taverek"}, "gmcp")
                    websocket_text(client, "Your Chaos Equipment has been prepared!!" if chaos
                                   else "Your starter kit is ready")
                    client.close()
                    client = login(server)
                    creation.reply(client, "1", "Taverek")
                    client.send("1")
                    route, _ = client.expect_any(("(Y/N)", "Pos: standing >"))
                    if route == "(Y/N)":
                        creation.reply(client, "y", "Pos: standing >")
                else:
                    client = account.MudClient(server.plain_port)
                    account.create_account(client, account.OLD_PASSWORD)
                    character_choices(client, chaos=chaos)
                    creation.reply(client, "y", creation.MENU)
                    # Pre-entry disconnect may not prepare or publish any kit.
                    assert not list((server.run_root / "journals/critical/starter-kits").glob("*.kit"))
                    client.close()
                    server.shutdown()
                    creation.reboot(server)
                    client = login(server)
                    creation.reply(client, "1", "Taverek")
                    creation.reply(client, "1", "(Y/N)")
                    creation.reply(client, "y", "PRESS RETURN")
                    creation.reply(client, "", "Your Chaos Equipment has been prepared!!" if chaos
                                   else "Your starter kit is ready")
                    client.expect("Pos: standing >")
                creation.reply(client, "save", "Saving Taverek.")
                before = saved_character(server, sql, inspector)
                pid = before[0]
                record = server.run_root / f"journals/critical/starter-kits/{pid}.kit"
                data = record.read_bytes()
                assert data[0] == 1 and hashlib.sha256(data[:-32]).digest() == data[-32:]

                def uids():
                    if sql:
                        return sql(f"SELECT obj_uid FROM player_items WHERE pid={pid} ORDER BY obj_uid")
                    return sorted(item["item_uid"] for group in read_item_ownership(server.state_root).values()
                                  for item in group if item["owner_id"] == pid and item["owner_type"] == 1)

                original_uids = uids()
                assert original_uids, "first grant published no durable items"
                client.close()
                server.shutdown()
                (server.run_root / "ISOLATED_RESTORE").touch()
                subprocess.run([str(qualifier), "--receipts", str(server.run_root)], check=True)
                # Model a committed transfer whose process died before recording its
                # callback. Keep command bytes, operation ID and every item UID exact.
                pending = bytes([0]) + data[1:-32]
                record.write_bytes(pending + hashlib.sha256(pending).digest())
                record.chmod(0o600)
                # The old snapshot can still owe its kit after the receipt committed.
                if sql:
                    sql(f"UPDATE player_data SET act3=act3|{1 << 24} WHERE pid={pid}")
                else:
                    subprocess.run([str(inspector), str(server.state_root), "starter-pending", str(pid)], check=True)
                creation.reboot(server)
                client = login(server)
                creation.reply(client, "1", "Taverek")
                creation.reply(client, "1", "(Y/N)")
                creation.reply(client, "y", "Your starter kit is ready")
                client.expect("Pos: standing >")
                creation.reply(client, "save", "Saving Taverek.")
                assert uids() == original_uids, "restart minted or replaced starter item UIDs"
                assert record.read_bytes() == data, "replay changed the bound command or operation"
                assert saved_character(server, sql, inspector) == before
                server.shutdown()
                print(f"PASS {backend} {transport} {'Chaos' if chaos else 'ordinary'} first kit and lost-callback replay", flush=True)
            except Exception:
                debug = account.ROOT / f"bin/tests/issue-612-starter-debug-{backend}.log"
                debug.write_text(server.server_output())
                import shutil
                shutil.copytree(server.run_root / "logs", account.ROOT / f"bin/tests/issue-612-starter-debug-logs-{backend}", dirs_exist_ok=True)
                records = list((server.run_root / "journals/critical/starter-kits").glob("*.kit"))
                print("retained record states", [(path.name, path.read_bytes()[0]) for path in records], flush=True)
                raise
            finally:
                if client:
                    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("mariadb", "flatfile"), default="flatfile")
    parser.add_argument("--server", type=Path)
    parser.add_argument("--chaos", action="store_true")
    parser.add_argument("--transport", choices=("telnet", "websocket"), default="telnet")
    args = parser.parse_args()
    with kept_journey_binary(args.server, args.backend) as binary:
        run(binary, args.backend, args.chaos, args.transport)
