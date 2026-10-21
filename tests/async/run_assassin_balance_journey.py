#!/usr/bin/env python3
"""Compare Assassin openings on pinned, seeded, isolated flat-file servers.

The actors and gear are controlled reference fixtures. Results measure real
command dispatch and damage delivery, not live PvP win rates.
"""

from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import tarfile
import tempfile
import time

import test_flatfile_combat_journey as journey
from run_paladin_balance_journey import command, hp
from test_flight_network_journey import command as combat_command
from test_assassin_combat_journey import ACTORS, fixture

ROOT = journey.ROOT
MANIFEST = ROOT / "bin/tests/assassin-comparative/binaries.json"
BASE = "24a2776f13a2f3580c91f945743b09f80144b829"
LEVELS = (30, 36, 41, 46, 51, 56)
RACES = ("Human", "Mountain Dwarf", "Duergar Dwarf")
NOTICE = "poison from your attacker's blade enters your bloodstream!"


# These are copied or read by the shared runtime fixture and command helpers.
RUNTIME_INPUTS = (
    "lib", "areas_mini", "areas/obj/heavens.obj",
    "tests/async/run_assassin_balance_journey.py",
    "tests/async/test_assassin_combat_journey.py",
    "tests/async/test_flatfile_combat_journey.py",
    "tests/async/assassin_journey_fixture.cpp",
    "tests/async/run_paladin_balance_journey.py",
    "tests/async/run_divine_refusal_journey.py",
    "tests/async/run_item_pilot_journey.py",
    "tests/async/test_flight_network_journey.py",
)


def source_digest(root, inputs=("src",)):
    digest = hashlib.sha256()
    for name in inputs:
        source = root / name
        paths = sorted(source.rglob("*")) if source.is_dir() else [source]
        for path in paths:
            if path.is_file():
                digest.update(str(path.relative_to(root)).encode() + b"\0")
                digest.update(path.read_bytes())
    return digest.hexdigest()


