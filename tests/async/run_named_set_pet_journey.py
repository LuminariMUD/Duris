#!/usr/bin/env python3
"""Native marked gear in pet-held containers, owner reboots and recovery."""

import json
import test_mariadb_combat_journey as journey
from named_set_gameplay import NamedSetGame, score, save, selector, put, expect_max_hp

ACCOUNT, CHARACTER, PID = "Namedguest", "Meranen", 2
PET_VNUM = 74132
game = NamedSetGame()
source = json.loads((game.runtime / "named-transfer-setup.json").read_text())
copies = json.loads((game.runtime / "named-edit-clone-setup.json").read_text())
uid, bag = source["uids"][1], source["inner"]
actor = None


def command(text, expected=None):
    actor.send(text)
    if expected:
        actor.expect(expected, timeout=30)
    score(actor)


def pet_rows():
    rows = [row for row in game.pets(PID) if row[2] == PET_VNUM]
    assert sum(row[3] == 0 for row in rows) == 1, rows
    assert all(row[7] == 0 for row in rows), rows
    return rows


def expect_held():
    rows = [row for row in pet_rows() if row[3]]
    index = next(i for i, row in enumerate(rows) if row[3] == bag)
    item = next(row for row in rows if row[3] == uid)
    assert item[4] == 1325 and item[5] == index and item[6] == 0, rows
    assert uid not in {row[0] for row in game.inventory(PID)}
    return rows


try:
    prior = {row[0]: row[1] for row in game.items() + game.items(PID)}
    for row in game.pets(PID):
        if row[4]:
            prior[str(row[3])] = str(row[4])
    # Give cannot accept consent to an NPC. Keep this controlled witness
    # portable while retaining its UID, origin, affects and equipment slots.
    game.sql("UPDATE player_items SET weight=1 WHERE pid=2 AND obj_uid=" + str(uid))
    game.sql("UPDATE player_pet_items i JOIN player_pets p ON p.id=i.pet_id "
             "SET i.weight=1 WHERE p.owner_pid=2 AND i.obj_uid=" + str(uid))
    game.make_overlord(CHARACTER)
    actor = game.boot("named-pet-prepare", account=ACCOUNT, character=CHARACTER)
    # Retain reward satchels created by earlier fixture preparation, freeing
    # mortal inventory slots through the ordinary container path.
    for row in game.inventory(PID):
        if row[1] == 400222 and row[2] == -1:
            put(actor, row[0], copies["outer"])
    if not any(row[2] == PET_VNUM for row in game.pets(PID)):
        command("givepet " + CHARACTER + " cat", "rubs up against your leg")
        save(actor, CHARACTER)
    if not any(row[3] == uid for row in pet_rows()):
        item = next(row for row in game.items(PID) if int(row[0]) == uid)
        if int(item[2]):
            command("remove " + selector(actor, uid), "You stop using")
        put(actor, uid, bag)
        command("give " + selector(actor, bag) + " cat", "Ok.")
        save(actor, CHARACTER)
    expected = expect_held()
    rewards = {row[0] for row in game.inventory(PID) if row[1] == 400222}
    game.stop()
    game.prepare_mortal(PID)
    for cycle in range(2):
        actor = game.boot(
            "named-pet-reboot-" + str(cycle), account=ACCOUNT, character=CHARACTER
        )
        command("look", "fat cat")
        save(actor, CHARACTER)
        assert expect_held() == expected
        assert {row[0] for row in game.inventory(PID) if row[1] == 400222} == rewards
        print(
            f"Pet restart {cycle + 1}: active cat, exact nested item UID/origin/slot retained",
            flush=True,
        )
        if cycle == 0:
            game.stop()
    command("order cat give backpack " + CHARACTER, "gives you")
    save(actor, CHARACTER)
    assert any(row[0] == bag for row in game.inventory(PID))
    command("get all " + selector(actor, bag), "You get")
    save(actor, CHARACTER)
    assert not any(row[3] == uid for row in pet_rows())
    assert next(row for row in game.items(PID) if int(row[0]) == uid)[1] == "1325"
    worn_body = next(
        (row for row in game.items(PID) if int(row[2]) and int(row[3]) & 8), None
    )
    if worn_body:
        command("remove " + selector(actor, int(worn_body[0])), "You stop using")
    # Compare against the receiver baseline already measured by the transfer journey.
    baseline = json.loads((game.runtime / "named-transfer-result.json").read_text())[
        "baseline"
    ]
    expect_max_hp(actor, baseline)
    command("wear " + selector(actor, uid))
    text = expect_max_hp(actor, baseline + 5)
    assert "armor (" in text
    save(actor, CHARACTER)
    before = {int(row[0]): row[:4] for row in game.items(PID)}
    game.stop()
    actor = game.boot("named-pet-return-reboot", account=ACCOUNT, character=CHARACTER)
    expect_max_hp(actor, baseline + 5)
    save(actor, CHARACTER)
    assert {int(row[0]): row[:4] for row in game.items(PID)} == before
    assert {row[0] for row in game.inventory(PID) if row[1] == 400222} == rewards
    final = {row[0]: row[1] for row in game.items() + game.items(PID)}
    assert prior.items() <= final.items()
    inventory = game.inventory() + game.inventory(PID)
    pet_items = [row[3] for row in game.pets(PID) if row[3]]
    all_uids = [row[0] for row in inventory] + pet_items
    assert len(all_uids) == len(set(all_uids))
    (game.runtime / "named-pet-result.json").write_text(
        json.dumps(
            {
                "uid": uid,
                "bag": bag,
                "pet_vnum": PET_VNUM,
                "origin": 1325,
                "restarts": 2,
            }
        )
    )
    print(
        "Native pet give/get recovered the same origin; wear and final reboot restored +5 HP and Armor",
        flush=True,
    )
finally:
    game.stop()
    (game.runtime / "named-pet-transcript.txt").write_bytes(
        b"\n".join(game.transcripts)
    )
