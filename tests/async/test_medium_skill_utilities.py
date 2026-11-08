#!/usr/bin/env python3
"""Exercise #715 skill eligibility, cooldowns, lag, and attack budgets."""
import re
import subprocess
from _paths import ROOT, source
from _source_contract import function_bodies, strip_comments


def function(file, signature):
    text = strip_comments(source(file).read_text())
    head = re.search(re.escape(signature) + r"[^;{]*\{", text)
    assert head, (file, signature)
    return head.group()[:-1] + function_bodies(text, re.escape(signature))[0]


pick = function("actmove.c", "void do_pick(")
breakage = re.search(r"percent = percent - chance \+ pick->value\[1\] -.*?;", pick, re.S).group()
assert pick.count("percent > BOUNDED(0, chance, 100)") == 2
flurry = function("actnew.c", "void do_flurry_of_blows(")
loop_head = r"for \(int i = 1;[^)]*\)"
loop = re.search(loop_head, flurry).group() + function_bodies(flurry, loop_head)[0]
throat = function("actnew.c", "void do_throat_crush(")
throat_roll = throat[throat.index("skl_lvl = MIN(i, 90);"):throat.index('send_to_char("You miss their throat!')]
throat_roll = throat_roll[:throat_roll.rindex("{")] + "{return true;} return false;"
throw = function("actnew.c", "bool throw_potion(")
assert throw.index("if (!(chance = chance_throw_potion") < throw.index("CharWait(ch,")
assert "if (chance < 0)" in throw
astray = re.search(r"if \((chance == 1 \?[^\n]*)\)", throw).group(1)
kit = re.search(r"if \((!IS_TRUSTED\(ch\) && !affected_by_spell\(ch, ACH_DECEPTICON\))\)", function("disguise.c", "static void disguise_as(")).group(1)
disguise = function("disguise.c", "static void disguise_as(")
assert "extract_obj(temp, TRUE)" in disguise
jin = function("new_skills.c", "void chant_jin_touch(")
assert jin.index("affected_by_skill(ch, SKILL_JIN_TOUCH)") < jin.index("CharWait(ch,")
jin = jin[:jin.index("if (number(1, 50) > skl_lvl)")] + "(void)dam; (void)percent; (void)skl_lvl; ++ready; }"
ki = function("new_skills.c", "void chant_ki_strike(")
assert ki.count("CharWait(ch, ki_strike_lag())") == 1
assert "CharWait(vict, ki_strike_target_lag())" in ki and "af.bitvector2 = AFF2_SLOW" in ki
assert "0.2 * PULSE_VIOLENCE" not in ki
mine = function("mining.c", "void do_mine(")
mine = mine[:mine.index("int i;")] + "(void)arg; ++ready;}"
mem = source("memorize.c").read_text()
start = mem.index('get_property("memorize.factor.tupor"')
mem = mem[start:mem.index("/* Don't know what to do", start)]
meditation = re.search(r"if \(!bStatOnly.*", mem, re.S).group()
roar = function("actnew.c", "int do_roar_of_heroes(")
assert roar.index("CharWait(ch, PULSE_VIOLENCE)") < roar.rindex("return 1;")
assert "affected_by_spell(ch, SKILL_ROAR_OF_HEROES)" in roar

