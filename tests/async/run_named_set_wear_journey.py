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

from named_set_gameplay import WEAR_CASES as CASES

zone = int(sys.argv[1]) if len(sys.argv) == 2 else 1325
generation_room, pieces, effect, spell = CASES[zone]
game = NamedSetGame()
runtime = game.runtime
client = None


def expect_set(count):
    # Vitality at capped cast level 56 adds its own 4 * 56 HP, separately
    # from the basic five HP per piece beyond two.
    spell_hp = 224 if zone == 824 and count >= 6 else 0
    text = expect_max_hp(client, baseline + max(0, count - 2) * 5 + spell_hp)
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


try:
    # Validate the synthetic authority and retain all earlier named identities,
    # including gear packed into nested containers by preceding cases.
    prior_origins = {row[0]: row[1] for row in game.items()}
    game.make_overlord()
    client = game.boot("named-generation")
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
    if zone == 824:
        client.send("load obj 2800")
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
        if len(chosen) >= 3:
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
    if zone == 824:
        # A level 22 Vitality potion once replaced this grant and could kill the wearer.
        deadline = time.monotonic() + 600
        while True:
            offset = len(client.transcript)
            client.send("quaff potion")
            score(client)
            output = client.transcript[offset:].decode(errors="replace")
            if "Nothing new seems to happen." in output:
                break
            assert ("another potion would do you any good yet" in output or
                    "almost ready to try another potion" in output), output
            assert time.monotonic() < deadline, "the potion cooldown never ended"
            time.sleep(5)
        expect_set(pieces)
    if zone == 87:
        assert not game.affects(41), "set Haste must not persist as an ordinary affect"
    if zone != 1325:
        client.send("remove " + selector(client, chosen[-1]))
        expect_set(pieces - 1)
        client.send("remove all")
        expect_set(0)
        save(client)
        if zone == 13:
            # The set's proc rejects Phantom Armor under ordinary Armor, silently.
            # The retained potion timer lasts three normal ticks; cold boots
            # restart the tick phase. Wait for native expiry without clearing it.
            deadline = time.monotonic() + 600
            while True:
                offset = len(client.transcript)
                client.send("quaff solution")
                score(client)
                if b"Bands of magic armor wrap around you!" in client.transcript[offset:]:
                    break
                assert time.monotonic() < deadline, "the potion cooldown never ended"
                time.sleep(5)
            for uid in chosen:
                client.send("wear " + selector(client, uid))
                score(client)
            offset = len(client.transcript)
            time.sleep(35)
            score(client)
            assert b"already affected" not in client.transcript[offset:]
            assert not game.affects(spell), "the rejected set effect must not apply"
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
        client.send("remove " + selector(client, uid))
        score(client)
    text = expect_max_hp(client, baseline + 5)
    assert "armor (" in text and "endurance (" not in text, text
    print(
        "Native five-piece save/reboot retained all UIDs, origins, wear slots and Endurance; returning to three cleaned Endurance",
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
    game.stop()
    (runtime / f"named-zone-{zone}-transcript.txt").write_bytes(
        b"\n".join(game.transcripts)
    )
