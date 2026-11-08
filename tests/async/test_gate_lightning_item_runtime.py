#!/usr/bin/env python3
"""Gate/lightning commands, portals and delayed storms in a controlled world.

Reuse the device suite's scene and real scheduler. World lookup, object allocation,
movement and damage are doubles; commands, adapters, spell wrappers, portal setup/
entry and lightning event bodies come from production. No running server is used.
"""
import ast
import os
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


def literal(name):
    tree = ast.parse((ROOT / "tests/async" / name).read_text())
    return next(ast.literal_eval(n.value) for n in tree.body
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "HARNESS" for t in n.targets))


platform = literal("test_nevent_scheduler_runtime.py").split("struct record_payload\n", 1)[0]
platform = platform.replace("DEFINE_LABEL_CALLBACK(event_item_action_active)", "")
platform = platform.replace("test_world[1]", "test_world[2]").replace("top_of_world = 0", "top_of_world = 1")
foundation = literal("test_item_actions_runtime.py").replace("int main() {", "void foundation_main() {")
foundation = foundation.replace("void send_to_char(const char *, P_char) {}", "")
foundation = foundation.replace("void act(const char *, int, P_char, P_obj, void *, int) {}", "")
foundation = foundation.replace("// INSERT_PRODUCTION_ABORT", extract_function("net/sparser.c", "void do_abort(P_char ch,"))
devices = literal("test_device_actions_runtime.py").split("int main() {", 1)[0]
commands = "\n".join(extract_function(path, signature) for path, signature in [
    ("core/utility.c", "void cast_as_area("),
    ("cmd/actoth.c", "void do_use("),
    ("cmd/actoth.c", "void do_recite("),
    ("cmd/actoth.c", "int combat_mind_quaff_chance("),
    ("cmd/actoth.c", "void do_quaff("),
    ("cmd/actnew.c", "static int throw_potion_lag("),
    ("cmd/actnew.c", "static int throw_potion_rest("),
    ("cmd/actnew.c", "bool throw_potion("),
])
devices = devices.replace("// INSERT_COMMANDS", '#include "world/epic.h"\n#include "combat/damage.h"\n' + commands)
spells = (ROOT / "src/magic/spells.c").read_text()
planes = spells[spells.index("int planes_room_num[]"):spells.index("// How many may pass a gate")]
production = planes + "\n".join(extract_function(path, signature) + (";" if signature.startswith("struct ") else "")
                                for path, signature in [
    ("magic/spells.c", "static int gate_throughput("),
    ("magic/spells.c", "static int gate_decay("),
    ("magic/spells.c", "void cast_gate("),
    ("magic/spells.c", "void cast_call_lightning("),
    ("magic/magic.c", "struct portal_data\n"),
    ("magic/magic.c", "void set_up_portals("),
    ("magic/magic.c", "bool spell_general_portal("),
    ("specs/specs.object.c", "int portal_general_internal(P_obj obj, P_char ch, int cmd, char *arg,\n\t\t\t    struct portal_action_messages *msg)\n"),
    ("magic/magic.c", "static int call_lightning_damage("),
    ("magic/magic.c", "static int call_lightning_more_strikes("),
    ("magic/magic.c", "static int call_lightning_delay("),
    ("magic/magic.c", "static int call_lightning_interval("),
    ("magic/magic.c", "static int call_lightning_stun("),
    ("magic/magic.c", "struct call_lightning_data\n"),
    ("magic/magic.c", "void event_call_lightning("),
    ("magic/magic.c", "void spell_call_lightning("),
])

