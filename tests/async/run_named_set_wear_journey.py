#!/usr/bin/env python3
"""Native wear/cast/reboot gate using a prepared, private full-world authority.

Run from the repository root after building the flat-file server and preparing
the runtime described in the named-zone-set implementation plan. The existing
synthetic account and generated item identities are retained between attempts.
This is deliberately a full-server journey, not a stubbed spell fixture.
"""

import json
import os
import re
import subprocess
import sys
import time
import test_flatfile_combat_journey as journey

# Required cases: generation room, maximum tier, primary native name and spell ID.
CASES = {
    1325: (132500, 5, "armor", 1),
    740: (74000, 5, "battletide", 395),
    827: (82701, 3, "protection from animals", 383),
    13: (1300, 3, "phantom armor", 400),
    44: (4401, 3, "globe of darkness", 302),
    204: (20400, 3, "sense life", 44),
    808: (80800, 3, "enhance agility", 177),
    811: (81100, 3, "protection from animals", 383),
    814: (81400, 3, "vapor strike", 467),
    990: (99001, 3, "scent of the bloodhound", 517),
    300: (30000, 3, "globe of darkness", 302),
    1350: (135001, 3, "phantom armor", 400),
    87: (8700, 5, "spirit ward", 220),
    370: (37000, 3, "endurance", 355),
    676: (67600, 4, "endurance", 355),
    824: (82400, 6, "vitality", 56),
}
zone = int(sys.argv[1]) if len(sys.argv) == 2 else 1325
generation_room, pieces, effect, spell = CASES[zone]
runtime = (journey.ROOT / "bin/tests/named-set-roster-world").resolve()
state = runtime / "state"
assert state.is_dir() and (runtime / "areas/world.zon").is_file(), (
    "prepare the isolated full-world runtime first"
)
fixture = journey.ROOT / "bin/tests/named-set-journey-fixture"
subprocess.run(
    [
        "g++",
        "-std=c++20",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Isrc",
        "tests/async/named_set_journey_fixture.cpp",
        "src/player/player_snapshot_codec.c",
        "src/flatfile/flatfile_player_snapshot_file.c",
        "src/flatfile/flatfile_store.c",
        "-lcrypto",
        "-o",
        str(fixture),
    ],
    check=True,
    cwd=journey.ROOT,
)
port, tls, websocket = journey.available_ports()
env = dict(
    PATH=os.environ.get("PATH", "/usr/bin:/bin"),
    ENVIRONMENT="local",
    PERSISTENCE_MODE="flatfile-primary",
    FLATFILE_STATE_DIR=str(state),
    CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
    LISTEN_ADDRESS="127.0.0.1",
    DURIS_TLS_PORT=str(tls),
    DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1",
    DURIS_WEBSOCKET_PORT=str(websocket),
    REDIS="FALSE",
    CHAOS_MUD="FALSE",
)
if os.environ.get("LD_LIBRARY_PATH"):
    env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
process = client = output = None
transcripts = []


def boot(label):
    global process, client, output
    output = (runtime / (label + ".out")).open("w")
    process = subprocess.Popen(
        [
            str(journey.ROOT / "bin/tests/named-set-flatfile-server"),
            "-d",
            str(runtime),
            str(port),
        ],
        cwd=runtime,
        env=env,
        stdout=output,
        stderr=subprocess.STDOUT,
    )
    deadline = time.monotonic() + 120
    while "Entering game loop." not in (runtime / (label + ".out")).read_text(
        errors="replace"
    ):
        assert process.poll() is None, label + " boot failed"
        assert time.monotonic() < deadline, label + " boot deadline"
        time.sleep(0.1)
    client = journey.reconnect_character(port, expected_room=None)
    client.send("")
    client.expect("Pos:", timeout=30)
    client.expect(">")
    client.socket.sendall(b"\xff\xfd\xc9")
    gmcp('Core.Supports.Set ["Duris.Capabilities 1","Duris.Session 1","Char.Items 1"]')
    gmcp('Duris.Subscribe ["Char.Items 1"]')


def stop():
    global process, client, output
    if client:
        transcripts.append(bytes(client.transcript))
        client.close()
        client = None
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if output:
        output.close()
        output = None


def score():
    client.send("score")
    text = client.expect("Score information for")
    text += client.expect("Pos:")
    text += client.expect(">")
    match = re.search(r"Hit points:\s*\d+\((\d+)\)", text)
    assert match, text
    return int(match[1]), text


