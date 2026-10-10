#!/usr/bin/env python3
"""The tick's work is spread over its pulses, and no character's numbers change.

On an idle world the tick was one slow pulse and three busy ones. affect_update() walked
all 56,000 mobs at once (40 to 140 ms on staging); the regeneration events it started all
ran 10 pulses later, and each rescheduled itself once more after filling its mob, only to
find it full 10 pulses after that; generic_char_event() ran on the same pulses.

The real event_move_regen(), event_hit_regen(), event_mana_regen(), event_ward_regen(),
StartRegen() and affect_update() run here:

- a regeneration event that fills its character does not reschedule; the points gained
  and the pulses they arrive on are those of an event that rescheduled once more;
- StartRegen() gives a mob's first event its own point within the delay, and the event
  counts the pulses that passed, so the gain is the same;
- affect_update() counts a mob's affects down at its own slice's pulse and a player's on
  the tick's first pulse: once a tick each, over a whole tick.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, source

events = source("events.c").read_text()
delays = "\n".join(line for line in events.splitlines()
                    if line.startswith("#define MOB_") and "_REGEN_DELAY" in line)

REGEN = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/events.h"
#include <cassert>
#include <cstdio>
#include <vector>

struct regen_event_state
{
    float accumulated;
    unsigned long long last_tick;
};

int pulse = 0;
unsigned long long ne_event_tick = 0;
P_room world = nullptr;
int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) != 0; }
static int rate = 0;
struct scheduled_regen
{
    event_func func;
    unsigned long long due;
    regen_event_state state;
};
static std::vector<scheduled_regen> queue;
''' + delays + r'''

int move_regen(P_char, bool) { return rate; }
int hit_regen(P_char, bool) { return rate; }
int mana_regen(P_char, bool) { return rate; }
int ward_regen(P_char, bool) { return rate; }
bool affected_by_spell(P_char, int) { return false; }
void send_to_char(const char *, P_char) {}
void stop_meditation(P_char) {}
int char_in_list(const P_char) { return 1; }
void die(P_char, P_char) { assert(false); }
void update_pos(P_char) {}
void gmcp_char_vitals(P_char) {}
void logit(const char *, const char *, ...) {}
void statuslog(int, const char *, ...) {}
P_nevent get_scheduled(P_char, event_func func)
{
    for (const auto &entry : queue)
        if (entry.func == func)
            return reinterpret_cast<P_nevent>(1);
    return nullptr;
}
nevent_schedule_result add_event(event_func func, int delay, P_char, P_char, P_obj, int,
                                 const void *data, int)
{
    queue.push_back({ func, ne_event_tick + delay,
                      *static_cast<const regen_event_state *>(data) });
    return {};
}
''' + "\n".join(extract_function("events.c", signature) for signature in (
    "static struct regen_event_state regen_state_from_data(",
    "static unsigned long long regen_elapsed_ticks(",
    "void event_mana_regen(P_char ch,",
    "void event_ward_regen(P_char ch,",
    "void event_move_regen(P_char ch,",
    "void event_hit_regen(P_char ch,",
    "void StartRegen(P_char ch, regen_resource resource)",
)) + r'''

// Runs every due event, pulse by pulse, until none is left or `pulses` have passed.
// Returns how many runs there were.
static int run(P_char ch, int pulses)
{
    int runs = 0;
    for (int step = 0; step < pulses && !queue.empty(); ++step)
    {
        ++ne_event_tick;
        for (size_t index = 0; index < queue.size();)
            if (queue[index].due == ne_event_tick)
            {
                const scheduled_regen entry = queue[index];
                queue.erase(queue.begin() + index);
                regen_event_state state = entry.state;
                entry.func(ch, nullptr, nullptr, &state);
                ++runs;
            }
            else
                ++index;
    }
    return runs;
}

int main()
{
    char_data mob{};
    npc_only_data npc{};
    mob.only.npc = &npc;
    mob.specials.act = ACT_ISNPC;
    npc.idnum = 3;

    // 300 a tick is a point a pulse: a mob 50 short gains 10 every 10 pulses. The fifth
    // run fills it and is the last: it rescheduled once more before, to find it full.
    rate = PULSES_IN_TICK;
    mob.points.max_vitality = 100;
    mob.points.vitality = 50;
    StartRegen(&mob, regen_resource::vitality);
    // Its first run comes at its own point within the 10 pulses: 1 + idnum % 10.
    assert(queue.size() == 1 && queue[0].due == ne_event_tick + 4);
    const unsigned long long started = ne_event_tick;
    assert(run(&mob, 1000) == 6);
    assert(mob.points.vitality == 100 && queue.empty());
    // The first run gained its 4 pulses; the next five gained 10 each and the last filled it.
    assert(ne_event_tick == started + 4 + 50);

    // A loss starts it again, and it keeps going until full.
    mob.points.vitality = 95;
    StartRegen(&mob, regen_resource::vitality);
    run(&mob, 1000);
    assert(mob.points.vitality == 100 && queue.empty());

    // Hit, mana and ward stop at full the same way; a player's first run is the next pulse.
    char_data player{};
    pc_only_data pc{};
    player.only.pc = &pc;
    player.player.m_class = CLASS_PSIONICIST;
    player.points.max_hit = 100;
    player.points.hit = 99;
    player.points.max_mana = 100;
    player.points.mana = 99;
    player.points.max_ward = 100;
    player.points.ward = 99;
    // event_mana_regen() takes its rate from power and intelligence, not mana_regen().
    player.curr_stats.Pow = player.curr_stats.Int = 100;
    for (regen_resource resource :
         { regen_resource::hit, regen_resource::mana, regen_resource::ward })
    {
        StartRegen(&player, resource);
        assert(queue.size() == 1 && queue[0].due == ne_event_tick + 1);
        run(&player, 1000);
        assert(queue.empty());
    }
    assert(player.points.hit == 100 && player.points.mana == 100 && player.points.ward == 100);
    std::puts("regeneration stops at the maximum with the same gains");
}
'''

affects = source("affects.c").read_text()
update = extract_function("affects.c", "void affect_update(int pulse)")
slicer = extract_function("handler.c", "unsigned int char_slice(P_char c, unsigned int slices)")
spread = affects[affects.index("// NPCs count down in AFFECT_UPDATE_SLICES"):
                 affects.index("void affect_update(int pulse)")]

AFFECTS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "magic/spells.h"
#include "world/events.h"
#include "world/falling.h"
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>

P_char character_list = nullptr;
extern const struct racial_data_type racial_data[];
const struct racial_data_type racial_data[LAST_RACE + 1] = {};
void StartRegen(P_char, regen_resource) {}
void remove_disguise(P_char, bool) {}
int number(int, int) { return 0; }
void wear_off_message(P_char, struct affected_type *) {}
P_char un_morph(P_char ch) { return ch; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void send_to_char(const char *, P_char) {}
bool char_falling(P_char) { return false; }
falling_start_result falling_start(P_char) { return {}; }
struct time_info_data age(P_char) { return {}; }
int GET_CLASS(P_char, uint) { return 0; }
static P_char shapechanged = nullptr;
int IS_MORPH(P_char ch) { return ch == shapechanged; }
static int removed = 0;
void affect_remove(P_char ch, struct affected_type *af)
{
    ch->affected = af->next;
    ++removed;
}
''' + slicer + "\n" + spread + update + r'''

int main()
{
    // Many mobs, so that every slice holds some, and one player.
    std::vector<char_data> mobs(400);
    std::vector<affected_type> buffs(mobs.size());
    for (size_t index = 0; index < mobs.size(); ++index)
    {
        mobs[index].specials.act = ACT_ISNPC;
        buffs[index].duration = 3;
        mobs[index].affected = &buffs[index];
        mobs[index].next = character_list;
        character_list = &mobs[index];
    }
    char_data player{};
    pc_only_data pc{};
    player.only.pc = &pc;
    player.player.level = 60; // trusted, as affect_update() asks of an ageing mortal
    affected_type player_buff{};
    player_buff.duration = 3;
    player.affected = &player_buff;
    player.next = character_list;
    character_list = &player;
    // A player's shapechanged body is an NPC, but counts down with the players.
    char_data body{};
    body.specials.act = ACT_ISNPC;
    affected_type body_buff{};
    body_buff.duration = 3;
    body.affected = &body_buff;
    body.next = character_list;
    character_list = &body;
    shapechanged = &body;

    // Over one tick, each affect counts down once, and the mobs at many pulses.
    std::vector<int> pulses_with_work;
    for (int pulse = 0; pulse < PULSES_IN_TICK; ++pulse)
    {
        int before = 0, after = 0;
        for (const auto &buff : buffs)
            before += buff.duration;
        affect_update(pulse);
        for (const auto &buff : buffs)
            after += buff.duration;
        if (after != before)
            pulses_with_work.push_back(pulse);
        if (pulse == 0)
            assert(player_buff.duration == 2 && body_buff.duration == 2);
    }
    for (const auto &buff : buffs)
        assert(buff.duration == 2);
    assert(player_buff.duration == 2);
    assert(pulses_with_work.size() == AFFECT_UPDATE_SLICES);
    // Three more ticks wear every buff off, each in its own slice's pulse.
    for (int tick = 0; tick < 3; ++tick)
        for (int pulse = 0; pulse < PULSES_IN_TICK; ++pulse)
            affect_update(pulse);
    assert(removed == static_cast<int>(mobs.size()) + 2);
    std::puts("a sliced mob's affects count down once a tick");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="tick-spread-", dir=ROOT / "bin/tests") as tmp:
    for name, text in (("regen", REGEN), ("affects", AFFECTS)):
        test, binary = Path(tmp) / f"{name}.cpp", Path(tmp) / name
        test.write_text(text)
        subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-function", "-fsanitize=address,undefined",
                        "-I", str(ROOT / "src"), str(test), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
