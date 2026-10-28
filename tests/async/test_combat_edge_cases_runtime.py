#!/usr/bin/env python3
"""Execute combat displacement and refusal edge cases with production code.

The shared movement implementation, combat handlers, character layout and macros
are real. Deterministic rolls and room/script fixtures isolate admission,
interruption, arrival effects, immunity and guard ordering without a server.
"""

from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, source


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/damage.h"
#include "combat/guard.h"
#include "combat/forced_movement.h"
#include "magic/spells.h"
#include "net/comm.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <functional>
#include <string>
#include <vector>

#define TAKEDOWN_ALL 65535U
#define TAKEDOWN_AGI_CHECK BIT_9
#define TAKEDOWN_FOOTING BIT_12
#define TAKEDOWN_CANCELLED -1
#define TAKEDOWN_PENALTY -2

static room_data rooms[5]{};
P_room world = rooms;
extern const int top_of_world = 4;
static zone_data zones[2]{};
zone_data *zone_table = zones;
const char *dirs[] = {"north", "east", "south", "west", "up", "down",
                      "northwest", "northeast", "southwest", "southeast"};
static char_data actor{}, victim{}, witness{}, stranger{};
static room_direction_data north{};
static std::vector<P_char> live;
static std::vector<std::string> fixture_messages;
struct Delivered { P_char recipient; std::string text; };
static std::vector<Delivered> delivered;
static P_char parsed_target, guard_target, forbidden_target;
static bool fight_allowed, improved, magical_wall, castle_wall;
static int damage_calls, guard_calls, victim_waits, actor_waits, stops, actor_lag;
static int notch_calls, total_waits;
static int callback_calls, arrivals, departure_calls, arrival_direction, engaged;
static P_char riding, rider;
enum class Leave { ordinary, veto, redirect, kill, extract, replace, retarget, seal,
                   move_actor, second_veto, second_redirect, second_extract };
enum class Enter { ordinary, redirect, kill, extract, combat };
static Leave leave;
static Enter enter;

static void remove_room(P_char ch)
{
    if (ch->in_room >= 0 && ch->in_room <= top_of_world)
    {
        P_char *link = &world[ch->in_room].people;
        while (*link && *link != ch)
            link = &(*link)->next_in_room;
        if (*link)
            *link = ch->next_in_room;
    }
    if (ch->in_room >= 0 && ch->in_room <= top_of_world)
        ch->specials.was_in_room = world[ch->in_room].number;
    ch->next_in_room = nullptr;
    ch->in_room = NOWHERE;
}

static void place(P_char ch, int room)
{
    remove_room(ch);
    ch->in_room = room;
    ch->next_in_room = world[room].people;
    world[room].people = ch;
}

static void forget(P_char ch)
{
    remove_room(ch);
    live.erase(std::remove(live.begin(), live.end(), ch), live.end());
}

P_char find_character_by_runtime_id(uint64_t id)
{
    for (P_char ch : live)
        if (ch->runtime_id == id)
            return ch;
    return nullptr;
}
int char_in_list(const P_char ch)
{
    return std::find(live.begin(), live.end(), ch) != live.end();
}

void char_from_room(P_char ch)
{
    ++departure_calls;
    if (leave == Leave::veto || (leave == Leave::second_veto && departure_calls == 2))
        return;
    if (leave == Leave::redirect || (leave == Leave::second_redirect && departure_calls == 2))
    {
        place(ch, 3);
        return;
    }
    if (leave == Leave::extract || (leave == Leave::second_extract && departure_calls == 2))
    {
        forget(ch);
        return;
    }
    if (leave == Leave::kill)
    {
        SET_POS(ch, STAT_DEAD);
        return;
    }
    if (leave == Leave::replace)
    {
        ++ch->runtime_id;
        return;
    }
    remove_room(ch);
    if (leave == Leave::retarget)
        north.to_room = 2;
    if (leave == Leave::seal)
        north.exit_info |= EX_BLOCKED;
    if (leave == Leave::move_actor)
        place(&actor, 3);
}