def save():
    client.send("save")
    client.expect("Save complete for " + journey.CHARACTER + ".", timeout=30)


def expect_max_hp(expected):
    deadline = time.monotonic() + 25
    while True:
        actual, text = score()
        if actual == expected:
            return text
        assert time.monotonic() < deadline, ("maximum HP", expected, actual, text)
        time.sleep(0.5)


def inspect():
    text = subprocess.check_output([str(fixture), str(state), "inspect"], text=True)
    return [line.split("|", 6) for line in text.splitlines()]


def stored_affects(spell_id):
    text = subprocess.check_output([str(fixture), str(state), "affects"], text=True)
    return [
        list(map(int, line.split("|")))
        for line in text.splitlines()
        if line.startswith(str(spell_id) + "|")
    ]


def expect_set(count):
    # Vitality at capped cast level 56 adds its own 4 * 56 HP, separately
    # from the basic five HP per piece beyond two.
    spell_hp = 224 if zone == 824 and count >= 6 else 0
    text = expect_max_hp(baseline + max(0, count - 2) * 5 + spell_hp)
    if zone == 1325:
        expected = {"armor": count >= 3, "endurance": count >= 5}
    elif zone == 87:
        expected = {"spirit ward": count >= 3, "haste": count >= 5}
    else:
        expected = {effect: count >= pieces}
    for name, present in expected.items():
        assert (name + " (" in text) == present, (zone, count, name, text)
    return text


def check_report():
    client.send("namedreport")
    text = client.expect("Current listing of spells granted by named sets by zone.")
    for _ in range(50):
        marker, part = client.expect_any(("Return to continue", "Pos:"), timeout=30)
        text += part
        if marker == "Pos:":
            break
        client.send("")
    else:
        raise AssertionError("report pagination did not finish")
    row = re.search(r"(?m)^\s*#" + str(zone) + r"\s+.*$", text)
    assert row and effect in row[0].lower(), (zone, row, text)


def gmcp(payload):
    client.socket.sendall(b"\xff\xfa\xc9" + payload.encode() + b"\xff\xf0")


def selector(uid):
    offset = len(client.raw_transcript)
    gmcp("Char.Items.Get []")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        client._receive()
        for packet in re.findall(
            rb"\xff\xfa\xc9(.*?)\xff\xf0", bytes(client.raw_transcript[offset:]), re.S
        ):
            if not packet.startswith(b"Char.Items.List "):
                continue
            payload = json.loads(packet.split(b" ", 1)[1])
            for item in payload["items"]:
                token = item.get("selector")
                if token and token.endswith(":" + str(uid)):
                    return token
    raise AssertionError("no current GMCP selector for " + str(uid))


