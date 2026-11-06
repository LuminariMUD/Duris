#!/usr/bin/env python3
"""Native persistent storage, nested item reload, retrieval and set recovery."""

import json
import subprocess
import time

import test_flatfile_combat_journey as journey
from named_set_gameplay import (
    NamedSetGame, expect_max_hp, get_from_container, inventory_graph, put, save, score, selector,
)

ACCOUNT, CHARACTER, PID, ROOM = "Namedguest", "Meranen", 2, 132500
game = NamedSetGame()
source = json.loads((game.runtime / "named-transfer-setup.json").read_text())
originals = source["uids"]
bag = json.loads((game.runtime / "named-locker-funded-setup.json").read_text())["bag"]
targets = set(originals + [bag])
manifest = game.runtime / "named-world-setup.json"
setup = json.loads(manifest.read_text()) if manifest.exists() else {}
actor = None


def stored():
    rows = json.loads(subprocess.check_output(
        [str(journey.INSPECTOR), str(game.state), "inspect-room-items", str(ROOM)], text=True
    ))["items"]
    return {row["uid"]: row for row in rows}


def wait_stored(present):
    deadline = time.monotonic() + 45
    while True:
        rows = stored()
        complete = targets <= rows.keys() if present else targets.isdisjoint(rows)
        if complete:
            return rows
        assert time.monotonic() < deadline, (present, rows)
        time.sleep(.2)


def command(text, expected=None):
    actor.send(text)
    if expected:
        actor.expect(expected, timeout=30)
    return score(actor)[1]


def check_world():
    rows = wait_stored(True)
    root = setup["root"]
    expected = {root: [83185, 0], bag: [83445, root]}
    expected.update({uid: [1252, bag] for uid in originals})
    assert {uid: [rows[uid]["vnum"], rows[uid]["parent_uid"]] for uid in expected} == expected
    assert rows[root]["type"] == 35  # Actual ITEM_STORAGE, not an ephemeral floor bag.
    assert all(rows[uid]["slot"] == -1 for uid in expected)
    assert all(rows[uid].get("named_origin") == "1325" for uid in originals)


try:
    prior = {row[0]: row[1] for row in game.items() + game.items(PID)}
    room = stored()
    in_storage = targets <= room.keys() and room[bag]["parent_uid"] == setup.get("root")
    if not in_storage:
        journey.make_overlord(game.state, CHARACTER)
        actor = game.boot("named-world-prepare", account=ACCOUNT, character=CHARACTER)
        command("vis 0")
        command("goto " + str(ROOM))
        if not setup:
            setup["slots"] = {row[0]: row[2] for row in game.items(PID) if int(row[0]) in originals}
            assert len(setup["slots"]) == 3 and all(int(slot) for slot in setup["slots"].values())
            manifest.write_text(json.dumps(setup, indent=2))
        command("remove all")
        # The collector's original keywords also include "bottomless". Keep
        # its collector keyword while distinguishing it from the floor root.
        command("string obj " + selector(actor, bag) + " name collector collectorproof", "Ok.")
        command("open " + selector(actor, bag))
        save(actor, CHARACTER)
        for uid in originals:
            graph = inventory_graph(game.inventory(PID))
            if graph[str(uid)][1] != bag:
                put(actor, uid, bag)
        save(actor, CHARACTER)
        setup["player_graph"] = {str(uid): inventory_graph(game.inventory(PID))[str(uid)] for uid in targets}
        if "root" not in setup:
            roots = [uid for uid, row in stored().items() if row["vnum"] == 83185 and row["type"] == 35]
            if not roots:
                command("storage new 83185", "This object now loads here")
            deadline = time.monotonic() + 30
            while True:
                roots = [uid for uid, row in stored().items() if row["vnum"] == 83185 and row["type"] == 35]
                if roots:
                    setup["root"], = roots
                    break
                assert time.monotonic() < deadline, "storage root was not durably created"
                time.sleep(.2)
        manifest.write_text(json.dumps(setup, indent=2))
        command("open bottomless")
        command("put " + selector(actor, bag) + " bottomless", "Ok.")
        save(actor, CHARACTER)
        check_world()
        assert targets.isdisjoint(row[0] for row in game.inventory(PID))
        print("Native ITEM_STORAGE contains the exact durable marked nested graph; player custody is absent", flush=True)
        game.stop()

    game.prepare_mortal(PID)
    actor = game.boot("named-world-reload", account=ACCOUNT, character=CHARACTER)
    assert "Level: 56" in score(actor)[1]
    check_world()
    command("open bottomless")
    command("get collectorproof bottomless", "You get")
    save(actor, CHARACTER)
    wait_stored(False)
    graph = inventory_graph(game.inventory(PID))
    assert {str(uid): graph[str(uid)] for uid in targets} == setup["player_graph"]
    for uid in originals:
        get_from_container(actor, uid, bag)
    baseline = score(actor)[0]
    for uid in originals:
        command("wear " + selector(actor, uid))
    assert "armor (" in expect_max_hp(actor, baseline + 5)
    save(actor, CHARACTER)
    assert {row[0]: row[2] for row in game.items(PID) if int(row[0]) in originals} == setup["slots"]
    assert not game.affects(1, PID)
    game.stop()
    actor = game.boot("named-world-wear-reboot", account=ACCOUNT, character=CHARACTER)
    assert "armor (" in expect_max_hp(actor, baseline + 5)
    save(actor, CHARACTER)
    rows = game.items(PID)
    assert {row[0]: row[2] for row in rows if int(row[0]) in originals} == setup["slots"]
    current = {row[0]: row[1] for row in game.items() + rows}
    assert all(current.get(uid) == origin for uid, origin in prior.items())
    assert all(current[str(uid)] == "1325" for uid in originals)
    wait_stored(False)
    print("World reboot/mortal retrieval and player reboot retain all UIDs/origins/parents/slots and Armor/+5 HP", setup["root"], flush=True)
finally:
    game.stop()
    (game.runtime / "named-world-transcript.txt").write_bytes(b"\n\n".join(game.transcripts))