bool char_to_room(P_char ch, int room, int direction)
{
    assert(room >= 0 && room <= top_of_world);
    place(ch, room);
    if (direction < 0)
        return true;
    ++arrivals;
    arrival_direction = direction;
    switch (enter)
    {
    case Enter::redirect: place(ch, 3); return false;
    case Enter::kill: SET_POS(ch, STAT_DEAD); return false;
    case Enter::extract: forget(ch); return false;
    case Enter::combat: ch->specials.fighting = &stranger; break;
    case Enter::ordinary: break;
    }
    return true;
}

bool check_castle_walls(int, int) { return castle_wall; }
int check_wall(int, int) { return magical_wall; }
P_char get_linked_char(P_char ch, ush_int type)
{
    return type == LNK_RIDING && ch == &victim ? riding : nullptr;
}
P_char get_linking_char(P_char ch, ush_int type)
{
    return type == LNK_RIDING && ch == &victim ? rider : nullptr;
}
void unlink_char(P_char ch, P_char target, ush_int type)
{
    assert(type == LNK_RIDING);
    if (ch == &victim && target == riding)
        riding = nullptr;
    if (ch == rider && target == &victim)
        rider = nullptr;
}
void act(const char *message, int, P_char ch, P_obj object, void *target, int)
{
    assert(!object); // this harness exercises only character references
    if (ch) assert(ch->in_room >= 0 && ch->in_room <= top_of_world);
    if (target)
    {
        P_char referred = static_cast<P_char>(target);
        assert(referred->in_room >= 0 && referred->in_room <= top_of_world);
    }
    fixture_messages.emplace_back(message);
}
void send_to_char(const char *message, P_char recipient)
{
    fixture_messages.emplace_back(message);
    delivered.push_back({recipient, message});
}
void debug(const char *, ...) {}
void send_to_room_except_two(const char *text, int, P_char, P_char) { fixture_messages.emplace_back(text); }
float get_property(const char *, double value) { return value; }
int get_property(const char *, int value) { return value; }
int number(int minimum, int maximum)
{
    // Every actual launch roll succeeds and selects the fixture's north exit.
    if (minimum == 0)
        return 0;
    assert(minimum <= maximum);
    return minimum;
}
int get_takedown_size(P_char ch) { return ch->player.size; }
int GET_CHAR_SKILL_P(P_char, int) { return 100; }
int chance_kick(P_char, P_char) { return fight_allowed ? 200 : 0; }
float takedown_check(P_char, P_char, float, int, ulong) { return 200; }
bool notch_skill(P_char, int, float) { ++notch_calls; return improved; }
int CanDoFightMove(P_char, P_char target) { return fight_allowed && target != forbidden_target; }
P_char guard_check(P_char, P_char target) { ++guard_calls; return guard_target ? guard_target : target; }
P_char ParseTarget(P_char, char *) { return parsed_target; }
int on_front_line(P_char) { return true; }
bool has_innate(P_char ch, int innate)
{
    return innate == INNATE_HORSE_BODY && ch->player.race == RACE_CENTAUR;
}
bool affected_by_spell(P_char, int) { return false; }
void appear(P_char, bool) {}
void CharWait(P_char ch, int wait)
{
    ++total_waits;
    if (ch == &actor) { ++actor_waits; actor_lag = wait; }
    if (ch == &victim) ++victim_waits;
}
void Stun(P_char, P_char, int, bool) {}
void engage(P_char, P_char) { ++engaged; }
void set_fighting(P_char ch, P_char target) { ch->specials.fighting = target; }
void stop_fighting(P_char ch) { ++stops; ch->specials.fighting = nullptr; }
void set_short_affected_by(P_char, int, int) {}
struct affected_type *affect_to_char(P_char, struct affected_type *effect) { return effect; }
int melee_damage(P_char, P_char, double, int, struct damage_messages *, int *)
{
    ++damage_calls;
    return DAM_NONEDEAD;
}
void kick_messages(P_char, P_char, bool, struct damage_messages *out)
{
    out->attacker = const_cast<char *>("kick hit");
    out->victim = const_cast<char *>("kick hit");
    out->room = const_cast<char *>("kick hit");
}
void branch(P_char, P_char) {}
void do_bite(P_char, char *, int) {}
'''

DRIVER = r'''
static void reset()
{
    for (auto &room : rooms) room = room_data{};
    for (auto &zone : zones) zone = zone_data{};
    zones[0].flags = ZONE_MAP;
    for (int i = 0; i <= top_of_world; ++i)
    {
        rooms[i].zone = 0;
        rooms[i].number = 500000 + i;
        rooms[i].sector_type = SECT_FIELD;
    }
    actor = char_data{};
    victim = char_data{};
    witness = char_data{};
    stranger = char_data{};
    uint64_t id = 1;
    for (P_char ch : {&actor, &victim, &witness, &stranger})
    {
        ch->runtime_id = id++;
        ch->in_room = NOWHERE;
        ch->player.race = RACE_HUMAN;
        ch->player.size = SIZE_SMALL;
        ch->player.level = 30;
        ch->player.name = const_cast<char *>("fixture");
        ch->curr_stats.Str = ch->curr_stats.Dex = ch->curr_stats.Agi = 100;
        ch->curr_stats.Luk = ch->curr_stats.Con = 100;
        SET_POS(ch, POS_STANDING + STAT_NORMAL);
    }
    actor.player.race = RACE_OGRE;
    actor.player.size = SIZE_HUGE;
    north = room_direction_data{};
    north.to_room = 1;
    rooms[0].dir_option[DIR_NORTH] = &north;
    live = {&actor, &victim, &witness, &stranger};
    place(&actor, 0);
    place(&victim, 0);
    place(&witness, 4);
    place(&stranger, 4);
    parsed_target = &victim;
    guard_target = forbidden_target = nullptr;
    fight_allowed = true;
    improved = true;
    magical_wall = castle_wall = false;
    damage_calls = guard_calls = actor_waits = victim_waits = stops = actor_lag = 0;
    notch_calls = total_waits = 0;
    callback_calls = arrivals = departure_calls = engaged = 0;
    arrival_direction = -9;
    riding = rider = nullptr;
    leave = Leave::ordinary;
    enter = Enter::ordinary;
    fixture_messages.clear();
    delivered.clear();
}

