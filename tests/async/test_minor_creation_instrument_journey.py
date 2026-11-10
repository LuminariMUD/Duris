#!/usr/bin/env python3
"""Real mortal Minor Creation -> pickup -> belt commands on disposable MariaDB."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

import test_mariadb_combat_journey as journey
from test_shambler_reflection_journey import PROMPTS, cast, command, staff_command
from test_flight_network_journey import command as fenced_command

ROOT = journey.ROOT
NAME = "Lyricist"
INSTRUMENTS = (("lyre", 1241), ("horn", 1242), ("drum", 1243),
               ("mandolin", 1244), ("harp", 1245), ("flute", 1246))
REPORT = ROOT / "bin/qualification/issue453/gameplay-report.json"

HEADER = (ROOT / "src/magic/spells.h").read_text()


def spell_id(name):
    expression = re.search(r"^#define " + name + r" ([^\n]+)", HEADER, re.M)[1]
    expression = re.sub(r"\b[A-Z_][A-Z_0-9]*\b", lambda match: str(spell_id(match[0])), expression)
    assert re.fullmatch(r"[0-9()+ ]+", expression), (name, expression)
    return int(eval(expression, {"__builtins__": {}}, {}))


def seed_bard(sql):
    """A level-51 Bard with Minor Creation fully memorized, in the arena."""
    memorize, spell = spell_id("TAG_MEMORIZE"), spell_id("SPELL_MINOR_CREATION")
    sql(f"UPDATE player_data SET m_class={1 << 15},secondary_class=0,spec=2,level=51,highest_level=51,"
        f"played_time=200000,base_hit=10000,hit_diff=0,base_mana=1000,mana=1000,screen_length=100,"
        f"last_room=22800 WHERE name='{NAME}'")
    pid = sql(f"SELECT pid FROM player_data WHERE name='{NAME}'")
    sql(f"DELETE FROM player_skills WHERE pid={pid}; DELETE FROM player_affects WHERE pid={pid};"
        f"INSERT INTO player_skills(pid,skill_id,learned,taught) VALUES({pid},{spell},100,100);"
        + f"INSERT INTO player_affects(pid,type,duration,flags,modifier,level) VALUES({pid},{memorize},-1,16,{spell},51);" * 20)
    for key in ("INSTRUMENT_FLUTE", "INSTRUMENT_DRUMS", "SONG_HEROISM", "SONG_HARMONY"):
        skill = spell_id(key)
        sql(f"REPLACE INTO player_skills(pid,skill_id,learned,taught) VALUES({pid},{skill},100,100)")
    sql(f"REPLACE INTO player_skills(pid,skill_id,learned,taught) "
        f"VALUES({pid},{spell_id('SKILL_HIDE')},90,90)")


def configure(runtime):
    journey.make_fixture(runtime)
    journey.generate_certificate(runtime)
    (runtime / "logs/log").mkdir(parents=True)
    (runtime / "logs/log/.since").touch()
    (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
    mini = runtime / "areas_mini"
    path = mini / "mini.obj"
    control = re.search(r"(?ms)^#89177\n.*?(?=^#\d+\n)",
                        (ROOT / "areas/obj/newhope.obj").read_text())[0]
    records = re.findall(r"(?ms)^#\d+\n.*?(?=^#\d+\n|^\$~)", path.read_text())
    records.append(control)
    records.sort(key=lambda record: int(record.splitlines()[0][1:]))
    path.write_text("".join(records) + "$~\n")
    zone = mini / "mini.zon"
    body = re.sub(r"^[MGE] .*\n", "", zone.read_text(), flags=re.M)
    zone.write_text(body.replace("\nS\n", "\nO 0 732 1 22800 100 0 0 0\nS\n"))


def inspect(staff, keyword, vnum, location):
    _, text = command(staff, f"stat obj {keyword}", "Object:")
    assert re.search(rf"Number:\s*\[{vnum}\]", text), text
    assert re.search(r"Type:\s*INSTRUMENT", text, re.I), text
    line = re.search(r"Location:\s*([^\r\n]+)", text)[1]
    assert location in line, text
    return text


def equipment(player):
    return command(player, "equipment", ("You are using", "You aren't wearing"))[1]


def run(binary):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.unlink(missing_ok=True)
    result = {"binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "instruments": []}
    with tempfile.TemporaryDirectory(prefix="minor-creation-journey-", dir=ROOT / "bin/tests") as temporary, \
            journey.mariadb_authority() as (authority, sql):
        root = Path(temporary)
        runtime = root / "runtime"
        runtime.mkdir()
        configure(runtime)
        (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
        port, tls, websocket = journey.available_ports()
        environment = {
            **authority,
            "CRITICAL_COMMAND_JOURNAL_DIR": str(runtime / "journals/critical"),
            "DURIS_TLS_PORT": str(tls), "DURIS_WEBSOCKET_PORT": str(websocket),
        }
        output_path = runtime / "server.out"
        process = log_stream = staff = player = None

        def stop():
            nonlocal process, log_stream, staff
            if staff:
                staff.close()
                staff = None
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if log_stream:
                log_stream.close()

        def start():
            nonlocal process, log_stream
            log_stream = output_path.open("w")
            process = subprocess.Popen(
                [str(binary), "--minimal", "-s", "-d", str(runtime), str(port)],
                cwd=runtime, env=environment, stdout=log_stream, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 90
            while "Entering game loop." not in output_path.read_text(errors="replace"):
                assert process.poll() is None and time.monotonic() < deadline, output_path.read_text()[-6000:]
                time.sleep(.1)

        try:
            start()
            for name in (journey.CHARACTER, NAME):
                print(f"Creating disposable character: {name}", flush=True)
                player = journey.MudClient(port)
                journey.create_character(player, account=name, character=name,
                                         email=f"{name.lower()}@example.invalid")
                command(player, "save", f"Saving {name}.")
                player.send("quit")
                player.expect("ACCOUNT MENU", timeout=30)
                player.close()
                player = None
            stop()
            journey.make_overlord(sql, journey.CHARACTER)
            seed_bard(sql)
            start()
            staff = journey.reconnect_character(port, account=journey.CHARACTER)
            staff.expect_any(PROMPTS)
            staff_command(staff, "vis 0")
            player = journey.reconnect_character(port, account=NAME, character=NAME)
            player.expect_any(PROMPTS)
            _, character = command(staff, f"stat char {NAME}", "ID numb:")
            assert re.search(r"Level:\s*51\(", character), character
            assert re.search(r"Class:\s*Bard\b", character, re.I), character
            command(player, "remove all", ("You stop using", "You are quite naked at the moment."))
            command(player, "get sash", "You get")
            command(player, "wear sash waist", "You clasp")
            for name, vnum in INSTRUMENTS:
                print(f"Minor Creation: {name} #{vnum}", flush=True)
                output = cast(player, "minor creation", name)
                assert "suddenly appears" in output, output
                text = inspect(staff, name, vnum, "22800")
                assert "carried by" not in text and "equipped by" not in text, text
                assert "NOSELL" in text and "STOREITEM" in text, text
                command(player, f"get {name}", "You get")
                inspect(staff, name, vnum, f"carried by {NAME}")
                command(player, f"wear {name} attach", ("You attach", "You can't", "You need"))
                inspect(staff, name, vnum, f"equipped by {NAME}")
                eq = equipment(player)
                assert re.search(rf"<worn on belt buckle>\s*.*\b{name}\b", eq), eq
                command(player, f"remove {name}", "You stop using")
                inspect(staff, name, vnum, f"carried by {NAME}")
                result["instruments"].append({"keyword": name, "vnum": vnum, "slot": 28})

            # The same real objects fill all three slots; a fourth stays carried.
            for name, vnum in INSTRUMENTS[:3]:
                command(player, f"wear {name} attach", "You attach")
                inspect(staff, name, vnum, f"equipped by {NAME}")
            eq = equipment(player)
            assert eq.count("<attached to belt>") == 2 and eq.count("<worn on belt buckle>") == 1, eq
            # A held flute no longer masks drums in the third belt slot.
            command(player, "hold flute", "You hold")
            for song in ("harmony", "heroism"):
                _, text = command(player, "play " + song, "You start playing")
                assert "won't work" not in text and "how did the song go" not in text, text
            def hidden():
                _, text = command(staff, f"stat char {NAME}", "ID numb:")
                flags = re.search(r"Affected by \(1\):\s*(\d+)", text)
                return bool(flags and int(flags[1]) & (1 << 20))
            for _ in range(10):
                command(player, "hide", "You attempt to hide yourself.")
                if hidden():
                    break
            assert hidden(), "Scoundrel failed to hide in ten attempts"
            command(player, "wail harmony", "You start playing")
            assert hidden(), "a singing Scoundrel's song switch revealed Hide"
            command(player, "play nonexistent", "You don't know that song.")
            assert not hidden(), "an invalid switch that stops singing must reveal Hide"
            command(player, "play harmony", "You start playing")
            for _ in range(10):
                command(player, "hide", "You attempt to hide yourself.")
                if hidden():
                    break
            assert hidden(), "Scoundrel failed to re-hide"
            command(player, "play", "You stop your song.")
            assert not hidden(), "stopping a song should reveal Hide"
            command(player, "remove flute", "You stop using")
            # The group path has no consent link, and the target does not act
            # before staff observes the actual Hide flag and Rope Trick affect.
            fenced_command(player, "follow " + journey.CHARACTER)
            staff_command(staff, "group " + NAME)
            cast(staff, "rope trick", NAME)
            assert hidden(), "grouped Rope Trick did not hide the nonconsenting target"
            _, text = command(staff, f"stat char {NAME}", "ID numb:")
            assert "rope trick" in text.lower(), text
            result["bard_utility"] = "matching belt/held instruments, hidden switch/stop, grouped Rope Trick"
            print("PASS: matching equipped instruments, Scoundrel hidden switch/stop, grouped Rope Trick", flush=True)
            command(player, "wear mandolin attach", "Your belt is full.")
            inspect(staff, "mandolin", 1244, f"carried by {NAME}")
            # Removing the waist item also returns all three attachments.
            command(player, "remove sash", "You stop using")
            for name, vnum in INSTRUMENTS:
                inspect(staff, name, vnum, f"carried by {NAME}")
            command(player, "wear harp attach", "You need a belt")
            inspect(staff, "harp", 1245, f"carried by {NAME}")
            command(player, "hold harp", "You hold")
            eq = equipment(player)
            assert re.search(r"<held>\s+.*\bharp\b", eq), eq
            command(player, "remove harp", "You stop using")
            command(player, "wear sash waist", "You clasp")
            # Load the control after the six cases so its shared "flute" keyword
            # cannot redirect staff's room-first lookup during those inspections.
            for name, _ in INSTRUMENTS:
                command(player, f"drop {name}", "You drop")
            staff_command(staff, "load obj 89177")
            staff_command(staff, f"give copper {NAME}")
            text = inspect(staff, "copper", 89177, f"carried by {NAME}")
            assert "ATTACH_BELT" not in text, text
            command(player, "wear copper attach", "You attach")
            inspect(staff, "copper", 89177, f"equipped by {NAME}")
            command(player, "remove copper", "You stop using")
            command(player, "wear copper", "You attach")
            inspect(staff, "copper", 89177, f"equipped by {NAME}")
            command(player, "remove copper", "You stop using")
            command(player, "wear all", "You attach")
            inspect(staff, "copper", 89177, f"equipped by {NAME}")
            command(player, "remove copper", "You stop using")
            command(player, "save", f"Saving {NAME}.")
            player.send("quit")
            player.expect("ACCOUNT MENU", timeout=30)
            player.close()
            player = journey.reconnect_character(port, account=NAME, character=NAME)
            player.expect_any(PROMPTS)
            text = inspect(staff, "copper", 89177, f"carried by {NAME}")
            assert "ATTACH_BELT" not in text, text
            command(player, "wear copper attach", "You attach")
            inspect(staff, "copper", 89177, f"equipped by {NAME}")
            command(player, "remove sash", "You stop using")
            command(player, "wear sash attach", "You can't attach that to your belt.")
            stop()
            assert process.returncode == 0, f"server shutdown failed: {process.returncode}"
            logs = output_path.read_text(errors="replace") + journey.runtime_logs(runtime)
            assert not any(marker in logs for marker in ("FATAL:", "assert:", "AddressSanitizer", "runtime error:")), logs[-6000:]
            result["controls"] = ["three slots", "full belt preserves inventory",
                                  "waist removal returns attachments", "belt required",
                                  "hold/remove", "unflagged instrument attaches",
                                  "automatic wear", "wear all", "saved unflagged instrument attaches",
                                  "unflagged non-instrument refuses"]
            REPORT.write_text(json.dumps(result, indent=2) + "\n")
            print("PASS: all six real mortal casts, room creation, pickup, attachment, flags, "
                  "three-slot/full/no-belt controls, hold/remove, unflagged instruments, "
                  "automatic wear, save/reload and non-instrument refusal.", flush=True)
        except Exception:
            for client in (player, staff):
                if client:
                    print(bytes(client.transcript).decode(errors="replace").replace(
                        journey.PASSWORD, "[REDACTED]")[-4500:])
            print(output_path.read_text(errors="replace")[-4000:])
            raise
        finally:
            if player:
                player.close()
            stop()


if __name__ == "__main__":
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    run(parser.parse_args().server.resolve())
