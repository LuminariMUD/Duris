#!/usr/bin/env python3
"""Native player death, corpse reboot, looting and named-set recovery."""

import json
import subprocess
import time
import test_flatfile_combat_journey as journey
from named_set_gameplay import (
    NamedSetGame,
    score,
    save,
    selector,
    expect_max_hp,
    get_from_container,
    inventory_graph,
)

ACCOUNT, CHARACTER, PID = "Namedguest", "Meranen", 2
game = NamedSetGame()
source = json.loads((game.runtime / "named-transfer-setup.json").read_text())
copies = json.loads((game.runtime / "named-edit-clone-setup.json").read_text())
targets = set(source["uids"] + copies["clones"])
manifest = game.runtime / "named-corpse-setup.json"
assert journey.INSPECTOR.is_file(), "build the maintained flat-file inspector first"
builder = actor = None


def world_rows():
    return json.loads(
        subprocess.check_output(
            [str(journey.INSPECTOR), str(game.state), "inspect-world-items", "1252"],
            text=True,
        )
    )["items"]


def corpse_items():
    return {row["uid"]: row for row in world_rows() if row["uid"] in targets}


def graph():
    return inventory_graph(game.inventory(PID))


def command(client, text, expected=None):
    client.send(text)
    if expected:
        client.expect(expected, timeout=30)
    score(client)


try:
    prior = {row[0]: row[1] for row in game.items() + game.items(PID)}
    setup = json.loads(manifest.read_text()) if manifest.exists() else None
    recovered = bool(
        setup
        and setup.get("death_saved")
        and not corpse_items()
        and graph() == setup["graph"]
    )
    journey.make_overlord(game.state, journey.CHARACTER)
    if not corpse_items() and not recovered:
        assert targets <= {int(row[0]) for row in game.items(PID)}, (
            "inspect any partial recovery before creating another death"
        )
        journey.make_overlord(game.state, CHARACTER)
        builder = game.boot("named-corpse-prepare")
        actor = game.login(
            account=ACCOUNT, character=CHARACTER, source_host="127.0.0.2"
        )
        command(actor, "vis 0")
        command(actor, "remove all")
        command(actor, "open " + selector(actor, source["outer"]))
        command(actor, "put all " + selector(actor, source["outer"]))
        save(actor, CHARACTER)
        manifest.write_text(json.dumps({"graph": graph(), "targets": sorted(targets)}))
        save(builder)
        game.stop()
        game.prepare_mortal(PID)
    setup = json.loads(manifest.read_text())
    if not recovered:
        builder = game.boot("named-corpse-death")
    if not corpse_items() and not recovered:
        actor = game.login(
            account=ACCOUNT, character=CHARACTER, source_host="127.0.0.2"
        )
        command(builder, "vis 0")
        command(builder, "goto 132500")
        command(builder, "transfer " + CHARACTER)
        assert "Level: 56" in score(actor)[1]
        builder.send("kill " + CHARACTER)
        builder.expect("rip out", timeout=30)
        actor.expect("ACCOUNT MENU", timeout=45)
        deadline = time.monotonic() + 30
        while True:
            records = corpse_items()
            if set(records) == targets and not (
                targets & {int(row[0]) for row in game.items(PID)}
            ):
                break
            assert time.monotonic() < deadline, records
            time.sleep(0.2)
        assert all(row.get("named_origin") == "1325" for row in records.values())
        print(
            "Native death persisted all six exact named UIDs/origins in the player corpse and removed them from the player",
            flush=True,
        )
        setup["death_saved"] = True
        manifest.write_text(json.dumps(setup))
    game.stop()
    game.prepare_mortal(PID)
    builder = game.boot("named-corpse-reboot")
    records = corpse_items()
    if recovered:
        assert not records
    else:
        assert set(records) == targets and all(
            row.get("named_origin") == "1325" for row in records.values()
        )
        setup["death_saved"] = True
        manifest.write_text(json.dumps(setup))
    actor = game.login(account=ACCOUNT, character=CHARACTER, source_host="127.0.0.2")
    command(builder, "vis 0")
    command(builder, "goto 132500")
    command(builder, "transfer " + CHARACTER)
    if not recovered:
        command(actor, "look in " + CHARACTER, "collector")
        command(actor, "get all " + CHARACTER, "You get ")
    save(actor, CHARACTER)
    assert graph() == setup["graph"], (
        "the complete nested inventory graph must survive the corpse"
    )
    assert not corpse_items(), "corpse custody must release recovered UIDs"
    restored_named = {int(row[0]): row for row in game.items(PID)}
    assert targets <= restored_named.keys() and all(
        restored_named[uid][1] == "1325" for uid in targets
    )
    for uid in source["uids"]:
        get_from_container(actor, uid, source["outer"])
    save(actor, CHARACTER)
    baseline = json.loads((game.runtime / "named-transfer-result.json").read_text())[
        "baseline"
    ]
    for uid in source["uids"]:
        command(actor, "wear " + selector(actor, uid))
    text = expect_max_hp(actor, baseline + 5)
    assert "armor (" in text
    save(actor, CHARACTER)
    before = {int(row[0]): row[:4] for row in game.items(PID)}
    game.stop()
    actor = game.boot(
        "named-corpse-return-reboot", account=ACCOUNT, character=CHARACTER
    )
    expect_max_hp(actor, baseline + 5)
    save(actor, CHARACTER)
    assert {int(row[0]): row[:4] for row in game.items(PID)} == before
    assert (
        prior.items()
        <= {row[0]: row[1] for row in game.items() + game.items(PID)}.items()
    )
    assert not corpse_items()
    (game.runtime / "named-corpse-result.json").write_text(
        json.dumps(
            {
                "uids": sorted(targets),
                "origin": 1325,
                "graph_items": len(setup["graph"]),
                "baseline": baseline,
            }
        )
    )
    print(
        "Native corpse boot/loot retained the full graph; returned pieces restored +5 HP/Armor and exact slots after reboot",
        flush=True,
    )
finally:
    game.stop()
    (game.runtime / "named-corpse-transcript.txt").write_bytes(
        b"\n".join(game.transcripts)
    )
