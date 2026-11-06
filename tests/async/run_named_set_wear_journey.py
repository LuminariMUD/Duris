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
import time
import test_flatfile_combat_journey as journey

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


def armor_affects():
    text = subprocess.check_output([str(fixture), str(state), "affects"], text=True)
    return [
        list(map(int, line.split("|")))
        for line in text.splitlines()
        if line.startswith("1|")
    ]


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
    existing = inspect()
    journey.make_overlord(state, journey.CHARACTER)
    boot("named-generation")
    client.send("goto 132500")
    _, text = score()
    assert "Level: 62" in text, text
    choices = []
    for slot, flag in (
        ("head", 16),
        ("body", 8),
        ("legs", 32),
        ("hands", 128),
        ("arms", 256),
    ):
        if not any(
            row[1] == "1325" and row[4] == "1" and row[5] == "-1" and int(row[3]) & flag
            for row in existing
        ):
            client.send("randobj eq " + slot + " 56 30")
            client.expect("Created 30 equipment items.", timeout=30)
            save()
            existing = inspect()
        rows = [
            row
            for row in existing
            if row[1] == "1325"
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
    client.send("load obj 39130")
    client.expect("You have created")
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
            text = expect_max_hp(baseline + 5 * (len(chosen) - 2))
            assert "armor (" in text, text
            assert ("endurance (" in text) == (len(chosen) == 5), text
    print(
        "Ordinary native wear: 2/3/4/5 pieces +0/+5/+10/+15 HP; Armor at 3, Endurance at 5",
        chosen,
        flush=True,
    )
    save()
    before = inspect()
    stop()
    boot("named-mortal-reboot")
    text = expect_max_hp(baseline + 15)
    assert "endurance (" in text, text
    save()
    after = inspect()
    for uid in chosen:
        old = next(row for row in before if int(row[0]) == uid)
        new = next(row for row in after if int(row[0]) == uid)
        assert old[:4] == new[:4], (old, new)
    assert not armor_affects(), "set Armor must not persist as an ordinary affect"
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
    ordinary = armor_affects()
    assert len(ordinary) == 1, ordinary
    client.send("remove " + selector(chosen[2]))
    score()
    text = expect_max_hp(baseline)
    assert "armor (" in text, text
    save()
    assert len(armor_affects()) == 1
    # The already ordinary Armor is present before this new set application.
    client.send("wear " + selector(chosen[2]))
    expect_max_hp(baseline + 5)
    client.send("remove " + selector(chosen[2]))
    expect_max_hp(baseline)
    save()
    saved_armor = armor_affects()
    assert len(saved_armor) == 1 and saved_armor[0][1] <= ordinary[0][1]
    stop()
    boot("named-ordinary-reboot")
    _, text = score()
    assert "armor (" in text, text
    save()
    assert len(armor_affects()) == 1
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
        (runtime / "named-wear-failure.txt").write_bytes(bytes(client.transcript))
    raise
finally:
    if client:
        (runtime / "named-wear-transcript.txt").write_bytes(bytes(client.transcript))
    stop()
