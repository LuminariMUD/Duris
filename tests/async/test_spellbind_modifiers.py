#!/usr/bin/env python3
"""Run Spellbind's command and committed mutation against independent item affects."""
import re
import subprocess
from _paths import ROOT, source
from _source_contract import function_bodies, strip_comments


def function(file, name):
    text = strip_comments(source(file).read_text())
    signature = r"(?m)^(?:static )?[\w:* ]+\b" + name + r"\s*\([^;]*?\)\s*\n(?=\{)"
    head = re.search(signature, text)
    assert head, name
    return head.group() + function_bodies(text, signature)[0]


cpp = r'''#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "world/epic.h"
#include "world/epic_transaction.h"
#include "magic/spells.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <vector>
P_obj object_list;
static bool strong, accepted=true, busy, has_identity=true;
static int submitted, refunded;
int number(int lo,int hi) {
    if(lo==0 && hi==40) return strong ? 0 : 1;
    return std::max(lo,1);
}
int dice(int count,int size) { return count*size; }
const Rolls live_rolls={dice,number};
int BOUNDED(int lo,int value,int hi) { return std::clamp(value,lo,hi); }
int GET_CHAR_SKILL_P(P_char ch,int skill) { return ch->only.pc->skills[skill].learned; }
void send_to_char(const char *,P_char) {}
void act(const char *,int,P_char,P_obj,void *,int) {}
int set_obj_condition(P_obj item,int value) { item->condition=value; return value; }
P_obj setsuffix_obj_new(P_obj item) { return item; }
void set_keywords(P_obj,const char *) {}
void set_short_description(P_obj,const char *) {}
char *one_argument(char *arg,char *word) { std::strcpy(word,arg); return arg+std::strlen(arg); }
P_obj get_obj_in_list_vis(P_char,const char *,P_obj list,bool) { return list; }
void persistence_assign_item_uid(P_obj obj,const char *) { if(has_identity) obj->obj_uid=1; }
bool epic_transaction_submit(P_char ch,int64_t delta,epic_reason_type,int64_t,uint16_t,
    critical_source_site,critical_deadline_class,epic_completion_fn completion,const void *context,size_t size) {
    if(busy) return false;
    if(delta>0) { ++refunded; ch->only.pc->epics+=delta; return true; }
    ++submitted;
    if(accepted) ch->only.pc->epics+=delta;
    if(completion) completion(ch,accepted,{},0,static_cast<const uint8_t *>(context),size);
    return true;
}
struct spellbind_context {unsigned long object_uid; int skill;};
'''
for file, names in (("salchemist.c", "spellbind_failure_roll spellbind_success_damage_roll spellbind_strong_roll spellbind_condition_loss spellbind_bonus spellbind_fine_bonus carried_object_by_uid is_neg_good"),
                    ("actobj.c", "is_stat_max"),
                    ("salchemist.c", "spellbind_committed do_spellbind")):
    cpp += "\n".join(function(file,name) for name in names.split()) + "\n"
