#!/usr/bin/env python3
"""Execute Web Spray dispatch, timed affects, persistence and completed movement.

Production functions and save/restore blocks use the real character/affect layouts.
The scheduler, combat outcomes and room placement are deterministic fixtures.
"""
import os
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function, source

PRELUDE = r'''
#include "core/prototypes.h"
#include "player/character_mechanics.h"
#include "core/utils.h"
#include "core/profile.h"
#include "core/files.h"
#include "core/mm.h"
#include "cmd/interp.h"
#include "magic/spells.h"
#include "world/events.h"
#include "persistence/copyover.h"
#include "world/transport.h"
#include <bsd/string.h>
#include <algorithm>
#include <cassert>
#include <cstring>
#include <vector>

extern const racial_data_type racial_data[];
P_char character_list;
bool do_profile = false;
PROFILE_DEFINE(short_affect_liveness)
void set_short_affected_by(P_char, int, int) {}
char *getString(char **) { std::abort(); }
void str_free(const char *) { std::abort(); }
void affect_to_char_with_messages(P_char, affected_type *, const char *, const char *) { std::abort(); }
char affect_total(P_char, int) { return 0; }
int checked_appendf(char *, size_t, const char *, ...) { return 0; }
Skill skills[MAX_SKILLS];
bool epic_summon(P_char, char *) { return false; }
void do_list_innates(P_char, char *) {}
void do_web_spray(P_char, char *, int);
void event_web_spray(P_char, P_char, P_obj, void *);
void unlink_char_affect(P_char, affected_type *) {}
void unlink_char_obj_affect(P_char, affected_type *) {}
void event_poison(P_char, P_char, P_obj, void *) {}
static int aff_vers, short_size = sizeof(short), int_size = sizeof(int), long_size = sizeof(long);
static mm_ds pool{};
mm_ds *dead_affect_pool = &pool;
static unsigned long long now, sequence;
static std::vector<P_nevent> events;
static int roll = 1, rolls, attacks, lag;
static bool legal = true, freedom = false, evading = false;
static P_char target, tank, decoy, mount_fixture, rider_fixture;
static bool placement_ok = true, carry = true;
static int destination = 1;
static int innate_unlock_level(P_char ch, int id) {
    return id == INNATE_WEB_SPRAY && GET_RACE(ch) == RACE_DRIDER ? 31 : 0;
}
bool SanityCheck(P_char ch, const char *) { return ch != nullptr; }
int fill_word(char *) { return false; }
int get_property(const char *, int fallback) { return fallback; }
int get_innate_property(int, const char *, int fallback) { return fallback; }
int CanDoFightMove(P_char, P_char) { return legal; }
bool check_freedom_of_movement(P_char, bool) { return freedom; }
int GET_CHAR_SKILL_P(P_char, int id) { return id == SKILL_EVADE && evading ? 100 : 0; }
int number(int low, int high) {
    if (low == 1 && high == 100) { ++rolls; return roll; }
    return low;
}
void appear(P_char, bool) {}
void CharWait(P_char, int pulses) { lag += pulses; }
void engage(P_char, P_char victim) { assert(victim == target || victim == tank || victim == decoy); ++attacks; }
P_char get_char_room_vis(P_char, const char *name) {
    if (!strcmp(name, "goblin")) return target;
    if (!strcmp(name, "tank")) return tank;
    if (!strcmp(name, "spray")) return decoy;
    return nullptr;
}
void *_mm_get(mm_ds *, const char *, int) { return new affected_type{}; }
void mm_release(mm_ds *, void *p) { delete static_cast<affected_type *>(p); }
mm_ds *mm_create(const char *, size_t, size_t, unsigned) { return &pool; }
void balance_affects(P_char) {}
void all_affects(P_char, int) {}
void gmcp_char_affects(P_char) {}
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
void wear_off_message(P_char, affected_type *) {}
void event_short_affect(P_char, P_char, P_obj, void *);

nevent_schedule_result add_event(event_func func, int delay, P_char ch, P_char victim,
                                 P_obj obj, int, const void *data, int size) {
    auto *ev = new nevent_data{};
    ev->func = func; ev->ch = ch; ev->victim = victim; ev->obj = obj;
    ev->due_tick = now + delay; ev->sequence = ++sequence;
    if (size) { ev->data = new unsigned char[size]; memcpy(ev->data, data, size); }
    ev->next_char_nev = ch->nevents; ch->nevents = ev;
    events.push_back(ev);
    return {nevent_schedule_status::scheduled, {ev, ev->sequence}};
}
nevent_handle nevent_handle_from_event(P_nevent ev) { return {ev, ev->sequence}; }
static void unlink_event(P_nevent ev) {
    auto **link = &ev->ch->nevents;
    while (*link && *link != ev) link = &(*link)->next_char_nev;
    if (*link) *link = ev->next_char_nev;
    events.erase(std::find(events.begin(), events.end(), ev));
}
nevent_cancel_result nevent_cancel(nevent_handle handle) {
    unlink_event(handle.event);
    delete[] static_cast<unsigned char *>(handle.event->data);
    delete handle.event;
    return nevent_cancel_result::canceled;
}
void disarm_char_nevents(P_char ch, event_func_type func) {
    for (auto *ev = ch->nevents; ev;) {
        auto *next = ev->next_char_nev;
        if (!func || ev->func == func) nevent_cancel(nevent_handle_from_event(ev));
        ev = next;
    }
}
int ne_event_time(P_nevent ev) { return ev->due_tick - now; }
static int pending(P_char ch, event_func_type func) {
    return std::count_if(events.begin(), events.end(), [=](auto *ev) { return ev->ch == ch && ev->func == func; });
}
static void advance(int pulses) {
    auto until = now + pulses;
    while (!events.empty()) {
        auto *ev = *std::min_element(events.begin(), events.end(), [](auto *a, auto *b) {
            return a->due_tick < b->due_tick;
        });
        if (ev->due_tick > until) break;
        now = ev->due_tick;
        unlink_event(ev);
        ev->func(ev->ch, ev->victim, ev->obj, ev->data);
        delete[] static_cast<unsigned char *>(ev->data);
        delete ev;
    }
    now = until;
}
P_char get_linked_char(P_char ch, ush_int) { return ch == rider_fixture ? mount_fixture : nullptr; }
P_char get_linking_char(P_char ch, ush_int) { return ch == mount_fixture ? rider_fixture : nullptr; }
void char_from_room(P_char ch) { ch->in_room = NOWHERE; }
bool char_to_room(P_char ch, int room, int) {
    if (!placement_ok) return false;
    ch->in_room = room;
    if (carry) {
        if (auto *other = get_linked_char(ch, LNK_RIDING)) other->in_room = room;
        if (auto *other = get_linking_char(ch, LNK_RIDING)) other->in_room = room;
    }
    return true;
}
room_data rooms[2]{};
P_room world = rooms;
index_data indexes[1]{};
P_index mob_index = indexes, obj_index = indexes;
void transport_capture(P_char, transport_snapshot *) {}
bool generated_npc_capture(P_char, std::string *) { return true; }
bool generated_npc_extension_encode(int, const std::string &, std::string *) { std::abort(); }

void telemetry_gameplay_context_changed(P_char) {}
void telemetry_gameplay_movement(P_char) {}
'''

