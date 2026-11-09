#!/usr/bin/env python3
"""Exercise repeated legacy grants with a second active player on disposable MariaDB."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import signal
import socket
import subprocess
import tempfile
import threading
import time

import test_flatfile_combat_journey as journey
import test_flatfile_chaos_new_character_kit as chaos_kit

ROOT = Path(__file__).resolve().parents[2]


class ObserverClient(journey.MudClient):
    """Use a separate loopback source address for the second synthetic player."""

    def __init__(self, port):
        self.socket = socket.create_connection(
            ("127.0.0.1", port), timeout=10, source_address=("127.0.0.2", 0))
        self.socket.settimeout(0.25)
        self.pending = bytearray()
        self.transcript = bytearray()
        self.raw_transcript = bytearray()


def install_legacy_objects(run_root):
    """Load the production legacy prototypes into the disposable minimal world."""
    source = run_root / "legacy_vnums.cpp"
    source.write_text('#include "account/newbie_kit_plan.h"\n#include <cstdio>\n'
                      'int main() { for (int v : newbie_kit_template_vnums()) printf("%d\\n", v); }\n')
    binary = run_root / "legacy_vnums"
    subprocess.run(["g++", "-std=c++20", "-Isrc", str(source),
                    "src/account/newbie_kit_plan.c", "-o", str(binary)], cwd=ROOT, check=True)
    vnums = set(map(int, subprocess.check_output([str(binary)], text=True).split()))
    path = run_root / "areas_mini/mini.obj"
    entries = {int(vnum): entry.rstrip() + "\n" for entry, vnum in re.findall(
        r"(?ms)(^#(\d+)$\n.*?)(?=^#\d+$|^\$~$)", path.read_text())}
    world = chaos_kit.world_object_text()
    for vnum in vnums - entries.keys():
        match = re.search(rf"(?ms)^#{vnum}$\n.*?(?=^#\d+$|^\$~$)", world)
        journey.require(match is not None, f"missing legacy prototype {vnum}")
        entries[vnum] = match[0].rstrip() + "\n"
    path.write_text("".join(entries[vnum] for vnum in sorted(entries)) + "$~\n")


def saved_items(sql):
    """Read the current synthetic player's saved item and spell identities."""
    rows = sql("SELECT i.obj_uid,i.vnum,i.extra_flags,i.value3,e.description FROM player_items i "
               "LEFT JOIN player_item_extra_descr e ON e.item_id=i.id AND e.keyword='SPELLBOOK' "
               "WHERE i.pid=1")
    lines = []
    for uid, vnum, flags, pages, book in (row.split("\t") for row in rows.splitlines()):
        lines.append(f"ITEM {uid} {vnum} {flags}")
        if book != "NULL":
            spells = sorted(json.loads(book))
            journey.require(spells and int(pages) == len(spells) and len(set(spells)) == len(spells),
                            f"malformed saved spellbook on item {uid}: pages={pages} spells={len(spells)} {book}")
            lines.append(f"BOOK {uid} {pages} " + " ".join(map(str, spells)))
    return sorted(lines)


def held(sql):
    """What the player's saved rows hold, by uid."""
    return {int(fields[1]): int(fields[2]) for fields in
            (line.split() for line in saved_items(sql)) if fields[0] == "ITEM"}


def save_and_wait(actor, sql, done, timeout=30):
    """Save, then wait for the asynchronous writer to land a file that satisfies done."""
    actor.send("save")
    actor.expect(f"Saving {journey.CHARACTER}.", timeout=20)
    actor.expect("Pos: standing >")
    deadline = time.monotonic() + timeout
    while True:
        current = held(sql)
        if done(current):
            return current
        journey.require(time.monotonic() < deadline, "the save did not reach the saved rows")
        time.sleep(0.05)


