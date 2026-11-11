#!/usr/bin/env python3
"""Execute real worn-set counting, tier selection, HP updates and event ownership.

Spell bodies and scheduler I/O are fixture boundaries. Actual effect ownership
and the scheduler's reschedule implementation have their own runtime gates.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, source

objects = source("specs.set.c").read_text()
prefix = objects[objects.index("typedef int (*set_func)"):objects.index("#define SETMSG_NONE")]
sets = objects[objects.index("struct set_data\n"):objects.index("int set_proc(", objects.index("struct set_data\n"))]
harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "world/db.h"
#include "world/vnum.obj.h"
#include "item/named_set_origin.h"
#include "item/named_sets.h"
#include "item/named_set_effects.h"
#include "item/random_equipment.h"
#include "magic/spells.h"
#include <algorithm>
#include <cassert>
#include <string>
#include <tuple>
#include <vector>

static zone_data zones[] = {
    {.number=159,.name=const_cast<char *>("Pit of Dragons")},
    {.number=455,.name=const_cast<char *>("Celestial Plane")},
    {.number=112,.name=const_cast<char *>("Arena of the Elder Brain")},
    {.number=14,.name=const_cast<char *>("&+WKobold Settlement&n")},
    {.number=1325,.name=const_cast<char *>("&+WTharnadia - City of Humans&n")},
    {.number=13,.name=const_cast<char *>("&+WBraddistock Mansion&n")},
    {.number=1350,.name=const_cast<char *>("&+WBraddistock Mansion&n")},
    {.number=44,.name=const_cast<char *>("&+LThe Underworld&n")},
    {.number=300,.name=const_cast<char *>("&+LThe Underworld&n")},
    {.number=808,.name=const_cast<char *>("&+gCeothia&n")},
    {.number=811,.name=const_cast<char *>("&n&+gCeothia&n")},
    {.number=814,.name=const_cast<char *>("&+gCeothia&n")},
    {.number=196,.name=const_cast<char *>("&+RTiamat&n")},
    {.number=199,.name=const_cast<char *>("&+RAstral Plane, Tiamat&n")},
    {.number=740,.name=const_cast<char *>("&+rBloodstone Keep&n")},
    {.number=990,.name=const_cast<char *>("&+gNeverwinter Woods&n")},
    {.number=87,.name=const_cast<char *>("&+gLair of the Gibberling King&n")},
    {.number=370,.name=const_cast<char *>("&+gCrystalspyre Mountains&n")},
    {.number=676,.name=const_cast<char *>("&+gTaliccicopiid&n")},
    {.number=824,.name=const_cast<char *>("&+gThe Temple of the Sun&n")},
    {.number=150,.name=const_cast<char *>("Retired Misty Chasm prototypes")},
    {.number=3000,.name=const_cast<char *>("&+LThe Chasm of the Misty Vale&n")},
};
zone_data *zone_table=zones;
int top_of_zone_table=sizeof zones/sizeof zones[0]-1;
static index_data indexes[2];
P_index obj_index=indexes;
static char_data wearer;
static obj_data gear[12];
static std::string names[12];
static unsigned long long tick, sequence;
static int disabled_timers;
static std::vector<std::tuple<int,int,int>> spells;
char *str_dup(const char *text) { return strdup(text); }
void *__malloc(size_t size,const char *,const char *,int) {return calloc(1,size);}
int real_zone(int zone) {
    for(int i=0;i<=top_of_zone_table;++i) if(zones[i].number==zone) return i;
    return -1;
}
void event_balance_affects(P_char,P_char,P_obj,void *) {}
void event_object_proc(P_char,P_char,P_obj,void *) {}
void disarm_obj_nevents(P_obj,event_func_type) {++disabled_timers;}
void disarm_char_nevents(P_char,event_func_type) {assert(false);}
int master_set(P_obj,P_char,int,char *) {return FALSE;}
void send_to_char(const char *,P_char) {}
void wear_off_message(P_char,affected_type *) {}
affected_type *affect_to_char(P_char ch,affected_type *value) {
    auto *af=new affected_type(*value); af->next=ch->affected; ch->affected=af; return af;
}
void affect_remove(P_char ch,affected_type *af) {
    auto **cursor=&ch->affected;
    while(*cursor && *cursor!=af) cursor=&(*cursor)->next;
    assert(*cursor==af); *cursor=af->next; delete af;
}
void affect_from_char(P_char ch,int type) {
    for(auto *af=ch->affected,*next=af;af;af=next) {
        next=af->next; if(af->type==type) affect_remove(ch,af);
    }
}
void apply_zone_spell(P_char,int count,const char *,int zone,P_obj,int spell) {
    spells.emplace_back(spell,count,zone);
}
nevent_schedule_result add_event(event_func func,int delay,P_char ch,P_char,P_obj,int,const void *data,int size) {
    if(func==event_balance_affects) return {nevent_schedule_status::scheduled,{nullptr,0}};
    auto *event=new nevent_data{};
    event->func=func; event->ch=ch; event->due_tick=tick+delay; event->sequence=++sequence;
    event->data=malloc(size); memcpy(event->data,data,size);
    event->next_char_nev=ch->nevents; ch->nevents=event;
    return {nevent_schedule_status::scheduled,{event,event->sequence}};
}
nevent_handle nevent_handle_from_event(P_nevent event) {return {event,event->sequence};}
bool nevent_reschedule_after(nevent_handle handle,unsigned long long delay) {
    assert(handle.event->sequence==handle.sequence);
    handle.event->due_tick=tick+delay; return true;
}
''' + extract_function("utility.c", "string strip_ansi(") + \
    extract_function("affects.c", "struct affected_type *get_spell_from_char(") + \
    prefix + extract_function("specs.set.c", "// Random zone eq spellups") + \
    extract_function("specs.set.c", "int random_set(") + sets + \
    extract_function("specs.set.c", "int set_proc(") + r'''
static void clear_marker(obj_data &object) {
    while(object.ex_description) {
        auto *entry=object.ex_description; object.ex_description=entry->next;
        free(entry->keyword); free(entry->description); free(entry);
    }
}
static void reset() {
    while(wearer.affected) affect_remove(&wearer,wearer.affected);
    while(wearer.nevents) {
        auto *event=wearer.nevents; wearer.nevents=event->next_char_nev;
        free(event->data); delete event;
    }
    for(auto &item:gear) {clear_marker(item); item={};}
    wearer={}; wearer.specials.position=STAT_NORMAL|POS_STANDING;
    tick=0; spells.clear(); disabled_timers=0;
}
static void wear(int item,int slot,int zone,bool marked=true) {
    auto &object=gear[item]; clear_marker(object); object={};
    object.R_num=item%2; object.loc_p=LOC_WORN; object.loc.wearing=&wearer;
    object.type=object.R_num ? ITEM_WEAPON : ITEM_ARMOR;
    int zi=real_zone(zone); assert(zi>=0);
    names[item]=std::string("a random item &+rfrom ")+zones[zi].name+"&n";
    object.short_description=names[item].data();
    if(marked) assert(set_named_set_origin(&object,zone));
    wearer.equipment[slot]=&object;
}
static void wear_tagged(int item,int slot,const char *title) {
    auto &object=gear[item]; clear_marker(object); object={};
    object.R_num=item%2; object.loc_p=LOC_WORN; object.loc.wearing=&wearer;
    object.type=object.R_num ? ITEM_WEAPON : ITEM_ARMOR;
    names[item]=std::string("a random item &+rfrom &+L")+title+"&n";
    object.short_description=names[item].data();
    wearer.equipment[slot]=&object;
}
static void process(int item) {
    for(auto &object:gear) REMOVE_BIT(object.extra2_flags,ITEM2_NOTIMER);
    set_proc(&gear[item],&wearer,CMD_PERIODIC,nullptr);
}
static affected_type *hp(int source) {
    return get_spell_from_char(&wearer,TAG_SETPROC,reinterpret_cast<void *>(static_cast<intptr_t>(source)));
}
static P_nevent pending(int source) {
    for(auto *event=wearer.nevents;event;event=event->next_char_nev)
        if(static_cast<random_set_wear_off *>(event->data)->context==reinterpret_cast<void *>(static_cast<intptr_t>(source))) return event;
    return nullptr;
}
static void expire(int source) {
    auto *event=pending(source); assert(event);
    auto **cursor=&wearer.nevents;
    while(*cursor!=event) cursor=&(*cursor)->next_char_nev;
    *cursor=event->next_char_nev;
    event->func(&wearer,nullptr,nullptr,event->data);
    free(event->data); delete event;
}
static size_t hp_count() {
    size_t count=0;
    for(auto *af=wearer.affected;af;af=af->next) count+=af->type==TAG_SETPROC;
    return count;
}
int main() {
    indexes[0].virtual_number=VOBJ_RANDOM_ARMOR; indexes[1].virtual_number=VOBJ_RANDOM_WEAPON;
    for(int count : {1,2,3,5,6,9}) {
        reset();
        for(int i=0;i<count;++i) wear(i,i+1,1325);
        process(0);
        assert(hp(1325) && hp(1325)->modifier==MAX(0,5*(count-2)));
        assert(count<2 || (hp(1325)->location==APPLY_HIT && hp(1325)->duration==-1 && (hp(1325)->flags&AFFTYPE_NOSAVE)));
        assert(spells.size()==static_cast<size_t>((count>=3)+(count>=4)));
        if(count>=3) assert(spells[0]==std::make_tuple(SPELL_ARMOR,count,1325));
        if(count>=4) assert(spells[1]==std::make_tuple(SPELL_BARKSKIN,count,1325));
    }
    // One-piece grant owns a cleanup deadline, contributes no HP, and disappears
    // when the last supporting armor is removed. Re-equipping refreshes the same deadline.
    reset(); wear(0,WEAR_BODY,159); process(0);
    assert(hp(159) && hp(159)->modifier==0 && pending(159));
    assert(spells.size()==1 && std::get<0>(spells[0])==SPELL_INFRAVISION);
    wearer.equipment[WEAR_BODY]=nullptr; expire(159); assert(!hp(159));
    // A catalog removal retains identity/HP without any spell; three tiers all dispatch.
    reset(); for(int i=0;i<4;++i) wear(i,i+1,112); process(0);
    assert(hp(112)->modifier==10 && spells.empty());
    for(int count=1;count<=8;++count) {
        reset(); for(int i=0;i<count;++i) wear(i,i+1,455); process(0);
        assert(spells.size()==static_cast<size_t>((count>=3)+(count>=5)+(count>=7)));
    }
    // The restored titles retain their existing HP and spell thresholds.
    for(int zone:{87,370,676,824}) for(int count:{2,3,4,5,6}) {
        reset(); for(int i=0;i<count;++i) wear(i,i+1,zone);
        process(0);
        assert(hp(zone) && hp(zone)->modifier==5*(count-2));
        std::vector<std::tuple<int,int,int>> expected;
        for(size_t i=0;i<named_set_count;++i) if(named_sets[i].zone==zone)
            for(const auto &tier:named_sets[i].proc_spells)
                if(tier[0] && count>=tier[0]) expected.emplace_back(tier[1],count,zone);
        assert(spells==expected);
        for(int slot=1;slot<=count;++slot) wearer.equipment[slot]=nullptr;
        expire(zone); assert(!hp(zone));
    }
    // Catalog row zero is a real nonzero source, not a wildcard.
    assert(named_sets[0].zone==13);
    reset(); for(int i=0;i<3;++i) wear(i,i+1,13); process(0);
    assert(hp(13) && hp(13)->modifier==5 && spells.size()==1);
    assert(spells[0]==std::make_tuple(SPELL_ARMOR,3,13));
    // Back and first belt count; attachments two/three do not.
    reset(); wear(0,WEAR_BODY,740); wear(1,WEAR_HEAD,740);
    wear(2,WEAR_ATTACH_BELT_2,740); wear(3,WEAR_ATTACH_BELT_3,740); process(0);
    assert(hp(740)->modifier==0);
    wear(4,WEAR_ATTACH_BELT_1,740); process(0); assert(hp(740)->modifier==5);
    wear(5,WEAR_BACK,740); process(0); assert(hp(740)->modifier==10);
    // New duplicate-title origins never count together, in either zone order.
    for(int reverse : {0,1}) {
        if(reverse) std::reverse(std::begin(zones),std::end(zones));
        for(const auto &group : {std::vector<int>{13,1350,1350},std::vector<int>{44,300,300},std::vector<int>{808,811,814}}) {
            reset(); for(int i=0;i<3;++i) wear(i,i+1,group[i]);
            for(int i=0;i<3;++i) process(i);
            for(auto *af=wearer.affected;af;af=af->next) assert(af->modifier==0);
        }
        // Ambiguous old gear has HP only and does not join new #808 pieces.
        reset(); for(int i=0;i<3;++i) wear(i,i+1,808,false);
        wear(3,4,808); wear(4,5,808); process(0); process(3);
        assert(hp(-808) && hp(-808)->modifier==5 && hp(808) && hp(808)->modifier==0 && hp_count()==2 && spells.size()==1 && std::get<0>(spells[0])==SPELL_BARKSKIN);
        // Retired #150 and new #3000 share a historical title, never a proved origin.
        reset(); for(int i=0;i<3;++i) {wear(i,i+1,3000,false); wear(i+3,i+4,3000);}
        process(0); process(3);
        assert(hp(-150) && hp(-150)->modifier==5 && hp(3000) && hp(3000)->modifier==5 && hp_count()==2);
        for(int i=0;i<3;++i) assert(!gear[i].ex_description && named_set_origin(&gear[i]).zone==0);
        // A title no zone carries any more keeps HP and its timer, with no spells or marker.
        for(const char *retired : {"The Ruins of Desecration","Vecnas Tomb"}) {
            reset();
            for(int i=0;i<3;++i) wear_tagged(i,i+1,retired);
            // A revealed weapon still joins by its base tag.
            gear[1].value[5]=spells_data[0].spell;
            names[1]+=std::string(" of ")+spells_data[0].name+"&n";
            gear[1].short_description=names[1].data();
            process(0);
            const int group=named_set_origin(&gear[0]).legacy_group;
            assert(group>=1<<24 && hp(-group) && hp(-group)->modifier==5);
            assert(hp_count()==1 && spells.empty() && !disabled_timers);
            for(int i=0;i<3;++i) assert(!gear[i].ex_description && named_set_origin(&gear[i]).zone==0);
        }
        // A different retired title is a different group.
        reset();
        for(int i=0;i<2;++i) {wear_tagged(i,i+1,"Newhaven"); wear_tagged(i+2,i+3,"Village of Miaeril");}
        process(0); process(2);
        assert(hp_count()==2 && !spells.size());
        // An untagged item still loses its timer, and carrying a piece never stamps it.
        reset();
        wear(0,1,740,false); gear[0].short_description=const_cast<char *>("a plain item");
        gear[0].loc_p=LOC_CARRIED; wearer.equipment[1]=nullptr;
        set_proc(&gear[0],&wearer,CMD_PERIODIC,nullptr);
        assert(disabled_timers==1 && !gear[0].ex_description);
        reset();
        wear(0,1,740,false); gear[0].loc_p=LOC_CARRIED; wearer.equipment[1]=nullptr;
        set_proc(&gear[0],&wearer,CMD_PERIODIC,nullptr);
        assert(!disabled_timers && !gear[0].ex_description && named_set_origin(&gear[0]).zone==740);
        // Unique legacy armor and revealed weapons migrate lazily when worn.
        reset(); for(int i=0;i<3;++i) wear(i,i+1,1325,false);
        gear[1].value[5]=spells_data[0].spell;
        names[1]+=std::string(" of ")+spells_data[0].name+"&n";
        gear[1].short_description=names[1].data(); process(0);
        assert(hp(1325)->modifier==5);
        for(int i=0;i<3;++i) assert(gear[i].ex_description && named_set_origin(&gear[i]).zone==1325);
        // Removing presentation text from identified gear does not erase membership.
        gear[1].short_description=const_cast<char *>("a renamed weapon"); process(0);
        assert(hp(1325)->modifier==5);
        // Astral Plane, Tiamat never receives the shorter Tiamat row.
        reset(); for(int i=0;i<3;++i) wear(i,i+1,199,false); process(0);
        assert(hp(199)->modifier==5 && spells.size()==2);
        assert(spells[0]==std::make_tuple(SKILL_AWARENESS,3,199));
    }
    // Independent refresh and removal: both orders, without raw affect pointers.
    for(int first : {740,990}) {
        reset(); for(int i=0;i<3;++i) {wear(i,i+1,740); wear(i+3,i+4,990);}
        process(0); process(3);
        assert(pending(740) && pending(990) && hp_count()==2);
        const auto deadline=pending(990)->due_tick;
        tick=4; process(0);
        assert(pending(990)->due_tick==deadline && pending(740)->due_tick==deadline+4);
        for(int slot=1;slot<=6;++slot) {
            auto *item=wearer.equipment[slot];
            if(named_set_origin(item).zone==first) wearer.equipment[slot]=nullptr;
        }
        expire(first);
        assert(!hp(first) && hp(first==740 ? 990 : 740)->modifier==5);
    }
    // A vanished HP affect cannot make a stale event remove a different set.
    reset(); for(int i=0;i<3;++i) wear(i,i+1,740); process(0);
    affect_remove(&wearer,hp(740));
    for(int i=0;i<3;++i) wear(i,i+1,990); process(0); expire(740);
    assert(hp(990) && hp(990)->modifier==5);
    reset();
}
'''

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="named-set-membership-", dir=build) as directory:
    cpp = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    cpp.write_text(harness)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
        "-ffunction-sections", "-fdata-sections", "-Isrc", str(cpp), "src/item/named_set_origin.c",
        "src/item/named_set_effects.c", "src/item/named_sets.c", "src/item/random_equipment_tables.c", str(HARNESS_STUBS),
        "-Wl,--gc-sections", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
print("named-set worn membership, HP thresholds, legacy separation, and independent cleanup: passed")
