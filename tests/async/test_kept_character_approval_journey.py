#!/usr/bin/env python3
"""Real staff approval/decline, delayed acknowledgment, disconnect and cold restart."""
import argparse
from pathlib import Path
import subprocess

import test_account_recovery_journey as account
import test_creation_prompt_journey as creation
from test_flatfile_combat_journey import make_overlord
from test_character_stat_choice_journey import WebSocketClient
from test_kept_character_journey import persistence, login, saved_character, pause_writer, character_choices as choices, websocket_character

STAFF = "Ostrand"
OWNER = "Keptacct"


def enter_staff(server):
    client = login(server)
    creation.reply(client, "1", STAFF)
    creation.reply(client, STAFF, "(Y/N)")
    creation.reply(client, "y", "Pos: standing >")
    return client


def waiting_login(server):
    client = login(server, OWNER)
    creation.reply(client, "1", "Taverek")
    creation.reply(client, "Taverek", "(Y/N)")
    creation.reply(client, "y", "waiting for staff approval")
    return client


def run(binary, backend):
    inspector = account.ROOT / "bin/tests/kept-character-inspector"
    if backend == "flatfile":
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                        "--build-inspector", str(inspector)], cwd=account.ROOT, check=True)
    with persistence(backend) as (environment, sql):
        fixture = account.IsolatedServer(binary, dict(environment, DURIS_WEBSOCKET="TRUE"))
        if backend == "flatfile":
            # Model a commissioned empty native backend. Missing required
            # authorities must keep deletion fail-closed, even for a new player.
            subprocess.run([str(inspector), str(fixture.state_root), "empty-authorities"], check=True)
        with fixture as server:
            staff = mortal = probe = creator = None
            try:
                staff = account.MudClient(server.plain_port)
                account.create_account(staff, account.OLD_PASSWORD)
                choices(staff, STAFF)
                creation.reply(staff, "y", "PRESS RETURN")
                creation.reply(staff, "", "Your starter kit is ready")
                staff.expect("Pos: standing >")
                creation.reply(staff, "save", f"Save complete for {STAFF}.")
                server.shutdown()
                staff.close()
                if sql:
                    sql("UPDATE player_data SET level=62,highest_level=62 WHERE name='Ostrand'")
                else:
                    make_overlord(server.state_root, STAFF)
                for directory in ("Players/Accepted/t", "Players/Declined/v"):
                    (server.run_root / directory).mkdir(parents=True, exist_ok=True)
                creation.reboot(server)
                staff = enter_staff(server)
                # Staff creation must publish its current account cache even
                # when the first MariaDB snapshot is still queued.
                creation.reply(staff, "newchar Staffprobe 3 11 56 false", "character saved.")
                creation.reply(staff, "quit", "Please select an option:")
                listing = creation.reply(staff, "1", "Staffprobe")
                assert listing.count("Staffprobe") == 1, listing
                creation.reply(staff, "0", "Please select an option:")
                creation.reply(staff, "1", STAFF)
                creation.reply(staff, STAFF, "(Y/N)")
                creation.reply(staff, "y", "Pos: standing >")
                creation.reply(staff, "approve on", "Pos: standing >")
                mortal = account.MudClient(server.plain_port)
                account.create_account(mortal, account.OLD_PASSWORD, name=OWNER)
                # WebSocket authentication leaves the authenticated Telnet menu
                # open. Publishing Keep must refresh that cache, and selecting
                # the new pending body must close/reload it without use-after-free.
                creator = WebSocketClient(server.websocket_port)
                auth = creator.command("login", {"account": OWNER, "password": account.OLD_PASSWORD}, "auth")
                assert auth["status"] == "success", auth
                kept = websocket_character(creator)
                assert kept["status"] == "created" and kept["waitingForApproval"], kept
                before = saved_character(server, sql, inspector)
                assert before[1] == 0 and len(before[2]) == 10, before
                creation.reply(mortal, "1", "Taverek")
                creation.reply(mortal, "Taverek", "(Y/N)")
                creation.reply(mortal, "y", "waiting for staff approval")
                assert saved_character(server, sql, inspector) == before
                creator.socket.settimeout(3)
                while creator.socket.recv(4096):
                    pass
                creator.close()
                mortal.close()
                server.shutdown()
                staff.close()
                creation.reboot(server)
                # approve_mode resets to off at boot. The saved requirement must
                # still hold, and staff must still be able to list/approve it.
                mortal = waiting_login(server)
                staff = enter_staff(server)
                listing = creation.reply(staff, "approve", "Pos: standing >")
                assert "Taverek" in listing, listing
                with pause_writer(server, sql, pid=before[0]):
                    staff.send("approve Taverek")
                    mortal.expect("Saving your character. Please wait.")
                    assert not (server.run_root / "Players/Accepted/t/taverek").exists(), "approval marker preceded commit"
                    mortal.close()  # before the clearing save is acknowledged
                server.shutdown()
                staff.close()
                assert (server.run_root / "Players/Accepted/t/taverek").is_file(), "offline approval never published"
                creation.reboot(server)
                mortal = login(server, OWNER)
                creation.reply(mortal, "1", "Taverek")
                creation.reply(mortal, "Taverek", "(Y/N)")
                creation.reply(mortal, "y", "PRESS RETURN")
                creation.reply(mortal, "", "Your starter kit is ready")
                mortal.expect("Pos: standing >")
                creation.reply(mortal, "save", "Save complete for Taverek.")
                after = saved_character(server, sql, inspector)
                assert after == (before[0], 1, before[2]), (before, after)
                server.shutdown()
                mortal.close()
                creation.reboot(server)
                staff = enter_staff(server)
                creation.reply(staff, "approve on", "Pos: standing >")
                mortal = login(server, OWNER)
                choices(mortal, "Veralis")
                creation.reply(mortal, "y", "waiting for staff approval")
                creation.reply(staff, "decline Veralis synthetic-name-policy", "Pos: standing >")
                mortal.expect("Your character application was declined.")
                mortal.expect(creation.MENU)
                if sql:
                    assert sql("SELECT COUNT(*) FROM player_data WHERE name='Veralis'") == "0"
                assert saved_character(server, sql, inspector) == after, "decline affected an established character"
                probe = WebSocketClient(server.websocket_port)
                result = probe.command("validate_name", {"name": "Veralis"})
                assert result["message"] == "That name is not allowed", result
                probe.close()
                accepted = server.run_root / "Players/Accepted/n/nariven"
                accepted.parent.mkdir(parents=True, exist_ok=True)
                accepted.touch()
                choices(mortal, "Nariven")
                # Approval is still on: the accepted-name exemption must commit
                # the same baseline and reach Return rather than the wait queue.
                creation.reply(mortal, "y", "PRESS RETURN")
                accepted_before = saved_character(server, sql, inspector, "Nariven")
                assert accepted_before[1] == 0
                server.shutdown()
                staff.close()
                mortal.close()
                creation.reboot(server)
                assert saved_character(server, sql, inspector) == after
                probe = WebSocketClient(server.websocket_port)
                result = probe.command("validate_name", {"name": "Veralis"})
                assert result["message"] == "That name is not allowed", result
                mortal = login(server, OWNER)
                creation.reply(mortal, "1", "Nariven")
                creation.reply(mortal, "Nariven", "(Y/N)")
                creation.reply(mortal, "y", "PRESS RETURN")
                creation.reply(mortal, "", "Your starter kit is ready")
                mortal.expect("Pos: standing >")
                creation.reply(mortal, "save", "Save complete for Nariven.")
                assert saved_character(server, sql, inspector, "Nariven") == (accepted_before[0], 1, accepted_before[2])
                server.shutdown()
            except Exception:
                for path in (server.run_root / "logs").rglob("*"):
                    if path.is_file():
                        for line in path.read_text(errors="replace").splitlines():
                            if any(token in line for token in ("delete_character", "artifact drain", "zone-story state cleanup")):
                                print(line)
                print(server.server_output()[-3000:])
                print(server.runtime_logs()[-8000:])
                raise
            finally:
                for client in (staff, mortal, probe, creator):
                    if client:
                        client.close()
    print(f"PASS: {backend} approval survives restart, offline acceptance commits, decline is scoped, accepted-name Keep resumes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("mariadb", "flatfile"), required=True)
    parser.add_argument("--server", type=Path, required=True)
    args = parser.parse_args()
    run(args.server.resolve(), args.backend)
