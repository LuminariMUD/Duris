#!/usr/bin/env python3
"""Native public account-locker custody, reboot, retrieval and set recovery."""

import json
import subprocess
import time
import test_flatfile_combat_journey as journey
from named_set_gameplay import (
    NamedSetGame,
    score,
    save,
    selector,
    put,
    inventory_graph,
    get_from_container,
    expect_max_hp,
)

ACCOUNT, CHARACTER, PID = "Namedguest", "Meranen", 2
LOCKER = "account.namedguest.1.locker"
game = NamedSetGame()
source = json.loads((game.runtime / "named-transfer-setup.json").read_text())
targets = set(source["uids"])
manifest = game.runtime / "named-locker-funded-setup.json"
setup = json.loads(manifest.read_text()) if manifest.exists() else None
actor = None


def stored():
    return json.loads(
        subprocess.check_output(
            [str(journey.INSPECTOR), str(game.state), "inspect-locker-items", LOCKER],
            text=True,
        )
    )["items"]


def wait_stored(present):
    deadline = time.monotonic() + 45
    while True:
        rows = stored()
        found = targets & {row["uid"] for row in rows}
        if found == targets if present else not found:
            return rows
        assert time.monotonic() < deadline, rows
        time.sleep(0.2)


def command(text, expected=None):
    actor.send(text)
    if expected:
        actor.expect(expected, timeout=30)
    return score(actor)[1]


def counter():
    command("goto 132500")
    command("load obj 3097", "You have created")


def enter():
    deadline = time.monotonic() + 60
    while True:
        actor.send("enter locker")
        matched, text = actor.expect_any(
            (
                "this cost you",
                "Please try later",
                "Slow your roll",
                "could not be opened",
            ),
            timeout=30,
        )
        if matched == "this cost you":
            text += score(actor)[1]
            assert (
                "GET OUT" not in text and "could not complete the payment" not in text
            ), text
            actor.send("look")
            actor.expect("The Storage Locker for", timeout=30)
            actor.expect("Pos:")
            actor.expect(">")
            return
        assert (
            matched in ("Please try later", "Slow your roll")
            and time.monotonic() < deadline
        ), text
        score(actor)
        time.sleep(0.2)


def leave():
    deadline = time.monotonic() + 45
    while True:
        opened = command("open door")
        if "belongings are being secured" in opened:
            assert time.monotonic() < deadline, opened
            continue
        actor.send("north")
        matched, text = actor.expect_any(
            ("applying magic locks", "still being secured"), timeout=30
        )
        score(actor)
        if matched == "applying magic locks":
            save(actor, CHARACTER)
            return
        assert time.monotonic() < deadline, text


try:
    prior = {row[0]: row[1] for row in game.items() + game.items(PID)}
    prior.update(
        {
            str(row["uid"]): row["named_origin"]
            for row in stored()
            if "named_origin" in row
        }
    )
    journey.make_overlord(game.state, CHARACTER)
    actor = game.boot("named-locker-deposit", account=ACCOUNT, character=CHARACTER)
    command("vis 0")
    command("goto 132500")
    if not setup:
        # Fund the real fee through native NPC currency transfer.
        command("force Kieta give 1 platinum " + CHARACTER, "gives you")
        command("remove all")
        save(actor, CHARACTER)
        before = {row[0] for row in game.inventory(PID)}
        command("load obj 83445", "You have created")
        save(actor, CHARACTER)
        bag = next(
            row[0]
            for row in game.inventory(PID)
            if row[0] not in before and row[1] == 83445
        )
        setup = {"bag": bag}
        manifest.write_text(json.dumps(setup))
        command("open " + selector(actor, bag))
    bag = setup["bag"]
    if not (targets <= {row["uid"] for row in stored()}):
        command("remove all")
        save(actor, CHARACTER)
        for uid in targets:
            item = next(row for row in game.items(PID) if int(row[0]) == uid)
            if item[5] == "-1":
                put(actor, uid, bag)
        save(actor, CHARACTER)
        setup["graph"] = inventory_graph(game.inventory(PID))
        manifest.write_text(json.dumps(setup))
        counter()
        enter()
        command("drop " + selector(actor, bag), "You drop")
        leave()
        held = wait_stored(True)
        assert all(
            row.get("named_origin") == "1325" for row in held if row["uid"] in targets
        )
        assert targets.isdisjoint(int(row[0]) for row in game.items(PID))
        print(
            "Funded native locker entry/deposit claimed the marked tree and removed it from player custody",
            flush=True,
        )
    game.stop()
    actor = game.boot("named-locker-reboot", account=ACCOUNT, character=CHARACTER)
    held = wait_stored(True)
    expected = setup["graph"]
    assert all(row["slot"] == -1 for row in held), held
    actual = {str(row["uid"]): [row["vnum"], row["parent_uid"], 0] for row in held}
    assert actual == expected
    assert all(
        row.get("named_origin") == "1325" for row in held if row["uid"] in targets
    )
    counter()
    enter()
    command("get collector", "You get")
    save(actor, CHARACTER)
    assert inventory_graph(game.inventory(PID)) == expected
    leave()
    wait_stored(False)
    game.stop()
    game.prepare_mortal(PID)
    actor = game.boot("named-locker-return", account=ACCOUNT, character=CHARACTER)
    baseline = json.loads((game.runtime / "named-transfer-result.json").read_text())[
        "baseline"
    ]
    expect_max_hp(actor, baseline)
    for uid in source["uids"]:
        get_from_container(actor, uid, bag)
        command("wear " + selector(actor, uid))
    text = expect_max_hp(actor, baseline + 5)
    assert "armor (" in text
    save(actor, CHARACTER)
    before = {int(row[0]): row[:4] for row in game.items(PID)}
    game.stop()
    actor = game.boot("named-locker-worn-reboot", account=ACCOUNT, character=CHARACTER)
    expect_max_hp(actor, baseline + 5)
    save(actor, CHARACTER)
    assert {int(row[0]): row[:4] for row in game.items(PID)} == before
    assert not stored()
    final = game.items() + game.items(PID)
    assert prior.items() <= {row[0]: row[1] for row in final}.items()
    (game.runtime / "named-locker-result.json").write_text(
        json.dumps(
            {
                "locker": LOCKER,
                "uids": sorted(targets),
                "graph_items": len(expected),
                "baseline": baseline,
            }
        )
    )
    print(
        "Native locker boot/retrieval retained the exact graph; original set restored +5 HP/Armor and exact slots after reboot",
        flush=True,
    )
finally:
    game.stop()
    (game.runtime / "named-locker-funded-transcript.txt").write_bytes(
        b"\n".join(game.transcripts)
    )
