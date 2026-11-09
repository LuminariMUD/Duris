#!/usr/bin/env python3
"""Bank/bag/quest/PC coin transfers across relog/restart on disposable MariaDB.

Invoke through tests/async/with_disposable_mariadb.sh. No checkout .env is read.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

import test_flatfile_combat_journey as journey
from run_item_pilot_journey import Server, object_records
from run_quest_staff_journey import configure as quest_fixture
from test_starter_arrow_journey import command, PROMPT

ROOT = journey.ROOT
TARGET = "Torven"
TARGET_ACCOUNT = "Targetacct"
saved_state = None  # The SQL reader, set once the disposable database exists.


def configure(runtime):
    quest_fixture(runtime)
    area = runtime / "areas"
    objects = object_records((area / "world.obj").read_text())
    # A visible inert bank counter; test_atm_present recognizes this native vnum.
    objects[3097] = """#3097
counter bank~
a bank counter~
A bank counter stands here.~
~
12 2 0 0 7 0 0 0 0 0 0
0 0 0 0 0 0 0 0
0 0 100
"""
    for vnum, name, coins in (
        (22820, "seedgold", (0, 0, 40, 0)),
        (22821, "rewardgold", (0, 0, 17, 0)),
        (22822, "mixedgold", (3, 12, 17, 0)),
        (22823, "capacitygold", (0, 0, 2147483647, 0)),
    ):
        objects[vnum] = f"""#{vnum}
{name}~
some {name} coins~
Some {name} coins lie here.~
~
20 16 1 0 7 0 0 1 0 0 0
{' '.join(map(str, coins))} 0 0 0 0
0 0 100
"""
    objects[390] = objects[390].replace("bag leather small~", "testbag bag leather small~")
    (area / "world.obj").write_text("".join(objects[v] for v in sorted(objects)) + "$~\n")
    mobiles = object_records((area / "world.mob").read_text())
    # Sentinel questers also use ACT_PATROL so the humanoid coin pickup
    # pulse leaves the player's dropped pile available to collect.
    quester_flags = 10 | (1 << 29)
    for vnum, name in ((22810, "quartermaster"), (22811, "rewarder")):
        mobiles[vnum] = f"""#{vnum}
{name} _nomoney_~
the {name}~
The {name} waits here.
~
~
{quester_flags} 0 0 0 0 0 0 0 S
PH 0 1 -1
50 0 0 100d1+100 1d1+1
0.0.0.0 0
8 8 0
"""
    (area / "world.mob").write_text("".join(mobiles[v] for v in sorted(mobiles)) + "$~\n")
    zone = re.sub(r"^[MGEOP] .*\n", "", (area / "world.zon").read_text(), flags=re.M)
    resets = "\n".join(
        f"O 0 {vnum} 1 22800 100 0 0 0"
        for vnum in (3097, 390, 22820, 22822, 22823)
    ) + "\nM 0 22810 1 22800 100 0 0 0\nM 0 22811 1 22800 100 0 0 0\n"
    (area / "world.zon").write_text(zone.replace("\nS\n", "\n" + resets + "S\n"))
    (area / "world.qst").write_text("""#22810
