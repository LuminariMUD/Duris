#!/usr/bin/env python3
"""Run Water Form crossings on the production scheduler and movement checks.

The ordinary command/dispatcher, entry checks, cost and movement prefix through
trap/exhaustion/deduction are production code. Final placement, room specials,
combat initiation and general effect services are controlled fixtures.
"""
import os
import re
import subprocess

from _paths import ROOT, HARNESS_STUBS, extract_function, source

prelude = r'''
#include "world/new_events.c"
#include "world/weather.h"
#include "world/graph.h"
#include "combat/grapple.h"
#include <cassert>
#include <cstring>
#include <string>
int pulse;
bool after_events_call;
P_char character_list;
P_obj object_list;
uint64_t character_removal_generation;
index_data indexes[1]{};
P_index obj_index = indexes, mob_index = indexes;
room_data rooms[3]{};
room_direction_data exits[3]{};
P_room world = rooms;
const int top_of_world = 2;
zone_data zones[1]{};
zone_data *zone_table = zones;
str_app_type str_app[201]{};
const int movement_loss[NUM_SECT_TYPES] = {2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2};
const int rev_dir[] = {2,3,0,1,5,4,9,8,7,6};
static mm_ds pool{};
static int load = 100, lag, movements, specials, mode, trap_mode;
static bool wall, trap, grease, linked_mount, linked_rider;
static P_char mount_fixture, rider_fixture;
static std::string output;
int do_simple_move_skipping_procs(P_char, int, unsigned int);
int bfs_cur_marker;
int LINKED_OBJECTS::Visible_Type() { assert(false); return 0; }
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
int GET_SECONDARY_CLASS(P_char, uint) { return 0; }
bool affected_by_spell(P_char ch, int type) {
    for (auto *af = ch->affected; af; af = af->next) if (af->type == type) return true;
    return false;
}
void affect_from_char(P_char ch, int type) {
    if(type == SPELL_WATER_FORM) disarm_char_nevents(ch,event_water_crossing);
    auto **link = &ch->affected;
    while (*link) { auto *af = *link; if(af->type == type) *link = af->next; else link = &af->next; }
}
void send_to_char(const char *text, P_char) { output += text; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void CharWait(P_char, int pulses) { lag += pulses; }
P_char get_linked_char(P_char, ush_int) { return linked_mount ? mount_fixture : nullptr; }
P_char get_linking_char(P_char, ush_int) { return linked_rider ? rider_fixture : nullptr; }
bool check_castle_walls(int, int) { return wall; }
int is_ice(P_char, int) { return 0; }
bool has_innate(P_char, int) { return false; }
bool SanityCheck(P_char ch, const char *) { return ch != nullptr; }
int char_in_list(const P_char ch) { for(auto *p=character_list;p;p=p->next) if(p==ch) return 1; return 0; }
int load_modifier(P_char) { return load; }
int total_carried_weight(P_char) { return 0; }
int STAT_INDEX(int) { return 100; }
int GET_CHAR_SKILL_P(P_char, int) { return 0; }
bool notch_skill(P_char, int, float) { return false; }
int number(int low, int) { return low; }
int BOUNDED(int low, int value, int high) { return std::max(low,std::min(value,high)); }
char *FirstWord(char *word) { return word; }
int exitnumb_to_cmd(int dir) { return dir+1; }
int cmd_to_exitnumb(int cmd) { return cmd-1; }
room_affect *get_spell_from_room(P_room, int) { return nullptr; }
char *one_argument(const char *, char *out) { *out=0; return out; }
void bfs_clear_marks() {}
void make_ice(P_char) {}
int leave_by_exit(P_char, int) { return !wall; }
bool grease_check(P_char) { return grease; }
bool special(P_char ch, int, char *) {
    ++specials;
    if(mode==1) return true;
    if(mode==2) { ++character_removal_generation; character_list=nullptr; delete ch; return false; }
    if(mode==3) affect_from_char(ch,SPELL_WATER_FORM);
    if(mode==4) disarm_char_nevents(ch,event_water_crossing); // transient combat during a proc
    return false;
}
bool checkmovetrap(P_char ch, int) {
    if(trap_mode) disarm_char_nevents(ch,event_water_crossing);
    return trap;
}
void char_from_room(P_char ch) { disarm_char_nevents(ch,event_water_crossing); ch->in_room=NOWHERE; }
bool char_to_room(P_char ch, int room, int) { ch->in_room=room; ++movements; return true; }
bool abort_item_action(P_char) { return false; }
void StopCasting(P_char) { assert(false); }
void update_pos(P_char) {}
'''

