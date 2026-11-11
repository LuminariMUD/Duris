#!/usr/bin/env python3
"""Native wear/cast/reboot gate using a prepared, private full-world authority.

Run from the repository root after building the MariaDB server and preparing
the runtime described in the named-zone-set implementation plan. The existing
synthetic account and generated item identities are retained between attempts.
This is deliberately a full-server journey, not a stubbed spell fixture.
"""

import json
import re
import sys
import time
import test_mariadb_combat_journey as journey
from named_set_gameplay import NamedSetGame, score, save, selector, expect_max_hp

from named_set_gameplay import WEAR_CASES as CASES, SET_TIERS

zone = int(sys.argv[1]) if len(sys.argv) == 2 else 1325
generation_room, pieces, effect, spell = CASES[zone]
game = NamedSetGame()
runtime = game.runtime
client = None
form_case = {883: (3, 25, "fire form"), 1424: (2, -10, "water form")}.get(zone)
form_max_hp = {}


def constitution():
    client.send("attributes")
    text = client.expect("Character attributes for")
    text += client.expect("Pos:") + client.expect(">")
    return int(re.search(r"Con:\s*(\d+)", text)[1])


def expect_set(count):
    expected={name:count>=threshold for threshold,name,spell_id in SET_TIERS.get(zone,[])
              if spell_id not in (78,)} # Conjure Elemental has a pet, not a timed wearer buff.
    deadline=time.monotonic()+20
    while True:
        active_form = form_case and count >= pieces
        text=score(client)[1] if active_form else expect_max_hp(client,baseline+max(0,count-2)*5)
        if all((name+" (" in text)==present for name,present in expected.items()):
            if form_case:
                assert constitution()==baseline_con+(form_case[1] if active_form else 0)
                if active_form:
                    maximum=score(client)[0]
                    if count in form_max_hp:assert form_max_hp[count]==maximum
                    form_max_hp[count]=maximum
            return text
        assert time.monotonic()<deadline,(zone,count,expected,text)
        time.sleep(.5)


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
    assert (row and effect in row[0].lower()) if zone in SET_TIERS else not row, (zone,row,text)


try:
    # Validate the synthetic authority and retain all earlier named identities,
    # including gear packed into nested containers by preceding cases.
    prior_origins = {row[0]: row[1] for row in game.items()}
    game.make_overlord()
    if form_case:
        game.sql("UPDATE player_data SET m_class=2048,secondary_class=0,spec="+str(form_case[0])+" WHERE pid=1")
    client = game.boot("named-generation")
    client.send("toggle aggimmune on")
    score(client)
    client.send("vis 61")
    score(client)
    client.send("toggle paging no")
    score(client)
    client.send("goto 132500")
    score(client)
    client.send("remove all")
    score(client)
    save(client)
    existing = game.items()
    client.send("goto " + str(generation_room))
    _, text = score(client)
    assert "Level: 62" in text, text
    choices = []
    for slot, flag in (
        ("head", 16),
        ("body", 8),
        ("legs", 32),
        ("hands", 128),
        ("arms", 256),
        ("feet", 64),
        ("about", 1024),
        ("waist", 2048),
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
            save(client)
            existing = game.items()
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
            client.send("wear " + selector(client, uid))
            score(client)
            save(client)
        assert int(next(row for row in game.items() if int(row[0]) == uid)[2])
        selected.append(uid)
    client.send("load obj 83445")
    client.expect("You have created")
    client.send("open collector")
    client.expect("Ok.")
    client.send("put all collector")
    score(client)
    if zone in (1325, 13):
        client.send("load obj 39130")
        client.expect("You have created")
    # Wearing outside the generation zone also checks that room identity is irrelevant.
    client.send("goto 132500")
    score(client)
    save(client)
    game.stop()
    game.prepare_mortal()
    client = game.boot("named-mortal-wear")
    client.send("remove all")
    score(client)
    save(client)
    assert not any(int(row[2]) for row in game.items()), (
        "remove all must really empty the named wear slots"
    )
    time.sleep(6)
    baseline, text = score(client)
    baseline_con = constitution() if form_case else None
    assert "Level: 56" in text, text
    check_report()
    client.send("inventory")
    score(client)
    chosen = []
    for uid in selected:
        client.send("wear " + selector(client, uid))
        score(client)
        save(client)
        item = next(item for item in game.items() if int(item[0]) == uid)
        assert int(item[2]), ("native mortal wear failed", item)
        chosen.append(uid)
        if len(chosen) == 2:
            time.sleep(6)
            two, _ = score(client)
            assert two == baseline, ("two-piece HP", baseline, two)
        expect_set(len(chosen))
    print(
        f"#{zone}: native HP and all spell thresholds passed through {pieces} pieces",
        chosen,
        flush=True,
    )
    save(client)
    before = game.items()
    game.stop()
    client = game.boot("named-mortal-reboot")
    expect_set(pieces)
    save(client)
    after = game.items()
    restored_origins = {row[0]: row[1] for row in after}
    assert prior_origins.items() <= restored_origins.items(), (
        "earlier named items must survive nested-container saves and reboot"
    )
    for uid in chosen:
        old = next(row for row in before if int(row[0]) == uid)
        new = next(row for row in after if int(row[0]) == uid)
        assert old[:4] == new[:4], (old, new)
    assert not game.affects(spell), "set effect must not persist as an ordinary affect"
    if zone != 1325:
        client.send("remove " + selector(client, chosen[-1]))
        expect_set(pieces - 1)
        client.send("remove all")
        expect_set(0)
        save(client)
        (runtime / f"named-zone-{zone}-result.json").write_text(
            json.dumps(
                {
                    "zone": zone,
                    "baseline": baseline,
                    "uids": chosen,
                    "threshold": pieces,
                    "effect": effect,
                    "form_max_hp": form_max_hp,
                    "baseline_constitution": baseline_con,
                }
            )
        )
        print(
            f"#{zone}: native report, inventory, wear, save/reboot identity and removal passed",
            flush=True,
        )
        sys.exit(0)
    for uid in chosen[3:]:
        client.send("remove " + selector(client, uid))
        score(client)
    text = expect_max_hp(client, baseline + 5)
    assert "armor (" in text and "barkskin (" not in text, text
    print(
        "Native four-piece save/reboot retained all UIDs, origins, wear slots and Barkskin; returning to three cleaned Barkskin",
        flush=True,
    )
    client.send("quaff solution")
    client.expect("Bands of magic armor wrap around you!", timeout=20)
    score(client)
    save(client)
    ordinary = game.affects(1)
    assert len(ordinary) == 1, ordinary
    client.send("remove " + selector(client, chosen[2]))
    score(client)
    text = expect_max_hp(client, baseline)
    assert "armor (" in text, text
    save(client)
    assert len(game.affects(1)) == 1
    # The already ordinary Armor is present before this new set application.
    client.send("wear " + selector(client, chosen[2]))
    expect_max_hp(client, baseline + 5)
    client.send("remove " + selector(client, chosen[2]))
    expect_max_hp(client, baseline)
    save(client)
    saved_armor = game.affects(1)
    assert len(saved_armor) == 1 and saved_armor[0][1] <= ordinary[0][1]
    game.stop()
    client = game.boot("named-ordinary-reboot")
    _, text = score(client)
    assert "armor (" in text, text
    save(client)
    assert len(game.affects(1)) == 1
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
                "four_piece_max": baseline + 10,
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
    game.stop()
    (runtime / f"named-zone-{zone}-transcript.txt").write_bytes(
        b"\n".join(game.transcripts)
    )
