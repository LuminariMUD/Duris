#!/usr/bin/env python3
"""Native visible-name editing, recursive cloning, wear and reboot proof."""

import json
import test_flatfile_combat_journey as journey
from named_set_gameplay import NamedSetGame, score, save, selector, put, expect_max_hp

ACCOUNT, CHARACTER, PID = "Namedguest", "Meranen", 2
game = NamedSetGame()
source = json.loads((game.runtime / "named-transfer-setup.json").read_text())
manifest = game.runtime / "named-edit-clone-setup.json"
setup = json.loads(manifest.read_text()) if manifest.exists() else {}
originals = source["uids"]
names = dict(
    zip(
        originals,
        (
            "a plain verification helm",
            "a plain verification coat",
            "some plain verification leggings",
        ),
    )
)
actor = None


def command(text, expected=None):
    actor.send(text)
    if expected:
        actor.expect(expected, timeout=30)
    score(actor)


def unpack(outer, inner):
    for uid in (outer, inner):
        rows = game.inventory(PID)
        index = next(i for i, row in enumerate(rows) if row[0] == uid)
        if any(row[2] == index for row in rows):
            command("get all " + selector(actor, uid), "You get")
            save(actor, CHARACTER)


def expect_tree(outer, inner, children):
    rows = game.inventory(PID)
    outer_index = next(i for i, row in enumerate(rows) if row[0] == outer)
    inner_index = next(i for i, row in enumerate(rows) if row[0] == inner)
    assert rows[inner_index][2] == outer_index
    assert all(
        next(row for row in rows if row[0] == uid)[2] == inner_index for uid in children
    )


def expect_names():
    rows = {int(row[0]): row for row in game.items(PID)}
    for uid in originals:
        assert rows[uid][1] == "1325" and rows[uid][6] == names[uid]
    for uid in setup.get("clones", []):
        assert rows[uid][1] == "1325" and rows[uid][6] in names.values()


try:
    prior = {row[0]: row[1] for row in game.items() + game.items(PID)}
    assert set(originals) <= {int(row[0]) for row in game.items(PID)}
    game.make_overlord(CHARACTER)
    actor = game.boot("named-edit-clone-prepare", account=ACCOUNT, character=CHARACTER)
    command("vis 0")
    command("remove all")
    save(actor, CHARACTER)
    unpack(source["outer"], source["inner"])
    if setup:
        unpack(setup["outer"], setup["inner"])
    for uid in originals:
        command("string obj " + selector(actor, uid) + " short " + names[uid], "Ok.")
    save(actor, CHARACTER)
    expect_names()
    for uid in originals:
        put(actor, uid, source["inner"])
    put(actor, source["inner"], source["outer"])
    save(actor, CHARACTER)
    expect_tree(source["outer"], source["inner"], originals)
    if not setup:
        before = {row[0] for row in game.inventory(PID)}
        command(
            "clone obj " + selector(actor, source["outer"]) + " 1",
            "You make a clone of",
        )
        save(actor, CHARACTER)
        added = [row for row in game.inventory(PID) if row[0] not in before]
        assert len(added) == 5, added
        setup = {
            "outer": next(row[0] for row in added if row[1] == 83445),
            "inner": next(row[0] for row in added if row[1] == 4917),
            "clones": [
                int(row[0]) for row in game.items(PID) if int(row[0]) not in before
            ],
        }
        assert len(setup["clones"]) == 3 and set(setup["clones"]).isdisjoint(originals)
        manifest.write_text(json.dumps(setup))
    else:
        for uid in setup["clones"]:
            put(actor, uid, setup["inner"])
        put(actor, setup["inner"], setup["outer"])
        save(actor, CHARACTER)
    expect_names()
    expect_tree(setup["outer"], setup["inner"], setup["clones"])
    print(
        "Native string edits removed visible zone cues; recursive clone minted five distinct UIDs with three preserved origins",
        flush=True,
    )
    game.stop()
    game.prepare_mortal(PID)
    actor = game.boot("named-edit-clone-reboot", account=ACCOUNT, character=CHARACTER)
    save(actor, CHARACTER)
    expect_names()
    expect_tree(source["outer"], source["inner"], originals)
    expect_tree(setup["outer"], setup["inner"], setup["clones"])
    baseline = score(actor)[0]
    unpack(setup["outer"], setup["inner"])
    for uid in setup["clones"]:
        command("wear " + selector(actor, uid))
    text = expect_max_hp(actor, baseline + 5)
    assert "armor (" in text
    save(actor, CHARACTER)
    assert not game.affects(1, PID)
    unpack(source["outer"], source["inner"])
    copied_head = next(
        int(row[0])
        for row in game.items(PID)
        if int(row[0]) in setup["clones"] and int(row[3]) & 16
    )
    command("remove " + selector(actor, copied_head))
    text = expect_max_hp(actor, baseline)
    assert "armor (" not in text
    command("wear " + selector(actor, originals[0]))
    expect_max_hp(actor, baseline + 5)
    save(actor, CHARACTER)
    worn = {int(row[0]): row[:4] for row in game.items(PID)}
    game.stop()
    actor = game.boot(
        "named-edit-clone-worn-reboot", account=ACCOUNT, character=CHARACTER
    )
    text = expect_max_hp(actor, baseline + 5)
    assert "armor (" in text
    save(actor, CHARACTER)
    expect_names()
    restored = {int(row[0]): row for row in game.items(PID)}
    assert all(restored[uid][:4] == fields for uid, fields in worn.items())
    final = game.items() + game.items(PID)
    assert prior.items() <= {row[0]: row[1] for row in final}.items()
    inventory = game.inventory() + game.inventory(PID)
    assert len(inventory) == len({row[0] for row in inventory})
    (game.runtime / "named-edit-clone-result.json").write_text(
        json.dumps(
            {
                "originals": originals,
                "clones": setup["clones"],
                "baseline": baseline,
                "origins_retained": len(final),
            }
        )
    )
    print(
        "Renamed clones and a mixed original/clone outfit retained +5 HP, Armor, exact slots and origins after reboot",
        flush=True,
    )
finally:
    game.stop()
    (game.runtime / "named-edit-clone-transcript.txt").write_bytes(
        b"\n".join(game.transcripts)
    )
