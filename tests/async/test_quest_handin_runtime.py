#!/usr/bin/env python3
"""Broken quest recipes cannot steal ingredients shared by a valid recipe."""
import os
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

fixture = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/db.h"
#include "net/comm.h"
#include <cassert>
#include <cstring>
static index_data objects[2]{}, mobiles[1]{};
P_index obj_index=objects, mob_index=mobiles;
quest_data quest_index[MAX_QUESTS]{};
static int consumed;
int real_object(const int vnum) { return vnum==677 ? 0 : vnum==256 ? 1 : -1; }
P_obj get_obj_in_list_vis(P_char,const char *,P_obj list,bool) { return list; }
void act(const char *,int,P_char,P_obj,void *,int) {}
void obj_from_char(P_obj obj) { obj->loc.carrying->carrying=nullptr; }
void extract_obj(P_obj,int) { ++consumed; }
void logit(const char *,const char *,...) {}
int SUB_MONEY(P_char ch,int amount,int) { ch->points.cash[0]-=amount; return amount; }
// FUNCTIONS
int main() {
 objects[0].virtual_number=677; objects[1].virtual_number=256;
 char_data mob{}, player{}; obj_data mace{};
 npc_only_data npc{}; mob.only.npc=&npc;
 mob.specials.act=ACT_ISNPC;
 mace.R_num=0; mace.type=ITEM_WEAPON; mace.loc.carrying=&mob;
 goal_data gift{}, missing{}, reward{};
 gift.goal_type=missing.goal_type=reward.goal_type=QUEST_GOAL_ITEM;
 gift.number=677; missing.number=29998; reward.number=256;
 quest_complete_data broken{}, valid{};
 broken.give=valid.give=&gift; broken.receive=&missing;
 valid.receive=&reward; broken.next=&valid;
 quest_index[0].quest_complete=&broken;
 player.carrying=&mace;
 assert(!quest_give_unrewarded(0,&mob,&player,"mace"));
 mob.carrying=&mace;
 assert(!quest_completion(&broken,&mob,&player));
 assert(mob.carrying==&mace && !consumed);
 assert(quest_completion(&valid,&mob,&player) && consumed==1);
 broken.next=nullptr;
 assert(quest_give_unrewarded(0,&mob,&player,"mace"));
 missing.next=&reward;
 assert(!quest_give_unrewarded(0,&mob,&player,"mace"));
 mob.carrying=&mace;
 assert(quest_completion(&broken,&mob,&player) && consumed==2);
 missing.next=nullptr;
 gift.goal_type=QUEST_GOAL_COINS; gift.number=20; broken.next=&valid;
 mob.points.cash[0]=20;
 assert(!quest_give_unrewarded(0,&mob,&player,nullptr));
 assert(!quest_completion(&broken,&mob,&player) && mob.points.cash[0]==20);
 assert(quest_completion(&valid,&mob,&player) && mob.points.cash[0]==0);
 puts("quest hand-ins: broken recipes skipped, shared items/coins reach valid recipes, mixed rewards preserved");
}
'''
functions = "\n".join(extract_function("quest.c", signature) for signature in (
    "static bool quest_completion_possible(",
    "bool quest_completion(struct quest_complete_data *qcp, P_char mob, P_char pl)",
    "static bool quest_give_unrewarded("))
with tempfile.TemporaryDirectory(prefix="quest-handin-") as temp:
    test = Path(temp) / "quest.cpp"
    binary = test.with_suffix("")
    test.write_text(fixture.replace("// FUNCTIONS", functions))
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                    "-ffunction-sections", "-fdata-sections", "-Isrc", "-I/usr/include/mysql",
                    str(test), str(HARNESS_STUBS), "-Wl,--gc-sections", "-o", str(binary)],
                   cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, env=dict(os.environ,
                   ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))
