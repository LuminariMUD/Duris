#!/usr/bin/env python3
"""Exercise modern bandage command/event with real healing and stabilization."""
import re
import subprocess
from _paths import ROOT, HARNESS_STUBS, extract_function, source

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "classes/paladins.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "net/comm.h"
#include "net/gmcp.h"
#include "world/events.h"
#include <cassert>
#include <cstdio>
#include <cstring>
static char_data healer{}, target{};
static descriptor_data descriptor{};
static obj_data bandage{};
static int rating = 7, consumed, scheduled, attackers, updates;
static bool aid, fumble, building;
struct bandage_data { int room; int healed; int maxheal; } pending;
bool SanityCheck(P_char ch,const char *) { return ch != nullptr; }
int GET_CLASS(P_char ch,uint cls) { return (ch->player.m_class & cls) != 0; }
int GET_CHAR_SKILL_P(P_char,int) { return rating; }
bool has_innate(P_char,int innate) { return aid && innate == INNATE_BATTLEAID; }
bool has_aura(P_char,int) { return false; }
int aura_mod(P_char,int) { return 0; }
float aura_healing_mod() { return 0; }
bool affected_by_skill(P_char,int) { return false; }
bool affected_by_spell(P_char ch,int spell) {
    return spell == TAG_BUILDING && building && ch == &target;
}
affected_type *get_spell_from_char(P_char,int,void *,int) { return nullptr; }
void affect_remove(P_char,affected_type *) { assert(false); }
void wear_off_message(P_char,affected_type *) { assert(false); }
int plague_heal_block_percent(const Rolls &) { assert(false); return 0; }
P_char ParseTarget(P_char,char *) { return &target; }
int NumAttackers(P_char) { return attackers; }
P_nevent get_scheduled(P_char,event_func_type) { return nullptr; }
void extract_obj(P_obj obj,int) { assert(obj == &bandage); ++consumed; healer.carrying = nullptr; }
affected_type *affect_to_char(P_char,affected_type *) { return nullptr; }
void CharWait(P_char,int) {}
void update_pos(P_char) { ++updates; }
void send_to_char(const char *,P_char) {}
void act(const char *,int,P_char,P_obj,void *,int) {}
int get_property(const char *,int fallback) { return fallback; }
bool notch_skill(P_char,int,float) { return false; }
int number(int low,int) { return fumble ? low : std::max(1,low); }
int dice(int n,int) { return n; }
const Rolls live_rolls = {dice,number};
int poison_common_remove(P_char) { return 0; }
nevent_schedule_result add_event(event_func,int,P_char,P_char,P_obj,int,const void *p,int size) {
    assert(size == sizeof(pending)); pending = *static_cast<const bandage_data *>(p); ++scheduled; return {};
}
'''
functions = [("fight.c", "int vamp(P_char ch,")] + [("tradeskill.c", s) for s in (
    "P_obj get_bandage(", "int tradeskill_vitality_cost(", "static int bandage_fumble_roll(",
    "static int bandage_heal(", "static int bandage_poison_roll(", "static int bandage_interval(",
    "static int bandage_duration(", "static int bandage_lag(",
    "void event_bandage_check(P_char ch,", "void do_bandage(P_char ch,",
)]
driver = r'''
static void reset(int hp, bool innate) {
    healer = {}; target = {}; bandage = {};
    SET_POS(&healer, POS_STANDING + STAT_NORMAL);
    SET_POS(&target, POS_PRONE + (hp <= 0 ? STAT_DYING : STAT_NORMAL));
    healer.desc = &descriptor;
    GET_VITALITY(&healer) = 50; GET_MAX_HIT(&target) = 100; GET_HIT(&target) = hp;
    healer.carrying = &bandage; bandage.type = ITEM_BANDAGE; bandage.value[0] = 20;
    aid = innate; fumble = building = false;
    consumed = scheduled = attackers = updates = 0;
}
static void start() { char arg[] = "target"; do_bandage(&healer,arg,0); }
static void round() { event_bandage_check(&healer,&target,nullptr,&pending); }
int main() {
    for (bool innate : {false,true}) for (int hp : {-9,-1,0,5}) {
        reset(hp,innate); start();
        assert(consumed == 1 && scheduled == 1 && GET_HIT(&target) == hp);
        round();
        int normal = hp + 2;
        assert(GET_HIT(&target) == (innate && normal <= 0 ? 1 : normal));
        assert(GET_VITALITY(&healer) == 48 && updates == 1 && scheduled == 2);
    }
    // Refusals preserve the existing command's consumable and skill requirements.
    reset(-9,true); healer.carrying = nullptr; start(); assert(!consumed && !scheduled && GET_HIT(&target) == -9);
    reset(-9,true); rating = 0; start(); assert(!consumed && !scheduled); rating = 7;
    reset(-9,true); attackers = 1; start(); assert(!consumed && !scheduled);
    reset(-9,true); healer.specials.fighting = &target; start(); assert(!consumed && !scheduled);
    // A scheduled attempt can still stop for its normal resource/eligibility gates.
    for (int gate : {0,1,2,3,4}) {
        reset(-9,true); start();
        if (gate == 0) GET_VITALITY(&healer) = 9;
        if (gate == 1) fumble = true;
        if (gate == 2) target.in_room = 1;
        if (gate == 3) target.specials.fighting = &healer;
        if (gate == 4) building = true; // vamp() rejects healing here
        int vitality = GET_VITALITY(&healer);
        round(); assert(GET_HIT(&target) == -9 && GET_VITALITY(&healer) == vitality && scheduled == 1);
    }
    puts("Battlefield Aid: modern command, consumed bandage, real healing, stabilization and preserved refusal/resource gates passed.");
}
'''
assert "do_OLD_bandage" not in source("interp.c").read_text()
build = ROOT / "bin/tests/battlefield-aid"
build.mkdir(parents=True,exist_ok=True)
cpp,binary = build/"harness.cpp",build/"harness"
cpp.write_text(prelude + "\n".join(extract_function(f,s) for f,s in functions) + driver)
subprocess.run(["g++","-std=c++20","-g","-fsanitize=address,undefined","-I"+str(ROOT/"src"),
                str(cpp),str(HARNESS_STUBS),"-o",str(binary)],check=True)
subprocess.run([str(binary)],check=True)
