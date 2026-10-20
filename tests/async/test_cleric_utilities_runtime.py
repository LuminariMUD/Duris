#!/usr/bin/env python3
"""Run cleric utility spell bodies with real protection/cure logic and isolated effects."""

import subprocess
from _paths import ROOT, extract_function
from _paths import HARNESS_STUBS

PRELUDE = r'''
#include "world/new_events.c"
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "magic/spells.h"
#include <cassert>
#include <cstdio>
#include <strings.h>


P_char character_list = nullptr;
P_obj object_list = nullptr;
P_index mob_index = nullptr, obj_index = nullptr;
static room_data rooms[6]{};
P_room world = rooms;
extern const int top_of_world = 5;
int pulse = 0;
bool after_events_call = false;
static mm_ds event_pool{};
bool nevent_periodic_begin(P_nevent) { return false; }
void nevent_periodic_complete(P_nevent) {}
void nevent_periodic_watchdog() {}
bool nevent_periodic_event_is_valid(P_nevent) { return true; }
long nevent_periodic_integrity_errors(bool) { return 0; }
float get_property(const char *, double fallback) { return fallback; }
void *__malloc(size_t size, const char *, const char *, int) { return std::malloc(size); }
void __free(void *p, const char *, int) { std::free(p); }
void *_mm_get(mm_ds *pool, const char *, int) {
    ++pool->objs_used;
    return std::calloc(1, sizeof(nevent_data));
}
void mm_release(mm_ds *pool, void *p) { --pool->objs_used; std::free(p); }
const char *event_name_registry_lookup(const void *) { return nullptr; }
char_link_data *link_char(P_char, P_char, ush_int) { std::abort(); }
void remove_link(P_char, char_link_data *) { std::abort(); }
#define LABEL(name) void name(P_char, P_char, P_obj, void *) {}
LABEL(release_mob_mem)
LABEL(event_hit_regen)
LABEL(event_move_regen)
LABEL(event_ward_regen)
LABEL(event_spellcast)
LABEL(event_item_action_active)
LABEL(event_memorize)
LABEL(event_balance_affects)
LABEL(event_mob_mundane)
LABEL(event_reset_zone)
LABEL(event_autosave)
LABEL(event_wait)
#undef LABEL
void wear_off_message(P_char, affected_type *) {}
static int published_short_affects = 0;
void gmcp_char_affects(P_char ch) {
    published_short_affects = 0;
    for (auto *af = ch->affected; af; af = af->next) {
        if (!(af->flags & AFFTYPE_SHORT)) continue;
        bool scheduled = false;
        for (auto *event = ch->nevents; event; event = event->next_char_nev)
            if (event->func == event_short_affect && event->data &&
                static_cast<event_short_affect_data *>(event->data)->af == af)
                scheduled = true;
        assert(scheduled);
        ++published_short_affects;
    }
}
static void advance(int pulses) {
    for (int i = 0; i < pulses; ++i) { ne_events(); nevent_advance_tick(); }
}

bool affected_by_spell(P_char ch, int type) {
    for (auto *af = ch->affected; af; af = af->next)
        if (af->type == type) return true;
    return false;
}
static void rebuild_bits(P_char ch) {
    ch->specials.affected_by = ch->specials.affected_by2 = 0;
    for (auto *af = ch->affected; af; af = af->next) {
        ch->specials.affected_by |= af->bitvector;
        ch->specials.affected_by2 |= af->bitvector2;
    }
}
affected_type *affect_to_char(P_char ch, affected_type *af) {
    auto *copy = new affected_type(*af);
    copy->next = ch->affected;
    ch->affected = copy;
    rebuild_bits(ch);
    return copy;
}
void affect_remove(P_char ch, affected_type *target) {
    for (auto **p = &ch->affected; *p; p = &(*p)->next) {
        if (*p != target) continue;
        *p = target->next;
        if (target->flags & AFFTYPE_SHORT)
            for (auto *e = ch->nevents; e; e = e->next_char_nev)
                if (e->func == event_short_affect && e->data &&
                    static_cast<event_short_affect_data *>(e->data)->af == target) {
                    nevent_cancel(nevent_handle_from_event(e));
                    break;
                }
        delete target;
        rebuild_bits(ch);
        return;
    }
}
void affect_from_char(P_char ch, int type) {
    for (auto *af = ch->affected; af;) {
        auto *next = af->next;
        if (af->type == type) affect_remove(ch, af);
        af = next;
    }
}
static void add(P_char ch, int type, unsigned int bits = 0, unsigned int bits2 = 0) {
    affected_type af{};
    af.type = type;
    af.duration = 7;
    af.bitvector = bits;
    af.bitvector2 = bits2;
    affect_to_char(ch, &af);
}
static int count(P_char ch) {
    int n = 0;
    for (auto *af = ch->affected; af; af = af->next) ++n;
    return n;
}
static void clear(P_char ch) {
    while (ch->affected) affect_remove(ch, ch->affected);
}
static void initialize(P_char ch) {
    ch->specials.position = STAT_NORMAL;
    ch->in_room = 5;
    ch->points.hit = 41;
    ch->points.max_hit = 100;
}
static void ailments(P_char ch) {
    add(ch, SPELL_POISON, 0, AFF2_POISONED);
    add(ch, POISON_LIFELEAK, 0, AFF2_POISONED);
    add(ch, SPELL_BLINDNESS, AFF_BLIND);
    add(ch, SPELL_DISEASE);
    add(ch, SPELL_CONTAGION);
    add(ch, SPELL_CURSE);
    add(ch, SPELL_PLAGUE);
    add(ch, SPELL_BLESS);
}
static void check_clean(P_char ch) {
    assert(count(ch) == 3);
    assert(!IS_AFFECTED(ch, AFF_BLIND));
    assert(!IS_AFFECTED2(ch, AFF2_POISONED));
    assert(affected_by_spell(ch, SPELL_CURSE));
    assert(affected_by_spell(ch, SPELL_PLAGUE));
    assert(affected_by_spell(ch, SPELL_BLESS));
    assert(ch->points.hit == 41 && ch->points.max_hit == 100);
}
'''

