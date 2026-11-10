#!/usr/bin/env python3
"""Exercise Disharmonist procs and spell-damage scaling through real server objects."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "combat/damage.h"
#include "world/events.h"
#include "abilities/abilities.h"
#include "world/specs.prototypes.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
extern P_room world;
extern P_index obj_index;
extern Skill skills[];
extern P_char character_list;
extern uint64_t character_removal_generation;
extern void initialize_skills();
extern void bard_storms(int,P_char,P_char,int);
extern void bard_chaos(int,P_char,P_char,int);
extern void bard_dissonance(int,P_char,P_char,int);
static std::vector<std::unique_ptr<affected_type>> stored;
static std::map<P_char,std::map<int,int>> markers;
static int proc_roll = 1, storm_roll = 1, coin, echo_percent = 40;
static int echo_calls, bolt_calls, hurricane_rolls, waits, stops, wears, echo_spell;
static bool saved, bolts, replace_target, throw_echo, in_probe;
struct delivered { P_char caster,target; double amount; int type; };
static std::vector<delivered> damage_hits;
static std::string output;
void send_to_char(const char *text,P_char ch) { if (std::string(text).find("and you succeed") != std::string::npos) assert(IS_ALIVE(ch)); output += text; }
void act(const char *text,int,P_char,P_obj,void *,int) { output += text; }
int attack_back(P_char,P_char,int) { return 0; }
void DamageStuff(P_char,int) {}
int raw_damage(P_char caster,P_char target,double amount,uint,damage_messages *message,int *) {
    damage_hits.push_back({caster,target,amount,message->damage_kind}); return DAM_NONEDEAD;
}
int number(int low,int high) {
    if (low == 1 && high == 4000) return proc_roll;
    if (low == 1 && high == 5) return storm_roll;
    if (low == 0 && high == 1) return coin;
    if (low == 30 && high == 50) return echo_percent;
    if (low == 0 && high == 2) return bolts ? 0 : 2;
    if (low == 0 && high == 3) return 0;
    if (low == 1 && high == 30) { ++hurricane_rolls; return 1; }
    return high;
}
int dice(int count,int sides) { return count*sides; }
bool NewSaves(P_char,int,int) { return saved; }
bool should_area_hit(P_char ch,P_char target) { return ch != target; }
bool grouped(P_char,P_char) { return false; }
void CharWait(P_char,int) { ++waits; }
void StopCasting(P_char ch) { ++stops; REMOVE_BIT(ch->specials.affected_by2,AFF2_CASTING); }
affected_type *affect_to_char(P_char ch,affected_type *af) {
    stored.emplace_back(new affected_type(*af)); auto *copy=stored.back().get();
    copy->next=ch->affected; ch->affected=copy; return copy;
}
void affect_remove(P_char ch,affected_type *af) {
    for (auto **p=&ch->affected;*p;p=&(*p)->next) if (*p == af) { *p=af->next; return; }
    assert(false);
}
void affect_from_char(P_char ch,int type) {
    for (auto *af=ch->affected;af;) { auto *next=af->next; if (af->type == type) affect_remove(ch,af); af=next; }
}
void wear_off_message(P_char,affected_type *) { ++wears; }
void balance_affects(P_char) {} // Fixture effects have no stat modifiers or scheduler work.
void set_short_affected_by(P_char ch,int type,int duration) {
    markers[ch][type]=duration;
    affected_type af{}; af.type=type; af.duration=duration; af.flags=AFFTYPE_SHORT|AFFTYPE_NODISPEL|AFFTYPE_NOSHOW;
    affect_to_char(ch,&af);
}
P_char un_morph(P_char ch) {
    P_char original=ch->only.npc->orig_char;
    original->in_room=ch->in_room; ch->in_room=NOWHERE; SET_POS(ch,POS_STANDING|STAT_DEAD);
    ++character_removal_generation; return original;
}
void spell_lightning_bolt(int,P_char,char *,int,P_char target,P_obj) {
    ++bolt_calls;
    if (replace_target) { forget_live_character(target); ++target->runtime_id; ++character_removal_generation; }
}
static char_data player(pc_only_data &pc,uint64_t id) {
    char_data ch{}; ch.only.pc=&pc; ch.runtime_id=id; ch.in_room=1;
    ch.player.level=56; ch.player.m_class=CLASS_BARD; ch.player.spec=SPEC_DISHARMONIST;
    ch.player.race=RACE_HUMAN; ch.player.name=const_cast<char *>("Fixture");
    ch.specials.position=POS_STANDING|STAT_NORMAL; ch.specials.affected_by3=AFF3_SINGING;
    ch.curr_stats.Cha=150; ch.curr_stats.Int=ch.curr_stats.Wis=100;
    ch.points.hit=ch.points.max_hit=10000;
    pc.skills[SONG_CHAOS].learned=pc.skills[SONG_DISSONANCE].learned=100;
    pc.skills[SKILL_CONCENTRATION].learned=100;
    return ch;
}
static void register_again(P_char ch) {
    for (auto **at=&character_list;*at;at=&(*at)->next)
        if (*at==ch) { *at=ch->next; break; }
    character_list_add(ch);
}
static void add(P_char ch,int type,int flags=0) {
    affected_type af{}; af.type=type; af.flags=flags; affect_to_char(ch,&af);
}
static int count(P_char ch,int type) {
    int result=0; for (auto *af=ch->affected;af;af=af->next) result += af->type == type; return result;
}
static void clear(P_char ch) { ch->affected=nullptr; markers[ch].clear(); }
void spell_napalm(int,P_char caster,char *,int,P_char target,P_obj) {
    spell_damage(caster,target,100,SPLDAM_GENERIC,SPLDAM_NODEFLECT|SPLDAM_NOSHRUG,nullptr);
}
static void proc_probe(int,P_char caster,char *,int,P_char target,P_obj) {
    spell_damage(caster,target,100,SPLDAM_GENERIC,SPLDAM_NOSHRUG,nullptr);
}
static void probe(int,P_char caster,char *args,int,P_char target,P_obj) {
    ++echo_calls;
    assert(!in_probe); in_probe=true;
    assert(!bard_spell_echo(caster,echo_spell,args,target->runtime_id,1));
    if (throw_echo) { in_probe=false; throw std::runtime_error("test spell callback"); }
    spell_damage(caster,target,100,SPLDAM_GENERIC,SPLDAM_NODEFLECT|SPLDAM_NOSHRUG,nullptr);
    spell_damage(target,caster,100,SPLDAM_GENERIC,SPLDAM_NODEFLECT|SPLDAM_NOSHRUG,nullptr);
    proc_data redirected{caster,100,SPLDAM_GENERIC,SPLDAM_NOSHRUG,nullptr};
    assert(deflect_spell(nullptr,target,redirected,"deflect","deflect","deflect"));
    in_probe=false;
}
'''
prelude = prelude.replace("static void probe(", extract_function("specs.underworld.c", "static bool deflect_spell(") + "\nstatic void probe(")
helpers = "\n".join(extract_function("bard.c", signature) for signature in (
    "static int disharmonist_song_chance(", "static int song_chaos_dispel_chance(",
    "static int song_dissonance_interrupt_chance(",
))
driver = r'''
int main() {
    nevent_bind_game_thread();
    initialize_skills(); world=new room_data[2]{}; world[1].sector_type=SECT_FIELD;
    pc_only_data pc{}, enemy_pc{}, other_pc{};
    char_data caster=player(pc,1), enemy=player(enemy_pc,2), other=player(other_pc,3);
    enemy.player.m_class=other.player.m_class=CLASS_WARRIOR; enemy.player.spec=other.player.spec=0;
    character_list=nullptr; character_list_add(&other); character_list_add(&enemy); character_list_add(&caster);
    other.next_in_room=&enemy; enemy.next_in_room=&caster; world[1].people=&other;
    assert(song_chaos_dispel_chance(&caster,&enemy,false)==700);
    assert(song_chaos_dispel_chance(&caster,&enemy,true)==350);
    enemy.player.level=52;
    assert(song_chaos_dispel_chance(&caster,&enemy,false)==740);
    enemy.player.level=56;
    assert(song_dissonance_interrupt_chance(&caster,&enemy)==500);
    caster.curr_stats.Cha=100; pc.skills[SONG_CHAOS].learned=50;
    assert(song_chaos_dispel_chance(&caster,&enemy,false)==200);
    caster.curr_stats.Cha=150; pc.skills[SONG_CHAOS].learned=100;
    add(&enemy,SPELL_BLESS,AFFTYPE_SET_SUSPENDED); add(&enemy,SPELL_BLESS);
    add(&enemy,SPELL_HASTE); add(&enemy,SKILL_RIFF,AFFTYPE_NODISPEL);
    coin=1; saved=false; proc_roll=1; wears=0;
    bard_chaos(56,&caster,&enemy,SONG_CHAOS);
    assert(!count(&enemy,SPELL_BLESS) && count(&enemy,SPELL_HASTE)==1);
    assert(count(&enemy,SKILL_RIFF)==1 && count(&enemy,SONG_CHAOS)==1 && wears==1);
    assert(markers[&enemy][SONG_CHAOS]==10*WAIT_SEC);
    bard_chaos(56,&caster,&enemy,SONG_CHAOS);
    assert(count(&enemy,SPELL_HASTE)==1 && wears==1); // Same-target immunity.
    add(&other,SPELL_BLESS);
    bard_chaos(56,&caster,&other,SONG_CHAOS);
    assert(!count(&other,SPELL_BLESS) && markers[&other][SONG_CHAOS]==10*WAIT_SEC);
    clear(&enemy); add(&enemy,SPELL_BLESS); saved=true;
    proc_roll=351; bard_chaos(56,&caster,&enemy,SONG_CHAOS); assert(count(&enemy,SPELL_BLESS));
    proc_roll=350; bard_chaos(56,&caster,&enemy,SONG_CHAOS); assert(!count(&enemy,SPELL_BLESS));
    saved=false; proc_roll=1; clear(&enemy); clear(&other);
    add(&enemy,SPELL_BLESS); add(&enemy,SPELL_BLESS,AFFTYPE_NODISPEL); add(&enemy,SPELL_HASTE);
    coin=0; bard_chaos(56,&caster,&enemy,SONG_CHAOS);
    assert(count(&enemy,SPELL_BLESS)==2 && !count(&enemy,SPELL_HASTE)); clear(&enemy);

    for (int spec : {SPEC_MINSTREL,0}) {
        caster.player.spec=spec; add(&enemy,SPELL_BLESS);
        bard_chaos(56,&caster,&enemy,SONG_CHAOS);
        assert(count(&enemy,SPELL_BLESS) && !count(&enemy,SONG_CHAOS)); clear(&enemy);
    }
    npc_only_data npc{}; caster.player.spec=SPEC_DISHARMONIST; caster.specials.act=ACT_ISNPC; caster.only.npc=&npc;
    add(&enemy,SPELL_BLESS); bard_chaos(56,&caster,&enemy,SONG_CHAOS);
    assert(count(&enemy,SPELL_BLESS) && !count(&enemy,SONG_CHAOS)); clear(&enemy);
    caster.specials.act=0; caster.only.pc=&pc;
    // Shared removal preserves ordinary full dispel, dormant grants and morph identity.
    add(&enemy,SPELL_BLESS); add(&enemy,SPELL_HASTE); add(&enemy,SKILL_RIFF,AFFTYPE_NODISPEL);
    spell_dispel_magic(56,&caster,nullptr,0,&enemy,nullptr);
    assert(!count(&enemy,SPELL_BLESS) && !count(&enemy,SPELL_HASTE) && count(&enemy,SKILL_RIFF));
    clear(&enemy);
    char_data original=player(other_pc,4), morph=player(enemy_pc,5);
    morph.specials.act=ACT_ISNPC; morph.only.npc=&npc; npc.orig_char=&original;
    add(&morph,SPELL_CALL_OF_THE_WILD);
    assert(dispel_character_affect(&caster,&morph,SPELL_CALL_OF_THE_WILD)==&original);
    assert(!IS_ALIVE(&morph) && IS_ALIVE(&original));
    SET_POS(&morph,POS_STANDING|STAT_NORMAL); morph.in_room=1; clear(&morph);
    add(&morph,SPELL_CALL_OF_THE_WILD); coin=0; damage_hits.clear();
    bard_chaos(56,&caster,&morph,SONG_CHAOS);
    assert(markers[&original][SONG_CHAOS]==10*WAIT_SEC && damage_hits.empty());
    clear(&original);
    SET_POS(&morph,POS_STANDING|STAT_NORMAL); morph.in_room=1; clear(&morph);
    add(&morph,SPELL_CALL_OF_THE_WILD);
    spell_dispel_magic(60,&morph,nullptr,0,&morph,nullptr); // Self-dispel messages precede body release.
    assert(!IS_ALIVE(&morph));
    npc.orig_char=nullptr;
    // Exactly one new storm hit per selected target; globes do not stop either choice.
    enemy.specials.affected_by2=other.specials.affected_by2=AFF2_GLOBE;
    for (int choice : {0,1}) { coin=choice;
        damage_hits.clear(); storm_roll=1; bolts=false;
        bard_storms(56,&caster,&enemy,SONG_STORMS); bard_storms(56,&caster,&other,SONG_STORMS);
        assert(damage_hits.size()==2 && damage_hits[0].target==&enemy && damage_hits[1].target==&other);
        for (const auto &hit : damage_hits) assert(hit.type==(coin?SPLDAM_COLD:SPLDAM_GENERIC));
    }
    damage_hits.clear(); storm_roll=2;
    bard_storms(56,&caster,&enemy,SONG_STORMS); assert(damage_hits.empty());
    storm_roll=1; caster.player.level=50;
    bard_storms(50,&caster,&enemy,SONG_STORMS); assert(damage_hits.empty()); caster.player.level=56;
    caster.specials.act=ACT_ISNPC; caster.only.npc=&npc;
    bard_storms(56,&caster,&enemy,SONG_STORMS); assert(damage_hits.empty()); caster.specials.act=0; caster.only.pc=&pc;
    // A scheduled song echo still hits the recorded room after the singer moves.
    bolts=true; storm_roll=2; bolt_calls=0;
    bard_storms(12,&caster,&enemy,SONG_STORMS); assert(bolt_calls==2);
    caster.in_room=0; bolt_calls=0;
    bard_storms(12,&caster,&enemy,SONG_STORMS); assert(bolt_calls==2);
    caster.in_room=1;
    bolts=replace_target=true; bolt_calls=0;
    bard_storms(56,&caster,&enemy,SONG_STORMS);
    assert(bolt_calls==1 && damage_hits.empty()); enemy.runtime_id=2; register_again(&enemy); bolts=replace_target=false;
    damage_hits.clear(); hurricane_rolls=0;
    cast_hurricane(56,&caster,nullptr,0,nullptr,nullptr);
    assert(damage_hits.size()==2 && hurricane_rolls==1); // Original shared room damage roll.
    // Real spell_damage profile and reflection both carry the same Echo factor.
    enemy.specials.affected_by2=other.specials.affected_by2=0;
    damage_hits.clear();
    spell_damage(&caster,&enemy,100,SPLDAM_GENERIC,SPLDAM_NODEFLECT|SPLDAM_NOSHRUG,nullptr);
    double normal=damage_hits.back().amount;
    spell_damage(&enemy,&caster,100,SPLDAM_GENERIC,SPLDAM_NODEFLECT|SPLDAM_NOSHRUG,nullptr);
    double reflected=damage_hits.back().amount;
    spell_damage(&enemy,&other,100,SPLDAM_GENERIC,SPLDAM_NODEFLECT|SPLDAM_NOSHRUG,nullptr);
    double redirected=damage_hits.back().amount;
    coin=0;
    for (int spell : {SPELL_MAGIC_MISSILE,SPELL_BURNING_HANDS,SPELL_LIGHTNING_BOLT,SPELL_FIREBALL,
                      SPELL_BIGBYS_CLENCHED_FIST,SPELL_SHATTER}) {
        echo_spell=spell; skills[spell].spell_pointer=probe;
        for (int percentage : {30,40,50}) { echo_percent=percentage;
            damage_hits.clear(); echo_calls=0;
            assert(bard_spell_echo(&caster,spell,nullptr,2,1));
            assert(echo_calls==1 && damage_hits.size()==3);
            assert(std::abs(damage_hits[0].amount-normal*echo_percent/100.0)<0.00001);
            assert(std::abs(damage_hits[1].amount-reflected*echo_percent/100.0)<0.00001);
            assert(damage_hits[2].caster==&enemy && damage_hits[2].target==&other);
            assert(std::abs(damage_hits[2].amount-redirected*echo_percent/100.0)<0.00001);
            assert(bard_spell_echo_factor()==1.0);
        }
    }
    // Actual cold_hammer CMD_GOTNUKED creates independent Napalm; it is not an Echo.
    obj_index=new index_data[1]{};
    obj_data hammer{}; hammer.loc_p=LOC_WORN; hammer.loc.wearing=&enemy;
    enemy.equipment[WIELD]=&hammer; obj_index[0].func.obj=cold_hammer;
    damage_hits.clear(); spell_napalm(40,&enemy,nullptr,SPELL_TYPE_SPELL,&caster,nullptr);
    double retaliation=damage_hits.back().amount;
    echo_spell=SPELL_FIREBALL; skills[echo_spell].spell_pointer=proc_probe;
    damage_hits.clear(); echo_percent=40; coin=0;
    assert(bard_spell_echo(&caster,echo_spell,nullptr,2,1));
    assert(damage_hits.size()==2 && damage_hits[0].caster==&enemy);
    assert(std::abs(damage_hits[0].amount-retaliation)<0.00001);
    assert(std::abs(damage_hits[1].amount-normal*0.4)<0.00001);
    // The real item redirection still belongs to the incoming Echo.
    obj_index[0].func.obj=elvenkind_cloak; damage_hits.clear();
    assert(bard_spell_echo(&caster,echo_spell,nullptr,2,1));
    assert(damage_hits.size()==1 && damage_hits[0].caster==&enemy && damage_hits[0].target==&other);
    assert(std::abs(damage_hits[0].amount-redirected*0.4)<0.00001);
    enemy.equipment[WIELD]=nullptr; delete[] obj_index; obj_index=nullptr;
    skills[SPELL_MAGIC_MISSILE].spell_pointer=probe;
    echo_spell=SPELL_MAGIC_MISSILE; echo_calls=0; coin=1;
    assert(!bard_spell_echo(&caster,echo_spell,nullptr,2,1) && !echo_calls);
    coin=0; caster.player.level=55;
    assert(!bard_spell_echo(&caster,echo_spell,nullptr,2,1)); caster.player.level=56;
    caster.player.spec=SPEC_MINSTREL;
    assert(!bard_spell_echo(&caster,echo_spell,nullptr,2,1)); caster.player.spec=SPEC_DISHARMONIST;
    caster.specials.act=ACT_ISNPC; caster.only.npc=&npc;
    assert(!bard_spell_echo(&caster,echo_spell,nullptr,2,1)); caster.specials.act=0; caster.only.pc=&pc;
    assert(!bard_spell_echo(&caster,SPELL_HEAL,nullptr,2,1));
    forget_live_character(&enemy); enemy.runtime_id=9; assert(!bard_spell_echo(&caster,echo_spell,nullptr,2,1));
    enemy.runtime_id=2; register_again(&enemy);
    enemy.in_room=0; assert(!bard_spell_echo(&caster,echo_spell,nullptr,2,1)); enemy.in_room=1;
    SET_POS(&enemy,POS_STANDING|STAT_DEAD); assert(!bard_spell_echo(&caster,echo_spell,nullptr,2,1));
    SET_POS(&enemy,POS_STANDING|STAT_NORMAL);
    throw_echo=true;
    try { bard_spell_echo(&caster,echo_spell,nullptr,2,1); assert(false); }
    catch (const std::runtime_error &) {}
    assert(bard_spell_echo_factor()==1.0); throw_echo=false;
    clear(&caster); clear(&enemy); clear(&other); clear(&morph); stored.clear(); delete[] world;
    std::puts("PASS Disharmonist exact chances, per-target one-effect dispel/immunity/save, full dispel/morph, Storms target/globe/identity, Hurricane shared roll, six-spell Echo/profile/reflection/recursion/lifetime/scope");
}
'''
subprocess.run(["make","-C","src","-j8"],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
link=subprocess.check_output(["make","-s","--no-print-directory","-C","src",
    "--eval=print-link:;@echo $(DMS_OBJS) $(LIBS)","print-link"],cwd=ROOT,text=True).split()
build=ROOT/"bin/tests"; build.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix="bard-disharmonist-",dir=build) as temporary:
    cpp,binary=Path(temporary)/"test.cpp",Path(temporary)/"test"
    cpp.write_text(prelude+helpers+driver)
    subprocess.run(["g++","-std=c++20","-g","-Isrc","-I/usr/include/libxml2","-I/usr/include/mysql",
                    str(cpp),"-o",str(binary),"-rdynamic","-Wl,--allow-multiple-definition",*link],cwd=ROOT,check=True)
    subprocess.run([str(binary)],check=True,timeout=30)