cpp = r'''#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "world/db.h"
#include "magic/spells.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
static int roll, draws, ready, waits, timers, creatures, pets, hits, notch_chance;
static bool cooldown, fail_creature, learn;
static char_data creature{};
static index_data indices[1]{};
P_index mob_index=indices;
int GET_CHAR_SKILL_P(P_char ch,int skill) { return ch->only.pc->skills[skill].learned; }
int GET_CLASS(P_char ch,uint cls) { return ch->player.m_class & cls; }
int GET_PRIME_CLASS(P_char ch,uint cls) { return GET_CLASS(ch,cls); }
int number(int lo,int hi) { ++draws; return std::clamp(roll,lo,hi); }
int panic_corruption_int(const char *,const char *,...) { std::abort(); }
int BOUNDED(int lo,int value,int hi) { return std::clamp(value,lo,hi); }
int get_property(const char *,int value) { return value; }
bool notch_skill(P_char,int,float chance) { notch_chance=chance; return learn; }
bool affected_by_skill(P_char,int) { return cooldown; }
bool affect_timer(P_char,int,int) { ++timers; return true; }
void send_to_char(const char *,P_char) {}
void act(const char *,int,P_char,P_obj,void *,int) {}
void CharWait(P_char,int duration) { waits+=duration; }
P_char read_mobile(int,int) { ++creatures; return fail_creature ? nullptr : &creature; }
bool char_to_room(P_char,int,int) { return true; }
void setup_pet(P_char,P_char,int,uint) { ++pets; }
void add_follower(P_char,P_char) {}
char *one_argument(char *arg,char *word) { std::strcpy(word,arg); return arg+std::strlen(arg); }
P_char get_char_room_vis(P_char,const char *) { return &creature; }
P_char get_linked_char(P_char,ush_int) { return nullptr; }
bool affected_by_spell(P_char ch,int spell) { return ch->affected && ch->affected->type==spell; }
bool should_not_kill(P_char,P_char) { return false; }
bool hit(P_char,P_char,P_obj,int *) { ++hits; return true; }
struct familiar_data {int vnum,skill; const char *name;};
static const familiar_data familiars[]={{1,5,"cat"},{2,30,"bat"},{}};
int summon_familiar_rest(int) { return 100; }
int summon_familiar_hit_points(int) { return 10; }
int summon_familiar_duration() { return 100; }
'''
cpp += function("actnew.c", "static int flurry_total_attacks(")
cpp += function("actnew.c", "static int flurry_hits_per_target(")
cpp += function("actnew.c", "int chance_throw_potion(")
cpp += function("new_skills.c", "static int ki_strike_lag(")
cpp += function("epic_skills.c", "void do_summon_familiar(")
cpp += jin + mine
cpp += "int wear(int percent,int chance,P_obj pick,P_obj obj) {" + breakage + "return percent;}\n"
cpp += "bool misses(P_char ch,int i) {int skl_lvl;" + throat_roll + "}\n"
cpp += "bool goes_astray(int chance) { return " + astray + ";}\n"
cpp += "bool needs_kit(P_char ch) { return " + kit + ";}\n"
cpp += "int recover(P_char ch,bool bStatOnly) {int remem_time=100;" + meditation + "return remem_time;}\n"
cpp += "void flurry_hits(P_char ch,P_char tch,int num_attacks,int targets) {int max_num_attacks=flurry_total_attacks(num_attacks),count=0; int num_hits_per_target=flurry_hits_per_target(max_num_attacks,targets,num_attacks); for(int t=0;t<targets;++t) {" + loop + "}}\n"
cpp += r'''
int main() {
    char_data actor{},target{}; pc_only_data pc{}; actor.only.pc=&pc;
    actor.player.level=20; actor.player.race=RACE_HUMAN;
    actor.specials.position=target.specials.position=creature.specials.position=STAT_NORMAL+POS_STANDING;
    obj_data pick{},lock{};
    assert(wear(90,50,&pick,&lock)==40); pick.value[1]=20; assert(wear(90,50,&pick,&lock)==60);
    lock.value[1]=CONT_HARDPICK; assert(wear(90,50,&pick,&lock)==45);
    for(int chance=-50;chance<=150;++chance) for(int die=1;die<=100;++die)
        assert((die>chance)==(die>BOUNDED(0,chance,100)));
    for(int normal=1;normal<=10;++normal) for(int targets=1;targets<=30;++targets) {
        hits=0; flurry_hits(&actor,&target,normal,targets);
        assert(hits==std::min(2*normal+1,normal*targets));
    }
    hits=0; flurry_hits(&actor,&target,3,3); assert(hits==7);
    for(bool gains : {false,true}) {
        learn=gains; roll=90; assert(!misses(&actor,200)); assert(notch_chance==4);
        roll=91; assert(misses(&actor,200));
        roll=50; assert(!misses(&actor,50)); roll=51; assert(misses(&actor,50));
    }
    pc.skills[SKILL_THROW_POTIONS].learned=0; draws=0; roll=140;
    assert(chance_throw_potion(&actor,&target)==0 && draws==0);
    pc.skills[SKILL_THROW_POTIONS].learned=1; actor.curr_stats.Agi=100;
    assert(chance_throw_potion(&actor,&target)==-1); roll=1;
    assert(chance_throw_potion(&actor,&target)==1);
    int aimed=0; for(roll=1;roll<=100;++roll) aimed+=!goes_astray(1); assert(aimed==1);
    roll=0; assert(goes_astray(50)); roll=1; assert(!goes_astray(50));
    assert(needs_kit(&actor)); affected_type achievement{}; achievement.type=ACH_DECEPTICON;
    actor.affected=&achievement; assert(!needs_kit(&actor)); actor.affected=nullptr;
    actor.player.level=60; assert(!needs_kit(&actor)); actor.player.level=20;
    actor.player.m_class=CLASS_MONK; cooldown=true; ready=waits=draws=0;
    char arg[]="target"; chant_jin_touch(&actor,arg,0); assert(ready==0 && waits==0 && draws==0);
    cooldown=false; chant_jin_touch(&actor,arg,0); assert(ready==1);
    assert(ki_strike_lag()==int(2.5*PULSE_VIOLENCE));
    ready=0; char empty[]=""; do_mine(&actor,empty,0); assert(ready==0);
    pc.skills[SKILL_MINE].learned=1; do_mine(&actor,empty,0); assert(ready==1);
    actor.specials.affected_by|=AFF_MEDITATE; learn=false;
    for(int rating : {0,40,100}) {
        pc.skills[SKILL_MEDITATE].learned=rating; int faster=0;
        for(roll=0;roll<=100;++roll) faster+=recover(&actor,false)==50;
        assert(faster==rating); assert(recover(&actor,true)==100);
    }
    timers=creatures=pets=0; char invalid[]="wrong",bat[]="bat",cat[]="cat";
    pc.skills[SKILL_SUMMON_FAMILIAR].learned=5;
    do_summon_familiar(&actor,invalid,0); do_summon_familiar(&actor,bat,0);
    assert(timers==0 && creatures==0);
    fail_creature=true; do_summon_familiar(&actor,cat,0); assert(timers==0 && creatures==1);
    fail_creature=false; cooldown=true; do_summon_familiar(&actor,cat,0); assert(timers==0 && creatures==1);
    cooldown=false; do_summon_familiar(&actor,cat,0); assert(timers==1 && creatures==2 && pets==1);
    std::puts("PASS #715 utilities: lock wear/bounds, seven-hit budget, learning, untrained/novice throws, kits, cooldowns, mining and recovery");
}
'''
out=ROOT / "bin/tests/medium-skill-utilities"
out.mkdir(parents=True,exist_ok=True)
path,binary=out / "harness.cpp",out / "harness"
path.write_text(cpp)
subprocess.run(["g++","-std=c++20","-Wall","-Wextra","-Werror","-ffunction-sections","-fdata-sections",
                "-Wl,--gc-sections","-fsanitize=address,undefined","-fno-sanitize-recover=all","-fno-pie","-no-pie",
                "-Isrc",str(path),"-o",str(binary)],cwd=ROOT,check=True)
subprocess.run([str(binary)],check=True,timeout=30)
