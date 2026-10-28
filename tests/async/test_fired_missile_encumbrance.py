#!/usr/bin/env python3
"""Starter/ordinary missiles survive misses; fire/gather accounts for weight once.

Executes production materialization, commands, room placement and decay callbacks.
Allocation, RNG, event dispatch and unrelated combat services are controlled.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


handler = "\n".join(extract_function("world/handler.c", signature) for signature in (
    "static const object_template *container_prototype(",
    "static int container_weight_reduction_pct(",
    "static int sum_direct_contents_weight(",
    "static void encumbrance_adjust(",
    "static int calculated_container_weight(",
    "void recalc_container_weight(",
    "static void reconcile_container_chain(",
    "void add_weight(P_obj obj, int weight)\n{",
    "bool obj_can_nest(",
    "bool obj_is_in_container(",
    "void obj_to_obj(",
    "void obj_from_obj(",
    "void obj_to_room(",
    "void Decay(",
))
materialize = extract_function("account/nanny.c", "static P_obj materialize_legacy_newbie_item(")
decay_callback = extract_function("magic/affects.c", "void event_obj_affect(")
commands = "\n".join(extract_function("combat/range.c", signature) for signature in (
    "void event_enchant_arrow(", "int enchant_arrows(", "void do_fire(", "void do_gather(",
))
strings = "\n".join(extract_function("classes/salchemist.c", signature) for signature in (
    "void set_keywords(", "void set_short_description(",
))
strings += "\n" + extract_function("world/db.c", "void free_obj(")
harness = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/object_template.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "combat/damage.h"
#include "combat/justice.h"
#include "item/objmisc.h"
#include "magic/spells.h"
#include "account/newbie_kit_plan.h"
#include "world/vnum.obj.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>

static room_data rooms[2] = {};
extern const int top_of_world = 1;
P_room world = rooms;
static index_data indices[8] = {};
P_index obj_index = indices;
int top_of_objt = 7;
const char *dirs[] = {"north"};
const char *dirs2[] = {"the north"};
extern const int rev_dir[];
const int rev_dir[] = {0};
static char_data target;
static bool cursed;
static int fired;
static bool force_hit;
static int scrapped, delivered, destroyed;
static int block_rolls, damage_calls, mark_events;
static int damage_result = DAM_NONEDEAD;
static bool block_first;
static bool enchant_kills;
static P_obj corpse_source;
static object_template prototype;
static P_obj allocation;
static bool keyword_added;
static std::vector<std::pair<P_obj, obj_affect>> pending;

// Deterministic hits/misses and returning arrows; no damage to a live target.
int GET_CHAR_SKILL_P(P_char, int skill) {
    if (skill == SKILL_ENCHANT_ARROWS && enchant_kills) return 200;
    return skill == SKILL_ARCHERY || skill == SKILL_SHIELD_BLOCK ? 100 : 0;
}
bool notch_skill(P_char, int skill, float) { return skill == SKILL_CURSED_ARROWS && cursed; }
int number(int, int high) {
    if (high == 1600) return ++block_rolls == 1 && block_first ? 1 : high;
    return high;
}
int dice(int, int) { return 1; }
int get_property(const char *, int fallback) { return fallback; }
float get_property(const char *, double fallback) { return fallback; }
int chance_to_hit(P_char, P_char, int, P_obj) { return force_hit ? 100 : 0; }
P_char misfire_check(P_char, P_char victim, int) { return victim; }
P_char get_char_room_vis(P_char, const char *) { return &target; }
P_char get_char_ranged(const char *, P_char, int, int) { return &target; }
int dir_from_keyword(char *) { return 0; }
int check_wall(int, int) { return 0; }
bool AdjacentInRoom(P_char, P_char) { std::abort(); }
bool is_natural_mount(P_char, P_char) { std::abort(); }
void stop_riding(P_char) { std::abort(); }
room_affect *get_spell_from_room(P_room, int) { return nullptr; }
void CharWait(P_char, int) {}
void startPvP(P_char, bool) { std::abort(); }
void set_short_affected_by(P_char, int, int) {}
// Run real string teardown and retire heap objects, exposing accesses after release to ASan.
void release_obj_mem(P_obj object) { delete object; }
void disarm_obj_nevents(P_obj, event_func_type) {}
char *str_dup(const char *text) { return text ? strdup(text) : nullptr; }
void str_free(const char *text) { free(const_cast<char *>(text)); }
int barb(P_obj, P_char, int, char *) { std::abort(); }
void free_obj(P_obj);
void MakeScrap(P_char, P_obj object) {
    assert(object->condition <= 0 && object->loc_p == LOC_NOWHERE);
    ++scrapped; free_obj(object);
}
int melee_damage(P_char, P_char victim, double, int, damage_messages *messages, int *) {
    ++damage_calls;
    assert(messages->obj && strstr(messages->obj->name, "arrow"));
    assert(strstr(messages->obj->short_description, "arrow"));
    assert(!strstr(messages->attacker, "shield"));
    if (damage_result != DAM_NONEDEAD) {
        victim->specials.position = STAT_DEAD;
        victim->in_room = NOWHERE;
    }
    return damage_result;
}
int arrow_spell_fire(int, P_char, char *, int, P_char, P_obj) { return DAM_NONEDEAD; }
int arrow_spell_cold(int, P_char, char *, int, P_char, P_obj) { return DAM_NONEDEAD; }
int arrow_spell_lightning(int, P_char, char *, int, P_char, P_obj) { return DAM_NONEDEAD; }
int arrow_spell_acid(int, P_char, char *, int, P_char victim, P_obj) {
    if (!enchant_kills) return DAM_NONEDEAD;
    victim->specials.position = STAT_DEAD; victim->in_room = NOWHERE;
    return DAM_VICTDEAD;
}
void spell_major_paralysis(int, P_char, char *, int, P_char, P_obj) { std::abort(); }
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int) {
    ++mark_events; return {};
}
void MobRetaliateRange(P_char, P_char) {}
void obj_to_char(P_obj object, P_char victim) {
    assert(victim == &target && object->loc_p == LOC_NOWHERE);
    object->loc_p = LOC_CARRIED; object->loc.carrying = victim; ++delivered;
}
void affect_from_char(P_char, int) { std::abort(); }
int BOUNDED(int low, int value, int high) { return MAX(low, MIN(value, high)); }
int checked_snprintf_at(const char *, int, char *, size_t, const char *, ...) { std::abort(); }
void half_chop(char *input, char *first, char *second) {
    strcpy(first, "target");
    strcpy(second, strstr(input, "north") ? "north" : "");
}
char *one_argument(const char *input, char *word) {
    strcpy(word, input);
    return const_cast<char *>(input);
}
int generic_find(const char *, int, P_char, P_char *, P_obj *object) {
    assert(corpse_source); *object = corpse_source; return 1;
}
void act(const char *message, int, P_char, P_obj, void *, int) {
    if (!strcmp(message, "You fire $p at $N and miss!")) ++fired;
}
P_obj read_object(int, int) { std::abort(); }
const object_template *find_object_template(int) { return &prototype; }
P_obj instantiate_object_template(const object_template &proto) {
    assert(allocation); allocation->type = proto.type; allocation->extra_flags = proto.extra_flags;
    return allocation;
}
void add_newbie_keyword(P_obj) { keyword_added = true; }
int AddSpellToSpellBook(P_char, P_obj, int) { std::abort(); }
void extract_obj(P_obj object, int) {
    if (object->loc_p == LOC_NOWHERE) { ++destroyed; free_obj(object); return; }
    assert(OBJ_ROOM(object) && !object->contains);
    obj_from_room(object); ++destroyed;
}
static void mark_container_dirty(P_obj) {}
void artifact_update_location_sql(P_obj) {}
void writeSavedItem(P_obj) { std::abort(); }
P_char training_dummy_item_owner(P_obj) { return nullptr; }
void add_weight(P_obj, int);
void set_obj_affected(P_obj object, int duration, int type, int modifier) {
    assert(duration == 0 && type == TAG_OBJ_DECAY && modifier == 0);
    obj_affect affect{}; affect.type = type;
    pending.emplace_back(object, affect);
}
void obj_affect_remove(P_obj, obj_affect *) {} // delayed pool reclamation
int real_room(int) { std::abort(); }
int real_object(const int) { return -1; }
int distance_from_shore(int) { std::abort(); }
void add_coins(P_obj, int, int, int, int) { std::abort(); }
int room_light(int, int) { std::abort(); }
void writeCorpse(P_obj) { std::abort(); }
bool falling_obj(P_obj, int, bool) { std::abort(); }
void obj_from_char(P_obj) { std::abort(); }
void balance_affects(P_char) { std::abort(); }
int total_carried_weight(P_char) { std::abort(); }
bool ac_can_see_obj(P_char, P_obj, int) { std::abort(); }
void obj_from_room(P_obj object) {
    assert(object->loc_p == LOC_ROOM);
    P_obj *link = &rooms[object->loc.room].contents;
    while (*link != object) { assert(*link); link = &(*link)->next_content; }
    *link = object->next_content;
    object->next_content = nullptr;
    object->loc_p = LOC_NOWHERE;
}
// Match the equip/unequip contribution while the real gather command reloads.
void equip_char(P_char ch, P_obj object, int slot, int) {
    assert(!ch->equipment[slot] && object->loc_p == LOC_NOWHERE);
    ch->equipment[slot] = object;
    object->loc_p = LOC_WORN;
    object->loc.wearing = ch;
    GET_CARRYING_W(ch) += GET_OBJ_WEIGHT(object) / 2;
}
P_obj unequip_char(P_char ch, int slot, bool) {
    P_obj object = ch->equipment[slot];
    assert(object && object->loc_p == LOC_WORN);
    GET_CARRYING_W(ch) -= GET_OBJ_WEIGHT(object) / 2;
    ch->equipment[slot] = nullptr;
    object->loc_p = LOC_NOWHERE;
    return object;
}

#define ARROW_MARK 1
#define ARROW_NONE 0
// String setters use ordinary allocations in this harness.
#undef FREE
#define FREE(pointer) do { free(pointer); pointer = nullptr; } while (false)
// PRODUCTION

static void dispatch_decay() {
    auto events = std::move(pending); pending.clear();
    for (auto &event : events) {
        obj_affect *affect = &event.second;
        event_obj_affect(nullptr, nullptr, event.first, &affect);
    }
}

static void scenario(int shell, int missile_weight, int requested, int loaded,
                     bool returning, bool starter, int landing) {
    char_data shooter = {};
    pc_only_data player = {};
    npc_only_data npc = {};
    shooter.only.pc = &player;
    player.pid = 42;
    shooter.specials.position = POS_STANDING | STAT_NORMAL;
    shooter.curr_stats.Dex = 100;
    shooter.curr_stats.Str = 100;
    target = {};
    target.only.npc = &npc;
    target.specials.act = ACT_ISNPC;
    target.specials.position = POS_STANDING | STAT_NORMAL;
    target.in_room = landing;
    room_direction_data exit{};
    exit.to_room = 1;
    rooms[0].dir_option[0] = &exit;
    obj_data bow = {}, quiver = {}, arrows[3] = {};
    bow.type = ITEM_FIREWEAPON;
    bow.value[0] = requested * 30;
    bow.value[1] = 100;
    shooter.equipment[WIELD] = &bow;
    quiver.type = ITEM_QUIVER;
    quiver.loc_p = LOC_NOWHERE;
    quiver.weight = shell;
    quiver.value[0] = 10;
    quiver.value[3] = loaded;
    for (int i = 0; i < loaded; ++i) {
        arrows[i].type = ITEM_MISSILE;
        arrows[i].loc_p = LOC_NOWHERE;
        arrows[i].weight = missile_weight;
        arrows[i].condition = 100;
        arrows[i].obj_uid = 100 + i;
        prototype.type = ITEM_MISSILE; prototype.extra_flags = 1032;
        if (starter) {
            allocation = &arrows[i]; keyword_added = false;
            assert(materialize_legacy_newbie_item(&shooter, {{1117, true}, {}}) == allocation);
            assert(keyword_added && allocation->cost == 1);
        }
        obj_to_obj(&arrows[i], &quiver);
    }
    GET_CARRYING_W(&shooter) = 100;
    equip_char(&shooter, &quiver, WEAR_QUIVER, FALSE);
    const int initial_weight = quiver.weight;
    const int initial_carried = GET_CARRYING_W(&shooter);
    cursed = returning;
    for (int cycle = 0; cycle < 50; ++cycle) {
        fired = 0;
        shooter.in_room = 0;
        char target_name[32]; strcpy(target_name, landing ? "target north" : "target");
        do_fire(&shooter, target_name, CMD_FIRE);
        const int removed = returning ? 0 : MIN(requested, loaded);
        assert(fired == (returning ? requested : removed));
        assert(quiver.value[3] == loaded - removed);
        assert(quiver.weight == initial_weight - removed * MAX(0, missile_weight));
        assert(GET_CARRYING_W(&shooter) == 100 + GET_OBJ_WEIGHT(&quiver) / 2);
        dispatch_decay();
        assert(destroyed == 0);
        for (int i = 0; i < loaded; ++i) {
            assert(arrows[i].condition == 100 && arrows[i].obj_uid == 100 + i);
            if (!returning && OBJ_ROOM(&arrows[i])) assert(arrows[i].loc.room == landing);
        }
        // Even a different PID wearing the same quiver cannot gather our arrows.
        shooter.in_room = landing;
        player.pid = 43;
        char gather[] = "";
        do_gather(&shooter, gather, 0);
        assert(quiver.value[3] == loaded - removed);
        player.pid = 42;
        do_gather(&shooter, gather, 0);
        assert(!rooms[landing].contents && quiver.value[3] == loaded);
        assert(quiver.weight == initial_weight && GET_CARRYING_W(&shooter) == initial_carried);
    }
}

static void controls() {
    char_data ch{}; pc_only_data pc{}; ch.only.pc = &pc;
    // Bow/quiver transience, and an explicitly transient missile, still dissolve.
    for (int type : {ITEM_FIREWEAPON, ITEM_QUIVER, ITEM_MISSILE, ITEM_WORN}) {
        obj_data object{}; object.loc_p = LOC_NOWHERE; allocation = &object;
        prototype.type = type;
        prototype.extra_flags = type == ITEM_FIREWEAPON || type == ITEM_WORN ? 0 : ITEM_TRANSIENT;
        materialize_legacy_newbie_item(&ch, {{1117, true}, {}});
        assert(IS_SET(object.extra_flags, ITEM_TRANSIENT));
        obj_to_room(&object, 0);
        assert(pending.size() == 1);
        int before = destroyed;
        dispatch_decay();
        assert(destroyed == before + 1 && !rooms[0].contents);
    }
    destroyed = 0;
}

static void hit_control(bool starter, bool returning, int condition, int death = 0) {
    char_data ch{}; pc_only_data pc{}; npc_only_data npc{};
    ch.only.pc = &pc; pc.pid = 42;
    ch.player.name = const_cast<char *>("Archer");
    ch.specials.position = POS_STANDING | STAT_NORMAL;
    ch.curr_stats.Str = ch.curr_stats.Dex = 100;
    target = {}; target.only.npc = &npc; target.specials.act = ACT_ISNPC;
    target.specials.position = POS_STANDING | STAT_NORMAL;
    obj_data bow{}, quiver{};
    P_obj arrow = new obj_data{};
    bow.type = ITEM_FIREWEAPON; bow.value[0] = 30; bow.value[1] = 100;
    ch.equipment[WIELD] = &bow;
    quiver.type = ITEM_QUIVER; quiver.loc_p = LOC_NOWHERE;
    quiver.value[0] = 10; quiver.value[3] = 1;
    arrow->type = ITEM_MISSILE; arrow->loc_p = LOC_NOWHERE; arrow->condition = condition;
    set_keywords(arrow, "custom arrow");
    set_short_description(arrow, "a custom arrow");
    if (starter) {
        allocation = arrow; prototype.type = ITEM_MISSILE; prototype.extra_flags = 1032;
        materialize_legacy_newbie_item(&ch, {{1117, true}, {}});
    }
    obj_to_obj(arrow, &quiver);
    equip_char(&ch, &quiver, WEAR_QUIVER, FALSE);
    force_hit = true; cursed = returning; scrapped = delivered = 0;
    damage_result = death == 1 ? DAM_VICTDEAD : DAM_NONEDEAD;
    enchant_kills = death == 2;
    int destroyed_before = destroyed;
    char argument[] = "target";
    do_fire(&ch, argument, CMD_FIRE);
    assert(quiver.value[3] == (returning ? 1 : 0));
    const bool broken = !returning && condition <= 5;
    assert(scrapped == (broken && !death ? 1 : 0));
    assert(destroyed == destroyed_before + (broken && death ? 1 : 0));
    assert(delivered == (!returning && condition > 5 ? 1 : 0));
    assert(pending.empty() && !rooms[0].contents);
    if (!broken) {
        assert(arrow->condition == (returning ? condition : condition - 5));
        if (returning) obj_from_obj(arrow);
        free_obj(arrow);
    }
    force_hit = false;
    damage_result = DAM_NONEDEAD;
    enchant_kills = false;
}

static void mark_control(bool customized) {
    char_data ch{}, victim{};
    ch.player.name = const_cast<char *>("Archer");
    ch.specials.position = victim.specials.position = POS_STANDING | STAT_NORMAL;
    indices[0].keys = str_dup("prototype arrow");
    indices[0].desc2 = str_dup("a prototype arrow");
    P_obj arrow = new obj_data{};
    arrow->name = indices[0].keys; arrow->short_description = indices[0].desc2;
    arrow->condition = 100;
    if (customized) {
        set_keywords(arrow, "newbie custom arrow");
        set_short_description(arrow, "a custom arrow");
    }
    int before = mark_events;
    for (int cycle = 0; cycle < 50; ++cycle) {
        enchant_arrows(&ch, &victim, arrow, ARROW_MARK);
        assert(strstr(arrow->name, "aArcher") && strstr(arrow->short_description, "Archer"));
        assert(arrow->timer[5] == ARROW_MARK);
        enchant_arrows(&ch, &victim, arrow, ARROW_MARK);
        assert(mark_events == before + cycle + 1);
        event_enchant_arrow(nullptr, nullptr, arrow, nullptr);
        assert(!strcmp(arrow->name, indices[0].keys));
        assert(!strcmp(arrow->short_description, indices[0].desc2));
        assert(arrow->name != indices[0].keys && arrow->short_description != indices[0].desc2);
        assert((arrow->str_mask & (STRUNG_KEYS | STRUNG_DESC2)) == (STRUNG_KEYS | STRUNG_DESC2));
        assert(arrow->timer[5] == ARROW_NONE);
    }
    free_obj(arrow);
    assert(!strcmp(indices[0].keys, "prototype arrow"));
    str_free(indices[0].keys); str_free(indices[0].desc2);
    indices[0].keys = indices[0].desc2 = nullptr;
}

static void gather_control(bool corpse) {
    char_data ch{}; pc_only_data pc{}; ch.only.pc = &pc; pc.pid = 42;
    obj_data quiver{}, source{}, arrows[3]{};
    quiver.type = ITEM_QUIVER; quiver.loc_p = LOC_NOWHERE;
    quiver.value[0] = 1; quiver.value[2] = 1;
    source.type = ITEM_CORPSE; source.loc_p = LOC_NOWHERE;
    corpse_source = corpse ? &source : nullptr;
    for (auto &arrow : arrows) {
        arrow.type = ITEM_MISSILE; arrow.loc_p = LOC_NOWHERE;
        arrow.weight = 1; arrow.timer[0] = pc.pid;
        arrow.value[3] = 1;
        if (corpse) obj_to_obj(&arrow, &source); else obj_to_room(&arrow, 0);
    }
    arrows[2].value[3] = 2; // First candidate is incompatible, so skip it.
    equip_char(&ch, &quiver, WEAR_QUIVER, FALSE);
    char argument[16]; strcpy(argument, corpse ? "corpse" : "");
    do_gather(&ch, argument, 0);
    assert(quiver.value[3] == 1 && quiver.weight == 1 && quiver.contains == &arrows[1]);
    for (int attempt = 0; attempt < 3; ++attempt) {
        do_gather(&ch, argument, 0);
        assert(quiver.value[3] == 1 && quiver.weight == 1 && !arrows[1].next_content);
    }
    assert(corpse ? OBJ_INSIDE(&arrows[0]) : OBJ_ROOM(&arrows[0]));
    assert(corpse ? OBJ_INSIDE(&arrows[2]) : OBJ_ROOM(&arrows[2]));
    for (auto &arrow : arrows)
        if (OBJ_INSIDE(&arrow)) obj_from_obj(&arrow); else obj_from_room(&arrow);
    assert(!rooms[0].contents && !source.contains);
    corpse_source = nullptr;
}

static void volley_control(bool adjacent) {
    char_data ch{}; pc_only_data pc{}; npc_only_data npc{};
    ch.only.pc = &pc; pc.pid = 42;
    ch.specials.position = POS_STANDING | STAT_NORMAL;
    ch.curr_stats.Str = ch.curr_stats.Dex = 100;
    target = {}; target.only.npc = &npc; target.specials.act = ACT_ISNPC;
    target.specials.position = POS_STANDING | STAT_NORMAL; target.in_room = adjacent ? 1 : 0;
    room_direction_data exit{}; exit.to_room = 1; rooms[0].dir_option[0] = &exit;
    obj_data bow{}, quiver{}, shield{};
    bow.type = ITEM_FIREWEAPON; bow.value[0] = 60; bow.value[1] = 100;
    quiver.type = ITEM_QUIVER; quiver.loc_p = LOC_NOWHERE; quiver.value[3] = 2;
    shield.type = ITEM_SHIELD; target.equipment[WEAR_SHIELD] = &shield;
    ch.equipment[WIELD] = &bow;
    P_obj arrows[2];
    for (auto &arrow : arrows) {
        arrow = new obj_data{}; arrow->type = ITEM_MISSILE; arrow->condition = 100;
        arrow->loc_p = LOC_NOWHERE;
        set_keywords(arrow, "arrow"); set_short_description(arrow, "an arrow");
        obj_to_obj(arrow, &quiver);
    }
    equip_char(&ch, &quiver, WEAR_QUIVER, FALSE);
    force_hit = block_first = true; cursed = false; block_rolls = damage_calls = 0;
    char argument[32]; strcpy(argument, adjacent ? "target north" : "target");
    do_fire(&ch, argument, CMD_FIRE);
    assert(block_rolls == 2 && damage_calls == 1 && quiver.value[3] == 0);
    for (auto arrow : arrows) free_obj(arrow);
    force_hit = block_first = false;
}

int main() {
    indices[0].virtual_number = 1117;
    for (int race : {RACE_HALFELF, RACE_WOODELF}) {
        newbie_kit_input input{}; input.race = race; input.main_class = CLASS_RANGER;
        auto kit = make_newbie_kit_plan(input);
        assert(std::count_if(kit.begin(), kit.end(), [](auto item) { return item.vnum == 1117; }) == 10);
    }
    for (int shell : {4, 5})
        for (int weight : {-1, 0, 1, 2})
            for (int shots : {1, 2, 3})
                for (int loaded : {1, 3})
                    for (bool returning : {false, true})
                        for (bool starter : {false, true})
                            for (int landing : {0, 1})
                                scenario(shell, weight, shots, loaded, returning, starter, landing);
    controls();
    for (bool starter : {false, true})
        for (bool returning : {false, true})
            for (int condition : {100, 1})
                hit_control(starter, returning, condition);
    hit_control(true, false, 1, 1);
    hit_control(true, false, 1, 2);
    for (bool variant : {false, true}) {
        mark_control(variant); gather_control(variant); volley_control(variant);
    }
    puts("fire/gather: 384 x 50 cycles; decay, 10 hit/retirement, 100 mark expiry, room/corpse gather and 2 volley controls passed");
}
'''.replace("// PRODUCTION", strings + "\n" + handler + "\n" + materialize + "\n" + decay_callback + "\n" + commands)

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="fired-missile-weight-", dir=build) as temporary:
    source = Path(temporary) / "harness.cpp"
    binary = Path(temporary) / "harness"
    source.write_text(harness)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-fsanitize=address,undefined",
        "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-ffunction-sections", "-fdata-sections", "-I", str(ROOT / "src"),
        str(source), str(ROOT / "src/account/newbie_kit_plan.c"),
        str(HARNESS_STUBS), "-Wl,--gc-sections", "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