HARNESS = r'''
#include "abilities/abilities.h"
static zone_data zones[2]{};
zone_data *zone_table = zones;
int portal_id=1;
static bool raidable=true;
static int potion_timers=0, strikes=0, nonmagical_hits=0;
static std::vector<P_obj> portals;
static P_obj selected_portal=nullptr;
int number(int low,int) { return low; }
int BOUNDED(int low,int value,int high) { return std::clamp(value,low,high); }
static int fixed_dice(int count,int sides) { return count*sides; }
extern const Rolls live_rolls={fixed_dice,number};
int real_room(int vnum) { return vnum==100?0:1; }
int get_room_in_zone(int,P_char) { return 1; }
float get_property(const char *key,double fallback) { return get_property(key,fallback,false); }
int get_property(const char *key,int fallback) { return get_property(key,double(fallback),false); }
int search_block(char *arg,const char *list[],int) {
    for(int i=0;strcmp(list[i],"\n");++i) if(!strcmp(arg,list[i])) return i;
    return -1;
}
int is_Raidable(P_char,char *,int) { return raidable; }
int is_prime_plane(int room) { return room==0; }
void zone_spellmessage(int,bool,const char *,const char *) {}
bool fear_check(P_char,bool) { return true; }
void Stun(P_char,P_char,int,bool) {}
bool NewSaves(P_char,int,int) { return true; }
void do_flee(P_char,char *,int) { assert(false); }
P_char get_random_char_in_room(int room,P_char ch,int) {
    for(auto p=world[room].people;p;p=p->next_in_room) if(p!=ch) return p;
    return nullptr;
}
int spell_damage(P_char,P_char,double damage,int type,uint,damage_messages *,int *) {
    assert(damage>0);
    if(type==SPLDAM_LIGHTNING) ++strikes; else ++nonmagical_hits;
    return DAM_NONEDEAD;
}
bool has_innate(P_char,int) { return false; }
int chance_throw_potion(P_char,P_char) { assert(false); return 0; }
bool gain_epic(P_char,int,int,int) { return true; }
affected_type *affect_to_char(P_char,affected_type *af) {
    assert(af->type==TAG_POTION_TIMER); ++potion_timers; return nullptr;
}
void set_obj_affected(P_obj,int,sh_int,sh_int) {}
void event_portal_owner_check(P_char,P_char,P_obj,void *) { assert(false); }
P_obj read_object(int vnum,int) {
    assert(vnum==752);
    auto p=new obj_data{}; p->obj_uid=1000+portals.size(); p->R_num=0;
    p->next=object_list; object_list=p; portals.push_back(p); return p;
}
void obj_to_room(P_obj p,int room) { p->loc_p=LOC_ROOM; p->loc.room=room; }
void statuslog(int,const char *,...) {}
void dispel_portal(P_char,P_obj) {}
int strn_cmp(const char *a,const char *b,uint n) { return strncmp(a,b,n); }
int generic_find(const char *,int,P_char,P_char *ch,P_obj *obj) {
    *ch=nullptr; *obj=selected_portal; return FIND_OBJ_ROOM;
}
int can_enter_room(P_char,int,int) { return true; }
void char_from_room(P_char ch) {
    P_char *p=&world[ch->in_room].people;
    while(*p && *p!=ch) p=&(*p)->next_in_room;
    if(*p) *p=ch->next_in_room;
    item_actions_character_leaving(ch); ch->in_room=NOWHERE;
}
bool char_to_room(P_char ch,int room,int) {
    ch->in_room=room; ch->next_in_room=world[room].people; world[room].people=ch; return true;
}
void Decay(P_obj) { assert(false); }
// INSERT_SPELLS

static bool said(const char *text) {
    return std::any_of(output.begin(),output.end(),[&](auto &line){return line.find(text)!=std::string::npos;});
}
struct spell_scene : device_scene {
    spell_scene(int item=ITEM_WAND,bool enabled=true):device_scene(item,enabled) {
        portals.clear(); selected_portal=nullptr; raidable=true;
        potion_timers=strikes=nonmagical_hits=0;
        world[0].zone=0; world[0].number=100; world[0].sector_type=SECT_FIELD;
        world[1]={}; world[1].zone=1; world[1].number=200;
        zones[0]={}; zones[1]={};
        skills[SPELL_GATE].targets=TAR_IGNORE|TAR_NOCOMBAT;
        skills[SPELL_GATE].spell_pointer=cast_gate;
        skills[SPELL_CALL_LIGHTNING].targets=TAR_AREA|TAR_OFFAREA|TAR_FIGHT_VICT|TAR_AGGRO;
        skills[SPELL_CALL_LIGHTNING].spell_pointer=cast_call_lightning;
        if(item==ITEM_POTION) {
            actor->equipment[WIELD]=nullptr; source->loc_p=LOC_CARRIED; source->loc.carrying=actor;
            source->next_content=actor->carrying; actor->carrying=source;
        }
    }
    void activate(int spell) {
        char arg[]="device earth";
        if(source->type==ITEM_SCROLL) {
            source->value[1]=spell; source->value[2]=source->value[3]=0;
            do_recite(actor,arg,CMD_RECITE);
        } else { source->value[3]=spell; do_use(actor,arg,CMD_USE); }
    }
    void quaff() { char arg[]="device"; do_quaff(actor,arg,CMD_QUAFF); }
};
static void gate_devices() {
    for(bool enabled:{false,true}) for(int item:{ITEM_SCROLL,ITEM_WAND,ITEM_STAFF}) {
        spell_scene s(item,enabled); s.activate(SPELL_GATE); advance(); device_actions_pulse();
        assert(portals.size()==2 && portals[0]->loc.room==0 && portals[1]->loc.room==1);
        assert(portals[0]->value[0]==200 && portals[1]->value[0]==100);
        assert(portals[0]->value[7]==portals[1]->value[7]);
        assert(said("gateway is opened to the earth plane"));
        if(item==ITEM_SCROLL) assert(extracts==1); else assert(s.source->value[2]==0);
        selected_portal=portals[0]; portal_action_messages messages{};
        messages.step_in_to_room=messages.step_in_to_char=messages.step_out_to_room="portal";
        char name[]="portal";
        assert(portal_general_internal(selected_portal,s.actor,CMD_ENTER,name,&messages));
        assert(s.actor->in_room==1);
        selected_portal=portals[1];
        assert(portal_general_internal(selected_portal,s.actor,CMD_ENTER,name,&messages));
        assert(s.actor->in_room==0);
    }
    for(int failure=0;failure<4;++failure) {
        spell_scene s; char arg[]="earth";
        if(failure==0) raidable=false;
        if(failure==1) world[1].room_flags=ROOM_NO_MAGIC;
        if(failure==2) world[0].room_flags=ROOM_NO_GATE;
        if(failure==3) strcpy(arg,"bad");
        cast_gate(50,s.actor,arg,SPELL_TYPE_SPELL,nullptr,nullptr);
        assert(portals.empty() && !output.empty());
    }
    for(int type:{SPELL_TYPE_POTION,SPELL_TYPE_SCROLL,SPELL_TYPE_WAND,SPELL_TYPE_STAFF}) {
        spell_scene s;
        cast_gate(50,s.actor,nullptr,type,nullptr,nullptr);
        assert(portals.empty() && said("named plane"));
    }
}
static void lightning_devices() {
    for(bool enabled:{false,true}) for(int item:{ITEM_SCROLL,ITEM_WAND,ITEM_STAFF}) {
        for(bool indoors:{false,true}) {
            spell_scene s(item,enabled); if(indoors) world[0].room_flags=ROOM_INDOORS;
            s.activate(SPELL_CALL_LIGHTNING);
            if(enabled) { assert(strikes==0); advance(); }
            if(item==ITEM_SCROLL) device_actions_pulse();
            assert(strikes==0); // A storm is delayed, including the legacy path.
            advance(100);
            assert(strikes==(indoors?0:3) && ne_event_counter==0);
            if(indoors) assert(said("must be outdoors"));
            if(item==ITEM_SCROLL) assert(extracts==1); else assert(s.source->value[2]==0);
        }
        spell_scene s(item,enabled); s.activate(SPELL_CALL_LIGHTNING);
        if(enabled) { char empty[]=""; do_abort(s.actor,empty,CMD_ABORT); }
        advance(100); device_actions_pulse();
        assert(strikes==(enabled?0:3)); // Paid channel cancellation retains the device cost.
    }
    for(int type:{SPELL_TYPE_SPELL,SPELL_TYPE_SCROLL,SPELL_TYPE_STAFF}) {
        spell_scene s; cast_call_lightning(17,s.actor,nullptr,type,s.target,nullptr);
        advance(100); assert(strikes==3);
    }
    for(int type:{SPELL_TYPE_POTION,SPELL_TYPE_WAND}) {
        spell_scene s; cast_call_lightning(17,s.actor,nullptr,type,s.target,nullptr);
        advance(100); assert(!strikes && !output.empty());
    }
}
static void potions() {
    for(int spell:{SPELL_GATE,SPELL_CALL_LIGHTNING}) for(bool mixed:{false,true}) {
        spell_scene s(ITEM_POTION); s.source->value[1]=spell;
        s.source->value[2]=mixed?2:0; s.source->value[3]=0;
        const int waits=unrelated_wait_changes;
        throw_potion(s.actor,s.source,s.target,nullptr);
        assert(!extracts && !potion_timers && calls.empty() && portals.empty());
        assert(s.actor->carrying==s.source && unrelated_wait_changes==waits);
        assert(said("cannot be invoked by throwing a potion"));
    }
    for(int spell:{SPELL_GATE,SPELL_CALL_LIGHTNING}) for(int sibling:{0,1,3}) {
        spell_scene s(ITEM_POTION); s.source->value[1]=spell;
        s.source->value[2]=sibling==1?2:0; s.source->value[3]=0;
        s.source->value[4]=sibling==3?10:0;
        const int waits=unrelated_wait_changes;
        s.quaff();
        assert(said("cannot be invoked by drinking a potion"));
        assert(portals.empty() && !strikes);
        assert(extracts==(sibling?1:0) && potion_timers==(sibling?1:0));
        assert(calls.size()==(sibling==1?1:0));
        if(sibling==1) assert(calls[0].id==2 && calls[0].type==SPELL_TYPE_POTION);
        assert(nonmagical_hits==(sibling==3?1:0));
        if(!sibling) assert(unrelated_wait_changes==waits && s.actor->carrying==s.source);
    }
    {
        spell_scene s(ITEM_POTION); s.source->value[1]=SPELL_GATE;
        s.source->value[2]=SPELL_CALL_LIGHTNING; s.source->value[3]=0;
        s.quaff(); assert(!extracts && !potion_timers && calls.empty());
    }
    {
        spell_scene s(ITEM_POTION); s.source->value[1]=SPELL_GATE; s.source->value[2]=2;
        s.source->value[3]=0; world[0].room_flags=ROOM_NO_MAGIC;
        s.quaff(); assert(extracts==1 && !potion_timers && calls.empty());
        assert(said("it fades"));
    }
}
int main() {
    nevent_bind_game_thread(); ne_dead_event_pool=&test_pool; fake_clock_ns=1000000000ULL; ne_events();
    gate_devices(); lightning_devices(); potions();
    puts("Gate/lightning: device routing, portal entry, delayed strikes, refusals and potion costs passed");
}
'''

with tempfile.TemporaryDirectory(prefix="duris-gate-lightning-") as directory:
    source = Path(directory) / "harness.cpp"
    binary = Path(directory) / "harness"
    source.write_text(platform + foundation + devices + HARNESS.replace("// INSERT_SPELLS", production))
    subprocess.run(["g++", "-std=c++20", "-O1", "-g", "-D__NO_MYSQL__", "-ffunction-sections", "-fdata-sections",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-pthread", "-no-pie",
                    "-I" + str(ROOT / "src"), str(source), str(ROOT / "src/persistence/latency_trace.c"),
                    str(HARNESS_STUBS), "-Wl,--gc-sections", "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True, env=dict(os.environ,
        ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1",
        DURIS_NEVENT_ANALYTICS="0", DURIS_NEVENT_BUDGET_USEC="0", DURIS_NEVENT_MAX_CALLBACKS="0",
        DURIS_NEVENT_PLAYER_PRIORITY="1"))