static bool said(const std::string &part)
{
    for (const auto &message : fixture_messages)
        if (message.find(part) != std::string::npos)
            return true;
    return false;
}

static forced_move_result single()
{
    return move_forced(&actor, &victim, DIR_NORTH, [] {
        assert(actor.in_room == 0 && victim.in_room == NOWHERE);
        ++callback_calls;
    });
}
static forced_move_result run_pair()
{
    return move_forced_pair(&actor, &victim, DIR_NORTH, [] {
        assert(actor.in_room == NOWHERE && victim.in_room == NOWHERE);
        ++callback_calls;
    });
}
static void require_block(forced_block reason)
{
    const auto result = single();
    assert(result.status == forced_move_status::blocked);
    assert(result.reason == reason);
    assert(actor.in_room == 0 && victim.in_room == 0);
    assert(departure_calls == 0 && callback_calls == 0 && arrivals == 0);
}

static void admission_cases()
{
    reset(); rooms[1].sector_type = SECT_MOUNTAIN; require_block(forced_block::mountain);
    reset(); rooms[1].sector_type = SECT_UNDRWLD_MOUNTAIN; require_block(forced_block::cavern_wall);
    reset(); north.to_room = NOWHERE; require_block(forced_block::invalid_room);
    reset(); north.to_room = top_of_world + 1; require_block(forced_block::invalid_room);
    reset(); north.to_room = 0; require_block(forced_block::barrier);
    reset(); north.exit_info = EX_SECRET; require_block(forced_block::barrier);
    reset(); north.exit_info = EX_BLOCKED; require_block(forced_block::barrier);
    reset(); magical_wall = true; require_block(forced_block::barrier);
    reset(); castle_wall = true; require_block(forced_block::barrier);
    reset(); north.exit_info = EX_CLOSED; require_block(forced_block::door);
    reset(); north.exit_info = EX_CLOSED | EX_LOCKED | EX_PICKPROOF;
    victim.specials.affected_by2 |= AFF2_PASSDOOR; require_block(forced_block::door);
    reset(); north.exit_info = EX_CLOSED | EX_LOCKED;
    victim.specials.affected_by2 |= AFF2_PASSDOOR;
    assert(single().status == forced_move_status::arrived && victim.in_room == 1);
    reset(); rooms[1].sector_type = SECT_MOUNTAIN; victim.player.level = 60;
    assert(single().status == forced_move_status::arrived && victim.in_room == 1);
    reset(); rooms[1].sector_type = SECT_MOUNTAIN; rooms[0].zone = 1;
    assert(single().status == forced_move_status::arrived && victim.in_room == 1);
    reset(); rooms[1].room_flags = ROOM_PRIVATE;
    place(&witness, 1); place(&stranger, 1); require_block(forced_block::private_room);
    reset(); rooms[1].room_flags = ROOM_PRIVATE; place(&witness, 1);
    const auto blocked_pair = run_pair();
    assert(blocked_pair.status == forced_move_status::blocked);
    assert(blocked_pair.reason == forced_block::private_room);
    assert(actor.in_room == 0 && victim.in_room == 0 && departure_calls == 0);
    reset(); rooms[1].room_flags = ROOM_PRIVATE;
    assert(run_pair().status == forced_move_status::arrived);
    assert(actor.in_room == 1 && victim.in_room == 1 && arrivals == 2);
    reset(); rooms[1].sector_type = SECT_MOUNTAIN; actor.player.level = 60;
    assert(run_pair().status == forced_move_status::blocked); // both permissions matter
    assert(actor.in_room == 0 && victim.in_room == 0);
}