cpp += r'''
int main() {
    char_data actor{}; pc_only_data pc{}; actor.only.pc=&pc;
    actor.player.level=20; actor.player.name=const_cast<char *>("Mage");
    actor.specials.position=STAT_NORMAL+POS_STANDING;
    obj_data item{}; object_list=&item; actor.carrying=&item;
    item.loc_p=LOC_CARRIED; item.loc.carrying=&actor;
    item.name=const_cast<char *>("ring"); item.short_description=const_cast<char *>("a ring");
    auto reset=[&] { item.extra_flags=0; item.condition=100; item.obj_uid=1; pc.epics=10;
                    for(auto &af:item.affected) { af={}; } strong=false; accepted=has_identity=true; busy=false; submitted=refunded=0; };
    auto commit=[&](int skill) { spellbind_context context{item.obj_uid,skill};
        spellbind_committed(&actor,true,{},0,reinterpret_cast<const uint8_t *>(&context),sizeof(context)); };
    const int locations[3]={APPLY_HITROLL,APPLY_ARMOR,APPLY_SAVING_SPELL};
    const int values[3]={3,-5,-2};
    // Reordering the affects cannot change the result for any individual stat.
    std::vector<int> order={0,1,2};
    do {
        reset();
        for(int i=0;i<3;++i) item.affected[i]={sbyte(locations[order[i]]),sbyte(values[order[i]])};
        commit(100);
        const int expected[3]={8,-10,-4};
        for(int i=0;i<3;++i) assert(item.affected[i].modifier==expected[order[i]]);
    } while(std::next_permutation(order.begin(),order.end()));
    // Every supported nonzero modifier improves in its beneficial direction without signed-byte wrap.
    for(int skill : {1,10,19,20,49,50,99,100}) for(bool powerful : {false,true})
        for(int location=1;location<APPLY_LUCK_MAX;++location) for(int value : {-119,-50,-5,-1,1,5,50,119}) {
            reset(); strong=powerful; item.affected[0]={sbyte(location),sbyte(value)}; commit(skill);
            int result=item.affected[0].modifier;
            assert(is_neg_good(location) ? result<value : result>value);
            assert(result>=-120 && result<=120);
        }
    reset(); strong=true;
    for(int i=0;i<3;++i) item.affected[i]={sbyte(locations[i]),sbyte(values[i])};
    commit(100); assert(item.affected[0].modifier==9 && item.affected[1].modifier==-15 && item.affected[2].modifier==-5);
    reset(); item.affected[0]={APPLY_ARMOR,-5}; item.affected[1]={APPLY_LUCK_MAX,5};
    commit(10); assert(item.affected[0].modifier==-6 && item.affected[1].modifier==5);
    reset(); item.affected[0]={APPLY_HITROLL,120}; item.affected[1]={APPLY_ARMOR,-120};
    commit(100); assert(item.affected[0].modifier==120 && item.affected[1].modifier==-120);
    // Exercise the real command-to-completion path and its one-point spend.
    reset(); pc.skills[SKILL_SPELLBIND].learned=100; item.affected[0]={APPLY_ARMOR,-5}; char arg[]="ring";
    do_spellbind(&actor,arg,0); assert(submitted==1 && pc.epics==9 && item.affected[0].modifier==-10);
    assert((item.extra_flags & (ITEM_NOREPAIR|ITEM_NOLOCATE))==(ITEM_NOREPAIR|ITEM_NOLOCATE));
    reset(); accepted=false; item.affected[0]={APPLY_ARMOR,-5}; do_spellbind(&actor,arg,0);
    assert(pc.epics==10 && item.affected[0].modifier==-5 && item.extra_flags==0);
    reset(); busy=true; do_spellbind(&actor,arg,0); assert(pc.epics==10 && item.extra_flags==0);
    reset(); has_identity=false; item.obj_uid=0; do_spellbind(&actor,arg,0); assert(submitted==0 && pc.epics==10);
    reset(); item.condition=99; commit(100); assert(refunded==1 && item.extra_flags==0);
    std::puts("PASS Spellbind: independent affects, beneficial signs, low skills, strong magic, byte limits and command/transaction outcomes");
}
'''
out=ROOT / "bin/tests/spellbind-modifiers"
out.mkdir(parents=True,exist_ok=True)
path,binary=out / "harness.cpp",out / "harness"
path.write_text(cpp)
subprocess.run(["g++","-std=c++20","-Wall","-Wextra","-Werror","-ffunction-sections","-fdata-sections",
                "-Wl,--gc-sections","-fsanitize=address,undefined","-fno-sanitize-recover=all","-fno-pie","-no-pie",
                "-Isrc",str(path),"-o",str(binary)],cwd=ROOT,check=True)
subprocess.run([str(binary)],check=True,timeout=30)
