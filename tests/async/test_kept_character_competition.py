#!/usr/bin/env python3
"""Two accounts choose one spelling before Keep; the loser cannot displace it."""
import argparse
from pathlib import Path
import subprocess
import time

import test_account_recovery_journey as account
import test_creation_prompt_journey as creation
from test_character_stat_choice_journey import WebSocketClient
from test_kept_character_journey import persistence, login, character_choices, pause_writer, saved_character


def run(binary, backend):
    inspector = account.ROOT / "bin/tests/kept-character-inspector"
    with persistence(backend) as (environment, sql):
        with account.IsolatedServer(binary, dict(environment, DURIS_WEBSOCKET="TRUE")) as server:
            winner = account.MudClient(server.plain_port)
            loser = account.MudClient(server.plain_port)
            try:
                account.create_account(winner, account.OLD_PASSWORD)
                character_choices(winner)
                account.create_account(loser, account.OLD_PASSWORD, name="Rivalacct")
                character_choices(loser, "taverek")
                with pause_writer(server, sql):
                    creation.reply(winner, "y", "Saving your character")
                    creation.reply(loser, "y", "Another character has taken that name meanwhile")
                    probe = WebSocketClient(server.websocket_port)
                    assert probe.command("validate_name", {"name": "TAVEREK"})["valid"] is False
                    probe.close()
                    winner.close()
                    loser.close()
                deadline = time.monotonic() + 15
                while True:
                    if sql:
                        committed = sql("SELECT COUNT(*) FROM player_data WHERE name='Taverek'") == "1"
                    else:
                        committed = (server.state_root / "players/1.snapshot").exists()
                    if committed: break
                    assert time.monotonic() < deadline
                    time.sleep(0.05)
                before = saved_character(server, sql, inspector)
                assert before[0] == 1 and before[1] == 0
                if sql:
                    assert sql("SELECT account_name FROM player_data WHERE name='Taverek'") == account.ACCOUNT
                    assert sql("SELECT COUNT(*) FROM account_characters WHERE account_name='Rivalacct'") == "0"
                server.shutdown()
                creation.reboot(server)
                winner = login(server)
                creation.reply(winner, "1", "Taverek")
                creation.reply(winner, "1", "(Y/N)")
                creation.reply(winner, "y", "PRESS RETURN")
                assert saved_character(server, sql, inspector) == before
                loser = login(server, "Rivalacct")
                creation.reply(loser, "1", "Account currently doesn't have any characters")
                server.shutdown()
                print(f"PASS {backend} case-insensitive Keep competition and loser cleanup without displacing winner", flush=True)
            finally:
                winner.close()
                loser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("mariadb", "flatfile"), required=True)
    parser.add_argument("--server", type=Path, required=True)
    args = parser.parse_args()
    run(args.server.resolve(), args.backend)
