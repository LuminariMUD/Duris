#!/usr/bin/env python3
"""Native nested-bag transfer, reboot and effective ordinary Armor journey."""

import json
from pathlib import Path
import re
import sys
import time
import test_flatfile_combat_journey as journey
from named_set_gameplay import (
    NamedSetGame,
    enable_items,
    score,
    save,
    selector,
    put,
    expect_max_hp,
)

ACCOUNT = "Namedguest"
RECIPIENT = "Meranen"
assert len(sys.argv) in (2, 3), "usage: run_named_set_transfer_journey.py copied-runtime [server]"
game = NamedSetGame(runtime=Path(sys.argv[1]), binary=Path(sys.argv[2]) if len(sys.argv) == 3 else None)
assert game.runtime != (journey.ROOT / "bin/tests/named-set-roster-world").resolve()
manifest = game.runtime / "named-transfer-setup.json"
setup = json.loads(manifest.read_text()) if manifest.exists() else {}
donor = receiver = None


def checkpoint():
    manifest.write_text(json.dumps(setup))


def load(client, pid, vnum):
    save(client, journey.CHARACTER if pid == 1 else RECIPIENT)
    before = {row[0] for row in game.inventory(pid)}
    client.send("load obj " + str(vnum))
    client.expect("You have created")
    save(client, journey.CHARACTER if pid == 1 else RECIPIENT)
    added = [
        row[0] for row in game.inventory(pid) if row[0] not in before and row[1] == vnum
    ]
    assert len(added) == 1, (vnum, added)
    return added[0]


def give(client, uid, name):
    client.send("give " + selector(client, uid) + " " + name)
    client.expect("Ok.", timeout=30)
    score(client)


def open_bag(client, uid):
    client.send("open " + selector(client, uid))
    score(client)


def owned(uid, pid):
    return any(row[0] == uid for row in game.inventory(pid))


def expect_nested():
    rows = game.inventory(2)
    inner = next(i for i, row in enumerate(rows) if row[0] == setup["inner"])
    outer = next(i for i, row in enumerate(rows) if row[0] == setup["outer"])
    assert rows[inner][2] == outer
    assert all(
        next(row for row in rows if row[0] == uid)[2] == inner for uid in setup["uids"]
    )


def unpack(client, pid):
    client.send("remove all")
    score(client)
    save(client, journey.CHARACTER if pid == 1 else RECIPIENT)
    # Only these two known test containers can enclose the selected pieces.
    for key in ("outer", "inner"):
        uid = setup.get(key)
        if uid and owned(uid, pid):
            rows = game.inventory(pid)
            index = next(i for i, row in enumerate(rows) if row[0] == uid)
            if any(row[2] == index for row in rows):
                client.send("get all " + selector(client, uid))
                client.expect("You get", timeout=30)
                score(client)
                save(client, journey.CHARACTER if pid == 1 else RECIPIENT)


def armor_points(client):
    client.send("attributes")
    text = client.expect("Character attributes for")
    text += client.expect("Pos:") + client.expect(">")
    match = re.search(r"Armor Points:\s*(-?\d+)", text)
    assert match, text
    result = int(match[1])
    assert -750 < result < 100, ("Armor Points must be away from the caps", text)
    return result


