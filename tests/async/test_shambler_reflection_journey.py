#!/usr/bin/env python3
"""Real Reflection/Mirror Image -> Shambler commands in a disposable flat-file world.

The two spell-route casters start as Illusionists and are changed to Scourges
after creating their images. This tests both real command routes without adding
a playable class combination. Racial cases use mortal Gnome/Kobold Scourges.
"""

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

ROOT = journey.ROOT
REPORT = ROOT / "bin/qualification/issue420/gameplay-report.json"
NAMES = ("Gnomirror", "Kobmirror", "Spellmirror", "Mirrormage")
PROMPTS = ("Pos: standing >", "<>")

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
    int found = 0;
    for (int pid = 1; pid <= 64; ++pid) {
        player_snapshot s; std::string error, name;
        if (flatfile_player_snapshot_read(root, pid, &s, &error) != flatfile_player_load_result::ok)
            continue;
        for (const auto &field : s.status_strings)
            if (field.field == player_status_string_field::name)
                name = field.value;
        if (name != "Gnomirror" && name != "Kobmirror" &&
            name != "Spellmirror" && name != "Mirrormage")
            continue;
        ++found;
        const bool mage = name == "Spellmirror" || name == "Mirrormage";
        auto set = [&](player_status_field key, int value) {
            for (auto &field : s.status_integers)
                if (field.field == key) {
                    field.signed_value = field.unsigned_value = value;
                    return;
                }
            assert(false);
        };
        set(player_status_field::class_primary, mage ? CLASS_ILLUSIONIST : CLASS_BLIGHTER);
        set(player_status_field::class_secondary, 0);
        set(player_status_field::specialization, SPEC_SCOURGE);
        set(player_status_field::race, name == "Kobmirror" ? RACE_KOBOLD : RACE_GNOME);
        set(player_status_field::level, 56);
        set(player_status_field::highest_level, 56);
        set(player_status_field::played_time, 200000);
        set(player_status_field::base_hit, 10000);
        set(player_status_field::hit_difference, 0);
        set(player_status_field::base_mana, 1000);
        set(player_status_field::mana, 1000);
        set(player_status_field::screen_length, 100);
        s.room_vnum = 22800;
        s.affects.clear();
        s.skills.clear();
        s.undead_slots.clear();
        for (int circle = 1; circle <= MAX_CIRCLE; ++circle)
            s.undead_slots.push_back({circle, 50, 0});
        for (int spell : {SPELL_SHAMBLER, SPELL_REFLECTION, SPELL_MIRROR_IMAGE,
                          SPELL_TITAN, SPELL_DISPLACEMENT}) {
            s.skills.push_back({spell, 100, 100});
            if (mage && spell != SPELL_SHAMBLER && spell != SPELL_DISPLACEMENT)
                for (int copy = 0; copy < 8; ++copy) {
                    player_affect_snapshot af{};
                    af.type = TAG_MEMORIZE; af.modifier = spell; af.duration = -1;
                    af.flags = MEMTYPE_FULL; af.level = 56;
                    s.affects.push_back(af);
                }
        }
        s.encoded_size_bound = PLAYER_SNAPSHOT_MAX_BYTES;
        std::vector<uint8_t> bytes;
        assert(flatfile_player_snapshot_encode_file(&s, &bytes));
        using namespace flatfile_player_snapshot_file;
        assert(flatfile_atomic_write(player_directory(root), player_filename(pid), bytes, &error));
    }
    assert(found == 4);
}
'''


def command(client, text, receipt, timeout=30):
    """Wait for this command's response, then its prompt, ignoring earlier prompts."""
    client.send(text)
    receipts = (receipt,) if isinstance(receipt, str) else receipt
    deadline = time.monotonic() + timeout
    parts = []
    while True:
        matched, output = client.expect_any(
            (*receipts, "Return to continue"), timeout=max(.1, deadline - time.monotonic()))
        parts.append(output)
        if matched != "Return to continue":
            break
        client.send("")
    while True:
        ending, output = client.expect_any(
            (*PROMPTS, "Return to continue"), timeout=max(.1, deadline - time.monotonic()))
        parts.append(output)
        if ending != "Return to continue":
            return matched, "".join(parts)
        client.send("")


def staff_command(staff, text):
    # Most setup commands are silent. An ordered echo provides their receipt.
    marker = f"issue420-receipt-{len(staff.transcript)}"
    _, output = command(staff, text + "\necho " + marker, marker)
    for error in ("Usage:", "No one by", "not a valid", "No such", "Let's try something real"):
        assert error not in output, output
    return output


def cast(client, spell, target=""):
    for _ in range(6):
        outcome, output = command(
            client, f"cast '{spell}' {target}".rstrip(),
            ("You complete your spell", "You abort your spell before",
             "You don't know that spell", "You don't have that spell memorized",
             "reserves are not sufficient"), timeout=60)
        if outcome == "You complete your spell":
            return output
        assert outcome == "You abort your spell before", output
    raise AssertionError(f"concentration failures exhausted retries for {spell}")


def pets(staff, keyword, vnum, owner):
    _, text = command(staff, f"stat char {keyword}", ("Numbers:", "No such character."))
    if "No such character." in text:
        return []
    count = int(re.search(r"# in game:\s*(\d+)", text)[1])
    result = []
    for index in range(1, count + 1):
        if index > 1:
            _, text = command(staff, f"stat char {index}.{keyword}", "Numbers:")
        identity = re.search(r"Numbers:\s*(\d+)-V\s+\d+-R\s+(\d+)-I", text)
        assert identity and int(identity[1]) == vnum, text
        assert re.search(rf"Master is:\s*{owner}\s", text), text
        assert re.search(rf"(?i)pet \(master\):\s*linked to {owner}\.", text), text
        result.append({
            "id": int(identity[2]),
            "keywords": re.search(r"Keywords:\s*([^\r\n]+)", text)[1].strip(),
        })
    assert len({row["id"] for row in result}) == count, result
    return sorted(result, key=lambda row: row["id"])


def player_selector(staff, name):
    # Images include their owner's name. Resolve the actual PC before staff edits.
    for ordinal in range(1, 6):  # One player plus at most four images.
        selector = f"{ordinal}.{name}"
        receipt, text = command(staff, f"stat char {selector}",
                                ("ID numb:", "Numbers:", "No such character."))
        assert receipt != "No such character.", text
        if receipt == "ID numb:":
            assert re.search(rf"Name:\s*{name}\s+ID numb:", text), text
            return selector
    raise AssertionError(f"could not distinguish {name} from its images")


def purge(staff, keyword, count):
    for _ in range(count):
        staff_command(staff, f"purge {keyword}")


def configure(runtime):
    journey.make_fixture(runtime)
    journey.generate_certificate(runtime)
    (runtime / "logs/log").mkdir(parents=True)
    (runtime / "logs/log/.since").touch()
    (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
    mini = runtime / "areas_mini"
    path = mini / "mini.mob"
    body = path.read_text()
    mound = re.search(r"(?ms)^#100\n.*?(?=^#\d+\n)",
                      (ROOT / "areas/mob/heavens.mob").read_text())[0]
    assert "#100\n" not in body
    for vnum, keys, title in (
        (22801, "companion ordinary", "an ordinary companion"),
        (22802, "sentinel target", "a patient sentinel"),
    ):
        mound += f"""#{vnum}
{keys}~
{title}~
{title.capitalize()} waits here.
~
~
10 0 0 0 0 0 0 0 S
PH 0 0 -1
1 0 100 1000d1+50000 1d1+0
0.0.0.0 0
8 8 0
"""
    # Mobile lookup expects the prototype index in ascending VNUM order.
    records = re.findall(r"(?ms)^#\d+\n.*?(?=^#\d+\n|^\$~)",
                         body.replace("$~", mound + "$~"))
    records.sort(key=lambda record: int(record.splitlines()[0][1:]))
    path.write_text("".join(records) + "$~\n")
    world = mini / "mini.wld"
    body = world.read_text()
    room = re.search(r"(?ms)^#22800\n.*?^S\n", body)[0]
    assert "1 0 0\nS\n" in room
    world.write_text(body.replace(room, room.replace("1 0 0\nS\n", "1 0 3\nS\n")))
    zone = mini / "mini.zon"
    body = re.sub(r"^[MGE] .*\n", "", zone.read_text(), flags=re.M)
    zone.write_text(body.replace("\nS\n", "\nM 0 22802 1 22800 100 0 0 0\nS\n"))


def run(binary):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.unlink(missing_ok=True)
    result = {"binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "cases": []}
    with tempfile.TemporaryDirectory(prefix="shambler-journey-", dir=ROOT / "bin/tests") as temporary:
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
            for name in (journey.CHARACTER, *NAMES):
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
            staff_command(staff, f"setbit char {journey.CHARACTER} pcact PAGING_ON 0")
            # Keep the Titan rejection control out of unrelated random retaliation.
            staff_command(staff, "setbit mob sentinel aff BLIND 1")
            for name in NAMES:
                print(f"Shambler command journey: {name}", flush=True)
                player = journey.reconnect_character(port, account=name, character=name)
                player.expect_any(PROMPTS)
                if name in ("Kobmirror", "Spellmirror"):
                    staff_command(staff, f"givepet {name} 22801")
                ordinary = pets(staff, "companion", 22801, name)
                if name in ("Gnomirror", "Kobmirror"):
                    _, output = command(player, "innate reflection", "into many images!")
                else:
                    spell = "reflection" if name == "Spellmirror" else "mirror image"
                    output = cast(player, spell, "me" if spell == "reflection" else "")
                images = pets(staff, "image", 250, name)
                assert len(images) >= 2, (name, images, output)
                if name == "Spellmirror":
                    cast(player, "reflection", "me")
                    replacement = pets(staff, "image", 250, name)
                    assert len(replacement) == len(images)
                    assert {row["id"] for row in images}.isdisjoint(
                        row["id"] for row in replacement)
                    assert pets(staff, "companion", 22801, name) == ordinary
                    images = replacement
                    blocked = cast(player, "titan", "sentinel")
                    assert "cant support so many different illusions" in blocked, blocked
                    assert not pets(staff, "titan", 650, name)
                if name in ("Spellmirror", "Mirrormage"):
                    staff_command(staff, f"setbit char {player_selector(staff, name)} class Blighter")
                output = cast(player, "shambler")
                assert "enough pets" not in output and "already have a mound" not in output, output
                mounds = pets(staff, "mound", 100, name)
                assert 3 <= len(mounds) <= 6, (name, mounds, output)
                assert pets(staff, "image", 250, name) == images
                assert pets(staff, "companion", 22801, name) == ordinary
                blocked = cast(player, "shambler")
                assert "You already have a mound." in blocked, blocked
                assert pets(staff, "mound", 100, name) == mounds
                purge(staff, "mound", len(mounds))
                if name == "Kobmirror":
                    staff_command(staff, f"givepet {player_selector(staff, name)} 22801")
                    two_pets = pets(staff, "companion", 22801, name)
                    assert len(two_pets) == 2
                    blocked = cast(player, "shambler")
                    assert "You already have enough pets." in blocked, blocked
                    assert not pets(staff, "mound", 100, name)
                    assert pets(staff, "image", 250, name) == images
                    assert pets(staff, "companion", 22801, name) == two_pets
                    purge(staff, "companion", 1)
                    ordinary = pets(staff, "companion", 22801, name)
                purge(staff, "image", len(images))
                assert pets(staff, "companion", 22801, name) == ordinary
                assert not pets(staff, "image", 250, name)
                # The same ordinary-pet allowance works after images are removed.
                cast(player, "shambler")
                after_cleanup = pets(staff, "mound", 100, name)
                assert 3 <= len(after_cleanup) <= 6
                purge(staff, "mound", len(after_cleanup))
                if name == "Gnomirror":
                    staff_command(staff, f"givepet {name} 650")
                    _, blocked = command(player, "innate reflection",
                                         "cant support so many different illusions")
                    assert not pets(staff, "image", 250, name), blocked
                    purge(staff, "titan", 1)
                if name == "Spellmirror":
                    staff_command(staff, f"setbit char {name} class MindFlayer")
                    _, displaced = command(player, "will 'displacement'",
                                           "Your mental manipulations become a reality", timeout=60)
                    assert "form shimmers" in displaced, displaced
                    assert not pets(staff, "image", 250, name)
                    staff_command(staff, f"setbit char {name} class Blighter")
                    cast(player, "shambler")
                    displaced_mounds = pets(staff, "mound", 100, name)
                    assert 3 <= len(displaced_mounds) <= 6
                    purge(staff, "mound", len(displaced_mounds))
                purge(staff, "companion", len(ordinary))
                result["cases"].append({"caster": name, "images": images, "mounds": mounds})
                player.close()
                player = None
            _, helptext = command(staff, "help shambler", "Reflection and")
            assert "at most one other pet" in helptext and "existing shambling" in helptext
            stop()
            logs = output_path.read_text(errors="replace") + journey.runtime_logs(runtime)
            assert not any(marker in logs for marker in ("FATAL:", "assert:", "AddressSanitizer", "runtime error:")), logs[-6000:]
            REPORT.write_text(json.dumps(result, indent=2) + "\n")
            print("PASS: both racial routes, Reflection/Mirror Image casts, real mounds, "
                  "ordinary-pet and duplicate caps, cleanup, Titan exclusions, Displacement and help.", flush=True)
        except Exception:
            if player:
                print(bytes(player.transcript).decode(errors="replace").replace(journey.PASSWORD, "[REDACTED]")[-9000:])
            if staff:
                print(bytes(staff.transcript).decode(errors="replace").replace(journey.PASSWORD, "[REDACTED]")[-9000:])
            print(output_path.read_text(errors="replace")[-4000:])
            raise
        finally:
            if player:
                player.close()
            stop()


if __name__ == "__main__":
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="shambler-build-", dir=ROOT / "bin/tests") as build:
        binary = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else journey.build_flatfile_server(Path(build))
        run(binary)