try:
    # Validate the synthetic authority and retain all earlier named identities,
    # including gear packed into nested containers by preceding cases.
    prior_origins = {row[0]: row[1] for row in inspect()}
    journey.make_overlord(state, journey.CHARACTER)
    boot("named-generation")
    client.send("remove all")
    score()
    save()
    existing = inspect()
    client.send("goto " + str(generation_room))
    _, text = score()
    assert "Level: 62" in text, text
    choices = []
    for slot, flag in (
        ("head", 16),
        ("body", 8),
        ("legs", 32),
        ("hands", 128),
        ("arms", 256),
        ("feet", 64),
    )[:pieces]:
        if not any(
            row[1] == str(zone)
            and row[4] == "1"
            and row[5] == "-1"
            and int(row[3]) & flag
            for row in existing
        ):
            client.send("randobj eq " + slot + " 56 30")
            client.expect("Created 30 equipment items.", timeout=30)
            save()
            existing = inspect()
        rows = [
            row
            for row in existing
            if row[1] == str(zone)
            and row[4] == "1"
            and row[5] == "-1"
            and int(row[3]) & flag
        ]
        assert rows, ("no HP/CON-clean named candidate", flag)
        choices.append(rows)
    # Wear the selected candidates before packing the surplus through native
    # commands. Otherwise a staff-sized inventory prevents mortal removal.
    selected = []
    for rows in choices:
        uid = int(rows[0][0])
        if not int(rows[0][2]):
            client.send("wear " + selector(uid))
            score()
            save()
        assert int(next(row for row in inspect() if int(row[0]) == uid)[2])
        selected.append(uid)
    client.send("load obj 83445")
    client.expect("You have created")
    client.send("open collector")
    client.expect("Ok.")
    client.send("put all collector")
    score()
    if zone == 1325:
        client.send("load obj 39130")
        client.expect("You have created")
    # Wearing outside the generation zone also checks that room identity is irrelevant.
    client.send("goto 132500")
    score()
    save()
    stop()
    subprocess.run([str(fixture), str(state), "mortal"], check=True)
    boot("named-mortal-wear")
    client.send("remove all")
    score()
    save()
    assert not any(int(row[2]) for row in inspect()), (
        "remove all must really empty the named wear slots"
    )
    time.sleep(6)
    baseline, text = score()
    assert "Level: 56" in text, text
    check_report()
    client.send("inventory")
    score()
    chosen = []
    for uid in selected:
        client.send("wear " + selector(uid))
        score()
        save()
        item = next(item for item in inspect() if int(item[0]) == uid)
        assert int(item[2]), ("native mortal wear failed", item)
        chosen.append(uid)
        if len(chosen) == 2:
            time.sleep(6)
            two, _ = score()
            assert two == baseline, ("two-piece HP", baseline, two)
        if len(chosen) >= 3:
            expect_set(len(chosen))
    print(
        f"#{zone}: native HP and all spell thresholds passed through {pieces} pieces",
        chosen,
        flush=True,
    )
    save()
    before = inspect()
    stop()
    boot("named-mortal-reboot")
    expect_set(pieces)
    save()
    after = inspect()
    restored_origins = {row[0]: row[1] for row in after}
    assert prior_origins.items() <= restored_origins.items(), (
        "earlier named items must survive nested-container saves and reboot"
    )
    for uid in chosen:
        old = next(row for row in before if int(row[0]) == uid)
        new = next(row for row in after if int(row[0]) == uid)
        assert old[:4] == new[:4], (old, new)
    assert not stored_affects(spell), (
        "set effect must not persist as an ordinary affect"
    )
    if zone == 87:
        assert not stored_affects(41), (
            "set Haste must not persist as an ordinary affect"
        )
    if zone != 1325:
        client.send("remove " + selector(chosen[-1]))
        expect_set(pieces - 1)
        client.send("remove all")
        expect_set(0)
        save()
        (runtime / f"named-zone-{zone}-result.json").write_text(
            json.dumps(
                {
                    "zone": zone,
                    "baseline": baseline,
                    "uids": chosen,
                    "threshold": pieces,
                    "effect": effect,
                }
            )
        )
        print(
            f"#{zone}: native report, inventory, wear, save/reboot identity and removal passed",
            flush=True,
        )
        sys.exit(0)
    for uid in chosen[3:]:
        client.send("remove " + selector(uid))
        score()
    text = expect_max_hp(baseline + 5)
    assert "armor (" in text and "endurance (" not in text, text
    print(
        "Native five-piece save/reboot retained all UIDs, origins, wear slots and Endurance; returning to three cleaned Endurance",
        flush=True,
    )
    client.send("quaff solution")
    client.expect("Bands of magic armor wrap around you!", timeout=20)
    score()
    save()
    ordinary = stored_affects(1)
    assert len(ordinary) == 1, ordinary
    client.send("remove " + selector(chosen[2]))
    score()
    text = expect_max_hp(baseline)
    assert "armor (" in text, text
    save()
    assert len(stored_affects(1)) == 1
    # The already ordinary Armor is present before this new set application.
    client.send("wear " + selector(chosen[2]))
    expect_max_hp(baseline + 5)
    client.send("remove " + selector(chosen[2]))
    expect_max_hp(baseline)
    save()
    saved_armor = stored_affects(1)
    assert len(saved_armor) == 1 and saved_armor[0][1] <= ordinary[0][1]
    stop()
    boot("named-ordinary-reboot")
    _, text = score()
    assert "armor (" in text, text
    save()
    assert len(stored_affects(1)) == 1
    print(
        "Native ordinary Armor and named HP removal passed",
        flush=True,
    )
    print(
        "Ordinary potion Armor before/after set application survived removal and reboot exactly once",
        flush=True,
    )
    (runtime / "named-wear-result.json").write_text(
        json.dumps(
            {
                "baseline": baseline,
                "uids": chosen,
                "three_piece_max": baseline + 5,
                "five_piece_max": baseline + 15,
            }
        )
    )
except Exception:
    if client:
        (runtime / f"named-zone-{zone}-failure.txt").write_bytes(
            bytes(client.transcript)
        )
    raise
finally:
    stop()
    (runtime / f"named-zone-{zone}-transcript.txt").write_bytes(b"\n".join(transcripts))