def run(binary, chaos, class_name="Warrior"):
    """Verify two repeat grants, durable contents, and concurrent command latency."""
    with tempfile.TemporaryDirectory(prefix="newbie-regrant-") as tmp, \
            journey.mariadb_authority() as (authority, sql):
        root = Path(tmp)
        runtime = root / "runtime"
        runtime.mkdir()
        (runtime / "logs/log").mkdir(parents=True)
        journey.make_fixture(runtime)
        chaos_kit.install_chaos_objects(runtime, "Warrior")
        if class_name != "Warrior":
            chaos_kit.install_chaos_objects(runtime, class_name)
        install_legacy_objects(runtime)
        # Keep this scheduling journey free of unrelated NPC combat.
        zone = runtime / "areas_mini/mini.zon"
        zone.write_text(re.sub(r"^[MG] .*\n", "", zone.read_text(), flags=re.M))
        journey.generate_certificate(runtime)
        journals = runtime / "journals"
        (journals / "players").mkdir(parents=True, mode=0o700)
        (journals / "critical").mkdir(mode=0o700)
        plain, tls, websocket = journey.available_ports()
        env = {**authority, "CRITICAL_COMMAND_JOURNAL_DIR": str(journals / "critical"),
               "DURIS_TLS_PORT": str(tls), "DURIS_WEBSOCKET_PORT": str(websocket),
               "CHAOS_MUD": "TRUE" if chaos else "FALSE", "CREATION_ALL_CLASSES": "TRUE",
               "CHAOS_EQ_PROFILE": "standard", "CHAOS_STARTER_BONUSES": "TRUE"}
        log = runtime / "server.out"
        with log.open("w") as output:
            process = subprocess.Popen([str(binary), "--minimal", "-s", "-d", str(runtime), str(plain)],
                                       cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
            actor = observer = None
            stop = threading.Event()
            worker = None
            latencies = []
            errors = []
            try:
                actor = journey.MudClient(plain)
                if chaos:
                    chaos_kit.create_chaos_character(actor, class_name, "n" if class_name == "Rogue" else "g")
                else:
                    journey.create_character(actor, expected_room=None, class_name=class_name.lower(),
                                             alignment="n" if class_name == "Rogue" else "g")
                actor.expect("Pos: standing >")
                initial = save_and_wait(actor, sql, lambda items: len(items) > 10)

                observer = ObserverClient(plain)
                original = journey.ACCOUNT, journey.CHARACTER, chaos_kit.ACCOUNT, chaos_kit.CHARACTER
                try:
                    journey.ACCOUNT = chaos_kit.ACCOUNT = "Observeacct"
                    journey.CHARACTER = chaos_kit.CHARACTER = "Valerek"
                    if chaos:
                        chaos_kit.create_chaos_character(observer)
                    else:
                        journey.create_character(
                            observer,
                            expected_room=None,
                            account="Observeacct",
                            character="Valerek",
                            email="observeacct@example.invalid",
                        )
                finally:
                    journey.ACCOUNT, journey.CHARACTER, chaos_kit.ACCOUNT, chaos_kit.CHARACTER = original
                observer.expect("Pos: standing >")

                def observe():
                    """Measure actual score-to-prompt round trips during actor logins."""
                    try:
                        while not stop.is_set():
                            started = time.monotonic()
                            observer.send("score")
                            # Room notifications can also produce prompts. Match
                            # this command's output before consuming its prompt.
                            observer.expect("Level:", timeout=10)
                            observer.expect("Pos: standing >", timeout=10)
                            latencies.append(time.monotonic() - started)
                            stop.wait(0.05)
                    except Exception as error:
                        errors.append(error)

                worker = threading.Thread(target=observe)
                worker.start()
                actor.send("toggle newbie")
                response = actor.expect("Pos: standing >")
                if "will not load with newbie EQ" in response:
                    actor.send("toggle newbie")
                    actor.expect("will now load with newbie EQ")
                    actor.expect("Pos: standing >")
                expected = None
                prior_uids = set(initial)
                for attempt in range(2):
                    actor.send("remove all")
                    actor.expect("Pos: standing >")
                    actor.send("drop all")
                    actor.expect("Pos: standing >", timeout=30)
                    save_and_wait(actor, sql, lambda items: not items)
                    actor.send("quit")
                    actor.expect("ACCOUNT MENU", timeout=40)
                    actor.send("0")
                    actor.close()
                    actor = None
                    started = time.monotonic()
                    actor = journey.reconnect_character(plain, expected_room=None)
                    actor.expect("Your starter kit is being prepared", timeout=15)
                    preparing = time.monotonic()
                    actor.expect("Your starter kit is ready", timeout=30)
                    actor.expect("Pos: standing >")
                    elapsed = time.monotonic() - preparing
                    login_elapsed = time.monotonic() - started
                    complete = save_and_wait(actor, sql, lambda items: len(items) > 10)
                    composition = Counter(complete.values())
                    journey.require(len(complete) > 10, "regrant omitted the legacy kit")
                    journey.require(not (set(complete) & prior_uids), "regrant reused an old item identity")
                    if expected is None:
                        expected = composition
                    if not chaos:
                        journey.require(composition == Counter(initial.values()), "regrant changed first-login contents")
                    if class_name in ("Ranger", "Rogue"):
                        journey.require(composition[1116] == 1 and composition[1117] == 10 and
                                        composition[1118] == 1, f"incomplete ordinary archery regrant: {composition}")
                    journey.require(composition == expected, "repeated grant changed kit contents")
                    saved = saved_items(sql)
                    journey.require(sum(line.startswith("ITEM ") for line in saved) == len(complete),
                                    "saved kit lost a root or transient item")
                    if class_name == "Sorcerer":
                        journey.require(any(line.startswith("BOOK ") for line in saved), "missing populated spellbook")
                    print(f"newbie regrant chaos={chaos} class={class_name} round={attempt + 1}: "
                          f"roots={len(complete)} prepare_to_prompt={elapsed:.3f}s "
                          f"login_to_prompt={login_elapsed:.3f}s", flush=True)
                    journey.require(elapsed < 8, "legacy grant still waits through serialized roots")
                    prior_uids |= set(complete)
                # A nonempty saved inventory must survive login without a third kit.
                saved = held(sql)
                saved_snapshot = saved_items(sql)
                actor.send("quit")
                actor.expect("ACCOUNT MENU", timeout=40)
                actor.send("0")
                actor.close()
                actor = journey.reconnect_character(plain, expected_room=None)
                text = actor.expect("Pos: standing >", timeout=20)
                journey.require("starter kit is being prepared" not in text, "nonempty inventory regranted")
                journey.require(held(sql) == saved, "saved kit identities changed across reload")
                actor.send("save")
                actor.expect(f"Saving {journey.CHARACTER}.", timeout=20)
                actor.expect("Pos: standing >")
                journey.require(saved_items(sql) == saved_snapshot,
                                "saved item flags or spellbook contents changed across reload")
                stop.set()
                worker.join(timeout=12)
                journey.require(not errors and not worker.is_alive(), f"observer failed: {errors}")
                journey.require(len(latencies) >= 4, "insufficient concurrent player observations")
                print(f"observer chaos={chaos} class={class_name}: samples={len(latencies)} "
                      f"max_score_to_prompt={max(latencies):.3f}s", flush=True)
                journey.require(max(latencies) < 5, "other player stalled for several seconds")
            except Exception:
                print(log.read_text(errors="replace")[-6000:])
                raise
            finally:
                stop.set()
                if worker:
                    worker.join(timeout=12)
                for client in (actor, observer):
                    if client:
                        client.close()
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=40)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("classes", nargs="*", default=("Warrior", "Sorcerer", "Ranger", "Rogue"))
    args = parser.parse_args()
    for chaos_mode in (False, True):
        for role in args.classes:
            run(args.server.resolve(), chaos_mode, role)
