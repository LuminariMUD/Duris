#!/usr/bin/env python3
"""Execute production poisons, cures, affects and the real event scheduler.

Unrelated stat/damage calculations and character links are narrow fixtures.
Timers, cancellation, affect allocation/removal and deferred bit publication
run in production code under ASan/UBSan.
"""

from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


PRELUDE = r'''
#include "world/new_events.c"
#include "net/comm.h"
#include "magic/spells.h"
#include "combat/damage.h"
#include <cassert>
#include <cstdio>
#include <cstring>

P_char character_list;
P_obj object_list;
P_index mob_index, obj_index;
static room_data rooms[2]{};
P_room world = rooms;
extern const int top_of_world = 1;
int pulse;
bool after_events_call;
static mm_ds event_pool{}, affect_pool{};
mm_ds *dead_affect_pool = &affect_pool;
Skill skills[MAX_SKILLS]{};
static char_data target{}, source{};
static bool minimum_roll;
static int waits, damage_calls;

bool nevent_periodic_begin(P_nevent) { return false; }
void nevent_periodic_complete(P_nevent) {}
void nevent_periodic_watchdog() {}
bool nevent_periodic_event_is_valid(P_nevent) { return true; }
long nevent_periodic_integrity_errors(bool) { return 0; }
float get_property(const char *key, double fallback) {
    if (!strcmp(key, "poison.maxDuration.min")) return 4;
    return fallback;
}
int get_property(const char *key, int fallback) { return get_property(key, double(fallback)); }
void *__malloc(size_t size, const char *, const char *, int) { return std::malloc(size); }
void __free(void *p, const char *, int) { std::free(p); }
void *_mm_get(mm_ds *pool, const char *, int) {
    ++pool->objs_used;
    return std::calloc(1, pool == &event_pool ? sizeof(nevent_data) : sizeof(affected_type));
}
void mm_release(mm_ds *pool, void *p) { --pool->objs_used; std::free(p); }
mm_ds *mm_create(const char *, size_t, size_t, unsigned) { return &affect_pool; }
const char *event_name_registry_lookup(const void *) { return nullptr; }
char_link_data *link_char(P_char ch, P_char victim, ush_int) {
    auto *link = new char_link_data{}; link->linking = ch; link->linked = victim; return link;
}
void remove_link(P_char, char_link_data *link) { event_broken(link); delete link; }
#define LABEL(name) void name(P_char, P_char, P_obj, void *) {}
LABEL(release_mob_mem)
LABEL(event_hit_regen)
LABEL(event_move_regen)
LABEL(event_ward_regen)
LABEL(event_spellcast)
LABEL(event_item_action_active)
LABEL(event_memorize)
LABEL(event_mob_mundane)
LABEL(event_reset_zone)
LABEL(event_autosave)
LABEL(event_wait)
LABEL(event_web_spray)
#undef LABEL
void all_affects(P_char ch, int add) {
    for (auto *af = ch->affected; af; af = af->next) {
        if (add) {
            ch->specials.affected_by |= af->bitvector;
            ch->specials.affected_by2 |= af->bitvector2;
        } else {
            ch->specials.affected_by &= ~af->bitvector;
            ch->specials.affected_by2 &= ~af->bitvector2;
        }
    }
}
void event_balance_affects(P_char ch, P_char, P_obj, void *) {
    ch->specials.affected_by = ch->specials.affected_by2 = 0;
    all_affects(ch, true);
}
void gmcp_char_affects(P_char) {}
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
void unlink_char_affect(P_char, affected_type *) { assert(false); }
void unlink_char_obj_affect(P_char, affected_type *) { assert(false); }
int number(int low, int high) { return minimum_roll ? low : high; }
void CharWait(P_char, int duration) { waits += duration; }
int raw_damage(P_char, P_char, double, uint, damage_messages *, int *) { ++damage_calls; return DAM_NONEDEAD; }
void berserk(P_char, int) {}
int GET_CLASS(P_char, uint) { return 0; }
bool resists_spell(P_char, P_char) { return false; }
bool saves_spell(P_char, int) { return false; }
void appear(P_char, bool) {}
void remember(P_char, P_char) {}
void MobStartFight(P_char, P_char) { assert(false); }
bool ac_can_see(P_char, P_char, bool) { return true; }
void spell_cure_blind(int, P_char, char *, int, P_char, P_obj) {}
void spell_cure_disease(int, P_char, char *, int, P_char, P_obj) {}
static void advance(int pulses) {
    for (int i = 0; i < pulses; ++i) { ne_events(); nevent_advance_tick(); }
}
'''