static void script_cases()
{
    reset();
    assert(single().status == forced_move_status::arrived);
    assert(victim.in_room == 1 && actor.in_room == 0);
    assert(arrivals == 1 && arrival_direction == DIR_NORTH && callback_calls == 1);
    for (const auto effect : {Leave::veto, Leave::redirect, Leave::kill,
                              Leave::extract, Leave::replace, Leave::retarget,
                              Leave::seal, Leave::move_actor})
    {
        reset(); leave = effect;
        const auto status = single().status;
        assert(status == ((effect == Leave::retarget || effect == Leave::seal)
                          ? forced_move_status::blocked : forced_move_status::interrupted));
        assert(callback_calls == 0 && arrivals == 0);
        if (effect == Leave::veto || effect == Leave::retarget || effect == Leave::seal)
            assert(victim.in_room == 0);
        if (effect == Leave::redirect) assert(victim.in_room == 3);
        if (effect == Leave::extract) assert(!char_in_list(&victim));
        if (effect == Leave::replace) assert(victim.runtime_id == 3);
        if (effect == Leave::move_actor) assert(actor.in_room == 3);
    }
    for (const auto effect : {Enter::redirect, Enter::kill, Enter::extract})
    {
        reset(); enter = effect;
        assert(single().status == forced_move_status::interrupted);
        assert(callback_calls == 1 && arrivals == 1 && arrival_direction == DIR_NORTH);
        if (effect == Enter::redirect) assert(victim.in_room == 3);
        if (effect == Enter::kill) assert(GET_STAT(&victim) == STAT_DEAD);
        if (effect == Enter::extract) assert(!char_in_list(&victim));
    }
    for (const auto effect : {Leave::second_veto, Leave::second_redirect, Leave::second_extract})
    {
        reset(); leave = effect;
        assert(run_pair().status == forced_move_status::interrupted);
        assert(actor.in_room == 0 && arrivals == 0 && callback_calls == 0);
        if (effect == Leave::second_veto) assert(victim.in_room == 0);
        if (effect == Leave::second_redirect) assert(victim.in_room == 3);
        if (effect == Leave::second_extract) assert(!char_in_list(&victim));
    }
    reset(); riding = &witness; rider = &stranger;
    assert(single().status == forced_move_status::arrived);
    assert(riding == nullptr && rider == nullptr);
    assert(witness.in_room == 4 && stranger.in_room == 4);
    reset(); riding = &witness; rider = &stranger;
    assert(run_pair().status == forced_move_status::arrived);
    assert(actor.in_room == 1 && victim.in_room == 1);
    assert(riding == nullptr && rider == nullptr);
    assert(witness.in_room == 4 && stranger.in_room == 4);
}

