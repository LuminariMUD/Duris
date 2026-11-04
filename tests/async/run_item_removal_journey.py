#!/usr/bin/env python3
"""Trace item removal on disposable SQL. Run make world before the full-world boot."""
from pathlib import Path
import re
import sys

import test_flatfile_combat_journey as journey
from run_world_restart_journey import Rig

UPGRADE_UID = 800000000041
SCRAP_UID = 800000000042
BAIT_UID = 800000000043
DONOR_UID = 800000000044
HEAVY_UID = 800000000045
THIEF_COUNT = 48


def run(binary):
    rig = Rig(binary, [], mobs=False)
    rig.env["REDIS_WORLD_STATE"] = "FALSE"
    client = None
    try:
        def records():
            return [line for line in rig.log("file").splitlines() if "domain=item_removal " in line]

        def item_records(uid):
            return [line for line in records() if f" uid={uid} " in line]

        def quit_character():
            client.send("quit")
            client.expect("ACCOUNT MENU", timeout=40)
            client.close()

        rig.boot("-d", str(rig.game))
        client = journey.MudClient(rig.port)
        journey.create_character(client, expected_room=None)
        quit_character()
        pid = rig.sql(f"SELECT pid FROM player_data WHERE name='{journey.CHARACTER}'")
        rows = [
            (678, UPGRADE_UID, "upgrade", 17, 100, 3),
            (679, DONOR_UID, "donor", 17, 100, 3),
            (678, SCRAP_UID, "broken", 17, 0, 3),
            (678, BAIT_UID, "bait", 17, 100, 0),
            (678, HEAVY_UID, "heavy", 17, 100, 10000),
        ]
        rig.sql(f"UPDATE player_data SET level=20,platinum=400 WHERE pid={pid};"
                f"DELETE FROM player_items WHERE pid={pid};"
                "INSERT INTO player_items(pid,vnum,obj_uid,name,item_type,wear_flags,"
                "item_condition,weight) VALUES " +
                ",".join(f"({pid},{vnum},{uid},'{name}',9,{wear},{condition},{weight})"
                         for vnum, uid, name, wear, condition, weight in rows))
        client = journey.reconnect_character(rig.port, expected_room=None)
        client.expect("Pos: standing >", timeout=20)
        client.send("wear broken")
        client.expect("falls to the ground in scraps.", timeout=20)
        client.send("enhance upgrade upgrade")
        client.expect("cannot enhance an item with itself", timeout=20)
        client.send("enhance upgrade donor")
        client.expect("Your enhancement is a success!", timeout=20)
        quit_character()

        assert len(item_records(SCRAP_UID)) == 1, records()
        assert "cause=scrap" in item_records(SCRAP_UID)[0]
        assert f"holder_pid={pid} " in item_records(SCRAP_UID)[0]
        replacement, = item_records(UPGRADE_UID)
        assert "cause=enhance_replacement" in replacement and f"destination_pid={pid} " in replacement
        result_uid = int(re.search(r"\bresult_uid=(\d+)", replacement).group(1))
        assert result_uid and result_uid != UPGRADE_UID
        assert rig.sql(f"SELECT pid FROM player_items WHERE obj_uid={result_uid}") == pid
        assert rig.sql(f"SELECT pid FROM player_items WHERE obj_uid={BAIT_UID}") == pid
        assert not item_records(BAIT_UID) and not item_records(HEAVY_UID), records()
        rig.stop()

        mob = rig.game / "areas_mini/mini.mob"
        # Use the vnum bound to the production thief special. It stays in the
        # room, and the crowd makes waiting for a real equipment roll practical.
        thief = """#40053
test thief~
a test thief~
A test thief waits here.
~
~
11 0 0 0 0 0 0 0 S
PH 0 0 -1
25 0 0 20d20+100 1d1+1
0.0.0.0 0
8 8 0
"""
        mob.write_text(mob.read_text().replace("$~", thief + "$~"))
        zone = rig.game / "areas_mini/mini.zon"
        reset = f"M 0 40053 {THIEF_COUNT} 22800 100 0 0 0 * test thief\n" * THIEF_COUNT
        zone.write_text(zone.read_text().replace("\nS\n", "\n" + reset + "S\n"))
        rig.sql(f"DELETE FROM player_items WHERE obj_uid={result_uid};"
                f"UPDATE player_data SET last_room=22800 WHERE pid={pid};"
                f"UPDATE player_items SET equip_slot=7 WHERE obj_uid={BAIT_UID}")
        rig.boot("--minimal")
        client = journey.reconnect_character(rig.port)
        rig.wait_for("no thief moved the bait", 150, lambda: item_records(BAIT_UID))
        theft, = item_records(BAIT_UID)
        assert "cause=npc_theft" in theft and "room=22800 source=worn" in theft
        assert "source_slot=6 " in theft
        assert f"holder_pid={pid} " in theft and "destination_mob_vnum=40053 " in theft
        assert f"result_uid={BAIT_UID} result_vnum=678" in theft
        quit_character()
        assert rig.sql(f"SELECT COUNT(*) FROM player_items WHERE obj_uid={BAIT_UID}") == "0"
        assert rig.sql(f"SELECT pid FROM player_items WHERE obj_uid={HEAVY_UID}") == pid
        assert not item_records(HEAVY_UID), records()
        assert len(item_records(BAIT_UID)) == 1, records()
        print("scrap and replacement emitted one record each, and theft UID matched the next rent")
    finally:
        if client:
            client.close()
        rig.close()


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve())
