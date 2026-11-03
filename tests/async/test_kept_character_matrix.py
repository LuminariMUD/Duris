#!/usr/bin/env python3
"""Ordinary/accepted × approval off/on × Chaos off/on, using real sockets."""
import argparse
import itertools
import json
from pathlib import Path
import subprocess
import time

import test_account_recovery_journey as account
import test_creation_prompt_journey as creation
from test_flatfile_combat_journey import make_overlord
from test_kept_character_approval_journey import enter_staff, STAFF
from test_kept_character_journey import persistence, login, character_choices, saved_character


def run(binary, backend, chaos):
    inspector = account.ROOT / "bin/tests/kept-character-inspector"
    if backend == "flatfile" and (not inspector.exists() or inspector.stat().st_mtime <
            (account.ROOT / "tests/async/flatfile_player_repository_harness.cpp").stat().st_mtime):
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                        "--build-inspector", str(inspector)], cwd=account.ROOT, check=True)
    with persistence(backend) as (environment, sql):
        with account.IsolatedServer(binary, dict(environment, CHAOS_MUD="TRUE" if chaos else "FALSE"),
                                    full_world=chaos) as server:
            clients = []
            try:
                ready = "Your Chaos Equipment has been prepared!!" if chaos else "Your starter kit is ready"
                staff = account.MudClient(server.plain_port)
                clients.append(staff)
                account.create_account(staff, account.OLD_PASSWORD)
                character_choices(staff, STAFF, chaos=chaos)
                creation.reply(staff, "y", "PRESS RETURN")
                creation.reply(staff, "", ready)
                staff.expect("Pos: standing >")
                creation.reply(staff, "save", f"Save complete for {STAFF}.")
                server.shutdown()
                staff.close()
                if sql:
                    sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{STAFF}'")
                else:
                    make_overlord(server.state_root, STAFF)
                creation.reboot(server)
                for index, (approval, accepted) in enumerate(itertools.product((False, True), repeat=2)):
                    name = ("Taverek", "Veralis", "Nariven", "Pelavor")[index]
                    owner = "Matrix" + chr(ord('a') + index)
                    staff = enter_staff(server)
                    clients.append(staff)
                    mode = "on" if approval else "off"
                    creation.reply(staff, "approve " + mode, "application system " + mode)
                    if accepted:
                        marker = server.run_root / f"Players/Accepted/{name[0].lower()}/{name.lower()}"
                        marker.parent.mkdir(parents=True, exist_ok=True)
                        marker.touch()
                    mortal = account.MudClient(server.plain_port)
                    clients.append(mortal)
                    account.create_account(mortal, account.OLD_PASSWORD, name=owner)
                    character_choices(mortal, name, chaos=chaos)
                    waiting = approval and not accepted
                    prompt = "waiting for staff approval" if waiting else "PRESS RETURN"
                    creation.reply(mortal, "y", prompt)
                    before = saved_character(server, sql, inspector, name)
                    assert before[1] == 0 and len(before[2]) == 10
                    mortal.close()
                    server.shutdown()
                    staff.close()
                    creation.reboot(server)  # Approval configuration resets; saved policy must survive.
                    staff = enter_staff(server)
                    clients.append(staff)
                    mortal = login(server, owner)
                    clients.append(mortal)
                    creation.reply(mortal, "1", name)
                    creation.reply(mortal, "1", "(Y/N)")
                    creation.reply(mortal, "y", prompt)
                    assert saved_character(server, sql, inspector, name) == before
                    if waiting:
                        creation.reply(staff, "approve " + name, "Pos: standing >")
                        mortal.expect("PRESS RETURN")
                    creation.reply(mortal, "", ready)
                    mortal.expect("Pos: standing >")
                    creation.reply(mortal, "save", f"Save complete for {name}.")
                    after = saved_character(server, sql, inspector, name)
                    assert after == (before[0], 56 if chaos else 1, before[2]), (before, after)

                    def rewards():
                        if sql:
                            row = sql(f"SELECT epics FROM player_data WHERE pid={after[0]}")
                            bank = sql(f"SELECT bank_platinum FROM account_banks WHERE LOWER(account_name)=LOWER('{owner}')")
                            return int(row), int(bank or 0)
                        record = json.loads(subprocess.check_output([str(inspector), str(server.state_root), "inspect", str(after[0])], text=True))
                        return record["epics"], record["bank"][3]

                    if chaos:
                        deadline = time.monotonic() + 10
                        while rewards() != (20000, 1000000):
                            assert time.monotonic() < deadline, rewards()
                            time.sleep(0.05)
                        assert "A free frigate!" in mortal.transcript.decode(errors="replace")
                    baseline_rewards = rewards()
                    mortal.close()
                    server.shutdown()
                    staff.close()
                    creation.reboot(server)
                    mortal = login(server, owner)
                    clients.append(mortal)
                    creation.reply(mortal, "1", name)
                    creation.reply(mortal, "1", "(Y/N)")
                    creation.reply(mortal, "y", "Pos: standing >")
                    creation.reply(mortal, "save", f"Save complete for {name}.")
                    assert saved_character(server, sql, inspector, name) == after
                    assert rewards() == baseline_rewards, "starter balances repeated after restart"
                    assert "A free frigate!" not in mortal.transcript.decode(errors="replace")
                    mortal.close()
                    server.shutdown()
                    print(f"PASS {backend} Chaos={chaos} approval={approval} accepted={accepted}: Keep, policy, restart, first entry and rewards", flush=True)
                    creation.reboot(server)
                server.shutdown()
            finally:
                for client in clients: client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("mariadb", "flatfile"), required=True)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--chaos", action="store_true")
    args = parser.parse_args()
    run(args.server.resolve(), args.backend, args.chaos)
