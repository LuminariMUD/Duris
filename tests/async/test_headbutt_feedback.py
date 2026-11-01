#!/usr/bin/env python3
"""Headbutt outcomes with production command, melee reductions and consuming wards.

Raw HP delivery and world services are deterministic fixtures. The companion
booted journey proves actual dispatch, raw damage and recipient filtering.
"""
from pathlib import Path
import subprocess

from _paths import ROOT, HARNESS_STUBS, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "net/comm.h"
#include <sanitizer/asan_interface.h>
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <map>
#include <string>
#include <vector>

static room_data rooms[1]{};
P_room world = rooms;
float dam_factor[LAST_DF + 1];
static char_data actor{}, victim{}, witness{};
static descriptor_data descriptors[3]{};
static pc_only_data players[3]{};
static std::map<P_char, std::string> output;
static std::vector<int> random_trace, mechanics;
static std::vector<affected_type> short_affects;
static affected_type ward{};
static int outcome, double_skill, stun_roll, armor, terminal_result, terminal_call, raw_calls, notches;
static int actor_size, victim_size, permitted;
static double damage_factor;
static bool feedback_ok = true;
static bool prevent_delivery;

static void replace(std::string &text, const std::string &key, const std::string &value) {
    size_t pos = 0;
    while ((pos = text.find(key, pos)) != std::string::npos) {
        text.replace(pos, key.size(), value); pos += value.size();
    }
}
void send_to_char(const char *text, P_char ch) { output[ch] += text; }
void act(const char *text, int, P_char ch, P_obj, void *target, int flags) {
    auto *v = static_cast<P_char>(target);
    for (P_char to : {&actor, &victim, &witness}) {
        int type = flags & 7;
        if (!to->desc || !IS_AWAKE(to) || to->in_room != ch->in_room ||
            to->specials.z_cord != ch->specials.z_cord || to->only.pc->ignored == ch)
            continue;
        if ((type == TO_CHAR && to != ch) || (type == TO_VICT && to != v) ||
            ((type == TO_NOTVICT || type == TO_NOTVICTROOM) && (to == ch || to == v)))
            continue;
        if ((flags & ACT_NOTTERSE) && IS_SET(to->specials.act2, PLR2_TERSE)) continue;
        std::string line = text;
        replace(line, "$n", ch->player.name);
        replace(line, "$N", v ? v->player.name : "(none)");
        replace(line, "$m", "him");
        output[to] += line + "\n";
    }
}
int number(int low, int high) {
    size_t index = random_trace.size() / 3;
    int value;
    if (low == 0 && high == 80) value = 80;
    else if (index == 2) value = outcome;
    else if (low == 20 && high == 30) value = 20;
    else if (low == 5 && high == 15) value = 5;
    else if (low == 1 && high == 8) value = 1;
    else if (low == 0 && high == 300) value = double_skill ? 0 : 300;
    else if (low == 1 && high == 50) value = stun_roll;
    else if (low == 2 && high == 3) value = 2;
    else if (low == 0 && high == 4) value = 1;
    else { assert(low == 1 && high == 100); value = 100; }
    assert(value >= low && value <= high);
    random_trace.insert(random_trace.end(), {low, high, value});
    return value;
}
float get_property(const char *name, double fallback) {
    return !strcmp(name, "skill.headbutt.damfactor") ? damage_factor : fallback;
}
int get_property(const char *, int fallback) { return fallback; }
int GET_CHAR_SKILL_P(P_char, int skill) {
    return skill == SKILL_HEADBUTT ? 100 : skill == SKILL_DOUBLE_HEADBUTT ? double_skill : 0;
}
int GET_CLASS(P_char, uint) { return 0; }
int IS_MORPH(P_char) { return 0; }
int get_takedown_size(P_char ch) { return ch == &actor ? actor_size : victim_size; }
int on_front_line(P_char) { return 1; }
P_char ParseTarget(P_char, char *arg) { return !strcmp(arg, "self") ? &actor : &victim; }
int CanDoFightMove(P_char, P_char) {
    if (!permitted) send_to_char("Combat refused.\n", &actor);
    return permitted;
}
bool notch_skill(P_char, int, float) { ++notches; return false; }
void CharWait(P_char ch, int delay) { mechanics.insert(mechanics.end(), {1, ch == &actor, delay}); }
affected_type *affect_to_char(P_char ch, affected_type *af) {
    mechanics.insert(mechanics.end(), {2, ch == &actor, af->type, af->duration, int(af->flags)});
    short_affects.push_back(*af); return nullptr;
}
bool affected_by_spell(P_char ch, int spell) {
    return spell == SKILL_HEADBUTT && ch->affected && ch->affected->type == SKILL_HEADBUTT;
}
affected_type *get_spell_from_char(P_char, int, void *, int) { return nullptr; }
affected_type *get_first_affect_with_flag(P_char ch, uint flags) {
    return ch->affected && (ch->affected->flags & flags) ? ch->affected : nullptr;
}
void affect_remove(P_char ch, affected_type *af) { assert(ch->affected == af); ch->affected = af->next; }
void wear_off_message(P_char ch, affected_type *) { output[ch] += "Ward expires.\n"; }
void set_fighting(P_char ch, P_char target) { ch->specials.fighting = target; }
void stop_fighting(P_char ch) { ch->specials.fighting = nullptr; mechanics.push_back(3); }
int calculate_ac(P_char) { return armor; }
int BOUNDED(int low, int value, int high) { return std::clamp(value, low, high); }
int dice(int, int) { assert(false); return 0; }
bool rapier_dirk_check(P_char) { return false; }
bool opposite_racewar(P_char, P_char) { return false; }
bool collector_presence_is_npc(P_char) { return false; }
void decrease_skin_counter(P_char, int) { assert(false); }
void DamageStuff(P_char, int) { assert(false); }
int check_shields(P_char, P_char, double, int) { return DAM_NONEDEAD; }
int attack_back(P_char, P_char, int) { return DAM_NONEDEAD; }
int spell_damage(P_char, P_char, double, int, uint, damage_messages *, int *) { assert(false); return 0; }
void knock_out(P_char ch, int delay) {
    mechanics.insert(mechanics.end(), {4, ch == &actor, delay});
    SET_BIT(ch->specials.affected_by, AFF_KNOCKED_OUT);
}
void Stun(P_char ch, P_char, int delay, bool) { mechanics.insert(mechanics.end(), {5, ch == &actor, delay}); }
int raw_damage(P_char ch, P_char target, double amount, uint, damage_messages *msg, int *sum) {
    ++raw_calls;
    if (prevent_delivery) return DAM_NONEDEAD;
    int dam = int(amount);
    GET_HIT(target) -= dam;
    if (sum) *sum += dam;
    act(msg->attacker, FALSE, ch, nullptr, target, TO_CHAR);
    act(msg->victim, FALSE, ch, nullptr, target, TO_VICT);
    act(msg->room, FALSE, ch, nullptr, target, TO_NOTVICTROOM);
    if (terminal_result != DAM_NONEDEAD && raw_calls == terminal_call) {
        // No command/lambda must inspect either character after terminal delivery.
        __asan_poison_memory_region(&actor, sizeof(actor));
        __asan_poison_memory_region(&victim, sizeof(victim));
        return terminal_result;
    }
    return DAM_NONEDEAD;
}
'''

DRIVER = r'''
static void reset(int terse) {
    actor = {}; victim = {}; witness = {}; ward = {};
    output.clear(); random_trace.clear(); mechanics.clear(); short_affects.clear();
    outcome = 60; double_skill = 0; stun_roll = 40; armor = 0;
    terminal_result = 0; raw_calls = notches = actor_size = victim_size = 0;
    terminal_call = 1; prevent_delivery = false;
    permitted = 1; damage_factor = 1;
    const char *names[] = {"Ram", "Target", "Witness"};
    P_char characters[] = {&actor, &victim, &witness};
    for (int i = 0; i < 3; ++i) {
        P_char ch = characters[i]; players[i] = {}; descriptors[i] = {};
        ch->player.name = const_cast<char *>(names[i]);
        ch->player.race = RACE_HUMAN; ch->player.level = 56;
        ch->curr_stats.Str = 180;
        ch->curr_stats.Agi = 100; ch->curr_stats.Luk = 0;
        ch->points.hit = ch->points.max_hit = 1000;
        ch->desc = &descriptors[i]; ch->only.pc = &players[i];
        ch->in_room = 0; SET_POS(ch, POS_STANDING + STAT_NORMAL);
        if (terse & (1 << i)) SET_BIT(ch->specials.act2, PLR2_TERSE);
        ch->next_in_room = i < 2 ? characters[i + 1] : nullptr;
    }
    world[0].people = &actor;
    std::fill(std::begin(dam_factor), std::end(dam_factor), 1.0f);
}
static void apply_ward(P_char target, bool innate, int capacity) {
    if (innate) GET_WARD(target) = capacity;
    else { ward.flags = AFFTYPE_DAM_WARD; ward.modifier = capacity; target->affected = &ward; }
}
static int count(const std::string &text, const std::string &needle) {
    int result = 0;
    for (size_t at = 0; (at = text.find(needle, at)) != std::string::npos; at += needle.size()) ++result;
    return result;
}
static void run(const std::string &name, int expected_zero, int expected_raw,
                const char *arg = "target") {
    do_headbutt(&actor, const_cast<char *>(arg), 0);
    __asan_unpoison_memory_region(&actor, sizeof(actor));
    __asan_unpoison_memory_region(&victim, sizeof(victim));
    assert(raw_calls == expected_raw);
    printf("STATE %s hp=%d,%d ward=%d,%d,%d fighting=%d,%d notch=%d raw=%d rng=",
        name.c_str(), GET_HIT(&actor), GET_HIT(&victim), GET_WARD(&actor), GET_WARD(&victim),
        ward.modifier, actor.specials.fighting != nullptr, victim.specials.fighting != nullptr,
        notches, raw_calls);
    for (int n : random_trace) printf("%d,", n);
    printf(" mechanics="); for (int n : mechanics) printf("%d,", n); puts("");
    int index = 0;
    for (P_char ch : {&actor, &victim, &witness}) {
        int expected = expected_zero;
        if (index == 2 && (!IS_AWAKE(ch) || players[2].ignored || ch->specials.z_cord)) expected = 0;
        feedback_ok &= count(output[ch], "does no damage") == expected;
        if (expected) {
            const char *hit[] = {"Your headbutt does no damage to Target.",
                "Ram's headbutt does no damage to you.", "Ram's headbutt does no damage to Target."};
            const char *failed[] = {"Your headbutt backfires, but does no damage to you.",
                "Ram's headbutt backfires, but does no damage to him.",
                "Ram's headbutt backfires, but does no damage to him."};
            feedback_ok &= output[ch].find(outcome <= 5 ? failed[index] : hit[index]) != std::string::npos;
        }
        printf("TEXT %s %d %s\n", name.c_str(), index++, output[ch].c_str());
    }
    fflush(stdout);
}
int main() {
    for (int terse = 0; terse < 8; ++terse) {
        for (bool innate : {false, true}) {
            std::string tag = std::to_string(terse) + (innate ? "-innate" : "-affect");
            reset(terse); apply_ward(&victim, innate, 1000);
            run(tag + "-full", 1, 0);
            assert(GET_HIT(&victim) == 1000 && (innate ? GET_WARD(&victim) : ward.modifier) == 944);
            if (!terse) assert(output[&actor].find("ward around") != std::string::npos);
            if (terse == 7) assert(output[&actor].find("ward around") == std::string::npos);
            reset(terse); apply_ward(&victim, innate, 8);
            run(tag + "-partial", 0, 1); assert(GET_HIT(&victim) == 940);
            reset(terse); apply_ward(&victim, innate, 56);
            run(tag + "-exact", 1, 0); assert(GET_HIT(&victim) == 1000);
            reset(terse); double_skill = 100; apply_ward(&victim, innate, 1000);
            run(tag + "-double-full", 2, 0);
            reset(terse); double_skill = 100; apply_ward(&victim, innate, 56);
            run(tag + "-double-depleted", 1, 1); assert(GET_HIT(&victim) == 965);
            for (int failure : {1, 4}) {
                reset(terse); outcome = failure; apply_ward(&actor, innate, 1000);
                run(tag + "-backfire-" + std::to_string(failure), 1, 0);
                assert(GET_HIT(&actor) == 1000 && GET_HIT(&victim) == 1000);
            }
        }
        reset(terse); run(std::to_string(terse) + "-ordinary", 0, 1);
        assert(GET_HIT(&victim) == 930 && output[&actor].find("swollen lump") != std::string::npos);
        reset(terse); victim.player.race = RACE_ANIMAL;
        run(std::to_string(terse) + "-nonhuman", 0, 1);
        assert(output[&actor].find("slam your head") != std::string::npos);
        reset(terse); damage_factor = .001; run(std::to_string(terse) + "-integer-zero", 1, 0);
        reset(terse); damage_factor = .02; double_skill = 100;
        run(std::to_string(terse) + "-positive-zero", 1, 1); assert(GET_HIT(&victim) == 999);
        reset(terse); outcome = 4; armor = -500;
        run(std::to_string(terse) + "-backfire-rounded", 1, 0);
        for (int failure : {1, 4}) {
            reset(terse); outcome = failure;
            run(std::to_string(terse) + "-backfire-hit-" + std::to_string(failure), 0, 1);
            assert(GET_HIT(&actor) == (failure == 1 ? 995 : 999));
        }
        for (int effect : {4, 8, 12}) {
            reset(terse); stun_roll = effect; apply_ward(&victim, true, 1000);
            run(std::to_string(terse) + "-effect-" + std::to_string(effect), 1, 0);
            assert(std::find(mechanics.begin(), mechanics.end(), effect == 4 ? 4 : 5) != mechanics.end());
        }
    }
    for (int terminal : {DAM_VICTDEAD, DAM_CHARDEAD, DAM_BOTHDEAD}) {
        for (int branch : {1, 4, 60}) {
            reset(7); terminal_result = terminal; outcome = branch; double_skill = 100;
            run("terminal-" + std::to_string(terminal) + "-" + std::to_string(branch), 0, 1);
        }
        reset(7); terminal_result = terminal; terminal_call = 2; double_skill = 100;
        run("terminal-" + std::to_string(terminal) + "-second", 0, 2);
        assert(short_affects.empty());
    }
    reset(7); prevent_delivery = true; run("raw-prevented", 1, 1);
    assert(GET_HIT(&victim) == 1000);
    reset(7); SET_POS(&actor, STAT_DEAD); run("dead-actor", 0, 0);
    assert(random_trace.empty() && short_affects.empty());
    for (int refusal = 0; refusal < 5; ++refusal) {
        reset(7);
        if (refusal == 1) victim_size = 2;
        if (refusal == 2) victim.player.race = RACE_GHOST;
        if (refusal == 3) { ward.type = SKILL_HEADBUTT; actor.affected = &ward; }
        if (refusal == 4) permitted = 0;
        run("refusal-" + std::to_string(refusal), 0, 0, refusal == 0 ? "self" : "target");
        assert(!output[&actor].empty() && random_trace.empty());
    }
    for (int filter = 0; filter < 3; ++filter) {
        reset(7); apply_ward(&victim, true, 1000);
        if (filter == 0) SET_POS(&witness, POS_PRONE + STAT_SLEEPING);
        if (filter == 1) players[2].ignored = &actor;
        if (filter == 2) witness.specials.z_cord = 1;
        run("observer-filter-" + std::to_string(filter), 1, 0);
        assert(output[&witness].empty());
    }
    assert(feedback_ok && "headbutt zero-damage feedback was missing, duplicated or misattributed");
    puts("Headbutt command, melee and wards: all feedback and mechanics cases passed");
}
'''


def main():
    build = ROOT / "bin/tests/headbutt-feedback"
    build.mkdir(parents=True, exist_ok=True)
    cpp, binary = build / "harness.cpp", build / "harness"
    functions = [("fight.c", "struct affected_type *get_ward_from_char("),
                 ("fight.c", "int check_damage_ward("),
                 ("fight.c", "int melee_damage("),
                 ("actoff.c", "void do_headbutt(")]
    cpp.write_text(PRELUDE + "\n" + "\n".join(extract_function(*f) for f in functions) + DRIVER)
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                    "-fno-pie", "-no-pie", "-Isrc", str(cpp), str(HARNESS_STUBS),
                    "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