DRIVER = r'''
static void clear(P_char ch) {
    while (ch->affected) affect_remove(ch, ch->affected);
    assert(!ch->nevents);
}
static void spray(P_char caster, const char *args = "web_spray goblin") {
    char command[MAX_INPUT_LENGTH]; strcpy(command, args);
    do_innate(caster, command, CMD_INNATE);
}
static void web(P_char ch, int moves = 7) {
    affected_type af{};
    af.type = TAG_WEB_SPRAY; af.modifier = moves;
    af.flags = AFFTYPE_SHORT | AFFTYPE_NODISPEL; af.duration = 30 * WAIT_SEC;
    affect_to_char(ch, &af);
}
int main() {
    char_data first{}, second{}, victim{}, opponent{}, named_spray{};
    target = &victim; tank = &opponent; decoy = &named_spray;
    std::vector<P_char> chars{&first, &second, target, tank, decoy};
    character_list = &first;
    for (size_t i = 0; i < chars.size(); ++i) {
        auto *ch = chars[i]; ch->next = i + 1 < chars.size() ? chars[i+1] : nullptr;
        SET_POS(ch, STAT_NORMAL + POS_STANDING); GET_RACE(ch) = RACE_DRIDER;
        ch->player.level = 31; GET_VITALITY(ch) = 100; ch->curr_stats.Agi = 100;
    }
    second.player.level = 56;
    // Real parser + dispatcher must retain an explicit target during combat,
    // even with a visible character named 'spray'. Also check level eligibility.
    first.specials.fighting = tank;
    first.player.level = 30; spray(&first); assert(!target->affected);
    first.player.level = 31; spray(&first);
    assert(affected_by_spell(target, TAG_WEB_SPRAY));
    assert(!tank->affected && !decoy->affected);
    assert(first.affected->duration == 300 * WAIT_SEC && lag == PULSE_VIOLENCE);
    assert(target->affected->modifier == 3 && pending(target, event_web_spray) == 1);
    const auto attacks_before = attacks; spray(&first); assert(attacks == attacks_before);

    // Two casters at t=0 and t=29: expiry must move to t=59, and only the
    // second caster's seven-move drain remains (including after restoration).
    advance(29 * WAIT_SEC); spray(&second);
    assert(target->affected->modifier == 7 && pending(target, event_web_spray) == 1);
    advance(WAIT_SEC); assert(affected_by_spell(target, TAG_WEB_SPRAY));
    int moves_before = GET_VITALITY(target);
    advance(PULSE_VIOLENCE); assert(GET_VITALITY(target) == std::max(0, moves_before - 7));
    advance(29 * WAIT_SEC - PULSE_VIOLENCE);
    assert(!target->affected && !pending(target, event_web_spray));
    for (auto *ch : chars) clear(ch);

    // Save remaining time at ten seconds using the production PC codec or
    // NPC copyover fields; both restores must restart one drain, not 30 seconds.
    for (int restore_path : {0, 1, 2}) {
        const bool npc = restore_path != 0;
        target->specials.act = npc ? ACT_ISNPC : 0;
        npc_only_data npc_data{}; target->only.npc = npc ? &npc_data : nullptr;
        GET_VITALITY(target) = 100; web(target); advance(10 * WAIT_SEC);
        char saved[4096]{}; int bytes = 0; copyover_affect mob_saved{};
        if (restore_path == 1) {
            assert(copyover_write_mob_to_buffer(target, saved, sizeof(saved)) > 0);
            memcpy(&mob_saved, saved + sizeof(copyover_mob), sizeof(mob_saved));
        } else if (restore_path == 2) {
            FILE *fp = tmpfile(); assert(fp);
            assert(write_mob_affects(fp, target)); rewind(fp);
            assert(fread(&mob_saved, sizeof(mob_saved), 1, fp) == 1); fclose(fp);
        } else {
            updateShortAffects(target);
            bytes = writeAffects(saved, target->affected);
        }
        clear(target);
        if (restore_path == 2) restore_copyover_affect(target, mob_saved);
        else if (npc) restore_npc_affect(target, mob_saved);
        else assert(restoreAffects(saved, target) == bytes);
        assert(target->affected->duration == 20 * WAIT_SEC);
        assert(target->affected->modifier == 7 && pending(target, event_web_spray) == 1);
        moves_before = GET_VITALITY(target);
        advance(PULSE_VIOLENCE); assert(GET_VITALITY(target) == moves_before - 7);
        advance(20 * WAIT_SEC - PULSE_VIOLENCE - 1); assert(target->affected);
        advance(1); assert(!target->affected && !pending(target, event_web_spray));
    }
    target->specials.act = 0; target->only.npc = nullptr;

    // Validation precedes cooldown. Miss, freedom and evade spend it and engage.
    first.specials.fighting = nullptr;
    spray(&first, "web_spray absent"); assert(!first.affected);
    legal = false; spray(&first); assert(!first.affected); legal = true;
    for (int defence = 0; defence < 3; ++defence) {
        freedom = defence == 0; evading = defence == 1; roll = defence == 2 ? 100 : 1;
        auto before = attacks; spray(&first);
        assert(first.affected && !target->affected && attacks == before + 1);
        clear(&first);
    }
    freedom = evading = false; roll = 1;

    // A room move rolls once for each participant, in either direction of
    // control. The visibility pass is outside the production completion block.
    mount_fixture = target; rider_fixture = tank;
    for (auto *actor : {target, tank}) {
        target->in_room = tank->in_room = 0; web(target); web(tank);
        rolls = 0; roll = 11;
        assert(completed_move(actor)); assert(rolls == 2);
        assert(target->affected && tank->affected);
        destination = 0; roll = 10;
        assert(completed_move(actor)); assert(rolls == 4);
        assert(!target->affected && !tank->affected);
        assert(!pending(target, event_web_spray) && !pending(tank, event_web_spray));
        destination = 1;
    }
    // Failed placement, a self-loop, or an uncarried/dead partner gets no extra roll.
    for (int blocked = 0; blocked < 4; ++blocked) {
        target->in_room = tank->in_room = 0; web(target); web(tank); rolls = 0; roll = 11;
        placement_ok = blocked != 0; destination = blocked == 1 ? 0 : 1; carry = blocked != 2;
        if (blocked == 3) SET_POS(target, STAT_DEAD);
        completed_move(tank);
        assert(rolls == (blocked < 2 ? 0 : 1));
        SET_POS(target, STAT_NORMAL + POS_STANDING);
        clear(target); clear(tank);
    }
    mount_fixture = rider_fixture = nullptr;
    GET_VITALITY(target) = 2; web(target); advance(PULSE_VIOLENCE); assert(GET_VITALITY(target) == 0);
    clear(target); assert(events.empty());
    puts("Web Spray: targeting, cooldown/defences, refresh, PC/NPC restoration, mounted escape and cleanup passed.");
}
'''