static void handler_cases()
{
    for (const bool rear : {false, true})
    {
        for (const int sector : {SECT_MOUNTAIN, SECT_UNDRWLD_MOUNTAIN})
        {
            reset(); rooms[1].sector_type = sector;
            if (rear) actor.player.race = RACE_CENTAUR;
            if (rear) do_rearkick(&actor, const_cast<char *>("fixture"), 0);
            else kick(&actor, &victim);
            assert(damage_calls == 1);
            assert(victim.in_room == 0 && actor.in_room == 0 && arrivals == 0);
            assert(GET_POS(&victim) == (rear ? POS_SITTING : POS_PRONE));
            assert(victim_waits > 0);
            assert(said(sector == SECT_MOUNTAIN ? "mountain" : "cavern"));
        }
        reset(); if (rear) actor.player.race = RACE_CENTAUR;
        enter = Enter::combat;
        if (rear) do_rearkick(&actor, const_cast<char *>("fixture"), 0);
        else kick(&actor, &victim);
        assert(damage_calls == 1 && victim.in_room == 1);
        assert(arrivals == 1 && arrival_direction == DIR_NORTH);
        assert(victim.specials.fighting == &stranger); // arrival-started combat survives
        assert(GET_POS(&victim) == POS_PRONE && victim_waits > 0);
        reset(); if (rear) actor.player.race = RACE_CENTAUR;
        leave = Leave::redirect;
        if (rear) do_rearkick(&actor, const_cast<char *>("fixture"), 0);
        else kick(&actor, &victim);
        assert(victim.in_room == 3 && arrivals == 0);
        assert(GET_POS(&victim) == POS_STANDING && victim_waits == 0);
        assert(!said("crashing") && !said("mountain"));
        for (const bool notch : {false, true})
        {
            reset(); improved = notch; victim.player.race = RACE_GHOST;
            if (rear) actor.player.race = RACE_CENTAUR;
            if (rear) do_rearkick(&actor, const_cast<char *>("fixture"), 0);
            else kick(&actor, &victim);
            assert(damage_calls == 0 && victim_waits == 0 && victim.in_room == 0);
            assert(!fixture_messages.empty());
        }
    }
    reset(); fight_allowed = false; victim.player.race = RACE_GHOST;
    do_kick(&actor, const_cast<char *>("fixture"), 0);
    assert(guard_calls == 0 && victim_waits == 0 && damage_calls == 0);
    reset(); fight_allowed = false; victim.player.race = RACE_GHOST;
    do_roundkick(&actor, const_cast<char *>("fixture"), 0);
    assert(guard_calls == 0 && victim_waits == 0 && damage_calls == 0);
    reset(); guard_target = forbidden_target = &witness;
    place(&witness, 0);
    do_roundkick(&actor, const_cast<char *>("fixture"), 0);
    assert(guard_calls == 1 && total_waits == 0 && damage_calls == 0 && notch_calls == 0);
    reset(); actor.player.size = victim.player.size;
    do_roundkick(&actor, const_cast<char *>("fixture"), 0);
    assert(guard_calls == 1 && damage_calls == 1);
    reset(); victim.player.race = RACE_GHOST;
    roundkick(&actor, &victim);
    assert(victim_waits == 0 && damage_calls == 0);
    assert(actor_waits == 1 && actor_lag == (int)(PULSE_VIOLENCE * 0.250));
    reset(); victim.player.race = RACE_GHOST;
    assert(chance_roundkick(&actor, &victim) == TAKEDOWN_CANCELLED);
    assert(actor_waits == 1 && actor_lag == (int)(PULSE_VIOLENCE * 0.250));
    assert(victim_waits == 0 && damage_calls == 0);

    reset(); actor.player.size = victim.player.size;
    rooms[1].sector_type = SECT_MOUNTAIN;
    do_tackle(&actor, const_cast<char *>("fixture"), 0);
    assert(actor.in_room == 0 && victim.in_room == 0 && arrivals == 0);
    assert(GET_POS(&victim) == POS_SITTING && said("mountain"));
    reset(); actor.player.size = victim.player.size;
    do_tackle(&actor, const_cast<char *>("fixture"), 0);
    assert(actor.in_room == 1 && victim.in_room == 1 && arrivals == 2);
    assert(GET_POS(&victim) == POS_SITTING);
    reset(); actor.player.size = victim.player.size;
    rooms[1].sector_type = SECT_OCEAN;
    do_tackle(&actor, const_cast<char *>("fixture"), 0);
    assert(actor.in_room == 0 && victim.in_room == 0 && arrivals == 0);
}

