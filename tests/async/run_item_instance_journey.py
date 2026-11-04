#!/usr/bin/env python3
"""Exercise crafted-item give and the essence cap through real MariaDB relog/restart."""
import re
import sys
from pathlib import Path

import test_flatfile_combat_journey as journey
from run_world_restart_journey import ROOT, Rig

CRAFTED = 16384
ENHANCED = 262144
SPARSE_UID = 800000000011
CRAFTED_UID = 800000000012


def install_prototypes(rig):
    mini = rig.game / "areas_mini/mini.obj"
    prototypes = []
    for vnum, source in ((98961, "tezcat"), (400251, "tradeskills")):
        text = (ROOT / f"areas/obj/{source}.obj").read_text()
        prototypes.append(re.search(rf"^#{vnum}\n.*?(?=^#\d+\n|^\$~)", text,
                                    re.MULTILINE | re.DOTALL).group())
    mini.write_text(mini.read_text().replace("$~", "".join(prototypes) + "$~"))


def quit_character(client):
    client.send("quit")
    client.expect("ACCOUNT MENU", timeout=40)
    client.close()


def command(client, text, expected):
    client.pending.clear()
    client.send(text)
    client.expect(expected, timeout=20)


def run(binary):
    rig = Rig(binary, ["M 0 11 1 22800 100 0 0 0 * recipient for crafted item"], mobs=False)
    rig.env["REDIS_WORLD_STATE"] = "FALSE"
    client = None
    try:
        install_prototypes(rig)
        rig.boot()
        client = journey.MudClient(rig.port)
        journey.create_character(client)
        quit_character(client)
        pid = rig.sql(f"SELECT pid FROM player_data WHERE name='{journey.CHARACTER}'")
        values = [
            f"({pid},98961,{SPARSE_UID},'sparse test',9,1,100,0,0,0,0)",
            f"({pid},98961,{CRAFTED_UID},'crafted test',9,1,100,{CRAFTED | ENHANCED},5,6,42)",
        ] + [f"({pid},400251,{800000000020 + n},'essence',8,1,100,0,0,0,0)"
             for n in range(4)]
        rig.sql(f"UPDATE player_data SET platinum=400 WHERE pid={pid};"
                "INSERT INTO player_items(pid,vnum,obj_uid,name,item_type,wear_flags,"
                "item_condition,extra2_flags,anti_flags,anti2_flags,craftsmanship) VALUES "
                + ",".join(values) + ";"
                "INSERT INTO player_item_affects(item_id,affect_slot,location,modifier) "
                "SELECT id,0,35,2 FROM player_items "
                f"WHERE obj_uid={SPARSE_UID};")

        client = journey.reconnect_character(rig.port)
        refuse_give = "You may not give crafted/forged items to mobs."
        command(client, "give crafted raoul", refuse_give)
        for name in ("sparse", "enhanced", "enhanced"):
            command(client, f"enhance {name} essence", "Your enhancement is a success!")
        quit_character(client)

        def stored_state():
            wallet = rig.sql(f"SELECT copper,silver,gold,platinum FROM player_data WHERE pid={pid}")
            essence = rig.sql(f"SELECT GROUP_CONCAT(obj_uid ORDER BY obj_uid) FROM player_items "
                              f"WHERE pid={pid} AND vnum=400251")
            return wallet, essence

        before = stored_state()
        assert before[1] and "," not in before[1], before
        assert rig.sql("SELECT GROUP_CONCAT(CONCAT_WS(':',affect_slot,location,modifier) "
                       "ORDER BY affect_slot) FROM player_item_affects a "
                       "JOIN player_items i ON i.id=a.item_id "
                       f"WHERE i.obj_uid={SPARSE_UID}") == "0:35:2,1:0:0,2:34:3,3:0:0"
        rig.stop()
        rig.boot()
        client = journey.reconnect_character(rig.port)
        command(client, "give crafted raoul", refuse_give)
        command(client, "enhance enhanced essence", "Too much magic.")
        quit_character(client)
        assert stored_state() == before, "rejected enhancement consumed currency or an essence"
        assert rig.sql("SELECT extra2_flags,anti_flags,anti2_flags,craftsmanship FROM player_items "
                       f"WHERE obj_uid={CRAFTED_UID}") == f"{CRAFTED | ENHANCED}\t5\t6\t42"
        print("crafted NPC-give restriction, instance fields and essence cap survived SQL restart")
    finally:
        if client:
            client.close()
        rig.close()


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve())