move = source('actmove.c').read_text()
structure = re.search(r'struct water_crossing_data\n\{.*?\n};',move,re.S)[0]
functions = [
    ('utility.c', 'bool has_water_form_travel('),
    ('utility.c', 'int move_cost('),
    ('actmove.c', 'static bool water_crossing_valid('),
    ('actmove.c', 'static bool completing_water_crossing('),
    ('actmove.c', 'static int can_enter_room_internal('),
    ('actmove.c', 'int can_enter_room('),
    ('actmove.c', 'void event_water_crossing('),
    ('actmove.c', 'static bool start_water_crossing('),
    ('actmove.c', 'static P_char movement_special_actor('),
    ('actmove.c', 'int do_simple_move('),
    ('actmove.c', 'void do_move('),
    ('sparser.c', 'void do_abort(P_char ch,'),
]
core = extract_function('actmove.c','int do_simple_move_skipping_procs(')
core = core[:core.index('\n\tif (!(flags & MVFLG_NOMSG))')]
core += '''
    (void)flags;
    const int destination = EXIT(ch,exitnumb)->to_room;
    char_from_room(ch); char_to_room(ch,destination,-1); return true;
}
'''
for file,sig in [('handler.c','void char_from_room('),('affects.c','void affect_remove('),('fight.c','void set_fighting(')]:
    body = extract_function(file,sig)
    assert 'disarm_char_nevents(ch, event_water_crossing)' in body
assert 'disarm_char_nevents(victim, event_water_crossing)' in extract_function('fight.c','void set_fighting(')

