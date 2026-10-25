#!/usr/bin/env python3
"""Exercise Conjure Water on the real scheduler with isolated object services."""
import os
import re
import subprocess

from _paths import ROOT, HARNESS_STUBS, extract_function, source

innates = source('innates.c').read_text()
table = re.search(r'const struct innate_data innates_data\[LAST_INNATE \+ 1\] = .*?\n};', innates, re.S)[0]
table = re.sub(r'(\{ "[^"]+", )\w+( \})', r'\1NULL\2', table)
arrays = innates[innates.index('char racial_innates['):innates.index('extern const struct race_names')]
macros = innates[innates.index('#define ADD_RACIAL_INNATE'):innates.index('float regen_factor')]
assert 'innate.timer.secs.conjureWater=300.000' in (ROOT / 'lib/duris.properties').read_text()
leave = extract_function('handler.c', 'void char_from_room(')
assert leave.index('ROOM_PROC_LEAVE_VETO') < leave.index('disarm_char_nevents(ch, event_conjure_water)') < leave.index('item_actions_character_leaving(ch)')
assert 'disarm_char_nevents(ch, NULL)' in extract_function('handler.c', 'void extract_char(')

prelude = r'''
#include "world/new_events.c"
#include "classes/necromancy.h"
#include <cassert>
#include <cstring>
#include <string>
int pulse;
bool after_events_call;
P_char character_list;
P_obj object_list;
index_data indexes[1]{};
P_index obj_index = indexes, mob_index = indexes;
room_data rooms[2]{};
P_room world = rooms;
const int top_of_world = 1;
static mm_ds pool{};
static int lag, successes, created, removed;
static bool creation_fails, placement_fails, revoke_on_placement;
static std::string output;
bool nevent_periodic_begin(P_nevent) { return false; }
void nevent_periodic_complete(P_nevent) {}
void nevent_periodic_watchdog() {}
bool nevent_periodic_event_is_valid(P_nevent) { return true; }
long nevent_periodic_integrity_errors(bool) { return 0; }
void *__malloc(size_t size, const char *, const char *, int) { return std::malloc(size); }
void __free(void *pointer, const char *, int) { std::free(pointer); }
void *_mm_get(mm_ds *p, const char *, int) { ++p->objs_used; return std::calloc(1,sizeof(nevent_data)); }
void mm_release(mm_ds *p, void *memory) { --p->objs_used; std::free(memory); }
char_link_data *link_char(P_char, P_char, ush_int) { assert(false); return nullptr; }
void remove_link(P_char, char_link_data *) { assert(false); }
const char *event_name_registry_lookup(const void *) { return nullptr; }
void release_mob_mem(P_char, P_char, P_obj, void *) {}
#define LABEL(name) void name(P_char, P_char, P_obj, void *) {}
LABEL(event_hit_regen) LABEL(event_move_regen) LABEL(event_ward_regen)
LABEL(event_spellcast) LABEL(event_memorize) LABEL(event_balance_affects)
LABEL(event_item_action_active) LABEL(event_mob_mundane) LABEL(event_reset_zone)
LABEL(event_autosave) LABEL(event_wait)
#undef LABEL
int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) != 0; }
void send_to_char(const char *text, P_char) { output += text; }
void send_to_room(const char *, int) { ++successes; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void CharWait(P_char, int pulses) { lag += pulses; }
int get_property(const char *key, int fallback) { return !strcmp(key,"innate.timer.secs.conjureWater") ? 300 : fallback; }
void event_short_affect(P_char, P_char, P_obj, void *);
affected_type *affect_to_char(P_char ch, affected_type *af) {
    auto *copy = new affected_type(*af); copy->next = ch->affected; ch->affected = copy;
    if (af->flags & AFFTYPE_SHORT) {
        event_short_affect_data data{ch,copy};
        assert(add_event(event_short_affect,af->duration,ch,nullptr,nullptr,0,&data,sizeof(data)));
    }
    return copy;
}
void wear_off_message(P_char, affected_type *) {}
void affect_remove(P_char ch, affected_type *af) {
    auto **link = &ch->affected; while (*link && *link != af) link = &(*link)->next;
    assert(*link); *link = af->next; delete af;
}
P_obj read_object(int vnum, int) {
    assert(vnum == 93300); if (creation_fails) return nullptr;
    auto *obj = new obj_data{}; obj->R_num = 0; obj->loc_p = LOC_NOWHERE;
    obj->next = object_list; object_list = obj; ++created; return obj;
}
void obj_to_room(P_obj obj, int room) {
    if (placement_fails) return;
    obj->loc_p = LOC_ROOM; obj->loc.room = room;
    obj->next_content = rooms[room].contents; rooms[room].contents = obj;
    if (revoke_on_placement) character_list->player.spec = SPEC_AIR;
}
void extract_obj(P_obj obj, int) {
    disarm_obj_nevents(obj,nullptr);
    if (OBJ_ROOM(obj)) {
        auto **link = &rooms[obj->loc.room].contents;
        while (*link && *link != obj) link = &(*link)->next_content;
        assert(*link); *link = obj->next_content;
    }
    auto **link = &object_list; while (*link && *link != obj) link = &(*link)->next;
    assert(*link); *link = obj->next; delete obj; ++removed;
}
static void expire_spring(P_char, P_char, P_obj obj, void *) { extract_obj(obj); }
void set_obj_affected(P_obj obj, int delay, sh_int type, sh_int) {
    assert(type == TAG_OBJ_DECAY && delay == 15*60*WAIT_SEC);
    assert(add_event(expire_spring,delay,nullptr,nullptr,obj,0,nullptr,0));
}
'''

