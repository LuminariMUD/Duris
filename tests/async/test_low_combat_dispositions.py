#!/usr/bin/env python3
"""Execute #715's low combat, Ogre Roar and player-corpse golem audit paths."""
import re
import subprocess

from _paths import ROOT, extract_function, source
from _source_contract import strip_comments

prelude = r'''
#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "classes/necromancy.h"
#include "player/pet_restore_runtime.h"
#include "magic/spells.h"
#include "net/comm.h"
#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
static room_data rooms[2]{};
P_room world=rooms;
static index_data indexes[10]{};
P_index obj_index=indexes;
static char_data mob{};
static npc_only_data npc{};
static P_char target;
static P_obj corpse;
static int roll, loaded, consumed, scheduled;
static std::vector<std::string> audit, staff;
int number(int low,int high) { return std::clamp(roll,low,high); }
int dice(int count,int sides) { return count*sides; }
const Rolls live_rolls={dice,number};
int BOUNDED(int low,int value,int high) { return std::clamp(value,low,high); }
int STAT_INDEX(int) { return 10; }
int GET_ALT_SIZE(P_char ch) { return ch->player.size; }
int GET_CLASS(P_char ch,uint cls) { return ch->player.m_class&cls; }
int GET_CHAR_SKILL_P(P_char ch,int skill) { return ch->only.pc->skills[skill].learned; }
float get_property(const char *,double fallback) { return fallback; }
void act(const char *,int,P_char,P_obj,void *,int) {}
void send_to_char(const char *,P_char) {}
void debug(const char *,...) {}
void logit(const char *kind,const char *format,...) {
    if(strcmp(kind,LOG_CORPSE)) return;
    char text[1024]; va_list args; va_start(args,format);
    vsnprintf(text,sizeof(text),format,args); va_end(args); audit.emplace_back(text);
}
void wizlog(int,const char *format,...) {
    char text[1024]; va_list args; va_start(args,format);
    vsnprintf(text,sizeof(text),format,args); va_end(args); staff.emplace_back(text);
}
P_char get_linked_char(P_char,ush_int) { return nullptr; }
bool has_innate(P_char,int id) { return id==INNATE_OGREROAR; }
bool check_innate_time(P_char,int,int) { return true; }
bool is_dragoon_mounted(P_char) { return true; }
bool affected_by_spell(P_char ch,int type) {
    for(auto *af=ch->affected;af;af=af->next) if(af->type==type) return true;
    return false;
}
affected_type *affect_to_char(P_char ch,affected_type *af) {
    auto *copy=new affected_type(*af); copy->next=ch->affected; ch->affected=copy; return copy;
}
void set_short_affected_by(P_char ch,int type,int duration) {
    affected_type af{}; af.type=type; af.duration=duration; affect_to_char(ch,&af);
}
void clear(P_char ch) { while(ch->affected) { auto *af=ch->affected; ch->affected=af->next; delete af; } }
char *one_argument(const char *arg,char *name) { strcpy(name,arg); return const_cast<char *>(arg+strlen(arg)); }
P_char get_char_room_vis(P_char,const char *) { return target; }
int CanDoFightMove(P_char,P_char) { return true; }
void stop_fighting(P_char ch) { ch->specials.fighting=nullptr; }
void remember(P_char,P_char) {}
void MobStartFight(P_char,P_char) {}
bool ac_can_see(P_char,P_char,bool) { return true; }
bool is_wearing_necroplasm(P_char) { return false; }
int count_undead(P_char) { return 0; }
P_obj get_globe(P_char) { return nullptr; }
int real_mobile(int vnum) { return vnum; }
P_char read_mobile(int,int) {
    ++loaded;
    mob={}; npc={}; mob.only.npc=&npc; mob.specials.act=ACT_ISNPC;
    SET_POS(&mob,STAT_NORMAL+POS_STANDING);
    mob.base_stats.Str=mob.base_stats.Agi=mob.base_stats.Con=100;
    return &mob;
}
void MonkSetSpecialDie(P_char ch) { ch->points.damnodice=2; ch->points.damsizedice=6; }
void summoned_pet_mark(P_char,summoned_pet_kind) {}
bool char_to_room(P_char ch,int room,int) { ch->in_room=room; return true; }
void obj_from_obj(P_obj obj) {
    if(corpse->value[CORPSE_FLAGS]&PC_CORPSE)
        assert(!audit.empty() && audit.back().find(obj->name)!=std::string::npos);
    assert(corpse->contains==obj); corpse->contains=obj->next_content; obj->next_content=nullptr;
}
bool obj_to_char(P_obj obj,P_char ch) { obj->next_content=ch->carrying; ch->carrying=obj; return true; }
obj_affect *get_obj_affect(P_obj,int) { return nullptr; }
int obj_affect_time(P_obj,obj_affect *) { return 0; }
void extract_obj(P_obj obj,int) { assert(obj==corpse && !obj->contains); ++consumed; }
void remove_plushit_bits(P_char) {}
void balance_affects(P_char) {}
int setup_pet(P_char,P_char,int duration,int flag) { assert(flag==PET_NOCASH); return duration; }
void add_follower(P_char pet,P_char ch) { pet->following=ch; }
void schedule_pet_death(P_char,int delay) { assert(delay>0); ++scheduled; }
'''

