#!/usr/bin/env python3
"""First-connection coins: in memory at once, written by the save, with either bank, over a reload."""

import argparse
import pathlib

from test_flatfile_combat_journey import (
    CHARACTER, inspect_authority, reconnect_character, require, run_journey,
)


def verify_first_session(client, port, sql, populated_bank):
    # The full starter kit fills the level-one inventory slot allowance.
    client.send("drop all")
    client.expect("You drop a steel long sword.", timeout=20)
    opening = inspect_authority(sql)
    bank = [19, 23, 31, 47] if populated_bank else [0, 0, 0, 0]
    # A bank with no deposit has no row on MariaDB and reads as revision 0.
    revision = 2 if populated_bank else 0
    require(opening["wallet"] == [0, 0, 0, 0] and opening["wallet_revision"] == 0,
            f"unexpected opening wallet: {opening}")
    require(opening["bank"] == bank and opening["bank_revision"] == revision,
            f"creation changed the selected account bank: {opening}")
    # The coins move into the wallet in memory; the save writes it.
    client.send("get coins")
    client.expect("There were: 3 silver coins.", timeout=20)
    client.send("save")
    client.expect(f"Saving {CHARACTER}.", timeout=20)
    credited = inspect_authority(sql)
    require(credited["wallet"] == [0, 3, 0, 0],
            f"the save did not write the credited wallet: {credited}")
    require(credited["bank"] == bank and credited["bank_revision"] == revision,
            f"a wallet credit changed the account bank: {credited}")
    # Repeating the pickup and saving cannot credit the absent pile again.
    client.send("get coins")
    client.send("save")
    client.expect(f"Saving {CHARACTER}.", timeout=20)
    client.send("quit")
    client.expect("ACCOUNT MENU", timeout=30)
    client.send("0")
    client.close()
    reloaded = reconnect_character(port)
    try:
        reloaded.send("get coins")
        reloaded.send("save")
        reloaded.expect(f"Saving {CHARACTER}.", timeout=20)
        after = inspect_authority(sql)
        for key in ("wallet", "bank", "bank_revision"):
            require(after[key] == credited[key], f"retry/reload changed {key}: {after}")
        # The reloaded wallet spends, and the next save writes what is left.
        reloaded.send("drop 1 silver")
        reloaded.expect("OK.", timeout=20)
        reloaded.send("save")
        reloaded.expect(f"Saving {CHARACTER}.", timeout=20)
        spent = inspect_authority(sql)
        require(spent["wallet"] == [0, 2, 0, 0] and spent["bank"] == bank
                and spent["bank_revision"] == revision,
                f"reloaded currency state was not usable: {spent}")
    finally:
        reloaded.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=pathlib.Path, required=True)
    binary = parser.parse_args().server.resolve()
    for populated in (False, True):
        run_journey(binary, reset_coins=True, first_session_only=True, populated_bank=populated)
    print("first-session currency, populated bank, retry and reload passed")
