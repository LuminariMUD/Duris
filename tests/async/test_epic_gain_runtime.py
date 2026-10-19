#!/usr/bin/env python3
"""Run real epic award/quaff code and score's epic section with fault-controlled adapters.

Restores the deleted quaff regression, now linking the actual synchronous epic
transaction and exercising awards at every level rather than a removed gate.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, rel

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "combat/damage.h"
#include "world/db.h"
#include "world/epic.h"
#include "world/epic_bonus.h"
#include "world/difficulty.h"
#include "world/vnum.obj.h"
#include "world/epic_transaction.h"
#include "world/achievements.h"
#include "guild/artifact_guild_transaction.h"
#include "economy/nexus_stones.h"
#include "persistence/persistence_checkpoint.h"
#include "magic/spells.h"
#include "net/comm.h"
#include <cassert>
#include <cerrno>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <limits>
#include <string>
#include <sys/random.h>

P_index obj_index;
P_room world;
zone_data *zone_table;
Skill skills[MAX_SKILLS]{};
int errand_notch = 500;
static int consumed, waits, unequips, potion_effects, artifacts, ledger_rows, tasks;
static bool fail_id, potion_timer;
static critical_submit_result admission;
static std::string output;
static affected_type total, task;
static obj_data nexus;

extern "C" ssize_t __real_getrandom(void *, size_t, unsigned int);
extern "C" ssize_t __wrap_getrandom(void *buf, size_t size, unsigned int flags) {
    if (fail_id) { errno = EIO; return -1; }
    return __real_getrandom(buf, size, flags);
}
float get_property(const char *, double fallback) { return fallback; }
int get_property(const char *, int fallback) { return fallback; }
void send_to_char(const char *text, P_char) { output += text; }
void send_to_char_f(P_char, const char *format, ...) {
    char buffer[512];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof buffer, format, args);
    va_end(args);
    output += buffer;
}
void act(const char *text, int, P_char, P_obj, void *, int) { output += text; }
char *one_argument(const char *text, char *out) {
    std::strcpy(out, text);
    return const_cast<char *>(text + std::strlen(text));
}
P_obj get_obj_in_list_vis(P_char, const char *, P_obj list, bool) { return list; }
bool isname(const char *a, const char *b) { return !strcmp(a, b); }
int number(int, int high) { return high; }
void CharWait(P_char, int) { ++waits; }
P_obj unequip_char(P_char ch, int slot, bool) {
    ++unequips;
    P_obj result = ch->equipment[slot];
    ch->equipment[slot] = nullptr;
    return result;
}
void extract_obj(P_obj, int) { ++consumed; }
int spell_damage(P_char, P_char, double, int, uint, damage_messages *, int *) { return 0; }
affected_type *affect_to_char(P_char, affected_type *) { ++potion_effects; return nullptr; }
int char_in_list(const P_char) { return 1; }
bool affected_by_spell(P_char, int type) { return type == TAG_POTION_TIMER && potion_timer; }
void mark_player_dirty_components(int, player_component_mask_t) {}
critical_submit_result critical_command_coordinator_submit(critical_command command) {
    epic_command_payload payload{};
    assert(epic_command_decode_payload(command, &payload));
    ++ledger_rows;
    return admission;
}
bool artifact_guild_transaction_submit(P_char, const critical_operation_id &, int, int) {
    ++artifacts;
    return true;
}
void epic_bonus_record_gain(P_char, int, int) {}
void epiclog(int, const char *, ...) {}
void epic_free_level(P_char) {}
int check_nexus_bonus(P_char, int amount, int) { return amount; }
float get_epic_bonus(P_char, int) { return 0; }
double difficulty_multiplier(difficulty_dial) { return 1; }
bool gameplay_read_state_add_completed_zone(gameplay_read_state *, int32_t) { return true; }
affected_type *get_spell_from_char(P_char ch, int type, void *, int) {
    for (auto *af = ch->affected; af; af = af->next)
        if (af->type == type) return af;
    return nullptr;
}
affected_type *apply_achievement(P_char ch, int type) {
    total = {};
    total.type = type;
    total.next = ch->affected;
    ch->affected = &total;
    return &total;
}
void epic_choose_new_epic_task(P_char ch) {
    ++tasks;
    task = {};
    task.type = TAG_EPIC_ERRAND;
    task.modifier = SPILL_BLOOD;
    task.next = ch->affected;
    ch->affected = &task;
}
int real_zone0(const int) { return 0; }
P_obj get_nexus_stone(int) { return &nexus; }
'''

DRIVER = r'''
static void check_quaff(int level, bool held, bool epic, int failure, bool fighting = false) {
    char_data ch{};
    pc_only_data pc{};
    obj_data bottle{};
    index_data index[1]{};
    room_data room[1]{};
    affected_type timer{};
    obj_index = index;
    world = room;
    index[0].virtual_number = epic ? VOBJ_EPIC_BOTTLE_EPICS : 1;
    ch.only.pc = &pc;
    pc.pid = failure == 2 ? 0 : 42;
    pc.epics = failure == 3 ? std::numeric_limits<long>::max() : 25;
    const auto before = pc.epics;
    ch.specials.position = STAT_NORMAL;
    if (fighting) ch.specials.fighting = &ch;
    ch.player.level = level;
    bottle.type = ITEM_POTION;
    bottle.R_num = 0;
    bottle.name = const_cast<char *>("potion");
    if (held) ch.equipment[HOLD] = &bottle;
    else ch.carrying = &bottle;
    fail_id = failure == 1;
    errand_notch = failure == 4 ? 0 : 500;
    potion_timer = failure == 6;
    timer.type = TAG_POTION_TIMER;
    timer.duration = 3;
    if (potion_timer) ch.affected = &timer;
    if (failure == 7) ch.specials.act |= ACT_ISNPC;
    admission = failure == 5 ? critical_submit_result::unavailable : critical_submit_result::accepted;
    consumed = waits = unequips = potion_effects = artifacts = ledger_rows = tasks = 0;
    output.clear();
    char argument[] = "potion";
    do_quaff(&ch, argument, 0);
    const bool allowed = failure == 0 || failure == 5;
    assert(consumed == (allowed ? 1 : 0));
    assert(pc.epics == (allowed && epic ? before + 75 : before));
    assert(waits == (allowed ? 1 : 0));
    assert(unequips == (allowed && held ? 1 : 0));
    assert(potion_effects == (allowed && !epic ? 1 : 0));
    assert(artifacts == (allowed && epic ? 1 : 0));
    assert(ledger_rows == (allowed && epic ? 1 : 0));
    assert(tasks == 0);
    if (!allowed) {
        assert(output.find("suddenly feel.. epic") == std::string::npos);
        assert(output.find("quaffs") == std::string::npos);
        assert(output.find("vial disappears") == std::string::npos);
        assert(output.find("You have gained") == std::string::npos);
        assert(held ? ch.equipment[HOLD] == &bottle : ch.carrying == &bottle);
    } else if (epic) {
        assert(output.find("You have gained 75 epic points") != std::string::npos);
        assert(output.find("suddenly feel.. epic") != std::string::npos);
        assert(output.find("You have gained") == output.rfind("You have gained"));
    }
}
static void check_awards_and_score(int level) {
    char_data ch{};
    pc_only_data pc{};
    ch.only.pc = &pc;
    ch.specials.position = STAT_NORMAL;
    ch.player.level = level;
    pc.pid = 42;
    fail_id = false;
    errand_notch = 500;
    admission = critical_submit_result::accepted;
    tasks = 0;
    for (int kill = 0; kill < 5; ++kill) {
        const int award = epic_calculate_pvp_award(&ch, 100);
        assert(award == 100);
        // Combat's committed transaction has already credited the balance.
        pc.epics += award;
        epic_publish_pvp_award(&ch, award);
    }
    assert(tasks == 1 && has_epic_task(&ch));
    // Score reads the character's saved affects, not the one-off award message.
    char_data reconnected = ch;
    zone_data zones[1]{};
    zone_table = zones;
    zones[0].name = const_cast<char *>("Test Runestone");
    nexus.short_description = const_cast<char *>("Test Nexus");
    for (auto [modifier, expected] : {
            std::pair{SPILL_BLOOD, "spill enemy blood"},
            std::pair{1, "Test Runestone"},
            std::pair{SPILL_BLOOD + 1, "Test Nexus"}}) {
        task.modifier = modifier;
        output.clear();
        render_epics(&reconnected);
        assert(output.find("500(500)") != std::string::npos);
        assert(output.find(expected) != std::string::npos);
    }
    // A real ordinary award still receives the task penalty, at every level.
    assert(gain_epic(&ch, EPIC_ZONE, 1, 100));
    assert(pc.epics == 525 && total.modifier == 525 && tasks == 1);
    assert(output.find("not able to progress at usual pace") != std::string::npos);
    ch.affected = &total;
    assert(!has_epic_task(&ch));
    assert(gain_epic(&ch, EPIC_ZONE, 1, 100));
    assert(pc.epics == 625 && total.modifier == 625);
    output.clear();
    render_epics(&ch);
    assert(output.find("625(625)") != std::string::npos);
    assert(output.find("Current task") == std::string::npos);
    ch.affected = nullptr;
    output.clear();
    render_epics(&ch);
    assert(output.find("625(0)") != std::string::npos);
}
int main() {
    for (int level : {1, 19, 20, 29, 30, 49, 50, 56}) {
        for (bool held : {false, true}) {
            for (int failure = 0; failure <= 7; ++failure)
                check_quaff(level, held, true, failure);
            check_quaff(level, held, true, 0, true);
            check_quaff(level, held, false, 0);
        }
        check_awards_and_score(level);
    }
    std::puts("Epic awards: quaff success/failure, held/inventory, low-level awards and score passed.");
}
'''

context = extract_function('epic.c', 'struct epic_award_context') + ';\n'
functions = '\n'.join(extract_function('epic.c', signature) for signature in (
    'struct affected_type *get_epic_task(', 'bool has_epic_task(',
    'epic_reason_type epic_award_reason(', 'critical_source_site epic_award_source(',
    'const char *epic_award_name(', 'void epic_award_committed(',
    'static bool prepare_epic_award(', 'bool gain_epic(',
    'int epic_calculate_pvp_award(', 'void epic_publish_pvp_award(',
))
score = extract_function('actinf.c', 'void do_score(')
start = score.index('#ifdef STANCES_ALLOWED')
start = score.index('#endif', start) + len('#endif')
end = score.index('\n\tEpicBonusData ebdata;', start)
render = 'void render_epics(P_char ch) { char buf[MAX_STRING_LENGTH]; int i; P_obj nexus;\n' + score[start:end] + '\n}\n'
code = PRELUDE + context + functions + extract_function('actoth.c', 'void do_quaff(') + render + DRIVER
build_root = ROOT / 'bin/tests'
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='epic-gain-', dir=build_root) as directory:
    cpp = Path(directory) / 'epic_gain.cpp'
    binary = Path(directory) / 'epic_gain'
    cpp.write_text(code)
    subprocess.run([
        'g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-g',
        '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-no-pie',
        '-ffunction-sections', '-fdata-sections', '-Isrc', str(cpp),
        rel('epic_transaction.c'), rel('epic_command.c'), rel('critical_command.c'),
        str(HARNESS_STUBS), '-Wl,--gc-sections', '-Wl,--wrap=getrandom', '-lcrypto',
        '-o', str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)


def test_epic_boon_publication() -> None:
    harness = (ROOT / 'tests/async/epic_boon_feedback.cpp').read_text()
    epic = (ROOT / 'src/world/epic.c').read_text()
    context = epic[epic.index('struct epic_award_context'):epic.index('struct epic_level_context')]
    functions = '\n'.join(extract_function('epic.c', signature) for signature in (
        'epic_reason_type epic_award_reason(', 'critical_source_site epic_award_source(',
        'const char *epic_award_name(', 'void epic_award_committed(',
        'static bool prepare_epic_award(', 'bool gain_epic(P_char ch, int type, int data, int amount)'))
    harness = harness.replace('// EPIC_AWARD_FUNCTIONS',
                              extract_function('utility.c', 'int BOUNDED(int a, int b, int c)') +
                              '\n' + context + functions)
    harness = harness.replace('// BOON_PUBLICATION', extract_function('boon.c', 'void boon_publish_transaction_result('))
    out = ROOT / 'bin/tests'; out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='epic-boon-feedback-', dir=out) as directory:
        cpp, binary = Path(directory) / 'fixture.cpp', Path(directory) / 'fixture'
        cpp.write_text(harness)
        subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                        '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                        '-g', '-no-pie', '-Isrc', '-I/usr/include/mysql', str(cpp),
                        'src/world/epic_transaction.c', 'src/world/epic_command.c',
                        'src/economy/boon_reward_transaction.c', 'src/economy/boon_reward_command.c',
                        'src/economy/boon_shop_command.c', 'src/economy/currency_command.c',
                        'src/combat/combat_outcome_command.c',
                        'src/flatfile/flatfile_boon_repository.c',
                        'src/flatfile/flatfile_player_domain_repository.c',
                        'src/flatfile/flatfile_authority_transaction.c', 'src/flatfile/flatfile_store.c',
                        'src/persistence/critical_command.c', str(HARNESS_STUBS),
                        '-Wl,--gc-sections', '-Wl,--wrap=getrandom', '-lcrypto', '-o', str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary), str(Path(directory) / 'state')], check=True, timeout=30)


test_epic_boon_publication()