necro = source('necromancy.c').read_text()
table = re.search(r'const struct golem_description golem_data\[4\] = .*?;', necro, re.S).group()
functions = []
for file, names in {
    'necromancy.c': 'raised_undead_corpse_margin raised_undead_strict_below '
                    'corpse_pet_globe_life raised_undead_late_death_roll raised_undead_death_delay '
                    'golem_power golem_cap golem_armor golem_form_roll golem_form_above '
                    'golem_hit_points golem_hitroll golem_damroll create_golem',
    'new_skills.c': 'ogre_roar_roll ogre_roar_worst_duration ogre_roar_best_duration '
                    'ogre_roar_duration ogre_roar_best_ac ogre_roar_ac ogre_roar_hitroll_divisor '
                    'ogre_roar_best_hitroll_divisor ogre_roar_worst_hitroll_divisor '
                    'ogre_roar_threshold do_ogre_roar',
}.items():
    text = source(file).read_text()
    for name in names.split():
        signature = re.search(r'^(?:static )?[\w:]+ '+name+r'\([^;\n]*', text, re.M).group()
        functions.append(extract_function(file, signature))
violence = strip_comments(extract_function('fight.c', 'void perform_violence('))
ignis = violence[violence.index('if (IS_DRAGOON(opponent)'):violence.index('if (!IS_SUNLIT(ch->in_room))')]

