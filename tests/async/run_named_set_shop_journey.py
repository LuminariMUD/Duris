#!/usr/bin/env python3
"""Native mortal sale, shop reboot, repurchase and set recovery on retained flat-file state."""

import json
import subprocess
import time

import test_flatfile_combat_journey as journey
from named_set_gameplay import NamedSetGame, expect_max_hp, save, score, selector
from run_shop_reboot_stock_journey import build_inspector

ACCOUNT, CHARACTER, PID = "Namedguest", "Meranen", 2
ROOM, KEEPER = 132500, 132617
game = NamedSetGame()
inspector = build_inspector()
source = json.loads((game.runtime / "named-transfer-setup.json").read_text())
originals = source["uids"]
uid = originals[0]
manifest = game.runtime / "named-shop-setup.json"
setup = json.loads(manifest.read_text()) if manifest.exists() else {}
actor = None


def stock():
    rows = subprocess.check_output(
        [str(inspector), str(game.state), str(ROOM), str(KEEPER), "named"], text=True
    )
    return {int(fields[0]): [int(value) for value in fields[1:5]] + [fields[5]]
            for line in rows.splitlines() if (fields := line.split("\t"))}


def wait_stock(present):
    deadline = time.monotonic() + 45
    while True:
        rows = stock()
        if (uid in rows) == present:
            return rows
        assert time.monotonic() < deadline, (uid, present)
        time.sleep(.2)


def command(text, expected=None):
    actor.send(text)
    if expected:
        actor.expect(expected, timeout=30)
    return score(actor)[1]


try:
    if uid not in stock():
        journey.make_overlord(game.state, CHARACTER)
        actor = game.boot("named-shop-prepare", account=ACCOUNT, character=CHARACTER)
        command("vis 0")
        save(actor, CHARACTER)
        if not setup:
            setup["slots"] = {row[0]: row[2] for row in game.items(PID) if int(row[0]) in originals}
            assert len(setup["slots"]) == 3 and all(int(slot) for slot in setup["slots"].values())
            manifest.write_text(json.dumps(setup, indent=2))
        # String resolves carried/floor items, not equipment.
        command("remove " + selector(actor, uid))
        command("string obj " + selector(actor, uid) + " name namedshopwitness", "Ok.")
        god = game.login()
        god.send("goto " + str(ROOM))
        score(god)
        god.send("transfer " + CHARACTER)
        god.expect("Ok.")
        score(god)
        # Reuse the maintained shop journey's native staff funding fixture.
        god.send("setbit char " + CHARACTER + " platinum 100000")
        score(god)
        save(actor, CHARACTER)
        manifest.write_text(json.dumps(setup, indent=2))
        game.stop()
        game.prepare_mortal(PID)
        actor = game.boot("named-shop-sale", account=ACCOUNT, character=CHARACTER)
        assert "Level: 56" in score(actor)[1]
        command("sell namedshopwitness", "gives you")
        save(actor, CHARACTER)
        held = wait_stock(True)[uid]
        assert held[1] == 0 and held[4] == "1325", held
        assert uid not in {int(row[0]) for row in game.items(PID)}
        setup["stock"] = held
        manifest.write_text(json.dumps(setup, indent=2))
        print("Native mortal sale durably moved the exact marked UID into shop payload", uid, flush=True)
        game.stop()

    actor = game.boot("named-shop-reload", account=ACCOUNT, character=CHARACTER)
    assert wait_stock(True)[uid] == setup["stock"]
    command("buy namedshopwitness", "You now have")
    save(actor, CHARACTER)
    wait_stock(False)
    item = next(row for row in game.items(PID) if int(row[0]) == uid)
    assert item[1] == "1325"
    command("remove all")
    time.sleep(6)
    baseline = score(actor)[0]
    for piece in originals:
        command("wear " + selector(actor, piece))
    assert "armor (" in expect_max_hp(actor, baseline + 5)
    save(actor, CHARACTER)
    assert {row[0]: row[2] for row in game.items(PID) if int(row[0]) in originals} == setup["slots"]
    assert not game.affects(1, PID)
    game.stop()
    actor = game.boot("named-shop-wear-reboot", account=ACCOUNT, character=CHARACTER)
    assert "armor (" in expect_max_hp(actor, baseline + 5)
    save(actor, CHARACTER)
    rows = [row for row in game.items(PID) if int(row[0]) in originals]
    assert all(row[1] == "1325" for row in rows)
    assert {row[0]: row[2] for row in rows} == setup["slots"]
    assert uid not in stock()
    print("Shop reboot, paid repurchase and player reboot retained UID/origin/slots and Armor/+5 HP", uid, flush=True)
finally:
    game.stop()
    (game.runtime / "named-shop-transcript.txt").write_bytes(b"\n\n".join(game.transcripts))
