#!/usr/bin/env python3
"""Compare Paladin balance through disposable servers and normal combat dispatch.

An authored Studio mob supplies fixed spell damage. Staff fixture commands set
initial HP, groups and affects; the server's damage, vamp and group code award HP.
Run once per baseline/revised binary; no production data or listeners are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import tempfile
import time
from pathlib import Path

import test_flatfile_combat_journey as journey
from run_divine_refusal_journey import drain
from run_item_pilot_journey import Server

ROOT = journey.ROOT
MATES = ("Matealpha", "Matebravo", "Matecharlie", "Matedelta", "Mateecho")
MOB = """#22805
balance sentinel~
a balance sentinel~
A balance sentinel waits for a controlled combat comparison.
~
~
10 0 0 0 0 0 0 0 S
PH 0 1 -1
50 0 0 200d1+20000 1d1+1
0.0.0.0 0
8 8 0
"""


def configure(root: Path, baseline: bool) -> None:
    (root / "logs/log").mkdir(parents=True)
    journey.make_fixture(root)
    journey.generate_certificate(root)
    if baseline:
        properties = root / "lib/duris.properties"
        properties.write_text(properties.read_text().replace(
            "vamping.maxHP.bonus.antipaladin=0.250",
            "vamping.maxHP.bonus.antipaladin=1.000"))
    mini = root / "areas_mini"
    mobiles = (mini / "mini.mob").read_text()
    (mini / "mini.mob").write_text(mobiles.replace("$~", MOB + "$~"))
    zone = re.sub(r"^[MGE] .*\n", "", (mini / "mini.zon").read_text(), flags=re.M)
    (mini / "mini.zon").write_text(zone)
    (root / "areas").unlink()  # replace only the temporary fixture's symlink
    (root / "areas").mkdir()
    generated = {"world.wld", "world.mob", "world.obj", "world.zon", "world.trg",
                 "world.shp", "world.qst", "world.tab", "world.weather"}
    for path in (ROOT / "areas").iterdir():
        if path.name not in generated:
            (root / "areas" / path.name).symlink_to(path, target_is_directory=path.is_dir())
    for suffix in ("wld", "mob", "obj", "zon"):
        (root / f"areas/world.{suffix}").write_text((mini / f"mini.{suffix}").read_text())
    for name in ("world.shp", "world.qst", "world.tab", "world.weather"):
        path = mini / name
        (root / "areas" / name).write_text(path.read_text() if path.exists() else "$~\n")
    (root / "areas/world.trg").write_text(
        '#22805 M\nT CMD say balancestrike\n'
        'attack 1d1+3999 type generic hit "BALANCE_STRIKE"\nblock\n~\n'
        "T CMD say battleon\naffect 'aura of battlelust' 100 on self apply NONE 56 aff PAL_AURA\n"
        "echo BATTLE_READY\nblock\n~\n"
        "T CMD say titheon\naffect 'blood tithe' 100 on actor apply NONE 999999\n"
        "echo TITHE_READY\nblock\n~\n"
        "T CMD say sacrificeon\naffect 'holy sacrifice' 100 on actor aff HOLY_SACR\n"
        "echo SACRIFICE_READY\nblock\n~\n"
        "T CMD say ecstasyon\nunaffect 'holy sacrifice' on actor\n"
        "affect 'battle ecstasy' 100 on actor aff BATTLE_ECS\n"
        "echo ECSTASY_READY\nblock\n~\n"
        "T CMD say vampireon\naffect 'vampiric touch' 100 on actor aff VAMP_TOUCH\n"
        "echo VAMP_READY\nblock\n~\nS\n#~\n"
    )


def command(client: journey.MudClient, text: str) -> str:
    drain(client, 0.05)
    client.send(text)
    parts = []
    while True:
        match, output = client.expect_any(("Return to continue", "< (news)>", "<>"), timeout=20)
        parts.append(output)
        if match != "Return to continue":
            return "".join(parts) + drain(client, 0.05)
        client.send("")


def hp(staff: journey.MudClient, name: str) -> tuple[int, int]:
    text = command(staff, f"stat char {name}")
    match = re.search(r"Hits:\s*\[\s*(-?\d+)\s*/\s*(\d+)", text)
    assert match, text
    return int(match[1]), int(match[2])


def run(binary: Path, baseline: bool) -> dict:
    with tempfile.TemporaryDirectory(prefix="duris-paladin-balance-") as temporary:
        root = Path(temporary)
        runtime, state = root / "runtime", root / "state"
        runtime.mkdir()
        state.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        configure(runtime, baseline)
        subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)
        server = Server(binary, runtime, state, "paladin")
        clients: list[journey.MudClient] = []
        result = {"baseline": baseline,
                  "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
        try:
            server.start()
            staff = journey.MudClient(server.port)
            server.client = staff
            journey.create_character(staff)
            staff.send("save")
            staff.expect("Save complete for Taverek.")
            staff.send("quit")
            staff.expect("ACCOUNT MENU")
            server.stop()
            journey.make_overlord(state, journey.CHARACTER)
            server.start()
            staff = server.client = journey.reconnect_character(server.port)
            command(staff, "vis 0")
            command(staff, "toggle page off")
            command(staff, "toggle damage")
            owner = journey.MudClient(server.port, source_host="127.0.0.2")
            clients.append(owner)
            journey.create_character(owner, account="Sacwarden", character="Sacwarden",
                                     email="sacrifice@example.invalid")
            mates = []
            for index, name in enumerate(MATES):
                client = journey.MudClient(server.port, source_host=f"127.0.0.{index+3}")
                clients.append(client)
                mates.append(client)
                journey.create_character(client, account=name, character=name,
                                         email=f"{name.lower()}@example.invalid")
            for name, client in [("Sacwarden", owner), *zip(MATES, mates)]:
                command(client, "toggle boon")
                command(client, f"consent {journey.CHARACTER}")
                grouped = command(staff, f"group {name}")
                assert "member of your group" in grouped, grouped
                command(staff, f"setbit char {name} basehit 10000")
                command(client, "toggle heal")
            result["owner_max_hp"] = hp(staff, "Sacwarden")[1]
            print("Fixture ready", result["owner_max_hp"], flush=True)
            rows = []
            for pet in (False, True):
                if pet:
                    command(staff, "purge sentinel")
                    text = command(staff, f"givepet {journey.CHARACTER} 22805")
                else:
                    text = command(staff, "load mob 22805")
                assert "No such" not in text, text
                for name in ("Sacwarden", *MATES):
                    command(staff, f"setbit char {name} hit {10000 if name == 'Sacwarden' else 100}")
                owner.send("say sacrificeon")
                owner.expect("SACRIFICE_READY", timeout=20)
                drain(owner)
                time.sleep(4.1)
                for client in [staff, owner, *mates]:
                    drain(client, 0.05)
                before = len(staff.transcript)
                mate_offsets = [len(client.transcript) for client in mates]
                owner.send("say balancestrike")
                owner.expect("BALANCE_STRIKE", timeout=20)
                for client in [staff, owner, *mates]:
                    drain(client, 0.15)
                output = bytes(staff.transcript[before:]).decode(errors="replace")
                damages = [int(value) for value in re.findall(r"\[Damage:\s*(\d+)", output)]
                awards = []
                for client, offset in zip(mates, mate_offsets):
                    output = bytes(client.transcript[offset:]).decode(errors="replace")
                    healing = [int(value) for value in re.findall(r"\[Heal:\s*(\d+)", output)]
                    # The fixed Studio strike is the first event. Normal combat
                    # can start afterward; do not combine those later hits.
                    awards.append(healing[0] if healing else 0)
                assert damages and damages[0] == 1000, damages
                damage = damages[0]
                expected = int(damage * 0.3) * len(mates) if baseline else round(
                    damage * (0.45 if pet else 0.9))
                assert sum(awards) == expected, (pet, damage, awards, expected)
                rows.append({"player_owned_pet": pet, "damage": damage,
                             "awards": awards, "total_healing": sum(awards)})
                print("PASS Holy Sacrifice gameplay:", rows[-1], flush=True)

            result["holy_sacrifice"] = rows

            # A staff-controlled grouped pet supplies fixed spell damage through
            # the real modifier pipeline. Full Tithe charge is a fixture affect;
            # run_blood_tithe_journey separately tests actual charging and decay.
            command(staff, "purge sentinel")
            command(staff, "setbit char Sacwarden class Anti-Paladin")
            command(staff, "setbit char Sacwarden level 56")
            enemy = mates[-1]
            command(staff, "group Mateecho")
            offense = []
            for tithe in (False, True):
                command(staff, f"givepet {journey.CHARACTER} 22805")
                command(staff, "setbit char Sacwarden hit 100")
                command(staff, "setbit char Mateecho hit 10000")
                owner.send("say ecstasyon")
                owner.expect("ECSTASY_READY", timeout=20)
                drain(owner)
                enemy.send("say battleon")
                enemy.expect("BATTLE_READY", timeout=20)
                drain(enemy)
                if tithe:
                    owner.send("say titheon")
                    owner.expect("TITHE_READY", timeout=20)
                    drain(owner)
                staff.send("switch sentinel")
                staff.expect("Ok.", timeout=20)
                drain(staff)
                for client in (staff, owner, enemy):
                    drain(client, 0.1)
                before_damage, before_heal = len(staff.transcript), len(owner.transcript)
                enemy.send("say balancestrike")
                enemy.expect("BALANCE_STRIKE", timeout=20)
                for client in (staff, owner, enemy):
                    drain(client, 0.2)
                damage_text = bytes(staff.transcript[before_damage:]).decode(errors="replace")
                healing_text = bytes(owner.transcript[before_heal:]).decode(errors="replace")
                damage = [int(x) for x in re.findall(r"\[Damage:\s*(\d+)", damage_text)]
                healing = [int(x) for x in re.findall(r"\[Heal:\s*(\d+)", healing_text)]
                assert damage and healing, (damage, healing, damage_text, healing_text)
                assert healing[0] == int(damage[0] * 0.4), (damage, healing)
                offense.append({"tithe": tithe, "damage": damage[0],
                                "battle_ecstasy_healing": healing[0]})
                staff.send("return")
                staff.expect("You return to your original body.", timeout=20)
                command(staff, "purge sentinel")
                print("PASS Tithe/Battlelust/Battle Ecstasy gameplay:", offense[-1], flush=True)
            expected_factor = 1 if baseline else 1 + 0.12 * math.sqrt(3 / 5) * 0.5
            assert abs(offense[1]["damage"] - offense[0]["damage"] * expected_factor) <= 1, offense
            result["offensive_stack_pvp"] = offense

            # Ordinary prime Anti-Paladin unarmed attacks exercise the real 70%
            # touch conversion and ceiling. No staff immunity applies to this PC.
            fighter = mates[0]
            # Preserve zero missing HP while changing the fixture's maximum.
            command(staff, f"setbit char Matealpha hit {hp(staff, 'Matealpha')[1]}")
            for field, value in (("race", "Orc"), ("class", "Anti-Paladin"), ("level", 56), ("align", -1000), ("pow", 300),
                                 ("str", 250), ("dex", 250), ("hitrol", 75),
                                 ("damrol", 50), ("con", 100), ("basehit", 1500)):
                command(staff, f"setbit char Matealpha {field} {value}")
            command(fighter, "toggle damage")
            command(fighter, "remove all")
            stats = command(staff, "stat char Matealpha")
            assert "VAMP_TOUCH" in stats
            power_match = re.search(r"Pow:\s*(\d+)", stats)
            assert power_match, stats
            power = int(power_match[1])  # effective stats, after the engine's racial caps
            maximum = hp(staff, "Matealpha")[1]
            base_cap = min(2.5, max(1.1, power / 90))
            multiplier = base_cap + 1 if baseline else min(2.5, base_cap + 0.25)
            cap = int(maximum * multiplier)
            touch = []
            for kind in ("innate", "consumable_spell", "ceiling"):
                near_cap = kind == "ceiling"
                command(staff, "load mob 22805")
                command(staff, "setbit char sentinel level 1")
                command(staff, "setbit char sentinel basehit 200000")
                command(staff, "setbit char sentinel hit 200000")
                command(staff, "setbit char sentinel savthr '127 127 127 127 127'")
                # Innate touch uses damage conversion; the consumable spell has
                # its own to-hit-based drain. Exercise both without conflating rates.
                if kind != "innate":
                    fighter.send("say vampireon")
                    fighter.expect("VAMP_READY", timeout=20)
                drain(fighter)
                command(staff, f"setbit char Matealpha hit {cap - 3 if near_cap else 100}")
                offset = len(fighter.transcript)
                fighter.send("kill sentinel")
                if kind != "innate":
                    fighter.expect("draining its life force.", timeout=30)
                    # Ignore any ordinary swings before the target fails its save.
                    offset = bytes(fighter.transcript).rfind(b"draining its life force.")
                fighter.expect("[Heal:", timeout=30)
                drain(fighter, 0.15)
                command(staff, "purge sentinel")
                output = bytes(fighter.transcript[offset:]).decode(errors="replace")
                damages = [int(x) for x in re.findall(r"\[Damage:\s*(\d+)", output)]
                awards = [int(x) for x in re.findall(r"\[Heal:\s*(\d+)", output)]
                assert damages and awards, output
                if kind == "innate":
                    assert abs(awards[0] - damages[0] * 0.7) <= 1, (damages, awards)
                current, observed_max = hp(staff, "Matealpha")
                assert observed_max == maximum
                if near_cap:
                    assert awards[0] < touch[1]["healing"], (touch, awards)
                    assert cap - 30 <= current <= cap, (cap, current, output)
                touch.append({"kind": kind, "damage": damages[0],
                              "healing": awards[0], "hp_after": current})
            result["vampiric_touch"] = {"max_hp": maximum, "effective_power": power, "ceiling": cap, "attacks": touch}
            print("PASS Vampiric Touch gameplay:", result["vampiric_touch"], flush=True)

            # Lowering the vamp ceiling does not truncate existing online HP.
            # Login recovery has always normalized to normal max HP; preserve it.
            command(staff, f"setbit char Matealpha hit {cap + 500}")
            before_decay = hp(staff, "Matealpha")[0]
            time.sleep(5)
            after_decay = hp(staff, "Matealpha")[0]
            assert cap < after_decay < before_decay <= cap + 500
            fighter.send("save")
            fighter.expect("Save complete for Matealpha.", timeout=30)
            fighter.send("quit")
            fighter.expect("ACCOUNT MENU", timeout=30)
            for client in clients:
                client.close()
            clients.clear()
            server.stop()
            server.start()
            staff = server.client = journey.reconnect_character(server.port)
            fighter = journey.reconnect_character(server.port, account="Matealpha",
                                                  character="Matealpha", source_host="127.0.0.3")
            clients.append(fighter)
            restored, restored_max = hp(staff, "Matealpha")
            assert 0 < restored == restored_max, (restored, restored_max)
            result["overcap_reload"] = {"online_before": before_decay, "online_after_five_seconds": after_decay,
                                       "restored": restored, "restored_max_hp": restored_max}
            print("PASS online over-cap decay and existing login normalization:",
                  result["overcap_reload"], flush=True)

            return result
        except Exception:
            print(server.output_path.read_text(errors="replace")[-5000:])
            print(journey.runtime_logs(runtime)[-5000:])
            for client in [server.client, *clients]:
                if client:
                    print(bytes(client.transcript).decode(errors="replace")
                          .replace(journey.PASSWORD, "[REDACTED]")[-4000:])
            raise
        finally:
            for client in clients:
                client.close()
            server.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not journey.INSPECTOR.is_file():
        journey.INSPECTOR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                        "--build-inspector", str(journey.INSPECTOR)],
                       cwd=ROOT, check=True, timeout=180)
    result = run(args.binary.resolve(), args.baseline)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
