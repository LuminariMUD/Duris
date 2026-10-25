#!/usr/bin/env python3
"""Execute Fire callers and matched-RNG plain/mephit summons with real pet setup.

Unchanged spell-damage globe/absorption/memory and shield-retaliation branches
are replayed verbatim; other combat, room placement and prototype reads are
fixtures. Combined server journeys supply complete damage/pet integration proof.
"""
import re
import subprocess

from _paths import ROOT, HARNESS_STUBS, extract_function, source

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "classes/necromancy.h"
#include "combat/damage.h"
#include "combat/dam_mods.h"
#include "combat/training_dummy.h"
#include "economy/collector_presence.h"
#include "guild/assocs.h"
#include "guild/guildhall.h"
#include "world/buildings.h"
#include "world/events.h"
#include "net/comm.h"
#include <cassert>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>
#include <set>
#include <map>
room_data rooms[2]{};
P_room world=rooms;
const int top_of_world=1;
float dam_factor[LAST_DF+1]{};
index_data indexes[1200]{};
P_index mob_index=indexes, obj_index=indexes;
static std::vector<P_char> pets;
static std::set<const char *> strings;
static std::vector<int> delays;
static unsigned rng=1;
static int variant, draws, infuse, delivered_damage, blind_count, immolate_count, ward;
static uint damage_flags;
static bool saved, missing, staff;
static P_char owner;
int GET_CLASS(P_char ch,uint cls) { return (ch->player.m_class&cls)!=0; }
int GET_CHAR_SKILL_P(P_char,int id) { return id==SKILL_INFUSE_LIFE?infuse:0; }
bool has_innate(P_char ch,int id) { return id==INNATE_FIRE_AURA && GET_RACE(ch)==RACE_F_ELEMENTAL; }
int number(int low,int high) { ++draws; rng=rng*1664525+1013904223; return low==0&&high==2?variant:low+int(rng%unsigned(high-low+1)); }
int dice(int count,int sides) { int result=0; while(count--) result+=number(1,sides); return result; }
int BOUNDED(int low,int value,int high) { return std::max(low,std::min(value,high)); }
int STAT_INDEX(int) { return 10; }
float get_property(const char *,double fallback) { return fallback; }
void send_to_char(const char *,P_char) {}
void act(const char *,int,P_char,P_obj,void *,int) {}
void update_pos(P_char) {}
void do_alert(P_char,char *,int) {}
int get_default_save_mod(P_char,P_char,int,int) { return 0; }
bool NewSaves(P_char,int,int) { return saved; }
bool training_dummy_is(P_char) { return false; }
bool training_dummy_capture_target_allowed(P_char) { return true; }
bool collector_presence_is_npc(P_char) { return false; }
bool blind(P_char,P_char,int) { ++blind_count; return true; }
void spell_immolate(int,P_char,char *,int,P_char,P_obj) { ++immolate_count; }
bool ac_can_see(P_char,P_char,bool) { return true; }
P_char get_linked_char(P_char ch,ush_int type) { return type==LNK_PET?ch->following:nullptr; }
P_obj get_globe(P_char) { return nullptr; }
void remove_plushit_bits(P_char) {}
void MonkSetSpecialDie(P_char ch) { ch->points.damnodice=3; ch->points.damsizedice=7; }
bool has_air_staff_arti(P_char) { return staff; }
void linked_affect_to_char(P_char mob,affected_type *af,P_char ch,int) {
    auto *copy=new affected_type(*af); copy->next=mob->affected; mob->affected=copy;
    mob->specials.affected_by|=af->bitvector; mob->following=ch;
}
affected_type *affect_to_char(P_char ch,affected_type *af) {
    auto *copy=new affected_type(*af); copy->next=ch->affected; ch->affected=copy;
    ch->specials.affected_by2|=af->bitvector2; return copy;
}
void apply_achievement(P_char mob,int type) { auto *af=new affected_type{}; af->type=type; af->duration=-1; af->next=mob->affected; mob->affected=af; }
void add_follower(P_char mob,P_char ch) { auto *follow=new follow_type{}; follow->follower=mob; follow->next=ch->followers; ch->followers=follow; mob->following=ch; }
void MobStartFight(P_char,P_char) {}
void event_pet_death(P_char,P_char,P_obj,void *) {}
nevent_schedule_result add_event(event_func,int delay,P_char,P_char,P_obj,int,const void *,int) { delays.push_back(delay); return {}; }
char *str_dup(const char *text) { auto *p=strdup(text); assert(strings.insert(p).second); return p; }
void str_free(const char *text) { assert(strings.erase(text)==1); free(const_cast<char *>(text)); }
void *__malloc(size_t size,const char *,const char *,int) { return calloc(1,size); }
void __free(void *p,const char *,int) { free(p); }
int real_mobile(int vnum) { return vnum; }
P_char read_mobile(int vnum,int) {
    if(missing) return nullptr;
    auto *mob=new char_data{}; auto *npc=new npc_only_data{}; mob->only.npc=npc;
    npc->R_num=vnum; indexes[vnum].virtual_number=vnum;
    mob->specials.act=ACT_ISNPC; SET_POS(mob,STAT_NORMAL+POS_STANDING);
    mob->player.name=const_cast<char *>("fire elemental");
    mob->player.short_descr=const_cast<char *>("a fire elemental");
    mob->player.long_descr=const_cast<char *>("A fire elemental waits.\n");
    mob->player.description=const_cast<char *>("A being of fire.\n");
    mob->player.race=RACE_F_ELEMENTAL; mob->player.m_class=CLASS_WARRIOR;
    mob->specials.affected_by2=AFF2_FIRE_AURA|AFF2_FIRESHIELD|AFF2_PROT_COLD;
    mob->points.max_hit=mob->points.base_hit=500; mob->points.base_mana=80;
    mob->points.base_vitality=50; mob->points.base_armor=-20;
    mob->base_stats.Str=mob->base_stats.Dex=mob->base_stats.Agi=mob->base_stats.Pow=100;
    mob->curr_stats.Int=mob->base_stats.Int=100; pets.push_back(mob); return mob;
}
bool char_to_room(P_char ch,int room,int) { ch->in_room=room; return true; }
void extract_char(P_char) { assert(false); }
int attack_back(P_char,P_char,int) { return 0; }
int vamp(P_char ch,double amount,double cap,bool) {
    int gain=std::max(0,std::min(int(amount),int(cap)-GET_HIT(ch))); GET_HIT(ch)+=gain; return gain;
}
'''

functions = [
    ('sparser.c','char *skip_spaces('),
    ('affects.c','struct affected_type *get_spell_from_char('),
    ('affects.c','bool affected_by_spell('),
    ('magic.c','const char *elemental_summon_failure_message('),
    ('magic.c','const char *elemental_form_failure_message('),
    ('magic.c','void spell_fire_form('),
    ('magic.c','static void make_fire_mephit('),
    ('magic.c','bool can_conjure_lesser_elem('),
    ('magic.c','bool can_conjure_greater_elem('),
    ('magic.c','int conjure_terrain_check(P_char ch, P_char mob)\n{'),
    ('mobact.c','int CheckFor_remember(P_char ch, P_char victim)\n{'),
    ('mobact.c','void remember(P_char ch, P_char victim, bool check_group_remember)'),
    ('mobact.c','void remember(P_char ch, P_char victim)\n{'),
    ('mobact.c','void clearMemory('),
    ('necromancy.c','int setup_pet('),
    ('magic.c','void spell_conjour_elemental('),
    ('magic.c','void conjure_specialized('),
    ('magic.c','void spell_conjour_greater_elemental('),
    ('magic.c','void spell_fireball('),
    ('magic.c','void spell_solar_flare('),
]
damage_source = extract_function('fight.c','int spell_damage(')
absorb = damage_source[damage_source.index('\tif (type == SPLDAM_FIRE'):damage_source.index('\tif (type == SPLDAM_COLD')]
memory = damage_source[damage_source.index('\t// Training dummies are deliberately'):damage_source.index('\n\t///////\n\t// Special Conditions',damage_source.index('\t// Training dummies are deliberately'))]
globes = damage_source[damage_source.index('\t// globes check'):damage_source.index('\t// end of globes check')]
damage_path = '''
int spell_damage(P_char ch,P_char victim,double dam,int type,uint flags,damage_messages *,int *) {
    damage_flags=flags; dam-=ward; if(dam<=0) return DAM_NONEDEAD;
ABSORB
MEMORY
GLOBES
    delivered_damage=int(dam); GET_HIT(victim)-=int(dam); return DAM_NONEDEAD;
}
'''.replace('ABSORB',absorb).replace('MEMORY',memory).replace('GLOBES',globes)
shields = extract_function('fight.c','int check_shields(')
start = shields.index('\telse if (result == DAM_NONEDEAD && IS_AFFECTED2(victim, AFF2_FIRESHIELD))')
end = shields.index('\telse if (result == DAM_NONEDEAD && IS_AFFECTED3(victim, AFF3_COLDSHIELD))',start)
retaliation = '''
void shield_retaliation(P_char ch,P_char victim,double dam) {
    int result=DAM_NONEDEAD; double fshield=0.2; uint sflags=SPLDAM_GLOBE|SPLDAM_NODEFLECT;
    damage_messages fireshield{};
    if(false) {}
SHIELD
    (void)result;
}
'''.replace('SHIELD',shields[start:end])

affs=extract_function('affects.c','void apply_affs(')
start=affs.index('\tif (mode)\n')
end=affs.index('\n\t/*\n\t * for stats,',start)
recalc='void recalc_intrinsic(P_char ch) { hold_data TmpAffs{}; int mode=TRUE;\n'+affs[start:end]+'\n}\n'
mods=source('dam_mods.c').read_text()
start=mods.index('MAKE_DAM_MOD_PRED(){ if (damageType != SPLDAM_COLD) return;')
opening=mods.index('{',start); depth=1; end=opening+1
while depth:
    depth+=(mods[end]=='{')-(mods[end]=='}'); end+=1
cold='dam_mod_predicate cold_response = '+mods[start:end]+';\n'

driver = r'''
static void clear(P_char ch) {
    for(auto *mob:pets) {
        clearMemory(mob);
        while(mob->affected) { auto *af=mob->affected; mob->affected=af->next; delete af; }
        const unsigned mask=mob->only.npc->str_mask;
        if(mask&STRUNG_KEYS) str_free(mob->player.name);
        if(mask&STRUNG_DESC1) str_free(mob->player.long_descr);
        if(mask&STRUNG_DESC2) str_free(mob->player.short_descr);
        if(mask&STRUNG_DESC3) str_free(mob->player.description);
        delete mob->only.npc; delete mob;
    }
    pets.clear();
    while(ch->followers) { auto *f=ch->followers; ch->followers=f->next; delete f; }
    assert(strings.empty()); delays.clear();
}
static std::vector<long long> snapshot(P_char mob) {
    std::vector<long long> values{GET_VNUM(mob),GET_LEVEL(mob),GET_RACE(mob),GET_SIZE(mob),
        mob->player.m_class,mob->player.spec,GET_HIT(mob),GET_MAX_HIT(mob),mob->points.base_hit,
        mob->points.base_hitroll,mob->points.hitroll,mob->points.base_damroll,mob->points.damroll,
        mob->points.damnodice,mob->points.damsizedice,mob->points.base_armor,mob->points.base_mana,
        mob->points.base_vitality,static_cast<long long>(mob->specials.affected_by),
        static_cast<long long>(mob->specials.affected_by2&~AFF2_FIRESHIELD),mob->specials.act};
    for(int i=0;i<10;++i) values.push_back(mob->base_stats[i]);
    for(auto *af=mob->affected;af;af=af->next) { values.push_back(af->type); values.push_back(af->duration); values.push_back(af->flags); }
    for(int delay:delays) values.push_back(delay);
    values.push_back(rng); values.push_back(draws); return values;
}
int main() {
    char_data fire{}, target{}; pc_only_data pc{};
    fire.only.pc=&pc; pc.pid=215; fire.player.name=const_cast<char *>("Firetest");
    fire.player.m_class=CLASS_CONJURER; fire.player.spec=SPEC_FIRE; fire.player.level=56;
    fire.curr_stats.Cha=150; fire.in_room=1; owner=&fire;
    SET_POS(&fire,STAT_NORMAL+POS_STANDING); SET_POS(&target,STAT_NORMAL+POS_STANDING);
    for(int spell:{SPELL_CONJURE_ELEMENTAL,SPELL_CONJURE_GREATER_ELEMENTAL}) {
        for(const char *arg:{""," ","mephit"," MePhIt \t"}) assert(!elemental_summon_failure_message(&fire,arg,spell));
        for(const char *arg:{"mephits","mephit 1112","strong","mephit extra"}) assert(elemental_summon_failure_message(&fire,arg,spell));
    }
    for(bool greater:{false,true}) for(int choice:{0,1,2}) for(int terrain:{SECT_INSIDE,SECT_FIREPLANE,SECT_WATER_PLANE}) for(int life:{0,100}) {
        rooms[1].sector_type=terrain; infuse=life; variant=choice;
        auto summon=greater?spell_conjour_greater_elemental:spell_conjour_elemental;
        rng=215; draws=0; char plain[]=""; summon(56,&fire,plain,0,nullptr,nullptr);
        assert(pets.size()==1 && IS_AFFECTED2(pets[0],AFF2_FIRESHIELD));
        const auto before=snapshot(pets[0]); clear(&fire);
        rng=215; draws=0; char option[]="mephit"; summon(56,&fire,option,0,nullptr,nullptr);
        assert(pets.size()==1 && !IS_AFFECTED2(pets[0],AFF2_FIRESHIELD));
        recalc_intrinsic(pets[0]); assert(!IS_AFFECTED2(pets[0],AFF2_FIRESHIELD));
        assert(snapshot(pets[0])==before && strstr(pets[0]->player.name,"mephit _Firetest_"));
        assert(IS_SET(pets[0]->only.npc->str_mask,STRUNG_KEYS));
        // Every random greater variant and regular prototype is retained.
        assert(GET_VNUM(pets[0])==(greater?1110+choice:1100));
        clear(&fire);
    }
    // Actual cap helpers see the same elemental identities in both modes.
    char option[]="mephit";
    for(int i=0;i<3;++i) spell_conjour_elemental(56,&fire,option,0,nullptr,nullptr);
    assert(pets.size()==3 && !can_conjure_lesser_elem(&fire,56) && !can_conjure_greater_elem(&fire,56));
    spell_conjour_greater_elemental(56,&fire,option,0,nullptr,nullptr); assert(pets.size()==3); clear(&fire);
    char invalid[]="mephit 1112"; spell_conjour_elemental(56,&fire,invalid,0,nullptr,nullptr); assert(pets.empty());
    // Fireball unlock uses player level, never the spell/item power.
    target.points.max_hit=target.points.hit=10000;
    target.specials.affected_by2=AFF2_GLOBE;
    for(int level:{50,51}) for(bool npc:{false,true}) {
        fire.player.level=level; fire.specials.act=npc?ACT_ISNPC:0; delivered_damage=0;
        spell_fireball(100,&fire,nullptr,0,&target,nullptr);
        assert(bool(delivered_damage)==(!npc&&level==51));
        assert(bool(damage_flags&SPLDAM_GLOBE)==(npc||level==50));
    }
    fire.specials.act=0; fire.player.level=56;
    target.specials.affected_by2=0;
    std::vector<unsigned> secondary;
    for(int spec:{SPEC_FIRE,SPEC_AIR}) for(bool npc:{false,true}) for(int type:{SPELL_TYPE_SPELL,SPELL_TYPE_WAND}) for(bool item:{false,true}) {
        fire.player.spec=spec; fire.specials.act=npc?ACT_ISNPC:0;
        obj_data object{}; rng=42; draws=0; blind_count=immolate_count=0;
        const int base=6*56+int((42u*1664525+1013904223)%25)+1;
        spell_solar_flare(56,&fire,nullptr,type,&target,item?&object:nullptr);
        assert(delivered_damage==((spec==SPEC_FIRE&&!npc&&type==SPELL_TYPE_SPELL&&!item)?base*110/100:base));
        std::vector<unsigned> observed{unsigned(draws),unsigned(blind_count),unsigned(immolate_count),rng};
        if(secondary.empty()) secondary=observed; else assert(observed==secondary);
    }
    fire.specials.act=0; fire.player.spec=SPEC_FIRE;
    fire.player.m_class=CLASS_ETHERMANCER; fire.player.spec=SPEC_STARMAGUS;
    rng=42; spell_solar_flare(56,&fire,nullptr,SPELL_TYPE_SPELL,&target,nullptr);
    assert(delivered_damage==(6*56+int((42u*1664525+1013904223)%25)+1));
    fire.player.m_class=CLASS_CONJURER; fire.player.spec=SPEC_FIRE;
    // Full Fire Form feeds the unchanged absorption and cold-vulnerability predicates.
    spell_fire_form(56,&fire,nullptr,0,&fire,nullptr);
    fire.points.max_hit=1000; fire.points.hit=1000;
    spell_fireball(56,&target,nullptr,0,&fire,nullptr);
    assert(fire.points.hit==1100);
    damage_mod cold_mod{};
    for(float &factor:dam_factor) factor=1.0;
    dam_factor[DF_VULNCOLD]=2.0;
    cold_response(&target,&fire,100,SPLDAM_COLD,0,&cold_mod,nullptr);
    assert(cold_mod.type==dam_mod_type::More && cold_mod.mod==1.0);
    while(fire.affected) { auto *af=fire.affected; fire.affected=af->next; delete af; }
    fire.specials.affected_by2=0;
    // Per-attacker Fireshield retaliation creates real owner memory; mephits omit it.
    char_data attackers[2]{}; npc_only_data npcs[2]{};
    for(int i=0;i<2;++i) { attackers[i].only.npc=&npcs[i]; attackers[i].specials.act=ACT_ISNPC|ACT_MEMORY; attackers[i].in_room=1; SET_POS(&attackers[i],STAT_NORMAL+POS_STANDING); }
    for(bool mephit:{false,true}) {
        char plain[]=""; rng=215;
        spell_conjour_elemental(56,&fire,mephit?option:plain,0,nullptr,nullptr); auto *pet=pets[0];
        for(auto &attacker:attackers) { shield_retaliation(&attacker,pet,100); assert(bool(CheckFor_remember(&attacker,&fire))==!mephit); clearMemory(&attacker); }
        spell_damage(pet,&attackers[0],10,SPLDAM_GENERIC,0,nullptr);
        assert(CheckFor_remember(&attackers[0],&fire)); clearMemory(&attackers[0]); clear(&fire);
    }
    puts("Fire: caller unlock/damage, optional original variants, matched RNG/stats/control/lifetime, string ownership and retaliation memory passed.");
}
'''

build=ROOT/'bin/tests/conjurer-fire'; build.mkdir(parents=True,exist_ok=True)
cpp,binary=build/'harness.cpp',build/'harness'
cpp.write_text(prelude+'\n'.join(extract_function(file,sig) for file,sig in functions)+damage_path+retaliation+recalc+cold+driver)
subprocess.run(['g++','-std=c++20','-g','-ffunction-sections','-fdata-sections','-fsanitize=address,undefined',
                '-fno-omit-frame-pointer','-fno-pie','-no-pie','-I'+str(ROOT/'src'),str(cpp),str(HARNESS_STUBS),
                '-Wl,--gc-sections','-lbsd','-o',str(binary)],check=True)
subprocess.run([str(binary)],check=True)