try:
    prior = {row[0]: row[1] for row in game.items()}
    if not (game.state / "players/2.snapshot").exists():
        donor = game.boot("named-transfer-create")
        receiver = journey.MudClient(game.port, source_host="127.0.0.2")
        game.clients.append(receiver)
        journey.create_character(
            receiver,
            expected_room=None,
            account=ACCOUNT,
            character=RECIPIENT,
            email="named-guest@example.invalid",
        )
        enable_items(receiver)
        score(receiver)
        save(receiver, RECIPIENT)
        save(donor)
        game.stop()
    # Require the expected native PID/name, never reseed a failed attempt.
    prior.update({row[0]: row[1] for row in game.items(2)})
    journey.make_overlord(game.state, journey.CHARACTER)
    journey.make_overlord(game.state, RECIPIENT)
    donor = game.boot("named-transfer-prepare")
    receiver = game.login(account=ACCOUNT, character=RECIPIENT, source_host="127.0.0.2")
    for actor in (donor, receiver):
        actor.send("vis 0")
        score(actor)
    donor.send("goto 132500")
    score(donor)
    donor.send("transfer " + RECIPIENT)
    score(donor)
    score(receiver)
    save(donor)
    save(receiver, RECIPIENT)

    if not setup:
        donor.send("remove all")
        score(donor)
        save(donor)
        selected = []
        for slot, flag in (("head", 16), ("body", 8), ("legs", 32)):
            candidates = [
                row
                for row in game.items()
                if row[1] == "1325"
                and row[4] == "1"
                and row[5] == "-1"
                and int(row[3]) & flag
            ]
            if not candidates:
                donor.send("randobj eq " + slot + " 56 30")
                donor.expect("Created 30 equipment items.", timeout=30)
                save(donor)
                candidates = [
                    row
                    for row in game.items()
                    if row[1] == "1325"
                    and row[4] == "1"
                    and row[5] == "-1"
                    and int(row[3]) & flag
                ]
            assert candidates, ("no native clean candidate", slot)
            selected.append(int(candidates[0][0]))
        setup["uids"] = selected
        checkpoint()
    for key, vnum in (("inner", 4917), ("outer", 83445)):
        if key not in setup:
            setup[key] = load(donor, 1, vnum)
            open_bag(donor, setup[key])
            checkpoint()
    unpack(donor, 1)
    unpack(receiver, 2)
    for uid in setup["uids"]:
        if owned(uid, 2):
            give(receiver, uid, journey.CHARACTER)
            save(receiver, RECIPIENT)
            save(donor)
        assert owned(uid, 1), ("selected UID missing", uid)
    # Hold the test bags with the other staff tester while the donor packs
    # the candidate pool. This avoids burying the bags in that large pool.
    for key in ("inner", "outer"):
        if owned(setup[key], 1):
            give(donor, setup[key], RECIPIENT)
            save(donor)
            save(receiver, RECIPIENT)
    for uid in setup["uids"]:
        donor.send("wear " + selector(donor, uid))
        score(donor)
    stash = load(donor, 1, 83445)
    open_bag(donor, stash)
    donor.send("put all " + selector(donor, stash))
    score(donor)
    for key in ("inner", "outer"):
        give(receiver, setup[key], journey.CHARACTER)
        save(receiver, RECIPIENT)
        save(donor)
    stash = load(receiver, 2, 83445)
    open_bag(receiver, stash)
    receiver.send("put all " + selector(receiver, stash))
    score(receiver)
    give(receiver, stash, journey.CHARACTER)
    donor.send("remove all")
    score(donor)
    save(donor)
    for uid in setup["uids"]:
        put(donor, uid, setup["inner"])
    potion = load(donor, 1, 39130)
    setup["potion"] = potion
    reference_potion = load(donor, 1, 39130)
    checkpoint()
    put(donor, potion, setup["inner"])
    put(donor, reference_potion, setup["inner"])
    put(donor, setup["inner"], setup["outer"])
    save(donor)
    save(receiver, RECIPIENT)
    game.stop()
    game.prepare_mortal()
    game.prepare_mortal(2)

    donor = game.boot("named-transfer-mortal")
    receiver = game.login(account=ACCOUNT, character=RECIPIENT, source_host="127.0.0.2")
    assert "Level: 56" in score(donor)[1] and "Level: 56" in score(receiver)[1]
    baseline = score(receiver)[0]
    receiver.send("consent " + journey.CHARACTER)
    score(receiver)
    give(donor, setup["outer"], RECIPIENT)
    save(donor)
    save(receiver, RECIPIENT)
    assert all(not owned(uid, 1) and owned(uid, 2) for uid in setup["uids"])
    expect_nested()
    print(
        "Native mortal give moved the complete two-level tree and original named UIDs to PID 2",
        flush=True,
    )
    game.stop()

    receiver = game.boot(
        "named-transfer-nested-reboot", account=ACCOUNT, character=RECIPIENT
    )
    save(receiver, RECIPIENT)
    expect_nested()
    unpack(receiver, 2)
    for uid in setup["uids"]:
        receiver.send("wear " + selector(receiver, uid))
        score(receiver)
    text = expect_max_hp(receiver, baseline + 5)
    assert "armor (" in text
    save(receiver, RECIPIENT)
    assert not game.affects(1, 2)

    # Establish ordinary Armor alone before reactivating the same three pieces.
    # This keeps every equipped item's own armor/stat contribution identical.
    receiver.send("remove " + selector(receiver, setup["uids"][-1]))
    expect_max_hp(receiver, baseline)
    deadline = time.monotonic() + 15
    while "armor (" in score(receiver)[1]:
        assert time.monotonic() < deadline, "set Armor did not wear off"
        time.sleep(0.5)
    receiver.send("quaff " + selector(receiver, reference_potion))
    receiver.expect("Bands of magic armor wrap around you!", timeout=30)
    score(receiver)
    ordinary_two_points = armor_points(receiver)
    receiver.send("wear " + selector(receiver, setup["uids"][-1]))
    expect_max_hp(receiver, baseline + 5)
    points = armor_points(receiver)
    save(receiver, RECIPIENT)
    reference = game.affects(1, 2)
    assert len(reference) == 1
    game.stop()

    # Clear only the copied tester's ordinary buffs, then exercise set-first.
    game.prepare_mortal(2)
    receiver = game.boot("named-transfer-set-first", account=ACCOUNT, character=RECIPIENT)
    assert "armor (" in expect_max_hp(receiver, baseline + 5)
    receiver.send("quaff " + selector(receiver, potion))
    receiver.expect("Bands of magic armor wrap around you!", timeout=30)
    score(receiver)
    save(receiver, RECIPIENT)
    ordinary = game.affects(1, 2)
    assert len(ordinary) == 1
    # Native Armor rolls an extra 0-10 AC. Match the ordinary cast's strength;
    # transient set affects are absent from these independently stored rows.
    adjustment = ordinary[0][3] - reference[0][3]
    points += adjustment
    ordinary_two_points += adjustment
    actual = armor_points(receiver)
    assert actual == points, ("overlap versus ordinary-only Armor on identical gear", points, actual)
    receiver.send("remove " + selector(receiver, setup["uids"][-1]))
    text = expect_max_hp(receiver, baseline)
    assert "armor (" in text
    assert armor_points(receiver) == ordinary_two_points
    receiver.send("wear " + selector(receiver, setup["uids"][-1]))
    expect_max_hp(receiver, baseline + 5)
    assert armor_points(receiver) == points, (
        "set support must not add to ordinary Armor"
    )
    save(receiver, RECIPIENT)
    worn = {int(row[0]): row[:4] for row in game.items(2)}
    game.stop()
    receiver = game.boot(
        "named-transfer-worn-reboot", account=ACCOUNT, character=RECIPIENT
    )
    expect_max_hp(receiver, baseline + 5)
    assert armor_points(receiver) == points
    save(receiver, RECIPIENT)
    restored = game.affects(1, 2)
    assert len(restored) == 1 and 0 < restored[0][1] <= ordinary[0][1]
    received = {int(row[0]): row for row in game.items(2)}
    assert all(
        received[uid][1] == "1325" and int(received[uid][2]) for uid in setup["uids"]
    )
    assert all(received[uid][:4] == worn[uid] for uid in setup["uids"])
    final = {row[0]: row[1] for row in game.items() + game.items(2)}
    assert prior.items() <= final.items()
    assert {row[0] for row in game.inventory()}.isdisjoint(
        row[0] for row in game.inventory(2)
    )
    (game.runtime / "named-transfer-result.json").write_text(
        json.dumps(
            {
                "uids": setup["uids"],
                "receiver_pid": 2,
                "baseline": baseline,
                "ordinary_armor_points": points,
            }
        )
    )
    print(
        "Native nested/worn reboots retained origins and slots; ordinary Armor stayed non-stacking at Armor Points "
        + str(points),
        flush=True,
    )
finally:
    game.stop()
    (game.runtime / "named-transfer-transcript.txt").write_bytes(
        b"\n".join(game.transcripts)
    )