def prepare_binaries():
    """Build three immutable source variants with the shared verified builder."""
    directory = MANIFEST.parent
    directory.mkdir(parents=True, exist_ok=True)
    original = directory / "original-24a2776f1"
    if not original.exists():
        original.mkdir()
        archive = subprocess.Popen(["git", "archive", BASE], cwd=ROOT, stdout=subprocess.PIPE)
        with archive.stdout, tarfile.open(fileobj=archive.stdout, mode="r|") as tar:
            tar.extractall(original, filter="data")
        assert archive.wait() == 0, "baseline archive failed"
        (original / "qualification-ref").write_text(BASE + "\n")
    assert (original / "qualification-ref").read_text().strip() == BASE

    cleansed = directory / "cleansed-24a2776f1"
    patch = (Path(__file__).parent / "fixtures/assassin_cleanse_only.patch").read_bytes()
    if not cleansed.exists():
        shutil.copytree(original, cleansed, ignore=shutil.ignore_patterns("bin"))
        (cleansed / "qualification-ref").write_text(BASE + "\n")
        (cleansed / "qualification-patch").write_bytes(patch)
    assert (cleansed / "qualification-ref").read_text().strip() == BASE
    assert (cleansed / "qualification-patch").read_bytes() == patch
    # git apply can silently skip paths when this archive is nested in a worktree.
    # Verify actual patch content, including caches written by the old runner.
    reversed_patch = subprocess.run(
        ["patch", "-p1", "--batch", "--reverse", "--forward", "--dry-run"], cwd=cleansed,
        input=patch, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if reversed_patch.returncode:
        subprocess.run(["patch", "-p1", "--batch", "--forward"], cwd=cleansed,
                       input=patch, check=True)
    assert source_digest(original) != source_digest(cleansed), "cleanse-only patch did not apply"

    seed = Path(__file__).with_name("assassin_seed_fixture.cpp")
    seed_sha = hashlib.sha256(seed.read_bytes()).hexdigest()
    seed_object = directory / f"seed-{seed_sha[:12]}.o"
    subprocess.run(["g++", "-std=c++20", "-c", str(seed), "-o", str(seed_object)], check=True)
    result = {}
    runtime_sha = source_digest(ROOT, RUNTIME_INPUTS)
    for name, source in (("original", original), ("cleansed", cleansed), ("revised", ROOT)):
        utility_path = source / "tests/async/server_build_artifacts.py"
        spec = importlib.util.spec_from_file_location("assassin_builder_" + name, utility_path)
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        saved = {key: os.environ.get(key) for key in
                 ("MAKEFLAGS", "DURIS_REGRESSION_BUILD_CACHE", "WSL_INTEROP")}
        try:
            os.environ["MAKEFLAGS"] = f"EXTRA_LDFLAGS=-Wl,--wrap=_Z9randomizem,{seed_object}"
            os.environ["DURIS_REGRESSION_BUILD_CACHE"] = str(source / "bin/qualification-cache")
            os.environ.pop("WSL_INTEROP", None)
            binary = builder.build_flatfile_server(source / "bin/qualification-build")
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        assert "__wrap__Z9randomizem" in subprocess.check_output(["nm", str(binary)], text=True)
        result[name] = dict(binary=str(binary), binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                            source=BASE if name != "revised" else subprocess.check_output(
                                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                            src_sha256=source_digest(source), runtime_sha256=runtime_sha, seed=187, seed_fixture_sha256=seed_sha)
    result["cleansed"]["patch_sha256"] = hashlib.sha256(patch).hexdigest()
    assert result["original"]["binary_sha256"] != result["cleansed"]["binary_sha256"], \
        "original and cleanse-only binaries are identical"
    MANIFEST.write_text(json.dumps(result, indent=2) + "\n")


def run_revised_scenarios(staff, assassin, victim, snapshot_fixture, state):
    """Exercise equal items, a mismatch, poison timing, cure and movement."""
    def set_char(who, field, value):
        command(staff, f"setbit char {who} {field} '{value}'")

    def settle():
        assert "monotone" in command(staff, "tranquilize Shadeblade")
        command(staff, "restore all")
        command(assassin, "wake")
        command(assassin, "stand")

    def opening(reset=True):
        if reset:
            settle()
        set_char("Venomtarget", "hit", "10000")
        before = hp(staff, "Venomtarget")[0]
        source_start, target_start = len(assassin.transcript), len(victim.transcript)
        assassin.send("backstab Venomtarget")
        time.sleep(.15)
        command(staff, "tranquilize Shadeblade")
        after = hp(staff, "Venomtarget")[0]
        assassin._receive(); victim._receive()
        command(victim, "score")
        source_text = bytes(assassin.transcript[source_start:]).decode(errors="replace")
        target_text = bytes(victim.transcript[target_start:]).decode(errors="replace")
        return {"damage": before-after,
                "landed": "as you place" in source_text or "stabs you in the back" in target_text,
                "notices": target_text.count(NOTICE),
                "critical_stab": "twist the blade" in source_text}

    def inspect():
        victim.send("save")
        victim.expect("Save complete for Venomtarget.", timeout=30)
        return subprocess.check_output([str(snapshot_fixture), str(state), "inspect"], text=True)

    def give(vnum, keyword, person):
        assert "created" in command(staff, f"load obj {vnum}")
        assert "Ok." in command(staff, f"give {keyword} {person}")

    result = {}
    settle()
    set_char("Venomtarget", "class", "Ranger")
    command(staff, "setbit char Venomtarget skill 'awareness' 80")
    # Both PCs now wield the same mundane dagger and wear the same leather suit.
    give(22810, "journeydagger", "Venomtarget")
    command(victim, "wield journeydagger")
    for person, client in (("Shadeblade", assassin), ("Venomtarget", victim)):
        give(681, "armor", person)
        wearing = command(client, "wear armor")
        assert "shrug into" in wearing.lower(), wearing
    set_char("Shadeblade", "race", "Human")
    for label, attacker_level, defender_level, defender_armor in (
        ("equal", 56, 56, 0), ("lower_attacker", 46, 56, 0),
        ("better_defense", 56, 51, -150)):
        set_char("Shadeblade", "level", str(attacker_level))
        set_char("Venomtarget", "level", str(defender_level))
        command(staff, f"setbit char Shadeblade skill 'critical stab' {100 if attacker_level >= 51 else 0}")
        set_char("Venomtarget", "ac", str(defender_armor))
        aligned = command(victim, "awareness")
        assert "aligned with your surroundings" in aligned, aligned
        result[label] = opening()
    print("revised equipped reference openings", {key: result[key] for key in
                                                ("equal", "lower_attacker", "better_defense")}, flush=True)

    # Control Flee uses the real room exit and escape checks after a live attack.
    set_char("Shadeblade", "level", "56")
    command(staff, "setbit char Shadeblade skill 'control flee' 100")
    for attempt in range(12):
        settle()
        assassin.send("hit Venomtarget")
        time.sleep(.15)
        text = combat_command(assassin, "flee east")
        if "Assassin Audit Refuge" in combat_command(assassin, "look"):
            result["flee"] = {"attempts": attempt+1, "east": True, "feedback": "east" in text.lower()}
            command(assassin, "west")
            print("revised Control Flee east", result["flee"], flush=True)
            break
    else:
        raise AssertionError("Control Flee did not escape east in twelve attempts")

    # Test a caster's real cure window and a subsequent uncured Heart tick.
    settle()
    set_char("Venomtarget", "class", "Cleric")
    set_char("Venomtarget", "level", "56")
    set_char("Venomtarget", "ac", "0")
    command(assassin, "drop all")
    command(victim, "drop all")
    command(victim, "remove armor")
    give(22814, "cursearmor", "Venomtarget")
    worn = command(victim, "wear cursearmor")
    assert "shrug into" in worn.lower(), worn
    saves = command(staff, "stat char Venomtarget")
    assert re.search(r"\(mods\)\s+\[\s*15\]", saves), saves

    def delivered(vnum, keyword, weapon="journeydagger"):
        for attempt in range(16):
            settle()
            give(vnum, keyword, "Shadeblade")
            applied = command(assassin, f"apply {keyword} {weapon}")
            assert "now drips" in applied, applied
            row = opening(False)
            if row["notices"]:
                row["attempts"] = attempt+1
                return row
        raise AssertionError(f"{keyword} never established a new poison")

    cured_symptom_start = len(victim.transcript)
    heart_cure = delivered(473, "heart")
    cured = command(victim, "cast 'remove poison' Venomtarget")
    assert "don't know" not in cured.lower(), cured
    snapshot = inspect()
    assert "affect 3 1539 " not in snapshot, snapshot
    first_tick_before_cure = "You suddenly feel sick" in bytes(
        victim.transcript[cured_symptom_start:]).decode(errors="replace")
    print("revised prepared Cleric Heart cure", {"first_tick_before_cure": first_tick_before_cure}, flush=True)
    command(staff, "restore all")
    cured_hp = hp(staff, "Venomtarget")[0]
    time.sleep(6.5)
    victim._receive()
    assert hp(staff, "Venomtarget")[0] == cured_hp, "cured Heart Toxin dealt delayed damage"
    symptom_start = len(victim.transcript)
    heart_tick = delivered(473, "heart")
    before_tick = hp(staff, "Venomtarget")[0]
    time.sleep(6.5)
    victim._receive()
    symptoms = bytes(victim.transcript[symptom_start:]).decode(errors="replace")
    assert "You suddenly feel sick" in symptoms, "uncured Heart Toxin did not reach its scheduled tick"
    after_tick = hp(staff, "Venomtarget")[0]
    result["heart"] = {"cured": heart_cure, "uncured": heart_tick,
                       "observed_hit_change_after_delivery": before_tick-after_tick,
                       "scheduled_symptom_seen": True,
                       "first_tick_before_preemptive_cure": first_tick_before_cure,
                       "no_later_tick_after_cure": True}
    print("revised Heart first tick", result["heart"], flush=True)
    command(victim, "cast 'remove poison' Venomtarget")
    assert "affect 3 1539 " not in inspect()

    slowness = delivered(475, "slowness")
    assert "affect 3 1541 " in inspect()
    command(victim, "cast 'remove poison' Venomtarget")
    assert "affect 3 1541 " not in inspect(), "prepared Cleric did not cleanse Slowness"
    result["slowness_cure"] = slowness
    print("revised Cleric cured Slowness", slowness, flush=True)

    # Current master retired Healer Warding Faith. A legal Healer must not
    # acquire its old absorption pool during the Heart delivery/tick path.
    set_char("Venomtarget", "spec", "2")
    settle()
    enabled = command(victim, "display ward")
    assert "ON" in enabled, enabled
    assert not re.search(r"\d+(?:/\d+)?W\b", command(victim, "score"))
    healer_symptom_start = len(victim.transcript)
    healer_heart = delivered(473, "heart")
    healer_hp = hp(staff, "Venomtarget")[0]
    time.sleep(6.5)
    victim._receive()
    healer_symptom = "You suddenly feel sick" in bytes(
        victim.transcript[healer_symptom_start:]).decode(errors="replace")
    assert healer_symptom, "Heart did not reach the unwarded Healer"
    assert not re.search(r"\d+(?:/\d+)?W\b", command(victim, "score"))
    result["healer_heart"] = {"application": healer_heart, "retired_ward_absent": True,
                              "symptom_seen": healer_symptom,
                              "observed_hit_change": healer_hp-hp(staff, "Venomtarget")[0]}
    print("revised Healer Heart tick without retired ward", result["healer_heart"], flush=True)

    # A dual opening can establish two different coatings; a duplicate ID is
    # consumed but cannot establish a second affect or victim notice.
    set_char("Venomtarget", "spec", "0")
    settle()
    give(22813, "offhand", "Shadeblade")
    wielded = command(assassin, "wield offhand")
    assert "wield" in wielded.lower(), wielded
    for label, second_vnum, second_name, expected in (
        ("mixed_dual", 475, "slowness", 2),
        ("duplicate_dual", 472, "neurotoxin", 1)):
        for attempt in range(12):
            settle()
            # restore replenishes resources; explicitly cure all earlier poisons.
            command(staff, "cast 'remove poison' Venomtarget")
            assert "affect 3 " not in inspect(), "dual opening inherited a poison"
            give(472, "neurotoxin", "Shadeblade")
            if second_vnum != 472:
                give(second_vnum, second_name, "Shadeblade")
            assert "now drips" in command(assassin, "apply neurotoxin journeydagger")
            assert "now drips" in command(assassin, f"apply {second_name} offhand")
            row = opening(False)
            saved = inspect()
            if row["notices"] == expected and "affect 3 1538 " in saved and \
                    (second_vnum == 472 or "affect 3 1541 " in saved):
                result[label] = {**row, "attempts": attempt+1}
                break
        else:
            raise AssertionError(label + " never produced its expected dual-poison outcome")
    print("revised dual poison openings", {key: result[key] for key in
                                           ("mixed_dual", "duplicate_dual")}, flush=True)

    # A disposable level-46 NPC supplies an actual solo kill and elapsed combat
    # time. Its 50-HP profile is a reference target, not a live PvE balance mob.
    settle()
    give(470, "lifeleak", "Shadeblade")
    assert "now drips" in command(assassin, "apply lifeleak journeydagger")
    loaded = command(staff, "load mob 22803")
    assert "No such" not in loaded, loaded
    command(staff, "setbit char assassinsentinel basehit 50")
    command(staff, "setbit char assassinsentinel hit 50")
    npc_stats = command(staff, "stat mob assassinsentinel")
    assert "assassinsentinel" in npc_stats.lower(), npc_stats
    npc_hp = re.search(r"Hits:\s*\[\s*(\d+)\s*/\s*(\d+)", npc_stats)
    assert npc_hp and int(npc_hp[1]) == 50 and int(npc_hp[2]) == 50, npc_stats
    actor_before = hp(staff, "Shadeblade")[0]
    started = time.monotonic()
    assassin.send("backstab assassinsentinel")
    deadline = started + 60
    while True:
        remaining = deadline - time.monotonic()
        assert remaining > 0, "solo Assassin did not finish the reference NPC"
        outcome, _ = assassin.expect_any(
            ("is dead! R.I.P.", "You stumble, but recover in time!",
             "You stumble in your attack, and jab at",
             "You stumble in your attack, and hit yourself!"), timeout=remaining)
        if outcome == "is dead! R.I.P.":
            break
        assassin.send("hit assassinsentinel")
    result["solo_pve"] = {"npc_level": 46, "reference_hp": 50,
                          "seconds_to_kill": round(time.monotonic()-started, 2),
                          "survived": hp(staff, "Shadeblade")[0] > 0,
                          "actor_hp_loss": actor_before-hp(staff, "Shadeblade")[0]}
    assert result["solo_pve"]["survived"]
    print("revised solo PvE", result["solo_pve"], flush=True)

    # A traded high-tier vial remains usable by a level-30 Assassin; the gate
    # intentionally belongs to mixing. It is not applied to another player.
    set_char("Shadeblade", "level", "30")
    settle()
    give(476, "madness", "Shadeblade")
    result["traded_madness"] = "now drips" in command(assassin, "apply madness journeydagger")
    assert result["traded_madness"]
    print("revised integrated scenarios", result, flush=True)
    return result


def run_variant(name, binary, snapshot_fixture, skip_matrix=False):
    with tempfile.TemporaryDirectory(prefix="assassin-audit-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        state = runtime / "state"
        state.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)
        fixture(runtime)
        world_path = runtime / "areas_mini/mini.wld"
        world = world_path.read_text()
        world = world.replace("1 0 0\nS\n$~", "1 0 0\nD1\n~\n~\n0 0 22801\nS\n$~")
        assert "0 0 22801" in world
        refuge = """#22801
The Assassin Audit Refuge~
A quiet room beyond the arena's eastern exit.
~
1 0 0
D3
~
~
0 0 22800
S
"""
        world_path.write_text(world.replace("$~", refuge + "$~"))
        objects = runtime / "areas_mini/mini.obj"
        offhand = """#22813
offhand auditdagger dagger~
an offhand audit dagger~
An offhand audit dagger rests here.~
~
5 11 2 3 7 0 0 8193 0 0 0
2 1 4 11 0 0 0 0
2 100 100
#22814
cursearmor auditarmor armor~
a porous audit armor~
A porous audit armor rests here.~
~
9 13 0 0 7 0 0 9 0 0 0
5 3 1 3 0 0 0 0
7 250 100
A
20 15
"""
        objects.write_text(objects.read_text().replace("$~", offhand + "$~"))
        mobiles = runtime / "areas_mini/mini.mob"
        sentinel = """#22803
assassinsentinel sentinel~
an assassin audit sentinel~
An assassin audit sentinel waits to test solo combat.
~
~
10 0 0 0 0 0 0 0 S
PH 0 0 -1
46 0 0 100d1+100 1d1+1
0.0.0.0 0
8 8 0
"""
        mobiles.write_text(mobiles.read_text().replace("$~", sentinel + "$~"))
        (runtime / "logs/log").mkdir(parents=True)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        (runtime / "journals/players").mkdir(mode=0o700)
        plain, tls, websocket = journey.available_ports()
        environment = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"), ENVIRONMENT="local",
                           PERSISTENCE_MODE="flatfile-primary", FLATFILE_STATE_DIR=str(state),
                           CRITICAL_COMMAND_JOURNAL_DIR=str(critical), REDIS="FALSE", CHAOS_MUD="FALSE",
                           LISTEN_ADDRESS="127.0.0.1", DURIS_TLS_PORT=str(tls),
                           DURIS_WEBSOCKET_PORT=str(websocket), DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1")
        if "LD_LIBRARY_PATH" in os.environ:
            environment["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        output_path = runtime / "server.out"
        process = None
        clients = []

        def boot(output):
            nonlocal process
            offset = output_path.stat().st_size
            process = subprocess.Popen([str(binary), "--minimal", "-s", "-d", str(runtime), str(plain)],
                                       cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 120
            while "Entering game loop." not in output_path.read_text(errors="replace")[offset:]:
                assert process.poll() is None and time.monotonic() < deadline, "isolated boot failed"
                time.sleep(.1)

        def stop():
            for client in clients:
                client.close()
            clients.clear()
            if process is not None and process.poll() is None:
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=30)
                assert process.returncode == 0, "isolated server shutdown failed"

        def login(actor):
            character, account = actor
            client = journey.reconnect_character(plain, expected_room=None, account=account,
                                                 character=character)
            clients.append(client)
            client.expect("Welcome to Duris", timeout=30)
            client.expect_any(("Pos: standing >", "<>"), timeout=20)
            command(client, "toggle paging no")
            return client

        rows = []
        with output_path.open("w") as output:
            try:
                boot(output)
                for character, account in ACTORS:
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, account=account, character=character,
                                             email=character.lower() + "@example.invalid")
                    client.send("save")
                    client.expect("Save complete for " + character + ".")
                stop()
                subprocess.run([str(snapshot_fixture), str(state), "audit"], check=True)
                boot(output)
                staff, assassin, victim = (login(actor) for actor in ACTORS)
                assert "created" in command(staff, "load obj 22810")
                assert "Ok." in command(staff, "give journeydagger Shadeblade")
                assert "You wield" in command(assassin, "wield journeydagger")
                for defender in (() if skip_matrix else ("Cleric", "Ranger")):
                    command(staff, f"setbit char Venomtarget class {defender}")
                    if defender == "Ranger":
                        command(staff, "setbit char Venomtarget skill 'awareness' 80")
                    for level in LEVELS:
                        for race in (RACES if name == "revised" else RACES[:1]):
                            for target, field, value in (("Shadeblade", "level", str(level)),
                                                         ("Venomtarget", "level", str(level)),
                                                         ("Shadeblade", "race", race)):
                                command(staff, f"setbit char {target} {field} '{value}'")
                            for skill in ("critical stab", "control flee"):
                                trained = 100 if level >= (51 if skill == "critical stab" else 45) else 0
                                command(staff, f"setbit char Shadeblade skill '{skill}' {trained}")
                            command(staff, "tranquilize Shadeblade")
                            command(staff, "restore all")
                            command(assassin, "wake")
                            command(assassin, "stand")
                            command(staff, "setbit char Venomtarget hit 10000")
                            if defender == "Ranger":
                                aligned = command(victim, "awareness")
                                assert "aligned with your surroundings" in aligned, aligned
                            before = hp(staff, "Venomtarget")[0]
                            victim_start = len(victim.transcript)
                            attack_start = len(assassin.transcript)
                            assassin.send("backstab Venomtarget")
                            time.sleep(.15)
                            command(staff, "tranquilize Shadeblade")
                            after = hp(staff, "Venomtarget")[0]
                            assassin._receive()
                            victim._receive()
                            attack = bytes(assassin.transcript[attack_start:]).decode(errors="replace")
                            seen = bytes(victim.transcript[victim_start:]).decode(errors="replace")
                            row = dict(defender=defender, level=level, assassin_race=race,
                                       damage=before-after,
                                       landed="stabs you in the back" in seen or "as you place" in attack,
                                       critical_stab="twist the blade" in attack,
                                       awareness_reduction="unable to take full advantage" in attack)
                            rows.append(row)
                            print(name, row, flush=True)
                if not skip_matrix:
                    assert any(row["landed"] for row in rows), "no backstab reached combat"
                scenarios = run_revised_scenarios(staff, assassin, victim, snapshot_fixture, state) \
                    if name == "revised" and skip_matrix else {}
                stop()
            except Exception:
                print(output_path.read_text(errors="replace")[-6000:])
                print(journey.runtime_logs(runtime)[-6000:])
                for client in clients:
                    print(client.transcript.decode(errors="replace")[-3000:])
                raise
            finally:
                stop()
        return {"openings": rows, "scenarios": scenarios}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("all", "original", "cleansed", "revised"), default="all")
    parser.add_argument("--scenarios-only", action="store_true", help="rerun revised integrated cases")
    parser.add_argument("--prepare", action="store_true", help="build the three pinned seeded server binaries")
    options = parser.parse_args()
    selected = options.variant
    assert not options.scenarios_only or selected == "revised", "scenarios-only requires --variant revised"
    if options.prepare or not MANIFEST.exists():
        prepare_binaries()
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["original"]["src_sha256"] != manifest["cleansed"]["src_sha256"], \
        "original and cleanse-only sources are identical; rerun --prepare"
    assert manifest["original"]["binary_sha256"] != manifest["cleansed"]["binary_sha256"], \
        "original and cleanse-only binaries are identical; rerun --prepare"
    fixture_binary = ROOT / "bin/tests/assassin-comparative/snapshot-fixture"
    subprocess.run(["g++", "-std=c++20", "-Isrc", "tests/async/assassin_journey_fixture.cpp",
                    "src/player/player_snapshot_codec.c", "src/flatfile/flatfile_player_snapshot_file.c",
                    "src/flatfile/flatfile_store.c", "-lcrypto", "-o", str(fixture_binary)],
                   cwd=ROOT, check=True)
    subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                    "--build-inspector", str(journey.INSPECTOR)], cwd=ROOT, check=True, timeout=180)
    result = {}
    runtime_sha = source_digest(ROOT, RUNTIME_INPUTS)
    for variant, entry in manifest.items():
        if selected != "all" and variant != selected:
            continue
        assert entry.get("runtime_sha256") == runtime_sha, "runtime fixture inputs changed; rerun --prepare"
        assert entry["source"] == BASE or variant == "revised"
        assert entry["src_sha256"] == source_digest(ROOT if variant == "revised" else
                                                     MANIFEST.parent / f"{variant}-24a2776f1")
        if variant == "cleansed":
            assert entry["patch_sha256"] == hashlib.sha256(
                (Path(__file__).parent / "fixtures/assassin_cleanse_only.patch").read_bytes()).hexdigest()
        assert entry["seed_fixture_sha256"] == hashlib.sha256(
            Path(__file__).with_name("assassin_seed_fixture.cpp").read_bytes()).hexdigest()
        binary = Path(entry["binary"])
        assert hashlib.sha256(binary.read_bytes()).hexdigest() == entry["binary_sha256"]
        result[variant] = run_variant(variant, binary, fixture_binary, options.scenarios_only)
    if selected == "all":
        assert len(result["original"]["openings"]) == len(result["cleansed"]["openings"]) == 12
    path = MANIFEST.with_name("results-scenarios.json" if options.scenarios_only else
                              "results-matrix.json")
    path.write_text(json.dumps(result, indent=2) + "\n")
    print("Comparative results:", path, flush=True)


if __name__ == "__main__":
    main()
