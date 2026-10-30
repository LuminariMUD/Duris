#!/usr/bin/env python3
"""Real mortal Minor Creation -> pickup -> belt commands in disposable state."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_shambler_reflection_journey import PROMPTS, cast, command, staff_command

ROOT = journey.ROOT
NAME = "Lyricist"
INSTRUMENTS = (("lyre", 1241), ("horn", 1242), ("drum", 1243),
               ("mandolin", 1244), ("harp", 1245), ("flute", 1246))
REPORT = ROOT / "bin/qualification/issue453/gameplay-report.json"

FIXTURE = r'''
#include "flatfile/flatfile_player_snapshot_file.h"
#include "flatfile/flatfile_store.h"
#include "core/structs.h"
#include "magic/spells.h"
#include <cassert>
#include <string>
#include <vector>

int main(int argc, char **argv) {
    assert(argc == 2);
    const std::string root = argv[1];
    for (int pid = 1; pid <= 64; ++pid) {
        player_snapshot s; std::string error;
        if (flatfile_player_snapshot_read(root, pid, &s, &error) != flatfile_player_load_result::ok)
            continue;
        bool named = false;
        for (const auto &field : s.status_strings)
            named |= field.field == player_status_string_field::name && field.value == "Lyricist";
        if (!named) continue;
        auto set = [&](player_status_field key, int value) {
            for (auto &field : s.status_integers)
                if (field.field == key) {
                    field.signed_value = field.unsigned_value = value;
                    return;
                }
            assert(false);
        };
        set(player_status_field::class_primary, CLASS_BARD);
        set(player_status_field::class_secondary, 0);
        set(player_status_field::specialization, 0);
        set(player_status_field::level, 51);
        set(player_status_field::highest_level, 51);
        set(player_status_field::played_time, 200000);
        set(player_status_field::base_hit, 10000);
        set(player_status_field::hit_difference, 0);
        set(player_status_field::base_mana, 1000);
        set(player_status_field::mana, 1000);
        set(player_status_field::screen_length, 100);
        s.room_vnum = 22800;
        s.affects.clear();
        s.skills = {{SPELL_MINOR_CREATION, 100, 100}};
        for (int copy = 0; copy < 20; ++copy) {
            player_affect_snapshot af{};
            af.type = TAG_MEMORIZE; af.modifier = SPELL_MINOR_CREATION; af.duration = -1;
            af.flags = MEMTYPE_FULL; af.level = 51;
            s.affects.push_back(af);
        }
        s.encoded_size_bound = PLAYER_SNAPSHOT_MAX_BYTES;
        std::vector<uint8_t> bytes;
        assert(flatfile_player_snapshot_encode_file(&s, &bytes));
        using namespace flatfile_player_snapshot_file;
        assert(flatfile_atomic_write(player_directory(root), player_filename(pid), bytes, &error));
        return 0;
    }
    assert(false);
}
'''


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
    with tempfile.TemporaryDirectory(prefix="minor-creation-journey-", dir=ROOT / "bin/tests") as temporary:
        root = Path(temporary)
        runtime, state = root / "runtime", root / "state"
        runtime.mkdir()
        state.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        configure(runtime)
        inspector = root / "inspector"
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                        "--build-inspector", str(inspector)], cwd=ROOT, check=True)
        subprocess.run([str(inspector), str(state), "seed-combat"], check=True)
        cpp, fixture = root / "fixture.cpp", root / "fixture"
        cpp.write_text(FIXTURE)
        subprocess.run(["g++", "-std=c++20", "-Isrc", str(cpp),
                        "src/player/player_snapshot_codec.c",
                        "src/flatfile/flatfile_player_snapshot_file.c",
                        "src/flatfile/flatfile_store.c", "-lcrypto", "-o", str(fixture)],
                       cwd=ROOT, check=True)
        (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
        port, tls, websocket = journey.available_ports()
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "ENVIRONMENT": "local",
            "PERSISTENCE_MODE": "flatfile-primary", "FLATFILE_STATE_DIR": str(state),
            "CRITICAL_COMMAND_JOURNAL_DIR": str(runtime / "journals/critical"),
            "LISTEN_ADDRESS": "127.0.0.1", "DURIS_TLS_PORT": str(tls),
            "DURIS_WEBSOCKET_LISTEN_ADDRESS": "127.0.0.1",
            "DURIS_WEBSOCKET_PORT": str(websocket), "REDIS": "FALSE", "CHAOS_MUD": "FALSE",
        }
        if os.environ.get("LD_LIBRARY_PATH"):
            environment["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
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
                command(player, "save", f"Save complete for {name}.")
                player.send("quit")
                player.expect("ACCOUNT MENU", timeout=30)
                player.close()
                player = None
            stop()
            journey.make_overlord(state, journey.CHARACTER)
            subprocess.run([str(fixture), str(state)], check=True)
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
            staff_command(staff, "load obj 89177")
            staff_command(staff, f"give copper {NAME}")
            command(player, "wear copper attach", "You can't attach that to your belt.")
            inspect(staff, "copper", 89177, f"carried by {NAME}")
            stop()
            assert process.returncode == 0, f"server shutdown failed: {process.returncode}"
            logs = output_path.read_text(errors="replace") + journey.runtime_logs(runtime)
            assert not any(marker in logs for marker in ("FATAL:", "assert:", "AddressSanitizer", "runtime error:")), logs[-6000:]
            result["controls"] = ["three slots", "full belt preserves inventory",
                                  "waist removal returns attachments", "belt required",
                                  "hold/remove", "unflagged instrument refuses"]
            REPORT.write_text(json.dumps(result, indent=2) + "\n")
            print("PASS: all six real mortal casts, room creation, pickup, attachment, flags, "
                  "three-slot/full/no-belt controls, hold/remove and unflagged control.", flush=True)
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
    with tempfile.TemporaryDirectory(prefix="minor-creation-build-", dir=ROOT / "bin/tests") as build:
        binary = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else journey.build_flatfile_server(Path(build))
        run(binary)
