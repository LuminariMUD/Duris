#!/usr/bin/env python3
"""Dissonance releases a cast-owned wait, never an unrelated replacement wait."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

prelude=r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
static nevent_data cast_event{}, first_wait{}, later_wait{};
static spellcast_datatype scheduled_data{};
static P_nevent current_wait;
static bool casting, abort_pending;
static int canceled, extra_lag;
unsigned long long ne_event_tick=100;
void event_spellcast(P_char,P_char,P_obj,void *) {}
void event_wait(P_char,P_char,P_obj,void *) {}
void event_abort_spell(P_char,P_char,P_obj,void *);
void send_to_char(const char *,P_char) {}
bool abort_item_action(P_char) { return false; }
void clear_links(P_char,ush_int) {}
P_nevent get_scheduled(P_char,event_func_type fn) {
    return fn==event_spellcast ? (casting?&cast_event:nullptr) : fn==event_wait?current_wait:nullptr;
}
void show_abort_casting(P_char ch) { casting=false; REMOVE_BIT(ch->specials.affected_by2,AFF2_CASTING); }
nevent_handle nevent_handle_from_event(P_nevent event) { return {event,event->sequence}; }
nevent_cancel_result nevent_cancel(nevent_handle handle) {
    assert(current_wait==handle.event && current_wait->sequence==handle.sequence);
    ++canceled; current_wait=nullptr; return nevent_cancel_result::canceled;
}
nevent_schedule_result add_event(event_func,int,P_char,P_char,P_obj,int,const void *data,int size) {
    assert(size==sizeof(spellcast_datatype)); scheduled_data=*static_cast<const spellcast_datatype *>(data);
    cast_event.data=&scheduled_data; casting=true; return {nevent_schedule_status::scheduled,{&cast_event,1}};
}
void disarm_char_nevents(P_char,event_func_type fn) { assert(fn==event_abort_spell); abort_pending=false; }
void CharWait(P_char,int) { ++extra_lag; }
void __free(void *value,const char *,int) { std::free(value); }
'''
functions="\n".join(extract_function("sparser.c",sig) for sig in (
    "void StopCasting(", "void interrupt_spellcasting(", "static bool schedule_spellcast(",
    "void event_abort_spell(P_char ch,",
))
driver=r'''
int main() {
    char_data ch{}; ch.specials.position=POS_STANDING|STAT_NORMAL;
    first_wait.sequence=10; later_wait.sequence=11;
    for (int scenario=0;scenario<4;++scenario) {
        casting=false; canceled=extra_lag=0;
        current_wait=scenario==2?nullptr:&first_wait;
        ch.specials.act2=PLR2_WAIT; ch.specials.affected_by2=AFF2_CASTING;
        ch.specials.wait_until_pulse=1000;
        spellcast_datatype data{};
        assert(schedule_spellcast(&ch,&ch,4,&data));
        assert(scheduled_data.wait_sequence==(scenario==2?0:10));
        if (scenario==1 || scenario==2) current_wait=&later_wait;
        if (scenario==3) current_wait=nullptr, REMOVE_BIT(ch.specials.act2,PLR2_WAIT);
        // Continuations must retain the original wait's identity.
        spellcast_datatype continuation=scheduled_data;
        assert(schedule_spellcast(&ch,&ch,4,&continuation));
        abort_pending=true;
        interrupt_spellcasting(&ch);
        assert(!casting && !IS_AFFECTED2(&ch,AFF2_CASTING) && !extra_lag);
        if (scenario==0) {
            assert(canceled==1 && !current_wait && !(ch.specials.act2&PLR2_WAIT));
            assert(ch.specials.wait_until_pulse==0);
        } else if (scenario==1 || scenario==2) {
            assert(!canceled && current_wait==&later_wait && (ch.specials.act2&PLR2_WAIT));
            assert(ch.specials.wait_until_pulse==1000);
        } else assert(!canceled && !current_wait);
        // The old top-circle failure must not abort an immediate replacement cast.
        casting=true; SET_BIT(ch.specials.affected_by2,AFF2_CASTING);
        if (abort_pending) event_abort_spell(&ch,nullptr,nullptr,nullptr);
        assert(casting && IS_AFFECTED2(&ch,AFF2_CASTING));
    }
    std::puts("PASS casting wait released, replacement/unowned waits retained, continuations preserve ownership, no recovery lag");
}
'''
build=ROOT/"bin/tests";build.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix="dissonance-wait-",dir=build) as temporary:
    cpp,binary=Path(temporary)/"test.cpp",Path(temporary)/"test"
    cpp.write_text(prelude+functions+driver)
    subprocess.run(["g++","-std=c++20","-Wall","-Wextra","-Werror","-fsanitize=address,undefined",
                    "-Isrc",str(cpp),"-o",str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],check=True)
