#!/usr/bin/env python3
"""Exercise Tupor display and recovery through the production command and callbacks.

Compile extracted production bodies with real game types; the scheduler and UI
are controlled doubles. No server or database is started.
"""
from pathlib import Path
import os
import subprocess
import tempfile
from _paths import HARNESS_STUBS

ROOT = Path(__file__).resolve().parents[2]
MEM = (ROOT / 'src/classes/memorize.c').read_text()


def extract(text, signature):
    start = text.index(signature)
    while ';' in text[start:text.index('{', start)]:
        start = text.index(signature, start + len(signature))
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]



PRELUDE = r"""
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "net/gmcp.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "magic/spells.h"
#include <cassert>
#include <string>
#include <vector>
#include <cstdarg>
#include <cstdio>
void event_memorize(P_char, P_char, P_obj, void *);
char Gbuf1[MAX_STRING_LENGTH], Gbuf2[MAX_STRING_LENGTH];
static int now, interval, rating, rolls, notches;
static bool notch;
static nevent_data pending_event;
static int payload;
static std::string output;
static std::vector<int> arrivals;
int GET_CLASS(P_char ch, uint cls) { return ch->player.m_class & cls; }
int GET_PRIME_CLASS(P_char ch, uint cls) { return GET_CLASS(ch, cls); }
int GET_SECONDARY_CLASS(P_char, uint) { return 0; }
int GET_CHAR_SKILL_P(P_char, int) { return rating; }
int is_wearing_necroplasm(P_char) { return 0; }
bool is_dragoon_mounted(P_char) { return false; }
int get_power_level(P_char) { return 0; }
int get_max_circle(P_char) { return 2; }
int max_spells_in_circle(P_char, int, int) { return 3; }
int max_spells_in_circle(P_char, int) { return 3; }
int get_spell_circle(P_char, int spell) { return spell; }
int get_circle_memtime(P_char ch, int circle, bool stat_only = false, bool roll_nature_bonus = true) {
    int time = interval + (circle - 1) * 8;
    if (!IS_AWAKE(ch) && GET_POS(ch) == POS_PRONE) time = time * 3 / 4;
    if (stat_only) { assert(!roll_nature_bonus); return time; }
    // Controlled interval provider: mirror the existing Tupor proc, not its balance formula.
    if (IS_AFFECTED(ch, AFF_MEDITATE)) {
        ++notches;
        if (notch || (++rolls, rating > 50)) time /= 2;
    }
    return time;
}
int number(int, int) { ++rolls; return 50; }
bool notch_skill(P_char, int, float) { ++notches; return notch; }
int get_property(const char *, int fallback) { return fallback; }
void send_to_char(const char *message, P_char) { output += message; }
int checked_snprintf_at(const char *, int, char *buffer, size_t size, const char *fmt, ...) {
    va_list args; va_start(args, fmt); int result = vsnprintf(buffer, size, fmt, args); va_end(args); return result;
}
P_nevent get_scheduled(P_char ch, event_func_type) { return ch->nevents; }
int ne_event_time(P_nevent event) { return event->due_tick - now; }

void disarm_char_nevents(P_char ch, event_func_type) { ch->nevents = nullptr; }
void stop_meditation(P_char ch) { REMOVE_BIT(ch->specials.affected_by, AFF_MEDITATE); }
void balance_align(P_char) {}
void CharWait(P_char, int) {}
void handle_memorize(P_char) { assert(false); }
nevent_schedule_result add_event(event_func, int delay, P_char ch, P_char, P_obj,
                                  int, const void *data, int size) {
    pending_event.due_tick = now + std::max(1, delay);
    if (data) { assert(size == sizeof(int)); payload = *static_cast<const int *>(data); }
    pending_event.data = data ? &payload : nullptr;
    ch->nevents = &pending_event;
    return {nevent_schedule_status::scheduled, {}};
}
"""
DRIVER = r"""
static void display(P_char ch, int64_t expected, bool active) {
    int old_rolls = rolls, old_notches = notches;
    P_nevent old_event = ch->nevents;
    auto due = old_event ? old_event->due_tick : 0;
    output.clear();
    do_assimilate(ch, const_cast<char *>(""), CMD_TUPOR);
    const std::string text = std::string("Estimated total recovery ") +
        (active ? "remaining: " : "if started now: ") +
        std::to_string((expected + WAIT_SEC - 1) / WAIT_SEC) + " seconds.";
    assert(output.find(text) != std::string::npos);
    assert(output.find(" seconds)\n") != std::string::npos);
    assert(output.find("Higher circles") == std::string::npos);
    assert(output.find("Meditation may") == std::string::npos);
    assert(output.find("already recovering") == std::string::npos);
    if (active) {
        assert(rolls == old_rolls && notches == old_notches);
        assert(ch->nevents == old_event && ch->nevents->due_tick == due);
    }
}
int main() {
    for (int t : {40, 41}) for (int slots : {1, 2, 3})
    for (bool sleeping : {false, true}) for (bool multiple : {false, true})
    for (int meditate : {0, 1, 2, 3}) for (bool harpy : {false, true}) {
        char_data ch{};
        SET_POS(&ch, sleeping ? STAT_SLEEPING | POS_PRONE : STAT_RESTING | POS_SITTING);
        ch.player.m_class = harpy ? CLASS_SORCERER : CLASS_ETHERMANCER;
        ch.player.race = harpy ? RACE_HARPY : RACE_HUMAN;
        ch.specials.undead_spell_slots[1] = 3 - slots;
        ch.specials.undead_spell_slots[2] = multiple ? 2 : 3;
        if (meditate) SET_BIT(ch.specials.affected_by, AFF_MEDITATE);
        rating = meditate == 1 ? 40 : 100;
        notch = meditate == 3;
        now = rolls = notches = 0; interval = t; arrivals.clear();
        int first = multiple ? 2 : 1;
        int base = get_circle_memtime(&ch, 1, true, false);
        int high = get_circle_memtime(&ch, first, true, false);
        int64_t baseline = high / 2 + (slots - (multiple ? 0 : 1)) * (base + base / 2);
        display(&ch, baseline, false);
        bool active;
        int expected_now = (meditate >= 2 ? high / 2 : high) / 2;
        while (ch.nevents) {
            assert(ch.nevents->due_tick == static_cast<unsigned>(expected_now));
            // Query halfway through both the initial and second-stage events.
            now += (ch.nevents->due_tick - now) / 2;
            int64_t estimate = spell_preparation_estimate(&ch, active);
            assert(active);
            if (meditate < 2) assert(estimate == baseline - now);
            display(&ch, estimate, true);
            now = ch.nevents->due_tick;
            bool has_data = ch.nevents->data != nullptr;
            int data = has_data ? payload : 0;
            int before = ch.specials.undead_spell_slots[1] + ch.specials.undead_spell_slots[2];
            ch.nevents = nullptr;
            event_memorize(&ch, nullptr, nullptr, has_data ? &data : nullptr);
            int after = ch.specials.undead_spell_slots[1] + ch.specials.undead_spell_slots[2];
            if (after != before) arrivals.push_back(now);
            if (ch.nevents) {
                if (has_data && meditate < 2) expected_now += data / 2;
                else expected_now += meditate >= 2 ? base / 2 : base;
            }
        }
        assert(arrivals.size() == static_cast<size_t>(slots + multiple));
        if (!meditate || meditate == 1) assert(now == baseline);
        else assert(now == high / 4 + (slots - (multiple ? 0 : 1)) * (base / 2));
        assert(spell_preparation_estimate(&ch, active) == 0 && !active);
        output.clear(); do_assimilate(&ch, const_cast<char *>(""), CMD_TUPOR);
        assert(output.find("Estimated total") == std::string::npos);
    }
    // Inspecting while standing neither begins recovery nor rolls Meditation.
    char_data paused{};
    SET_POS(&paused, STAT_NORMAL | POS_STANDING);
    paused.player.m_class = CLASS_ETHERMANCER;
    paused.specials.undead_spell_slots[1] = 0;
    paused.specials.undead_spell_slots[2] = 3;
    interval = 40; rolls = notches = 0;
    display(&paused, 140, false);
    assert(!paused.nevents && !rolls && !notches);
    output.clear();
    do_assimilate(&paused, const_cast<char *>("nl"), CMD_TUPOR);
    assert(output.empty() && !paused.nevents && !rolls && !notches);
    // Each short circle keeps its own row, showing that circle's share of the total.
    char_data rows{};
    SET_POS(&rows, STAT_NORMAL | POS_STANDING);
    rows.player.m_class = CLASS_ETHERMANCER;
    rows.specials.undead_spell_slots[1] = 1;
    rows.specials.undead_spell_slots[2] = 2;
    display(&rows, 144, false);
    assert(output.find(" 1st circle:  1 of  3   (  30 seconds)\n") != std::string::npos);
    assert(output.find(" 2nd circle:  2 of  3   (   6 seconds)\n") != std::string::npos);
}
"""
source = PRELUDE + '\n'.join([
    extract(MEM, 'bool can_assimilate('),
    extract(MEM, 'static bool schedule_memorize('),
    extract(MEM, 'void handle_undead_mem('),
    extract(MEM, 'static bool uses_slot_recovery('),
    extract(MEM, 'static int64_t spell_preparation_by_circle('),
    extract(MEM, 'int64_t spell_preparation_estimate('),
    extract(MEM, 'void event_memorize('),
    extract(MEM, 'void do_assimilate('),
]) + DRIVER
with tempfile.TemporaryDirectory(prefix='tupor-display-') as directory:
    cpp = Path(directory) / 'harness.cpp'
    binary = Path(directory) / 'harness'
    cpp.write_text(source)
    subprocess.run(['g++', '-std=c++20', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    '-I' + str(ROOT / 'src'), str(cpp), str(HARNESS_STUBS), '-o', str(binary)], check=True)
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1')
    subprocess.run([str(binary)], env=env, check=True)
print('Tupor command estimates and unchanged recovery callbacks passed under ASan/UBSan')
