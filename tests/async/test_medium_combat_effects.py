#!/usr/bin/env python3
"""Run #715 effect lifetimes and shield-block outcomes under ASan/UBSan."""
import re
import subprocess
from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments


def function(file, signature):
    return strip_comments(extract_function(file, signature))


fight = strip_comments(source("fight.c").read_text())
violence = function("fight.c", "void perform_violence(")
assert violence.count("battle_senses_threshold(opponent)") == 1
start = violence.index("if (!affected_by_spell(opponent, SKILL_BATTLE_SENSES)")
end = violence.index("if (IS_DRAGOON(opponent)", start)
battle = violence[start:end]
assert "battle_senses_duration()" in battle
block = function("fight.c", "int blockSucceed(")
assert not re.search(r"\bpercent\b", block)
assert "number(0, attackerweaponskill) > number(0, learned)" in block
assert "SKILL_DODGE" not in function("fight.c", "int dodgeSucceed(")
assert "Your rating doesn't matter: dodging uses your agility." in source("fight.c").read_text()
# Caller stops a blocked attack, then checks participant location before continuing.
assert "blockSucceed(opponent, ch, wpn)" in fight
selection = re.search(r'get_property\("skill.anatomy.NPC", 5.000\) [<>]= number\(1, 100\)', fight).group()
reflection = re.search(r'flame_mastery_level_roll\(live_rolls\) <= GET_LEVEL\(\w+\)', fight).group()
devotion = re.search(r'rnumber -= GET_CHAR_SKILL\(\w+, SKILL_DEVOTION\) / 50;', fight).group()
safe = re.search(r'!affected_by_spell\(ch, SPELL_FLY\) &&\s*GET_CHAR_SKILL\(ch, SKILL_SAFE_FALL\) [<>]=? number\(0, 100\)', source("specs.venthix.c").read_text()).group()
protection = re.search(r'IS_UNDEAD\(victim\) \|\| IS_ANGEL\(\w+\)', source("bard.c").read_text()).group()
observer = function("sparser.c", "void SpellCastShow(")
notches = observer[observer.index("if (idok == 1)"):observer.rindex("}")].rstrip().removesuffix("}")
interrupt = function("sparser.c", "bool check_disruptive_blow(")
interrupt_notch = re.search(r'notch_skill\(\w+, SKILL_DISRUPTIVE_BLOW, 17\)', interrupt).group()
stun = re.search(r'Stun\(victim, \w+, PULSE_VIOLENCE, FALSE\);', function("actoff.c", "void event_sneaky_strike(")).group()