driver = r'''
int main() {
    char_data caster{}, victim{}; pc_only_data pc{}, victim_pc{};
    caster.only.pc=&pc; victim.only.pc=&victim_pc;
    SET_POS(&caster,STAT_NORMAL+POS_STANDING); SET_POS(&victim,STAT_NORMAL+POS_STANDING);
    caster.player.level=victim.player.level=50;
    caster.in_room=victim.in_room=1; caster.player.name=const_cast<char *>("Builder");
    rooms[1].number=1234; target=&victim;
    // Exhaust the activation roll: only the defending Dragoon's Power matters.
    victim.player.m_class=CLASS_DRAGOON;
    victim_pc.skills[SKILL_SPELL_KNOWLEDGE_SHAMAN].learned=100;
    for(int attacker_power : {20,100,200}) for(int defender_power : {20,100,200}) {
        caster.curr_stats.Pow=attacker_power; victim.curr_stats.Pow=defender_power;
        int activations=0;
        for(roll=1;roll<=100;++roll) {
            affected_type af{}; af.type=SPELL_SANGUINIS_IGNIS; affect_to_char(&victim,&af);
            ignis(&caster,&victim);
            activations+=affected_by_spell(&victim,SPELL_SANGUINIS_IGNIS_AFF);
            clear(&victim);
        }
        assert(activations==11+defender_power/20);
    }
    caster.curr_stats.Pow=victim.curr_stats.Pow=100;
    caster.curr_stats.Wis=victim.curr_stats.Wis=100;
    caster.points.hitroll=80; victim.points.hitroll=60;
    char argument[]="target";
    for(int result : {1,40,101}) {
        roll=result; do_ogre_roar(&caster,argument,0);
        P_char recipient=result==101 ? &caster : &victim;
        P_char other=result==101 ? &victim : &caster;
        assert(!other->affected && recipient->affected && recipient->affected->next);
        assert(recipient->affected->location==APPLY_HITROLL);
        assert(recipient->affected->next->location==APPLY_AC);
        if(result==101) {
            assert(recipient->affected->modifier==-40);
            assert(recipient->affected->next->modifier==26);
        }
        clear(&caster); clear(&victim);
    }
    // Run the real golem handler with two pieces of corpse equipment, including
    // the player-corpse branch; every item is logged before its unchanged transfer.
    for(bool player_corpse : {false,true}) for(int type : {0,1,2,3}) {
        obj_data remains{}, first{}, second{}; corpse=&remains;
        caster.player.level=56; caster.player.m_class=type==3 ? CLASS_THEURGIST : CLASS_NECROMANCER;
        remains.type=ITEM_CORPSE; remains.value[CORPSE_LEVEL]=56;
        remains.value[CORPSE_FLAGS]=player_corpse ? PC_CORPSE : 0;
        remains.loc.room=1; remains.short_description=const_cast<char *>("the corpse of Test");
        first.name=const_cast<char *>("sword"); first.R_num=1; indexes[1].virtual_number=101;
        second.name=const_cast<char *>("shield"); second.R_num=2; indexes[2].virtual_number=202;
        first.next_content=&second; remains.contains=&first;
        audit.clear(); staff.clear(); loaded=consumed=scheduled=0; roll=50;
        create_golem(56,&caster,nullptr,&remains,type);
        assert(loaded==1 && consumed==1 && scheduled==1 && mob.following==&caster);
        assert(mob.carrying==&second && second.next_content==&first && !first.next_content);
        if(player_corpse) {
            assert(audit.size()==3 && staff.size()==1);
            assert(audit[0].find("golem")!=std::string::npos && audit[0].find("Builder")!=std::string::npos);
            assert(audit[1].find("[101] sword")!=std::string::npos);
            assert(audit[2].find("[202] shield")!=std::string::npos);
        } else assert(audit.empty() && staff.empty());
    }
    // Refuse an over-level corpse before loading a mobile into the game. The
    // old ordering left an unplaced mobile alive on every rejected attempt.
    for(int type : {0,1,3}) for(bool player_corpse : {false,true}) {
        obj_data remains{}, equipment{}; corpse=&remains;
        caster.player.level=type==1 ? 46 : 41;
        caster.player.m_class=type==3 ? CLASS_THEURGIST : CLASS_NECROMANCER;
        remains.type=ITEM_CORPSE; remains.value[CORPSE_LEVEL]=70;
        remains.value[CORPSE_FLAGS]=player_corpse ? PC_CORPSE : 0;
        remains.loc.room=1; remains.contains=&equipment;
        audit.clear(); staff.clear(); loaded=consumed=scheduled=0;
        create_golem(caster.player.level,&caster,nullptr,&remains,type);
        assert(!loaded && !consumed && !scheduled && remains.contains==&equipment);
        assert(audit.empty() && staff.empty());
    }
    puts("PASS low combat: defender Power, Ogre Roar recipients, corpse audit/transfer and golem rejection");
}
'''

build = ROOT / 'bin/tests/low-combat-dispositions'
build.mkdir(parents=True, exist_ok=True)
cpp, binary = build/'harness.cpp', build/'harness'
cpp.write_text(prelude+table+'\n'+'\n'.join(functions)+'\nvoid ignis(P_char ch,P_char opponent) {\n(void)ch;\n'+ignis+'}\n'+driver)
subprocess.run(['g++','-std=c++20','-g','-Wall','-Wextra','-Werror',
                '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie',
                '-Isrc',str(cpp),'-o',str(binary)], cwd=ROOT, check=True)
subprocess.run([str(binary)], check=True, timeout=30)
