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
    "void do_fire(", "void do_gather(",
))
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
static index_data indices[1] = {};
P_index obj_index = indices;
int top_of_objt = 0;
const char *dirs[] = {"north"};
const char *dirs2[] = {"the north"};
extern const int rev_dir[];
const int rev_dir[] = {0};
static char_data target;
static bool cursed;
static int fired;
static bool force_hit;
static int scrapped, delivered, destroyed;
static object_template prototype;
static P_obj allocation;
static bool keyword_added;
static std::vector<std::pair<P_obj, obj_affect>> pending;

// Deterministic hits/misses and returning arrows; no damage to a live target.
int GET_CHAR_SKILL_P(P_char, int skill) { return skill == SKILL_ARCHERY ? 100 : 0; }
bool notch_skill(P_char, int skill, float) { return skill == SKILL_CURSED_ARROWS && cursed; }
int number(int, int high) { return high; }
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
int enchant_arrows(P_char, P_char, P_obj, int) { return DAM_NONEDEAD; }
void MakeScrap(P_char, P_obj object) { assert(object->condition <= 0); ++scrapped; }
int melee_damage(P_char, P_char, double, int, damage_messages *, int *) { return DAM_NONEDEAD; }
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
    assert(!*input);
    *word = '\0';
    return const_cast<char *>(input);
}
int generic_find(const char *, int, P_char, P_char *, P_obj *) { std::abort(); }
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

static void hit_control(bool starter, bool returning, int condition) {
    char_data ch{}; pc_only_data pc{}; npc_only_data npc{};
    ch.only.pc = &pc; pc.pid = 42;
    ch.specials.position = POS_STANDING | STAT_NORMAL;
    ch.curr_stats.Str = ch.curr_stats.Dex = 100;
    target = {}; target.only.npc = &npc; target.specials.act = ACT_ISNPC;
    target.specials.position = POS_STANDING | STAT_NORMAL;
    obj_data bow{}, quiver{}, arrow{};
    bow.type = ITEM_FIREWEAPON; bow.value[0] = 30; bow.value[1] = 100;
    ch.equipment[WIELD] = &bow;
    quiver.type = ITEM_QUIVER; quiver.loc_p = LOC_NOWHERE;
    quiver.value[0] = 10; quiver.value[3] = 1;
    arrow.type = ITEM_MISSILE; arrow.loc_p = LOC_NOWHERE; arrow.condition = condition;
    if (starter) {
        allocation = &arrow; prototype.type = ITEM_MISSILE; prototype.extra_flags = 1032;
        materialize_legacy_newbie_item(&ch, {{1117, true}, {}});
    }
    obj_to_obj(&arrow, &quiver);
    equip_char(&ch, &quiver, WEAR_QUIVER, FALSE);
    force_hit = true; cursed = returning; scrapped = delivered = 0;
    char argument[] = "target";
    do_fire(&ch, argument, CMD_FIRE);
    assert(quiver.value[3] == (returning ? 1 : 0));
    assert(arrow.condition == (returning ? condition : condition - 5));
    assert(scrapped == (!returning && condition <= 5 ? 1 : 0));
    assert(delivered == (!returning && condition > 5 ? 1 : 0));
    assert(pending.empty() && !rooms[0].contents);
    force_hit = false;
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
    puts("fire/gather: 384 scenarios x 50 cycles; decay and 8 hit/wear/returning controls passed");
}
'''.replace("// PRODUCTION", handler + "\n" + materialize + "\n" + decay_callback + "\n" + commands)

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