def production():
    return "\n".join(extract_function(file, signature) for file, signature in [
        ("affects.c", "void balance_affects("),
        ("affects.c", "bool affected_by_spell("),
        ("affects.c", "struct affected_type *get_spell_from_char("),
        ("affects.c", "struct affected_type *affect_to_char("),
        ("affects.c", "void affect_remove("),
        ("affects.c", "void affect_from_char("),
        ("handler.c", "int poison_common_remove("),
        ("handler.c", "struct affected_type *poison_common("),
        ("handler.c", "void event_poison("),
        *[("handler.c", "void poison_" + name + "(") for name in
          ("lifeleak", "moveleak", "heart_toxin", "neurotoxin", "weakness", "slowness", "madness")],
        ("magic.c", "void spell_remove_poison("),
        ("magic.c", "static void purify_group_member("),
        ("magic.c", "void spell_slow("),
    ])


DRIVER = r'''
static void clear(P_char ch) {
    while (ch->affected) affect_remove(ch, ch->affected);
    disarm_char_nevents(ch, nullptr);
}
static void reset() {
    clear(&target); clear(&source);
    target = {}; source = {};
    for (auto *ch : {&target, &source}) {
        SET_POS(ch, POS_STANDING + STAT_NORMAL);
        ch->in_room = 1; ch->player.level = 46;
        ch->points.hit = ch->points.max_hit = 1000;
        GET_VITALITY(ch) = GET_MAX_VITALITY(ch) = 100;
    }
    character_list = &target; target.next = &source;
    minimum_roll = false; waits = damage_calls = 0;
}
static void poison(int type, P_char ch = &target) {
    skills[type].spell_pointer(46, &source, nullptr, 0, ch, nullptr);
}
static void slowness() {
    reset(); poison(POISON_SLOWNESS);
    assert(IS_AFFECTED2(&target, AFF2_SLOW) && IS_AFFECTED2(&target, AFF2_POISONED));
    advance(1);
    assert(IS_AFFECTED2(&target, AFF2_SLOW));
    assert(IS_AFFECTED2(&target, AFF2_POISONED));
    assert(poison_common_remove(&target)); advance(1);
    assert(!affected_by_spell(&target, POISON_SLOWNESS));
    assert(!IS_AFFECTED2(&target, AFF2_SLOW) && !IS_AFFECTED2(&target, AFF2_POISONED));
    poison(POISON_SLOWNESS); advance(1);
    purify_group_member(46, &source, 0, &target);
    assert(!affected_by_spell(&target, POISON_SLOWNESS));
    poison(POISON_SLOWNESS); advance(1);
    spell_remove_poison(46, &source, nullptr, 0, &target, nullptr);
    assert(!affected_by_spell(&target, POISON_SLOWNESS));
    reset(); spell_slow(46, &source, nullptr, 0, &target, nullptr);
    poison(POISON_SLOWNESS); advance(1);
    assert(poison_common_remove(&target)); advance(1);
    assert(affected_by_spell(&target, SPELL_SLOW));
    assert(IS_AFFECTED2(&target, AFF2_SLOW) && !IS_AFFECTED2(&target, AFF2_POISONED));
}
static void replacement() {
    reset(); poison(POISON_LIFELEAK);
    advance(10);
    assert(poison_common_remove(&target));
    poison(POISON_LIFELEAK);
    advance(71);
    assert(GET_HIT(&target) == 1000);
    advance(10);
    assert(GET_HIT(&target) == 990);
}
static void timers() {
    for (int type = FIRST_POISON; type <= LAST_POISON; ++type) {
        reset(); poison(type);
        auto old = nevent_handle_from_event(get_scheduled(&target, event_poison));
        assert(nevent_handle_is_active(old));
        auto old_due = old.event->due_tick;
        advance(5);
        spell_remove_poison(46, &source, nullptr, 0, &target, nullptr);
        assert(!get_scheduled(&target, event_poison));
        poison(type);
        auto replacement = nevent_handle_from_event(get_scheduled(&target, event_poison));
        auto new_due = replacement.event->due_tick;
        assert(new_due == old_due + 5);
        advance(int(old_due - ne_event_tick + 1));
        assert(nevent_handle_is_active(replacement));
        assert(replacement.event->due_tick == new_due);
        // Expiry and arbitrary affect removal use the same production cleanup.
        affect_remove(&target, get_spell_from_char(&target, type));
        assert(!get_scheduled(&target, event_poison));
        advance(int(new_due - ne_event_tick + 1));
        assert(!affected_by_spell(&target, type));
    }
    // Removing one type preserves another's timer and unrelated events.
    reset(); poison(POISON_LIFELEAK); poison(POISON_NEUROTOXIN);
    auto neuro = nevent_handle_from_event(target.nevents_tail);
    affect_from_char(&target, POISON_LIFELEAK);
    assert(nevent_handle_is_active(neuro));
    assert(affected_by_spell(&target, POISON_NEUROTOXIN));
    // Clean up any duplicate old timers as well as the normal one.
    short type = POISON_NEUROTOXIN;
    add_event(event_poison, 10, &target, nullptr, nullptr, 0, &type, sizeof(type));
    assert(poison_common_remove(&target));
    assert(!get_scheduled(&target, event_poison));
}
static void recurrence() {
    for (int type = FIRST_POISON; type <= LAST_POISON; ++type) {
        reset(); poison(type);
        auto due = get_scheduled(&target, event_poison)->due_tick;
        advance(int(due - ne_event_tick + 1));
        if (type == POISON_SLOWNESS || type == POISON_HEART_TOXIN)
            assert(!affected_by_spell(&target, type));
        else
            assert(affected_by_spell(&target, type));
        // Aid can remove each poison from within its currently executing event.
        reset(); poison(type);
        affected_type aid{}; aid.type = SPELL_AID; affect_to_char(&target, &aid);
        minimum_roll = true;
        due = get_scheduled(&target, event_poison)->due_tick;
        advance(int(due - ne_event_tick + 2));
        assert(!affected_by_spell(&target, type));
        assert(!get_scheduled(&target, event_poison));
        assert(affected_by_spell(&target, SPELL_AID));
    }
    reset(); poison(POISON_NEUROTOXIN);
    assert(waits == 0); advance(81); assert(waits == 4 * WAIT_SEC);
    reset(); affected_type slow{}; slow.type = SPELL_SLOW_POISON; slow.bitvector = AFF_SLOW_POISON;
    affect_to_char(&target, &slow); poison(POISON_NEUROTOXIN);
    advance(81); assert(waits == 0); advance(160); assert(waits == 4 * WAIT_SEC);
    // Attacker extraction breaks the existing scheduler link, canceling Heart Toxin.
    reset(); poison(POISON_HEART_TOXIN);
    auto *heart = get_scheduled(&target, event_poison);
    auto *link = heart->cld;
    event_broken(link); delete link;
    advance(25); assert(damage_calls == 0);
    // Victim extraction/disconnect cleanup cannot dispatch any retained timer.
    reset(); poison(POISON_NEUROTOXIN);
    disarm_char_nevents(&target, nullptr); advance(81); assert(waits == 0);
}
int main() {
    nevent_bind_game_thread(); ne_dead_event_pool = &event_pool;
    skills[POISON_LIFELEAK].spell_pointer = reinterpret_cast<spell_func>(poison_lifeleak);
    skills[POISON_MOVELEAK].spell_pointer = reinterpret_cast<spell_func>(poison_moveleak);
    skills[POISON_HEART_TOXIN].spell_pointer = reinterpret_cast<spell_func>(poison_heart_toxin);
    skills[POISON_NEUROTOXIN].spell_pointer = reinterpret_cast<spell_func>(poison_neurotoxin);
    skills[POISON_WEAKNESS].spell_pointer = reinterpret_cast<spell_func>(poison_weakness);
    skills[POISON_SLOWNESS].spell_pointer = reinterpret_cast<spell_func>(poison_slowness);
    skills[POISON_MADNESS].spell_pointer = reinterpret_cast<spell_func>(poison_madness);
    slowness(); replacement(); timers(); recurrence(); reset();
    assert(ne_event_counter == 0 && event_pool.objs_used == 0 && affect_pool.objs_used == 0);
    puts("Poison lifecycle: cleansing and replacement event regressions passed");
}
'''


def main():
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="poison-lifecycle-", dir=build) as directory:
        cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
        cpp.write_text(PRELUDE + production() + DRIVER)
        subprocess.run([
            "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-parameter", "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
            "-I" + str(ROOT / "src"), str(cpp),
            str(ROOT / "src/persistence/latency_trace.c"), str(HARNESS_STUBS), "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, env={**os.environ,
            "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})


if __name__ == "__main__":
    main()