Q
GOLD_PAYMENT_ACCEPTED~
G C 1000
R I 15
S
#22811
Q
GOLD_REWARD_ACCEPTED~
G I 15
R I 22821
S
#~
""")
    # The isolated server's area-debugger boot selects minimal mob/object/zone
    # files; legacy quests still come from areas/world.qst.
    for suffix in ("obj", "mob", "zon"):
        (runtime / f"areas_mini/mini.{suffix}").write_text(
            (area / f"world.{suffix}").read_text())


def saved(client, state, name=journey.CHARACTER, pid=1):
    command(client, "save", f"Saving {name}.")
    return saved_state(state, pid)


def wallet(client, state, expected, name=journey.CHARACTER, pid=1):
    data = saved(client, state, name, pid)
    journey.require(data["wallet"] == expected, f"{name}: expected {expected}, got {data}")
    journey.require(data["level"] < 61, "test actor accidentally has staff minting privileges")
    print(f"{name}: saved wallet {data['wallet']}", flush=True)
    return data


def bag_coins(data, expected):
    actual = [entry["coins"] for entry in data["coin_items"]]
    journey.require(actual == ([expected] if any(expected) else []),
                    f"bag coin snapshot mismatch: {actual}; expected {expected}")


def quit_character(client):
    client.send("quit")
    client.expect("ACCOUNT MENU", timeout=30)
    client.send("0")
    client.close()


def play_journey(binary, environment):
    report = {"backend": "mariadb",
              "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "checks": []}
    with tempfile.TemporaryDirectory(prefix="coin-denominations-", dir=ROOT / "bin/tests") as directory:
        root = Path(directory)
        runtime, state = root / "runtime", root / "state"
        runtime.mkdir()
        state.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        configure(runtime)
        server = Server(binary, runtime, state, "coin-denominations", environment=environment)
        actor = target = None
        try:
            server.start()
            actor = journey.MudClient(server.port)
            journey.create_character(actor)
            actor.expect(PROMPT)
            command(actor, "drop all", "You drop ")
            command(actor, "get testbag", "You get a small leather bag.")
            command(actor, "get seedgold", "There were: 40 gold coins.")
            wallet(actor, state, [0, 0, 40, 0])
            command(actor, "deposit 40 gold", "Your account contains:")
            deposited = wallet(actor, state, [0, 0, 0, 0])
            journey.require(deposited["bank"] == [0, 0, 40, 0], "bank did not receive 40 gold")
            command(actor, "withdraw 40 gold", "Your account contains:")
            withdrawn = wallet(actor, state, [0, 0, 40, 0])
            journey.require(withdrawn["bank"] == [0, 0, 0, 0], "withdrawal did not debit bank")
            command(actor, "put 10 gold testbag", "coins into a small leather bag.")
            command(actor, "put 30 gold testbag", "coins into a small leather bag.")
            bag_coins(wallet(actor, state, [0, 0, 0, 0]), [0, 0, 40, 0])
            quit_character(actor)
            actor = journey.reconnect_character(server.port)
            bag_coins(saved(actor, state), [0, 0, 40, 0])
            command(actor, "get all.coins testbag", "You get ")
            wallet(actor, state, [0, 0, 40, 0])
            report["checks"].append("authored gold pickup, bank deposit/withdraw, bag merge, relog, bulk pickup")

            for remaining in (30, 20):
                command(actor, "give 10 gold quartermaster", "GOLD_PAYMENT_ACCEPTED")
                wallet(actor, state, [0, 0, remaining, 0])
            command(actor, "put 10 gold testbag", "coins into a small leather bag.")
            before = wallet(actor, state, [0, 0, 10, 0])
            bag_coins(before, [0, 0, 10, 0])
            quit_character(actor)
            actor = None
            server.stop()
            journey.require(server.process.returncode == 0, "first shutdown failed")
            server.start()
            actor = journey.reconnect_character(server.port)
            after = wallet(actor, state, [0, 0, 10, 0])
            bag_coins(after, [0, 0, 10, 0])
            command(actor, "get coins testbag", "There were: 10 gold coins.")
            for remaining in (10, 0):
                command(actor, "give 10 gold quartermaster", "GOLD_PAYMENT_ACCEPTED")
                wallet(actor, state, [0, 0, remaining, 0])
            output = command(actor, "give 10 gold quartermaster", "You do not have")
            journey.require("GOLD_PAYMENT_ACCEPTED" not in output, "failed fifth payment completed a quest")
            wallet(actor, state, [0, 0, 0, 0])
            report["checks"].append("four real quester completions without exchange, with wallet and bag restart checkpoints")

            command(actor, "give banana rewarder", "GOLD_REWARD_ACCEPTED")
            command(actor, "put rewardgold testbag", "Ok.")
            command(actor, "get rewardgold testbag", "There were: 17 gold coins.")
            wallet(actor, state, [0, 0, 17, 0])
            command(actor, "get mixedgold", "There were:")
            wallet(actor, state, [3, 12, 34, 0])
            command(actor, "drop 4 gold", "OK.")
            wallet(actor, state, [3, 12, 30, 0])
            command(actor, "get coins", "There were: 4 gold coins.")
            wallet(actor, state, [3, 12, 34, 0])
            report["checks"].append("authored quest money-object reward, mixed pile and drop/get preserve exact coins")

            target = journey.MudClient(server.port, source_host="127.0.0.2")
            journey.create_character(target, account=TARGET_ACCOUNT, character=TARGET,
                                     email="target@example.invalid")
            target.expect(PROMPT)
            command(target, "drop all", "You drop ")
            command(actor, f"give 10 gold {TARGET}", "Ok.")
            wallet(actor, state, [3, 12, 24, 0])
            wallet(target, state, [0, 0, 10, 0], TARGET, 2)
            quit_character(target)
            target = journey.reconnect_character(server.port, account=TARGET_ACCOUNT,
                                                  character=TARGET, source_host="127.0.0.2")
            wallet(target, state, [0, 0, 10, 0], TARGET, 2)
            # A real recipient refusal after sender debit must refund exactly and save.
            command(target, "drop all.coins", "You drop ")
            command(target, "get capacitygold", "There were:")
            wallet(target, state, [0, 0, 2147483647, 0], TARGET, 2)
            refused = command(actor, f"give 10 gold {TARGET}", "did not commit")
            journey.require("Ok." not in refused, "refused give announced success")
            wallet(actor, state, [3, 12, 24, 0])
            wallet(target, state, [0, 0, 2147483647, 0], TARGET, 2)
            command(actor, "close testbag", ("You close", "Ok."))
            before = saved(actor, state)
            command(actor, "put 5 gold testbag", "It is not an open, durable container.")
            after = wallet(actor, state, [3, 12, 24, 0])
            journey.require(after["wallet_revision"] == before["wallet_revision"], "closed bag debited wallet")
            command(actor, "open testbag", ("You open", "Ok."))
            command(actor, "put all.coins testbag", "coins into a small leather bag.")
            bag_coins(wallet(actor, state, [0, 0, 0, 0]), [3, 12, 24, 0])
            quit_character(actor)
            quit_character(target)
            actor = target = None
            server.stop()
            journey.require(server.process.returncode == 0, "second shutdown failed")
            server.start()
            actor = journey.reconnect_character(server.port)
            bag_coins(wallet(actor, state, [0, 0, 0, 0]), [3, 12, 24, 0])
            target = journey.reconnect_character(server.port, account=TARGET_ACCOUNT,
                                                  character=TARGET, source_host="127.0.0.2")
            wallet(target, state, [0, 0, 2147483647, 0], TARGET, 2)
            command(actor, "get coins testbag", "There were:")
            bag_coins(wallet(actor, state, [3, 12, 24, 0]), [0, 0, 0, 0])
            command(actor, "get coins testbag", "does not contain")
            wallet(actor, state, [3, 12, 24, 0])
            report["checks"].append("PC credit/relog, overflow refund, closed bag refusal, mixed bag/restart and no duplicate pickup")
        except Exception as error:
            transcript = actor.transcript.decode(errors="replace")[-7000:] if actor else ""
            raise AssertionError(f"{error}\n{transcript}\n{journey.runtime_logs(runtime)}") from error
        finally:
            for client in (actor, target):
                if client:
                    client.close()
            server.stop()
    output = ROOT / "bin/qualification/issue444"
    output.mkdir(parents=True, exist_ok=True)
    (output / "gameplay-mariadb.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


def run(binary):
    database = "coin_journey_test_" + uuid.uuid4().hex[:12]
    host = os.environ["TEST_DB_HOST"]
    assert host == "127.0.0.1", "use the disposable loopback database runner"
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "ENVIRONMENT": "local", "DB_HOST": host,
        "DB_PORT": os.environ["TEST_DB_PORT"], "DB_NAME": database,
        "DB_USER": os.environ["TEST_DB_USER"], "DB_PASSWD": os.environ["TEST_DB_PASSWORD"],
        "DB_ALLOWED_TARGETS": host + "/" + database,
        "MYSQL_PWD": os.environ["TEST_DB_PASSWORD"], "DB_TLS": "FALSE", "DB_SOCKET": "",
        "PERSISTENCE_MODE": "mariadb-primary", "REDIS": "FALSE", "CHAOS_MUD": "FALSE",
    }
    if "LD_LIBRARY_PATH" in os.environ:
        environment["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    mysql = ["mysql", "--protocol=tcp", "--skip-ssl", "-h", host,
             "-P", environment["DB_PORT"], "-u", environment["DB_USER"], "-N", "-B"]

    def sql(text, selected=True):
        return subprocess.check_output(
            mysql + ([database] if selected else []), input=text,
            text=True, env=environment, timeout=120).strip()

    def inspect(_state, pid=1):
        assert pid in (1, 2)
        name = journey.CHARACTER if pid == 1 else TARGET
        account = journey.ACCOUNT if pid == 1 else TARGET_ACCOUNT
        fields = list(map(int, sql(
            "SELECT pid,copper,silver,gold,platinum,wallet_revision,level,racewar "
            f"FROM player_data WHERE name='{name}'").split("\t")))
        actual_pid, *values = fields
        bank = sql("SELECT bank_copper,bank_silver,bank_gold,bank_platinum "
                   f"FROM account_banks WHERE account_name='{account}' AND racewar={values[6]}")
        piles = sql("SELECT obj_uid,container_id,value0,value1,value2,value3 "
                    f"FROM player_items WHERE pid={actual_pid} AND item_type=20 ORDER BY id")
        return {
            "wallet": values[:4], "wallet_revision": values[4], "level": values[5],
            "bank": list(map(int, bank.split("\t"))) if bank else [0, 0, 0, 0],
            "coin_items": [
                {"uid": int(row[0]), "coins": list(map(int, row[2:]))}
                for row in (line.split("\t") for line in piles.splitlines())
            ],
        }

    sql("CREATE DATABASE " + database + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", False)
    try:
        sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
        subprocess.run(["python3", "scripts/migration_runner.py", "adopt", "--kind", "fresh_bootstrap"],
                       cwd=ROOT, env=environment, check=True)
        subprocess.run(["python3", "scripts/migration_runner.py", "run"],
                       cwd=ROOT, env=environment, check=True)
        global saved_state
        saved_state = inspect
        play_journey(binary, environment)
    finally:
        sql("DROP DATABASE " + database, False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    args = parser.parse_args()
    run(args.server.resolve())