functions = [
    ('utility.c', 'int flag2idx('),
    ('affects.c', 'struct affected_type *get_spell_from_char('),
    ('affects.c', 'bool affected_by_spell('),
    ('affects.c', 'void event_short_affect('),
    ('innates.c', 'static int innate_char_race('),
    ('innates.c', 'static int innate_unlock_level('),
    ('innates.c', 'bool has_innate('),
    ('innates.c', 'void assign_innates('),
    ('innates.c', 'void get_property_format('),
    ('innates.c', 'int get_innate_property('),
    ('innates.c', 'bool can_use_innate('),
    ('innates.c', 'bool check_innate_time('),
    ('innates.c', 'static bool conjured_spring_in_room('),
    ('innates.c', 'void event_conjure_water('),
    ('innates.c', 'void do_conjure_water(P_char ch,'),
]
driver = r'''
static void advance(int ticks) {
    for (int i = 0; i < ticks; ++i) { ne_events(); nevent_advance_tick(); }
}
static void clear(P_char ch) {
    disarm_char_nevents(ch,nullptr);
    while (ch->affected) affect_remove(ch,ch->affected);
}
int main() {
    nevent_bind_game_thread(); ne_dead_event_pool = &pool;
    assign_innates(); indexes[0].virtual_number = 93300;
    char_data first{}, second{};
    for (P_char ch : {&first,&second}) {
        ch->player.m_class = CLASS_CONJURER; ch->player.spec = SPEC_WATER;
        ch->player.level = 46; ch->player.race = RACE_HUMAN;
        SET_POS(ch,STAT_NORMAL+POS_STANDING);
    }
    first.next = &second; character_list = &first;
    first.next_in_room = &second; rooms[0].people = &first;
    auto summon = [](P_char ch) { do_conjure_water(ch,nullptr,0); };
    summon(&first); assert(lag == PULSE_VIOLENCE && !first.affected && get_scheduled(&first,event_conjure_water));
    summon(&first); summon(&second);
    assert(lag == PULSE_VIOLENCE && !second.affected && !get_scheduled(&second,event_conjure_water));
    advance(PULSE_VIOLENCE); assert(!rooms[0].contents && !first.affected);
    advance(1); assert(rooms[0].contents && successes == 1 && !get_scheduled(&first,event_conjure_water));
    assert(first.affected && first.affected->location == INNATE_CONJURE_WATER);
    assert(first.affected->duration == 300*WAIT_SEC && first.affected->modifier == 1);
    summon(&second); assert(!second.affected && lag == PULSE_VIOLENCE);
    advance(300*WAIT_SEC); assert(!first.affected && rooms[0].contents);
    advance(600*WAIT_SEC); assert(!rooms[0].contents && !object_list);
    summon(&second); advance(PULSE_VIOLENCE+1); assert(successes == 2 && second.affected);
    clear(&second); extract_obj(rooms[0].contents);
    // A spring arriving during preparation causes a no-use rejection.
    summon(&first); P_obj rival = read_object(93300,VIRTUAL); obj_to_room(rival,0);
    advance(PULSE_VIOLENCE+1); assert(!first.affected && rooms[0].contents == rival && successes == 2);
    extract_obj(rival);
    // Failed creation, failed placement, and final eligibility loss clean up only this attempt.
    for (int failure : {0,1,2}) {
        creation_fails = failure == 0; placement_fails = failure == 1; revoke_on_placement = failure == 2;
        summon(&first); advance(PULSE_VIOLENCE+1);
        assert(!first.affected && !object_list && !get_scheduled(&first,event_conjure_water));
        first.player.spec = SPEC_WATER;
    }
    creation_fails = placement_fails = revoke_on_placement = false;
    // Room departure cancels the actor event, so leaving and returning cannot revive it.
    summon(&first); disarm_char_nevents(&first,event_conjure_water);
    first.in_room = 1; first.in_room = 0;
    advance(PULSE_VIOLENCE+1); assert(!first.affected && !object_list);
    summon(&second); advance(PULSE_VIOLENCE+1); assert(second.affected && successes == 3);
    clear(&second); extract_obj(rooms[0].contents);
    // Death without extraction revalidates; extraction's real cancel API frees pending payloads.
    summon(&first); SET_POS(&first,STAT_DEAD); advance(PULSE_VIOLENCE+1);
    assert(!first.affected && !object_list); SET_POS(&first,STAT_NORMAL+POS_STANDING);
    summon(&first); disarm_char_nevents(&first,nullptr);
    assert(!get_scheduled(&first,event_conjure_water));
    auto *extracted = new char_data(first);
    extracted->in_room = 1; extracted->next = nullptr; extracted->next_in_room = nullptr;
    rooms[1].people = extracted;
    summon(extracted); assert(get_scheduled(extracted,event_conjure_water));
    disarm_char_nevents(extracted,nullptr); rooms[1].people = nullptr; delete extracted;
    advance(PULSE_VIOLENCE+1); assert(!object_list); // ASan: no owner/payload survives extraction.
    summon(&first); first.player.spec = SPEC_AIR;
    advance(PULSE_VIOLENCE+1); assert(!first.affected && !object_list);
    first.player.spec = SPEC_WATER;
    summon(&first); assert(check_innate_time(&first,INNATE_CONJURE_WATER));
    auto *prior_timer = first.affected;
    advance(PULSE_VIOLENCE+1);
    assert(first.affected == prior_timer && prior_timer->modifier == 1 && !object_list);
    clear(&first);
    // A real scheduler refusal adds neither wait nor use, and retry succeeds.
    int prior_lag = lag; auto prior_sequence = ne_event_sequence;
    ne_event_sequence = ULLONG_MAX; summon(&first);
    assert(lag == prior_lag && !first.affected && !get_scheduled(&first,event_conjure_water));
    ne_event_sequence = prior_sequence;
    summon(&first); advance(PULSE_VIOLENCE+1); assert(first.affected && successes == 4);
    clear(&first); extract_obj(rooms[0].contents);
    assert(created == removed && ne_event_counter == 0 && pool.objs_used == 0);
    puts("Conjure Water: real pulse timing, room race, delayed charge, cooldown/decay, cancellation/failure and cleanup passed.");
}
'''

build = ROOT / 'bin/tests/conjure-water'
build.mkdir(parents=True, exist_ok=True)
cpp, binary = build / 'harness.cpp', build / 'harness'
cpp.write_text(prelude + macros + arrays + table + '\n'.join(extract_function(file,sig) for file,sig in functions) + driver)
subprocess.run(['g++','-std=c++20','-O1','-g','-ffunction-sections','-fdata-sections',
                '-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie','-pthread',
                '-I'+str(ROOT/'src'),str(cpp),str(ROOT/'src/persistence/latency_trace.c'),
                str(HARNESS_STUBS),'-Wl,--gc-sections','-lbsd','-o',str(binary)],check=True)
env = dict(os.environ, DURIS_NEVENT_BUDGET_USEC='0', DURIS_NEVENT_MAX_CALLBACKS='0')
subprocess.run([str(binary)],env=env,check=True)