static void observer_case()
{
    reset();
    actor.player.size = victim.player.size;
    descriptor_data descriptor{};
    witness.desc = stranger.desc = &descriptor;
    witness.specials.z_cord = 0;
    stranger.specials.z_cord = 1;
    place(&witness, 0);
    place(&stranger, 0);
    char_data sleeping{}, disconnected{};
    sleeping.runtime_id = 50;
    disconnected.runtime_id = 51;
    sleeping.in_room = disconnected.in_room = NOWHERE;
    sleeping.desc = &descriptor;
    SET_POS(&sleeping, STAT_SLEEPING + POS_PRONE);
    SET_POS(&disconnected, STAT_NORMAL + POS_STANDING);
    live.push_back(&sleeping);
    live.push_back(&disconnected);
    place(&sleeping, 0);
    place(&disconnected, 0);
    do_tackle(&actor, const_cast<char *>("fixture"), 0);
    assert(actor.in_room == 1 && victim.in_room == 1 && arrivals == 2);
    int launch_deliveries = 0;
    for (const auto &message : delivered)
        if (message.text.find("two combatants") != std::string::npos)
        {
            assert(message.recipient == &witness);
            ++launch_deliveries;
        }
    assert(launch_deliveries == 1);
    forget(&sleeping);
    forget(&disconnected);
}

int main()
{
    observer_case();
    admission_cases();
    script_cases();
    handler_cases();
    std::puts("combat edge cases: admission, scripted transfers, kick/rearkick/tackle, immunity and guards passed");
}
'''

functions = [extract_function("utility.c", "int BOUNDED(")] + [
    extract_function("actoff.c", signature)
    for signature in (
        "static void forced_rebound_messages(",
        "void kick(",
        "int chance_roundkick(",
        "bool roundkick(",
        "void do_roundkick(",
        "void do_kick(",
        "void do_tackle(",
        "void do_rearkick(",
    )
]

# A caller can keep all scratch artifacts in its isolated D: build tree.
build_root = Path(os.environ.get("BIN_ROOT", ROOT / "bin")) / "tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="combat-edge-cases-", dir=build_root) as directory:
    harness = Path(directory) / "harness.cpp"
    binary = Path(directory) / "harness"
    harness.write_text("\n".join((PRELUDE, *functions, DRIVER)), encoding="utf-8")
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-ffunction-sections", "-fdata-sections", f"-I{ROOT / 'src'}",
        str(harness), str(source("combat/forced_movement.c")), str(HARNESS_STUBS),
        "-Wl,--gc-sections", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