DRIVER = r'''
int main() {
    char_data caster{}, ally{}, remote{}, stranger{}, dead{}, pet{};
    P_char characters[] = {&caster, &ally, &remote, &stranger, &dead, &pet};
    for (auto *ch : characters) initialize(ch);
    remote.in_room = 6;
    dead.specials.position = STAT_DEAD;

    nevent_bind_game_thread();
    ne_dead_event_pool = &event_pool;
    character_list = &caster;
    // Explicit non-self and invalid targets never receive any protection.
    spell_divine_warding(56, &caster, nullptr, 0, &ally, nullptr);
    spell_divine_warding(56, &caster, nullptr, 0, &remote, nullptr);
    spell_divine_warding(56, &caster, nullptr, 0, &dead, nullptr);
    spell_divine_warding(56, nullptr, nullptr, 0, &stranger, nullptr);
    spell_divine_warding(56, &caster, nullptr, 0, nullptr, nullptr);
    for (auto *ch : characters) assert(count(ch) == 0);
    caster.in_room = NOWHERE;
    spell_divine_warding(56, &caster, nullptr, 0, &caster, nullptr);
    assert(count(&caster) == 0);
    caster.in_room = 5;
    const int protections[] = {SPELL_PROTECT_FROM_FIRE, SPELL_PROTECT_FROM_COLD,
        SPELL_PROTECT_FROM_ACID, SPELL_PROTECT_FROM_GAS, SPELL_PROTECT_FROM_LIGHTNING,
        SPELL_PROTECT_FROM_GOOD, SPELL_PROTECT_FROM_EVIL};
    using spell_func = void (*)(int, P_char, char *, int, P_char, P_obj);
    const spell_func individual[] = {spell_protection_from_fire, spell_protection_from_cold,
        spell_protection_from_acid, spell_protection_from_gas, spell_protection_from_lightning,
        spell_protection_from_good, spell_protection_from_evil};
    for (int phase : {0, 1, 299}) {
        advance(phase);
        add(&caster, SPELL_BLESS);
        // Tick-based individual protection becomes an elapsed-time bundle member.
        spell_protection_from_fire(56, &caster, nullptr, 0, &caster, nullptr);
        spell_divine_warding(56, &caster, nullptr, 0, &caster, nullptr);
        assert(count(&caster) == 8 && ne_event_counter == 7);
        assert(published_short_affects == 7);
        for (auto *af = caster.affected; af; af = af->next)
            if (af->type != SPELL_BLESS) {
                assert(af->flags & AFFTYPE_SHORT);
                assert(af->duration == 2640);
                assert(!(af->flags & AFFTYPE_NODISPEL));
            }
        advance(2640);
        assert(count(&caster) == 8); // due pulse has not been dispatched yet
        advance(1);
        assert(count(&caster) == 1 && affected_by_spell(&caster, SPELL_BLESS));
        clear(&caster);
    }
    // Bundle recasts cancel old callbacks; dispelling one effect leaves six.
    spell_divine_warding(56, &caster, nullptr, 0, &caster, nullptr);
    advance(1000);
    spell_divine_warding(56, &caster, nullptr, 0, &caster, nullptr);
    spell_divine_warding(56, &caster, nullptr, 0, &caster, nullptr);
    assert(count(&caster) == 7 && ne_event_counter == 7);
    affect_from_char(&caster, SPELL_PROTECT_FROM_FIRE);
    assert(count(&caster) == 6 && ne_event_counter == 6);
    advance(1641); // canceled original deadline cannot remove refreshed members
    assert(count(&caster) == 6);
    for (int i = 1; i < 7; ++i) {
        individual[i](46, &caster, nullptr, 0, &caster, nullptr);
        auto *af = caster.affected;
        while (af && af->type != protections[i]) af = af->next;
        assert(af && af->duration == 46 && !(af->flags & AFFTYPE_SHORT));
    }
    assert(ne_event_counter == 0);
    advance(3000);
    assert(count(&caster) == 6); // later ordinary casts have no old bundle expiry
    clear(&caster);
    // Removal/extraction cancels all timers; no callback retains freed affects.
    spell_divine_warding(56, &caster, nullptr, 0, &caster, nullptr);
    clear(&caster);
    assert(ne_event_counter == 0);
    advance(2641);
    assert(count(&caster) == 0);
    // A real scheduler admission failure must not leave permanent protections.
    const auto sequence = ne_event_sequence;
    ne_event_sequence = ULLONG_MAX;
    spell_divine_warding(56, &caster, nullptr, 0, &caster, nullptr);
    assert(count(&caster) == 0 && ne_event_counter == 0);
    ne_event_sequence = sequence;

    // Solo purification works, preserves unrelated effects and never heals.
    ailments(&caster);
    spell_mass_purification(56, &caster, nullptr, 0, nullptr, nullptr);
    check_clean(&caster);
    spell_mass_purification(56, &caster, nullptr, 0, nullptr, nullptr);
    check_clean(&caster);
    clear(&caster);

    // A nonleader caster cleans the leader and local members, never bystanders,
    // dead members or members elsewhere. Null entries are harmless.
    for (auto *ch : characters) ailments(ch);
    group_list pet_entry{&pet, nullptr};
    group_list null_entry{nullptr, &pet_entry};
    group_list dead_entry{&dead, &null_entry};
    group_list remote_entry{&remote, &dead_entry};
    group_list caster_entry{&caster, &remote_entry};
    group_list leader_entry{&ally, &caster_entry};
    caster.group = &leader_entry;
    spell_mass_purification(56, &caster, nullptr, 0, nullptr, nullptr);
    check_clean(&caster);
    check_clean(&ally);
    check_clean(&pet);
    assert(count(&remote) == 8 && count(&stranger) == 8 && count(&dead) == 8);
    spell_mass_purification(56, nullptr, nullptr, 0, nullptr, nullptr);
    dead.group = &leader_entry;
    spell_mass_purification(56, &dead, nullptr, 0, nullptr, nullptr);
    assert(count(&dead) == 8);
    for (auto *ch : characters) clear(ch);

    // Both flag-only ailments and spell effects follow the normal cure paths.
    caster.group = nullptr;
    caster.specials.affected_by |= AFF_BLIND;
    caster.specials.affected_by2 |= AFF2_POISONED;
    spell_mass_purification(56, &caster, nullptr, 0, nullptr, nullptr);
    assert(!IS_AFFECTED(&caster, AFF_BLIND) && !IS_AFFECTED2(&caster, AFF2_POISONED));
    ailments(&caster);
    caster.in_room = NOWHERE;
    spell_mass_purification(56, &caster, nullptr, 0, nullptr, nullptr);
    assert(count(&caster) == 8);
    clear(&caster);
    std::puts("Cleric warding targets, refresh, independent effects, and group cleansing passed.");
}
'''

functions = [extract_function("magic.c", "static void set_protection_duration(")]
functions += [extract_function("magic.c", "void spell_protection_from_" + name + "(")
             for name in ("fire", "cold", "acid", "gas", "lightning", "good", "evil")]
functions += [extract_function("affects.c", "void event_short_affect(").replace(
    "PROFILE_START(short_affect_liveness);", "").replace("PROFILE_END(short_affect_liveness);", "")]
functions += [extract_function("handler.c", "int poison_common_remove(")]
functions += [extract_function("magic.c", signature) for signature in (
    "void spell_cure_blind(", "void spell_cure_disease(", "void spell_divine_warding(",
    "static void purify_group_member(", "void spell_mass_purification(")]
output = ROOT / "bin/tests/cleric-utilities"
output.mkdir(parents=True, exist_ok=True)
harness = output / "harness.cpp"
harness.write_text(PRELUDE + "\n".join(functions) + DRIVER)
binary = output / "harness"
subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-I" + str(ROOT / "src"),
                str(harness), str(ROOT / "src/persistence/latency_trace.c"), str(HARNESS_STUBS), "-o", str(binary)], check=True)
subprocess.run([str(binary)], check=True)
