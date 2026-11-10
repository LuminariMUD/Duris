#!/usr/bin/env python3
"""Claim publication uses exact SQL identities, suppresses replay and retains refused sources."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function, rel

harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "economy/auction_command.h"
#include "player/player_load_items.h"
#include "player/player_snapshot_codec.h"
#include "world/object_template.h"
#include <cassert>
#include <string>
static obj_data item{};
static object_template prototype{};
P_obj object_list=nullptr;
static int mode, delivered, alerts, dirty;
static std::string output;
const object_template *find_object_template(int vnum) {
    assert(vnum==77);
    return mode==2 ? nullptr : &prototype;
}
bool player_load_item_graph_materialize_for_owner(P_char ch,
    const std::vector<player_item_snapshot> &items,
    const std::vector<player_load_item_identity> &identities,
    const item_owner_identity &owner,uint64_t revision,bool hydrate,bool complete,
    player_load_item_materialize_metrics *) {
    assert(mode!=1 && mode!=2 && mode!=4 && mode!=5);
    assert(items.size()==1 && items[0].object_uid==42 && identities.size()==1);
    assert(identities[0].database_id==901 && identities[0].item_uid==42);
    assert(identities[0].item_revision==2 && owner.id==44 && revision==5 && !hydrate && complete);
    if(mode==3) return false;
    ++delivered; item={}; item.obj_uid=42; item.db_item_id=901;
    item.loc_p=LOC_CARRIED; item.loc.carrying=ch; ch->carrying=&item; object_list=&item;
    return true;
}
void send_to_char(const char *message,P_char) { output+=message; }
void send_to_char_f(P_char,const char *,...) {}
void persistence_alert(int,const char *,const char *,const char *,const char *,
                       const char *reason,const char *,...) {
    assert(std::string(reason)=="source_retained"); ++alerts;
}
void mark_player_dirty_components(int,player_component_mask_t) { ++dirty; }
'''
harness += extract_function('auction_houses.c', 'bool auction_publish_item_claim(')
harness += r'''
int main() {
    char_data actor{},other{}; pc_only_data pc{}; pc.pid=44; actor.only.pc=&pc;
    auction_command_payload payload{}; payload.actor_pid=44; payload.item_count=1;
    payload.items[0]={42,1,77};
    player_item_snapshot snapshot{}; snapshot.object_uid=42; snapshot.vnum=77;
    snapshot.parent_index=PLAYER_SNAPSHOT_NO_PARENT; snapshot.type=ITEM_WEAPON; snapshot.condition=100;
    std::vector<uint8_t> bytes;
    assert(player_item_snapshot_list_encode({snapshot},&bytes)==player_snapshot_codec_result::ok);
    std::copy(bytes.begin(),bytes.end(),payload.item_blob.begin()); payload.item_blob_size=bytes.size();
    auction_command_result result{}; result.action=auction_action::claim_item;
    result.item_count=1; result.item_uids[0]=42; result.item_revisions[0]=2;
    result.materialized_item_ids[0]=901; result.player_owner_revision=5;
    for(mode=0;mode<=5;++mode) {
        delivered=alerts=dirty=0; output.clear(); actor.carrying=nullptr; object_list=nullptr;
        prototype.extra_flags=mode==1 ? ITEM_ARTIFACT : 0;
        if(mode==4 || mode==5) {
            item={}; item.obj_uid=42; item.loc_p=LOC_CARRIED;
            item.loc.carrying=mode==4 ? &actor : &other; object_list=&item;
        }
        assert(auction_publish_item_claim(&actor,result,payload));
        const bool retained=mode==1 || mode==2 || mode==3 || mode==5;
        assert(delivered==(mode==0) && alerts==retained && dirty==1);
        assert(bool(pc.retained_items)==retained);
        if(retained) {
            assert(pc.retained_items->rows.size()==1);
            assert(pc.retained_items->rows[0].source_row_id==901 && pc.retained_items->rows[0].root_item_uid==42);
            assert(output.find("saved storage")!=std::string::npos);
        }
        // Repeated publication neither creates a second body nor duplicates a retained selector.
        assert(auction_publish_item_claim(&actor,result,payload));
        assert(delivered==(mode==0) && alerts==retained);
        if(pc.retained_items) assert(pc.retained_items->rows.size()==1);
        delete pc.retained_items; pc.retained_items=nullptr;
    }
    result.materialized_item_ids[0]=0;
    assert(!auction_publish_item_claim(&actor,result,payload));
    assert(!auction_publish_item_claim(nullptr,result,payload));
    puts("auction claims: exact SQL row/UID, replay suppression and refused/artifact storage retention pass");
}
'''
build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='auction-claim-', dir=build) as directory:
    cpp=Path(directory)/'test.cpp'; binary=Path(directory)/'test'
    cpp.write_text(harness)
    subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-fno-pie','-no-pie',
                    '-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
                    '-Isrc','-I/usr/include/mysql',str(cpp),str(HARNESS_STUBS),
                    rel('player_snapshot_codec.c'),'-o',str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],check=True)