driver = r'''
static void advance(int ticks) { for(int i=0;i<ticks;++i) { ne_events(); nevent_advance_tick(); } }
int main() {
    nevent_bind_game_thread(); ne_dead_event_pool=&pool;
    str_app[100].carry_w=10000;
    char_data ch{}, mount{}, rider{};
    mount_fixture=&mount; rider_fixture=&rider;
    affected_type form{}; form.type=SPELL_WATER_FORM;
    ch.player.m_class=CLASS_CONJURER; ch.player.spec=SPEC_WATER; ch.player.level=46;
    SET_POS(&ch,STAT_NORMAL+POS_STANDING); character_list=&ch; ch.affected=&form;
    for(int room=0;room<3;++room) { exits[room].to_room=room==0?1:0; rooms[room].dir_option[0]=&exits[room]; }
    rooms[0].sector_type=SECT_FIELD; rooms[1].sector_type=SECT_OCEAN; rooms[2].sector_type=SECT_OCEAN;
    auto walk = [&]() { char argument[]=""; do_move(&ch,argument,1); };
    auto reset = [&]() {
        disarm_char_nevents(&ch,nullptr); ch.in_room=0; ch.affected=&form;
        ch.player.spec=SPEC_WATER; ch.specials.fighting=nullptr;
        ch.specials.affected_by=ch.specials.affected_by2=ch.specials.affected_by3=0;
        GET_VITALITY(&ch)=100; lag=movements=specials=mode=trap_mode=0;
        trap=wall=grease=linked_mount=linked_rider=false; ch.lobj=nullptr;
        rooms[1].current_speed=0;
        exits[0].to_room=1; exits[0].exit_info=0;
        exits[1].to_room=0; exits[1].exit_info=0;
    };
    for(int level : {46,50,51}) {
        reset(); ch.player.level=level;
        assert(!can_enter_room(&ch,1,false)); // Generic teleport entry never gains the exception.
        walk(); assert(ch.in_room==0 && lag==5*WAIT_SEC && get_scheduled(&ch,event_water_crossing));
        walk(); assert(lag==5*WAIT_SEC);
        advance(5*WAIT_SEC); assert(ch.in_room==0 && movements==0);
        advance(1); assert(ch.in_room==1 && movements==1 && specials==1 && GET_VITALITY(&ch)==99);
        walk(); advance(5*WAIT_SEC); assert(ch.in_room==1);
        advance(1); assert(ch.in_room==0 && movements==2);
    }
    reset(); ch.in_room=1; exits[1].to_room=2; walk();
    assert(ch.in_room==2 && !get_scheduled(&ch,event_water_crossing) && lag==0);
    exits[1].to_room=0;
    // The same payable cost is used for exhaustion and subtraction, with min-one rounding.
    for(int weight : {1,50,100,199,300,1000}) {
        reset(); load=weight;
        int cost=move_cost(&ch,0);
        ch.affected=nullptr; int ordinary=move_cost(&ch,0); ch.affected=&form;
        assert(cost==std::max(1,ordinary*3/4));
        GET_VITALITY(&ch)=cost; walk(); advance(5*WAIT_SEC+1);
        assert(ch.in_room==1 && GET_VITALITY(&ch)==0);
        reset(); GET_VITALITY(&ch)=cost-1; walk(); advance(5*WAIT_SEC+1);
        assert(ch.in_room==0 && GET_VITALITY(&ch)==cost-1);
    }
    load=100;
    // Stance/flurry/injury surcharges stay after the discounted base cost.
    for(int stance : {POS_STANDING,POS_KNEELING,POS_PRONE}) {
        reset(); SET_POS(&ch,STAT_NORMAL+stance);
        affected_type injury{}; injury.type=TAG_CRIPPLED; form.next=&injury;
        ch.specials.affected_by2=AFF2_FLURRY;
        int payable=move_cost(&ch,0)+5+2+(stance==POS_PRONE?6:(stance==POS_KNEELING?3:0));
        GET_VITALITY(&ch)=payable; walk(); advance(5*WAIT_SEC+1);
        assert(ch.in_room==1 && GET_VITALITY(&ch)==0); form.next=nullptr;
        SET_POS(&ch,STAT_NORMAL+POS_STANDING);
    }
    reset(); ch.in_room=1; rooms[1].current_speed=100; rooms[1].current_direction=2;
    walk(); advance(5*WAIT_SEC+1); assert(ch.in_room==1 && GET_VITALITY(&ch)==100);
    for(bool outbound : {false,true}) for(int change : {0,1,2,3,4,5,6,7,8}) {
        reset(); const int origin=outbound?1:0; ch.in_room=origin; walk();
        if(change==0) { disarm_char_nevents(&ch,event_water_crossing); ch.specials.fighting=&mount; ch.specials.fighting=nullptr; }
        if(change==1) { affect_from_char(&ch,SPELL_WATER_FORM); ch.affected=&form; }
        if(change==2) { char_from_room(&ch); ch.in_room=origin; }
        if(change==3) exits[origin].exit_info=EX_CLOSED;
        if(change==4) exits[origin].to_room=2;
        if(change==5) SET_POS(&ch,STAT_DEAD);
        if(change==6) do_abort(&ch,nullptr,0);
        if(change==7) mode=3; // form lost by an ordinary movement proc at completion
        if(change==8) trap_mode=1; // combat begins/ends in the normal trap check
        advance(5*WAIT_SEC+1); assert(ch.in_room==origin && movements==0 && GET_VITALITY(&ch)==100);
        SET_POS(&ch,STAT_NORMAL+POS_STANDING);
    }
    reset(); linked_mount=true; walk(); assert(!get_scheduled(&ch,event_water_crossing));
    reset(); linked_rider=true; walk(); assert(!get_scheduled(&ch,event_water_crossing));
    reset(); ch.lobj=reinterpret_cast<decltype(ch.lobj)>(1); walk(); assert(!get_scheduled(&ch,event_water_crossing));
    reset(); ch.affected=nullptr; ch.specials.affected_by2=AFF2_WATER_AURA;
    walk(); assert(ch.in_room==0 && !get_scheduled(&ch,event_water_crossing));
    reset(); ch.player.spec=SPEC_AIR; walk(); assert(ch.in_room==0);
    reset(); auto sequence=ne_event_sequence; ne_event_sequence=ULLONG_MAX; walk();
    assert(lag==0 && !get_scheduled(&ch,event_water_crossing)); ne_event_sequence=sequence;
    reset(); walk(); advance(5*WAIT_SEC+1); assert(ch.in_room==1);
    reset(); disarm_char_nevents(&ch,nullptr);
    // A special may free a mover and return false: the dispatcher must stop before grease/core.
    auto *freed=new char_data(ch); character_list=freed; mode=2;
    assert(!do_simple_move(freed,0,0)); character_list=&ch; mode=0;
    assert(pool.objs_used==0 && ne_event_counter==0);
    puts("Water shoreline: native command/scheduler, timed directions, interruption, exact costs and isolated entry exception passed.");
}
'''

build = ROOT / 'bin/tests/water-shoreline'
build.mkdir(parents=True,exist_ok=True)
cpp,binary=build/'harness.cpp',build/'harness'
cpp.write_text(prelude+structure+'\n'+'\n'.join(extract_function(file,sig) for file,sig in functions)+core+driver)
subprocess.run(['g++','-std=c++20','-O1','-g','-ffunction-sections','-fdata-sections',
                '-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie','-pthread',
                '-I'+str(ROOT/'src'),str(cpp),str(ROOT/'src/persistence/latency_trace.c'),
                str(HARNESS_STUBS),'-Wl,--gc-sections','-lbsd','-o',str(binary)],check=True)
subprocess.run([str(binary)],env=dict(os.environ,DURIS_NEVENT_BUDGET_USEC='0',DURIS_NEVENT_MAX_CALLBACKS='0'),check=True)