cpp = r'''#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/events.h"
#include "magic/spells.h"
#include "combat/damage.h"
#include "net/comm.h"
#include "item/objmisc.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
static int roll, damage_calls, damage_status=DAM_NONEDEAD, next_round, pending, notches, activations;
static bool learn, moved;
static P_char learner, stun_source;
static float anatomy;
const str_app_type str_app[251]{};
int number(int lo,int hi) { return std::clamp(roll,lo,hi); }
int dice(int count,int sides) { return count*sides; }
const Rolls live_rolls={dice,number};
int get_property(const char *,int fallback) { return fallback; }
float get_property(const char *,double) { return anatomy; }
int GET_CHAR_SKILL_P(P_char ch,int skill) { return ch->only.pc->skills[skill].learned; }
int GET_CLASS(P_char ch,uint value) { return ch->player.m_class & value; }
int STAT_INDEX(int stat) { return stat; }
bool affected_by_spell(P_char ch,int skill) { return ch->affected && ch->affected->type==skill; }
bool notch_skill(P_char ch,int,float) { learner=ch; ++notches; return learn; }
void act(const char *,int,P_char,P_obj,void *,int) {}
void send_to_char(const char *,P_char) {}
void make_bloodstain(P_char) {}
int raw_damage(P_char,P_char,double,uint,damage_messages *,int *) { ++damage_calls; return damage_status; }
int melee_damage(P_char,P_char,double,int,damage_messages *,int *) { ++damage_calls; return damage_status; }
void Stun(P_char,P_char source,int,bool) { stun_source=source; }
nevent_schedule_result add_event(event_func,int,P_char,P_char,P_obj,int,const void *data,int) {
    ++pending; next_round=*static_cast<const int *>(data); return {};
}
int shield_block_rating_score(P_char) { return 100; }
int shield_block_dex_score(P_char) { return 0; }
int shield_block_monk_score(int value) { return value; }
int shield_block_flaying_score(int value) { return value; }
int WeaponSkill(P_char,P_obj) { return 0; }
int storm_shield_discharge_roll(const Rolls &) { return 0; }
void spell_lightning_bolt(int,P_char,char *,int,P_char,P_obj) { moved=true; }
int is_char_in_room(P_char,int) { return !moved; }
void affect_from_obj(P_obj,int) {}
int improved_shield_combat_threshold(P_char) { return 100; }
int improved_shield_combat_damage(const Rolls &,P_char) { return 5; }
int battle_senses_threshold(P_char) { return 50; }
int battle_senses_duration() { return 10; }
void set_short_affected_by(P_char,int,int duration) { ++activations; assert(duration==10); }
int flame_mastery_level_roll(const Rolls &) { return roll; }
'''
cpp += function("actoff.c", "int sneaky_strike_bleed_damage(") + "\n"
cpp += function("actoff.c", "static int sneaky_strike_bleed_rounds(") + "\n"
cpp += function("specs.object.c", "static int trap_bleed_count(") + "\n"
cpp += function("actoff.c", "void event_bleedproc(") + "\n" + block
cpp += "\nvoid senses(P_char opponent) {" + battle + "}\n"
cpp += "bool anatomy_proc() { return " + selection + ";}\n"
cpp += "bool reflects(P_char victim) {return " + reflection + ";}\n"
cpp += "int soul_frequency(P_char victim) {int rnumber=9;" + devotion + "return rnumber;}\n"
cpp += "bool landing_hurts(P_char ch) {return " + safe + ";}\n"
cpp += "bool undead_skin(P_char victim) {return " + protection + ";}\n"
cpp += "void recognize(P_char tch,int idok) {" + notches + "}\n"
cpp += "void interrupt_learn(P_char tch) {" + interrupt_notch + ";}\n"
cpp += "void merc_stun(P_char ch,P_char victim) {" + stun + "}\n"
cpp += r'''
int main() {
    char_data defender{}, attacker{}; pc_only_data pc{}, apc{};
    defender.only.pc=&pc; attacker.only.pc=&apc;
    defender.specials.position=attacker.specials.position=STAT_NORMAL+POS_STANDING;
    defender.player.race=attacker.player.race=RACE_HUMAN;
    defender.player.level=10; attacker.player.level=55;
    obj_data shield{}; defender.equipment[WEAR_SHIELD]=&shield;
    pc.skills[SKILL_SHIELD_BLOCK].learned=100;
    pc.skills[SKILL_IMPROVED_SHIELD_COMBAT].learned=100;
    assert(!blockSucceed(nullptr,&attacker,nullptr));
    for(int status : {DAM_NONEDEAD,DAM_CHARDEAD,DAM_VICTDEAD}) {
        damage_status=status; damage_calls=0; roll=1;
        assert(blockSucceed(&defender,&attacker,nullptr)); assert(damage_calls==1);
    }
    affected_type storm{}; storm.type=SPELL_STORMSHIELD; defender.affected=&storm;
    damage_calls=0; moved=false;
    assert(blockSucceed(&defender,&attacker,nullptr)); assert(moved && damage_calls==0);
    defender.affected=nullptr; moved=false; damage_status=DAM_NONEDEAD;
    for(int rounds : {0,1,3,7,6,9}) {
        damage_calls=0; pending=0; int remaining=rounds;
        do { pending=0; event_bleedproc(&attacker,&defender,nullptr,&remaining); remaining=next_round; } while(pending);
        assert(damage_calls==rounds);
    }
    int remaining=9; pending=damage_calls=0; damage_status=DAM_VICTDEAD;
    event_bleedproc(&attacker,&defender,nullptr,&remaining); assert(damage_calls==1 && pending==0);
    roll=0; assert(sneaky_strike_bleed_rounds(live_rolls)==6 && trap_bleed_count(live_rolls)==3);
    roll=100; assert(sneaky_strike_bleed_rounds(live_rolls)==9 && trap_bleed_count(live_rolls)==7);
    for(int percent : {0,5,100}) {
        anatomy=percent; int hits=0;
        for(roll=1;roll<=100;++roll) hits+=anatomy_proc();
        assert(hits==percent);
    }
    pc.skills[SKILL_DEVOTION].learned=100; apc.skills[SKILL_DEVOTION].learned=0;
    assert(soul_frequency(&defender)==7); assert(soul_frequency(&attacker)==9);
    roll=11; assert(!reflects(&defender)); defender.player.level=11; assert(reflects(&defender));
    for(int rating : {0,50,100}) {
        pc.skills[SKILL_SAFE_FALL].learned=rating; int hurts=0;
        for(roll=0;roll<=100;++roll) hurts+=landing_hurts(&defender);
        assert(hurts==100-rating);
    }
    affected_type fly{}; fly.type=SPELL_FLY; defender.affected=&fly;
    pc.skills[SKILL_SAFE_FALL].learned=0; roll=100; assert(!landing_hurts(&defender)); defender.affected=nullptr;
    defender.player.race=RACE_ANGEL; assert(undead_skin(&defender));
    defender.player.race=RACE_HUMAN; assert(!undead_skin(&defender));
    for(int id=1;id<=3;++id) { learner=nullptr; recognize(&defender,id); assert(learner==&defender); }
    learner=nullptr; interrupt_learn(&defender); assert(learner==&defender);
    merc_stun(&attacker,&defender); assert(stun_source==&attacker);
    pc.skills[SKILL_BATTLE_SENSES].learned=100;
    for(bool gains : {false,true}) {
        learn=gains; roll=51; notches=activations=0; senses(&defender); assert(notches==1 && activations==0);
        roll=50; senses(&defender); assert(notches==2 && activations==1);
    }
    std::puts("PASS #715 combat effects: exact bleed rounds, blocked counters, death/movement, percentages, owners and activation boundaries");
}
'''
out=ROOT / "bin/tests/medium-combat-effects"
out.mkdir(parents=True,exist_ok=True)
path,binary=out / "harness.cpp",out / "harness"
path.write_text(cpp)
subprocess.run(["g++","-std=c++20","-Wall","-Wextra","-Werror","-ffunction-sections","-fdata-sections",
                "-Wl,--gc-sections","-fsanitize=address,undefined","-fno-sanitize-recover=all","-fno-pie","-no-pie",
                "-Isrc",str(path),"-o",str(binary)],cwd=ROOT,check=True)
subprocess.run([str(binary)],check=True,timeout=30)
