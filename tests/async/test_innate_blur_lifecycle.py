#!/usr/bin/env python3
"""Execute Blur casting, affect removal/countdown and intrinsic bit rebuilding."""
import subprocess
from _paths import ROOT, HARNESS_STUBS, extract_function

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/mm.h"
#include "net/gmcp.h"
#include "magic/spells.h"
#include "item/named_set_effects.h"
#include "world/specs.prototypes.h"
#include "cmd/interp.h"
#include "net/comm.h"
#include "world/events.h"
#include <cassert>
#include <cstdio>
#include <cstring>
static mm_ds pool{};
mm_ds *dead_affect_pool = &pool;
static hold_data TmpAffs{};
int GET_CLASS(P_char ch,uint cls) { return (ch->player.m_class & cls) != 0; }
int GET_CHAR_SKILL_P(P_char,int) { return 0; }
bool has_innate(P_char ch,int id) { return id == INNATE_BLUR && GET_RACE(ch) == RACE_DRAGON && GET_LEVEL(ch) >= 56; }
void *_mm_get(mm_ds *,const char *,int) { return new affected_type{}; }
void mm_release(mm_ds *,void *p) { delete static_cast<affected_type *>(p); }
mm_ds *mm_create(const char *,size_t,size_t,unsigned) { return &pool; }
void gmcp_char_affects(P_char) {}
int char_light(P_char) { return 0; }
int room_light(int,int) { return 0; }
void balance_affects(P_char) {}
void unlink_char_affect(P_char,affected_type *) { assert(false); }
void unlink_char_obj_affect(P_char,affected_type *) { assert(false); }
void disarm_char_nevents(P_char,event_func_type) {}
void event_web_spray(P_char,P_char,P_obj,void *) {}
nevent_schedule_result add_event(event_func,int,P_char,P_char,P_obj,int,const void *,int) { return {}; }
nevent_handle nevent_handle_from_event(P_nevent) { return {}; }
nevent_cancel_result nevent_cancel(nevent_handle) { return nevent_cancel_result::canceled; }
void send_to_char(const char *,P_char) {}
void act(const char *,int,P_char,P_obj,void *,int) {}
void wear_off_message(P_char,affected_type *) {}
int IS_MORPH(P_char) { return false; }
P_char un_morph(P_char) { assert(false); return nullptr; }
bool isname(const char *,const char *) { return true; }
proc_data *defense_proc_data(P_obj,P_char,int,int,char *) { assert(false); return nullptr; }
P_char melee_proc_target(P_obj,P_char,int,char *) { assert(false); return nullptr; }
int number(int low,int) { return low; }
bool hit(P_char,P_char,P_obj,int *) { assert(false); return false; }
int char_in_list(const P_char) { return true; }
void act_trio(const char *,const char *,const char *,int,P_char,P_obj,P_char) { assert(false); }
'''
# Only the stat-free bit/innate portion of apply_affs is relevant here; execute it
# unchanged. List insertion/removal and the actual expiry loop are production.
apply = extract_function("affects.c", "void apply_affs(")
a = apply.index("\tif (mode)\n")
b = apply.index("\n\t/*\n\t * for stats,",a)
rebuild = "void apply_bits(P_char ch,int mode) {\n" + apply[a:b] + "}\n"
rebuild += r'''
void all_affects(P_char ch,int mode) {
    TmpAffs = {};
    for (auto *af = ch->affected; af; af = af->next) TmpAffs.BV_3 |= af->bitvector3;
    apply_bits(ch,mode);
}
'''
functions = [("affects.c",s) for s in (
    "bool affected_by_spell(", "struct affected_type *affect_to_char(",
    "void affect_remove(", "void affect_from_char(",
)] + [("magic.c", "static int blur_duration("), ("magic.c", "void spell_blur(int /*level*/,")]
updates = extract_function("affects.c", "void affect_update(")
a = updates.index("\t\t\tfor (af = i->affected;")
b = updates.index("\n\t\t\tif (morphed)",a)
tick = "void tick(P_char i) { affected_type *af,*next_af_dude; P_char orig; int morphed = FALSE;\n" + updates[a:b] + "}\n"
driver = r'''
int main() {
    for (int race : {RACE_HUMAN,RACE_DRAGON}) for (int level : {55,56}) {
        char_data ch{}; ch.player.race = race; ch.player.level = level;
        ch.player.m_class = CLASS_WARRIOR;
        SET_POS(&ch,POS_STANDING + STAT_NORMAL);
        const bool innate = race == RACE_DRAGON && level == 56;
        all_affects(&ch,true);
        assert(bool(IS_AFFECTED3(&ch,AFF3_BLUR)) == innate);
        spell_blur(level,&ch,nullptr,0,&ch,nullptr);
        assert(IS_AFFECTED3(&ch,AFF3_BLUR));
        for (int n = 0; n < 11; ++n) tick(&ch);
        assert(!ch.affected && bool(IS_AFFECTED3(&ch,AFF3_BLUR)) == innate);
        spell_blur(level,&ch,nullptr,0,&ch,nullptr);
        affect_from_char(&ch,SPELL_BLUR); // the normal dispel removal path
        assert(!ch.affected && bool(IS_AFFECTED3(&ch,AFF3_BLUR)) == innate);
        all_affects(&ch,false); all_affects(&ch,true);
        assert(bool(IS_AFFECTED3(&ch,AFF3_BLUR)) == innate);
        spell_blur(level,&ch,nullptr,0,&ch,nullptr);
        obj_data weapon{}; weapon.loc_p = LOC_WORN; weapon.loc.wearing = &ch;
        char name[] = "mangler";
        madman_mangler(&weapon,&ch,CMD_REMOVE,name);
        assert(!ch.affected && bool(IS_AFFECTED3(&ch,AFF3_BLUR)) == innate);
    }
    puts("Innate Blur: initial recalculation, normal expiry, dispel, repeated recalculation and proc removal passed.");
}
'''
build = ROOT/"bin/tests/innate-blur-lifecycle"
build.mkdir(parents=True,exist_ok=True)
cpp,binary = build/"harness.cpp",build/"harness"
cpp.write_text(prelude + rebuild + "\n".join(extract_function(f,s) for f,s in functions) + tick +
               extract_function("specs.object.c", "int madman_mangler(") + driver)
subprocess.run(["g++","-std=c++20","-g","-fsanitize=address,undefined","-I"+str(ROOT/"src"),
                str(cpp),str(HARNESS_STUBS),"-o",str(binary)],check=True)
subprocess.run([str(binary)],check=True)