innates = source("innates.c").read_text()
# Preserve every registered name and index, linking only the handler under test.
table = re.search(r"const struct innate_data innates_data\[LAST_INNATE \+ 1\] = .*?\n};", innates, re.S).group()
table = re.sub(r'(\{ "[^"]+", )(\w+)( \})',
               lambda m: m[1] + (m[2] if m[2] == 'do_web_spray' else 'NULL') + m[3], table)
assert 'ADD_RACIAL_INNATE(INNATE_WEB_SPRAY, RACE_DRIDER, 31);' in innates

production = '\n'.join(extract_function(file, signature) for file, signature in [
    ('utility.c', 'int BOUNDED('),
    ('interp.c', 'void argument_interpreter('), ('interp.c', 'bool is_abbrev('),
    ('innates.c', 'bool has_innate('), ('innates.c', 'bool can_use_innate('),
    ('innates.c', 'P_char parse_victim('), ('innates.c', 'bool check_innate_time('),
    ('affects.c', 'struct affected_type *get_spell_from_char('),
    ('affects.c', 'bool affected_by_spell('), ('affects.c', 'void event_short_affect('),
    ('affects.c', 'struct affected_type *affect_to_char('),
    ('affects.c', 'void affect_remove('), ('affects.c', 'void affect_from_char('),
    ('innates.c', 'void event_web_spray('), ('innates.c', 'void do_web_spray(P_char ch,'),
    ('innates.c', 'void web_spray_move_check('),
    ('files.c', 'ush_int getShort('), ('files.c', 'uint getInt('), ('files.c', 'long getLong('),
    ('files.c', 'void updateShortAffects('), ('files.c', 'int writeAffects('),
    ('files.c', 'int restoreAffects('),
])
production += '\n' + table + '\n' + extract_function('innates.c', 'void do_innate(P_char ch,')
copyover = source('copyover.c').read_text()
restore = re.search(r'\t\tstruct affected_type af;\n\t\tmemset\(&af, 0, sizeof\(af\)\);\n\t\taf.type = aff_entry.type;.*?affect_to_char\(mob, &af\);', copyover, re.S).group()
production += '\n' + extract_function('copyover.c', 'static int write_mob_affects(')
production += '\n' + extract_function('copyover.c', 'int copyover_write_mob_to_buffer(')
production += '\nvoid restore_npc_affect(P_char mob, copyover_affect aff_entry) {\n' + restore + '\n}\n'
copyover_restore = re.search(r'\t\t\tstruct affected_type af;\n\t\t\tmemset\(&af, 0, sizeof\(af\)\);\n\t\t\taf.type = aff_entries\[a\].type;.*?affect_to_char\(mob, &af\);', copyover, re.S).group()
production += '\nvoid restore_copyover_affect(P_char mob, copyover_affect saved) { copyover_affect aff_entries[] = {saved}; int a = 0;\n' + copyover_restore + '\n}\n'
move = extract_function('actmove.c', 'int do_simple_move_skipping_procs(')
start = move.rfind('\tchar_from_room(ch);', 0, move.index('\ttelemetry_gameplay_context_changed(ch);'))
if '\t// Snapshot the linked participants' in move:
    start = move.index('\t// Snapshot the linked participants')
end = move.index('\n\tchar_light(ch);', start)
production += '\nint completed_move(P_char ch) { P_char mount, rider; int was_in = ch->in_room, new_room = destination, exitnumb = 0;\n' + move[start:end] + '\nreturn true; }\n'

build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='web-spray-', dir=build) as directory:
    cpp, binary = Path(directory) / 'harness.cpp', Path(directory) / 'harness'
    cpp.write_text(PRELUDE + production + DRIVER)
    subprocess.run(['g++', '-std=c++20', '-g', '-ffunction-sections', '-fdata-sections',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                    '-I' + str(ROOT / 'src'), str(cpp), str(ROOT / 'src/core/constant.c'),
                    str(HARNESS_STUBS), '-Wl,--gc-sections', '-lbsd',
                    '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, env={**os.environ,
        'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
        'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'})
