#!/usr/bin/env python3
"""Turn in Kjelgar's authored recipe through a disposable local flat-file server."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

import test_flatfile_combat_journey as journey
from run_item_pilot_journey import Server
from run_weapon_actions_journey import drain


ROOT = journey.ROOT
ACCOUNT = "Crystalacct"
CHARACTER = "Kyralin"


def record(path, vnum):
    match = re.search(rf"^#{vnum}\n.*?(?=^#|^\$|\Z)", path.read_text(), re.MULTILINE | re.DOTALL)
    assert match, (path, vnum)
    return match[0]


def configure(runtime, baseline):
    journey.make_fixture(runtime)
    journey.generate_certificate(runtime)
    (runtime / "logs/log").mkdir(parents=True)
    (runtime / "logs/log/.since").touch()
    (runtime / "areas").unlink()
    (runtime / "areas").mkdir()
    generated = {f"world.{suffix}" for suffix in
                 ("wld", "mob", "obj", "zon", "trg", "shp", "qst", "tab", "weather")}
    for path in (ROOT / "areas").iterdir():
        if path.name not in generated:
            (runtime / "areas" / path.name).symlink_to(path, target_is_directory=path.is_dir())
    for suffix in ("wld", "mob", "obj", "zon"):
        shutil.copyfile(runtime / f"areas_mini/mini.{suffix}", runtime / f"areas/world.{suffix}")
    for suffix in ("shp", "tab", "weather"):
        source = runtime / f"areas_mini/world.{suffix}"
        (runtime / f"areas/world.{suffix}").write_text(source.read_text() if source.exists() else "$~\n")
    (runtime / "areas/world.trg").write_text("#~\n")

    mobiles = runtime / "areas/world.mob"
    mobiles.write_text(mobiles.read_text().replace(
        "$~", record(ROOT / "areas/mob/vehicles.mob", 47124) + "$~"))
    objects = runtime / "areas/world.obj"
    additions = "".join(record(ROOT / f"areas/obj/{name}.obj", vnum) for name, vnum in
                        (("vehicles", 47096), ("wh", 55033), ("tradeskills", 400094)))
    objects.write_text(objects.read_text().replace("$~", additions + "$~"))
    # Remove the borrowed combat resets; Kjelgar is loaded by the fixture staff.
    zone = runtime / "areas/world.zon"
    zone.write_text(re.sub(r"^[MGE] .*\n", "", zone.read_text(), flags=re.MULTILINE))
    for suffix in ("mob", "obj", "zon"):
        shutil.copyfile(runtime / f"areas/world.{suffix}", runtime / f"areas_mini/mini.{suffix}")
    quest = record(ROOT / "areas/qst/vehicles.qst", 47124)
    if baseline:
        assert quest.count("G I 400094\n") == 5
        quest = quest.replace("G I 400094\n", "G I 400941\n")
    (runtime / "areas/world.qst").write_text(quest + "$~\n")


def command(client, text):
    drain(client, 0.05)
    client.send(text)
    _, output = client.expect_any(("Pos: standing >", "< (news)>", "<>"), timeout=30)
    return output + drain(client, 0.05)


def run(binary, baseline):
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kjelgar-turn-in-", dir=ROOT / "bin/tests") as directory:
        runtime, state = Path(directory) / "runtime", Path(directory) / "state"
        runtime.mkdir()
        state.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        configure(runtime, baseline)
        server = Server(binary, runtime, state, "kjelgar")
        player = None
        result = {"baseline": baseline, "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                  "checks": []}
        try:
            server.start()
            staff = server.client = journey.MudClient(server.port)
            journey.create_character(staff)
            staff.send("save")
            staff.expect(f"Save complete for {journey.CHARACTER}.")
            server.stop()
            journey.make_overlord(state, journey.CHARACTER)
            server.start()
            staff = server.client = journey.reconnect_character(server.port)
            command(staff, "vis 0")
            loaded = command(staff, "load mob 47124")
            assert "created" in loaded, loaded

            player = journey.MudClient(server.port)
            journey.create_character(player, account=ACCOUNT, character=CHARACTER,
                                     email="crystal@example.invalid")
            command(player, "drop all")
            greeting = command(player, "ask kjelgar hello")
            assert "moonstone" in greeting and "100 platinum" in greeting, greeting
            command(staff, f"setbit char {CHARACTER} platinum 100")
            for vnum, keyword, count in ((400094, "crystal", 5), (55033, "token", 2)):
                for _ in range(count):
                    loaded = command(staff, f"load obj {vnum}")
                    assert "created" in loaded, loaded
                    command(staff, f"give {keyword} {CHARACTER}")
            inventory = command(player, "inventory")
            assert "moonstone" in inventory and "shopkeepers token" in inventory, inventory
            # Pay first, then hand over items through ordinary mortal commands.
            payment = command(player, "give 100 platinum kjelgar")
            assert "Ok." in payment, payment
            for _ in range(4):
                command(player, "give crystal kjelgar")
            command(player, "give token kjelgar")
            assert "Vokstron" not in command(player, "inventory")
            result["checks"].append("four crystals, one token and full payment grant no harp")
            command(player, "give crystal kjelgar")
            assert "Vokstron" not in command(player, "inventory")
            result["checks"].append("five crystals and one token grant no harp")
            completion = command(player, "give token kjelgar")
            inventory = command(player, "inventory")
            result["turn_in_output"] = completion
            result["inventory"] = inventory
            if baseline:
                assert "completes a" not in completion and "Vokstron" not in inventory
                result["checks"].append("original 400941 recipe fails with all advertised ingredients")
                return result
            assert "completes a harp" in completion and "Vokstron" in completion, completion
            assert inventory.count("Vokstron") == 1, inventory
            assert "moonstone" not in inventory and "shopkeepers token" not in inventory, inventory
            result["checks"].append("mortal turn-in grants exactly one Vokstron harp")
            wallet = command(player, "score")
            result["score"] = wallet
            coins = re.search(r"Coins carried:\s*(\d+) platinum\s*(\d+) gold\s*(\d+) silver\s*(\d+) copper", wallet)
            assert coins and tuple(map(int, coins.groups())) == (0, 0, 0, 0), wallet
            result["checks"].append("the mortal pays exactly 100 platinum")
            player.send("save")
            player.expect(f"Save complete for {CHARACTER}.")
            player.send("quit")
            player.expect("ACCOUNT MENU", timeout=45)
            player.close()
            player = None
            server.stop()
            server.start()
            player = journey.reconnect_character(server.port, account=ACCOUNT, character=CHARACTER)
            inventory = command(player, "inventory")
            assert inventory.count("Vokstron") == 1, inventory
            result["checks"].append("harp survives save, server restart and mortal reconnect")
            return result
        except Exception as error:
            raise AssertionError(f"{error}\n{server.output_path.read_text(errors='replace')[-5000:]}\n"
                                 f"{journey.runtime_logs(runtime)}") from error
        finally:
            if player:
                player.close()
            server.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.binary.resolve(), args.baseline)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
