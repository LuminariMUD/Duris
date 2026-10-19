#!/usr/bin/env python3
"""Execute Freedom of Movement's reviewed callers and binding lifecycle.

Compile complete spell/proc/unbind functions and the production affect list
operations. The large shield, wall and damage functions contribute their exact
affected branches; unrelated combat, movement and stat recalculation are fixtures.
"""

from pathlib import Path
import os
import re
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/mm.h"
#include "core/profile.h"
#include "cmd/interp.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "world/events.h"
#include "world/specs.prototypes.h"
#include "world/graph.h"
#include <cassert>
#include <cstdio>
#include <cstring>

static room_data rooms[2]{};
P_room world = rooms;
static char_data caster, target, other;
static bool saved, moved;
static int roll, message_count, dispels, moves, position_updates;
static mm_ds pool{}, link_pool{};
mm_ds *dead_affect_pool = &pool;
mm_ds *dead_link_pool = &link_pool;
link_description link_types[LNK_MAX + 1]{};
P_char character_list;
bool do_profile = false;
PROFILE_DEFINE(short_affect_liveness)

int number(int low, int high) { return roll >= low && roll <= high ? roll : low; }
bool NewSaves(P_char, int, int) { return saved; }
bool saves_spell(P_char, int) { return saved; }
bool resists_spell(P_char, P_char) { return false; }
int GET_CLASS(P_char, uint) { return 0; }
void act(const char *, int, P_char, P_obj, void *, int) { ++message_count; }
void send_to_char(const char *, P_char) { ++message_count; }
void stop_fighting(P_char) {}
void StopMercifulAttackers(P_char) {}
void remember(P_char, P_char) {}
void MobStartFight(P_char, P_char) { assert(false); }
bool ac_can_see(P_char, P_char, bool) { return true; }
void CharWait(P_char, int) {}
P_char get_char_room_vis(P_char, const char *) { return &target; }
char *one_argument(const char *arg, char *out) { std::strcpy(out, arg); return out + std::strlen(out); }
const str_app_type str_app[] = {{}};
int IS_THIEF(P_char) { return false; }
int STAT_INDEX(int) { return 0; }
void update_pos(P_char) { ++position_updates; }
int GET_ALT_SIZE(P_char) { return SIZE_MEDIUM; }
int do_simple_move_skipping_procs(P_char ch, int, int) {
    ++moves;
    if (moved) ch->in_room = 1;
    return moved;
}
void spell_dispel_magic(int, P_char, char *, int, P_char, P_obj) { ++dispels; }
const char *dirs[] = {"north"};

void *_mm_get(mm_ds *allocator, const char *, int) {
    if (allocator == dead_link_pool) return new char_link_data{};
    return new affected_type{};
}
void mm_release(mm_ds *allocator, void *p) {
    if (allocator == dead_link_pool) delete static_cast<char_link_data *>(p);
    else delete static_cast<affected_type *>(p);
}
mm_ds *mm_create(const char *, size_t, size_t, unsigned) { return &pool; }
void balance_affects(P_char) {}
void gmcp_char_affects(P_char) {}
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
void unlink_char_affect(P_char, affected_type *);
void wear_off_message(P_char, affected_type *) {}
void unlink_char_obj_affect(P_char, affected_type *) { assert(false); }
void event_web_spray(P_char, P_char, P_obj, void *) {}
void disarm_char_nevents(P_char, event_func_type) {}
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int) {
    return {};
}
nevent_handle nevent_handle_from_event(P_nevent) { return {}; }
nevent_cancel_result nevent_cancel(nevent_handle) { return nevent_cancel_result::canceled; }
// Apply/remove only the affect bits used here, leaving unrelated raw bindings intact.
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
'''


def production():
    code = "\n".join(extract_function(file, signature) for file, signature in [
        ("affects.c", "bool affected_by_spell("),
        ("affects.c", "struct affected_type *get_spell_from_char("),
        ("affects.c", "struct affected_type *affect_to_char("),
        ("affects.c", "void affect_remove("),
        ("affects.c", "void affect_from_char("),
        ("affects.c", "void affect_join("),
        ("affects.c", "void event_short_affect("),
        ("affects.c", "void define_link("),
        ("affects.c", "struct char_link_data *link_char_with_affect("),
        ("affects.c", "P_char get_linked_char("),
        ("affects.c", "P_char get_linking_char("),
        ("affects.c", "void dispose_link("),
        ("affects.c", "void internal_unlink_char("),
        ("affects.c", "void unlink_char("),
        ("affects.c", "void unlink_char_affect(P_char ch, struct affected_type *af)"),
        ("affects.c", "void clear_links(P_char ch, ush_int type)"),
        ("affects.c", "void clear_all_links("),
        ("affects.c", "void linked_affect_to_char("),
        ("magic.c", "bool check_freedom_of_movement("),
        ("magic.c", "void spell_freedom_of_movement("),
        ("magic.c", "void spell_entangle("),
        ("beh_magic.c", "void spell_beholder_paralyze("),
        ("specs.object.c", "int imprison_armor("),
        ("specs.mobile.c", "int plant_attacks_paralysis("),
        ("new_skills.c", "void do_unbind("),
    ])
    # Use the actual registration without pulling in unrelated link callbacks.
    links = extract_function("affects.c", "void initialize_links()")
    registration = re.search(r'define_link\(LNK_PLANT_PARALYSIS,.*?;', links, re.S)
    assert registration, "plant holds must have a registered link type"
    code += "\nvoid initialize_plant_link() { " + registration[0] + " }\n"
    shields = extract_function("fight.c", "int check_shields(")
    start = shields.index("\t\t\t\tcase 1:")
    end = shields.index("\t\t\t\tcase 2:", start)
    code += "\nvoid soulshield_paralysis(P_char ch, P_char victim) { affected_type af{}; af.flags = AFFTYPE_SHORT; switch (1) {\n"
    code += shields[start:end] + "case 2: break; }}\n"
    wall = extract_function("specs.object.c", "int wall_generic(")
    start = wall.index("\tcase WEB:")
    end = wall.index("\tcase LIFE_WARD:", start)
    code += "\nint web_wall(P_obj obj, P_char ch) { int dircmd = 0; char buffer[MAX_STRING_LENGTH]; affected_type af; bool drag_followers = false; switch (WEB) {\n"
    code += wall[start:end] + "} return drag_followers; }\n"
    damage = extract_function("fight.c", "int raw_damage(")
    start = damage.index("\t\t/* if char is bound there is a chance the dam cut the binding */")
    end = damage.index("\t\t/* make mirror images disappear */", start)
    code += "\nvoid cut_bindings(P_char ch, P_char victim, int dam) {\n" + damage[start:end] + "}\n"
    return code


DRIVER = r'''
static void clear(P_char ch) {
    while (ch->affected) affect_remove(ch, ch->affected);
}
static void reset() {
    clear(&caster); clear(&target); clear(&other);
    for (auto *ch : {&caster, &target, &other}) assert(!ch->linking && !ch->linked);
    caster = {}; target = {}; other = {};
    for (auto *ch : {&caster, &target, &other}) {
        SET_POS(ch, POS_STANDING + STAT_NORMAL);
        ch->player.level = 50;
    }
    rooms[0] = {}; rooms[1] = {};
    rooms[0].sector_type = SECT_FOREST;
    rooms[0].people = &caster;
    caster.next_in_room = &target;
    target.next_in_room = &other;
    character_list = &caster;
    caster.next = &target;
    target.next = &other;
    saved = false; moved = false; roll = 1;
    message_count = dispels = moves = position_updates = 0;
}
static void freedom(P_char ch) {
    spell_freedom_of_movement(46, &caster, nullptr, 0, ch, nullptr);
}
static void behold() {
    reset();
    spell_beholder_paralyze(50, &caster, &target, nullptr);
    assert(IS_AFFECTED2(&target, AFF2_MAJOR_PARALYSIS));
    clear(&target);
    freedom(&target);
    for (int i = 0; i < 3; ++i) spell_beholder_paralyze(50, &caster, &target, nullptr);
    assert(!IS_AFFECTED2(&target, AFF2_MAJOR_PARALYSIS));
    assert(check_freedom_of_movement(&target));
    clear(&target); saved = true;
    spell_beholder_paralyze(50, &caster, &target, nullptr);
    assert(!target.affected);
}
static void soulshield() {
    for (bool attacker : {false, true}) for (bool defender : {false, true}) {
        reset();
        if (attacker) freedom(&caster);
        if (defender) freedom(&target);
        soulshield_paralysis(&caster, &target);
        assert(bool(IS_AFFECTED2(&caster, AFF2_MINOR_PARALYSIS)) == !attacker);
        assert(check_freedom_of_movement(&caster) == attacker);
        assert(check_freedom_of_movement(&target) == defender);
    }
}
static void armor() {
    reset(); obj_data armor{}; proc_data data{}; data.victim = &target;
    for (int i = 0; i < 5; ++i) {
        assert(imprison_armor(&armor, &caster, CMD_GOTHIT, reinterpret_cast<char *>(&data)));
        auto *af = target.affected;
        assert(af && af->type == SPELL_MAJOR_PARALYSIS && af->duration == 5);
        assert(af->bitvector2 == AFF2_MAJOR_PARALYSIS);
        assert(!af->wear_off_message_index && !af->flags && !af->modifier && !af->location);
        assert(!af->loc2 && !af->context && !af->level && !af->bitvector);
        assert(!af->bitvector3 && !af->bitvector4 && !af->bitvector5 && !af->next);
        clear(&target);
    }
    freedom(&target);
    imprison_armor(&armor, &caster, CMD_GOTHIT, reinterpret_cast<char *>(&data));
    assert(!IS_AFFECTED2(&target, AFF2_MAJOR_PARALYSIS) && check_freedom_of_movement(&target));
}
static void plant() {
    reset(); roll = 0;
    freedom(&other);
    assert(plant_attacks_paralysis(&caster, nullptr, 0, nullptr));
    assert(IS_AFFECTED2(&target, AFF2_MAJOR_PARALYSIS));
    assert(!IS_AFFECTED2(&other, AFF2_MAJOR_PARALYSIS));
    auto *hold = target.affected;
    assert(hold->duration == 10 * WAIT_SEC);
    assert(IS_SET(hold->flags, AFFTYPE_SHORT) && IS_SET(hold->flags, AFFTYPE_NOSAVE));
    assert(get_linking_char(&caster, LNK_PLANT_PARALYSIS) == &target);
    assert(!plant_attacks_paralysis(&caster, &other, CMD_LOOK, nullptr));
    assert(target.affected == hold);
    plant_attacks_paralysis(&other, &caster, CMD_DEATH, nullptr);
    assert(target.affected == hold); // a different plant cannot release this hold
    // Death dispatch supplies the killer as pl, unlike a periodic invocation.
    assert(!plant_attacks_paralysis(&caster, &other, CMD_DEATH, nullptr));
    assert(!target.affected && !IS_AFFECTED2(&target, AFF2_MAJOR_PARALYSIS));
    assert(check_freedom_of_movement(&other));
    assert(!plant_attacks_paralysis(&caster, nullptr, CMD_DEATH, nullptr));
    assert(!target.affected); // no reapplication during cleanup

    reset(); roll = 0;
    spell_beholder_paralyze(50, &caster, &other, nullptr);
    auto *unrelated = other.affected;
    assert(unrelated && plant_attacks_paralysis(&caster, nullptr, 0, nullptr));
    plant_attacks_paralysis(&caster, &target, CMD_DEATH, nullptr);
    assert(!target.affected);
    assert(other.affected == unrelated && IS_AFFECTED2(&other, AFF2_MAJOR_PARALYSIS));

    // Removing the plant's instance must leave another paralysis on the same victim.
    reset(); roll = 0; freedom(&other);
    assert(plant_attacks_paralysis(&caster, nullptr, 0, nullptr));
    affected_type independent{};
    independent.type = SPELL_MAJOR_PARALYSIS;
    independent.duration = 30 * WAIT_SEC;
    independent.flags = AFFTYPE_SHORT;
    independent.bitvector2 = AFF2_MAJOR_PARALYSIS;
    unrelated = affect_to_char(&target, &independent);
    plant_attacks_paralysis(&caster, &other, CMD_DEATH, nullptr);
    assert(target.affected == unrelated && !unrelated->next);
    assert(IS_AFFECTED2(&target, AFF2_MAJOR_PARALYSIS));
    assert(!caster.linked && !target.linking);

    // All existing affect/character cleanup paths must release both link ends.
    for (int release = 0; release < 4; ++release) {
        reset(); roll = 0; freedom(&other);
        assert(plant_attacks_paralysis(&caster, nullptr, 0, nullptr));
        if (release == 0) freedom(&target);
        if (release == 1) {
            event_short_affect_data expiry{&target, target.affected};
            event_short_affect(&target, nullptr, nullptr, &expiry);
        }
        if (release == 2) clear_all_links(&caster); // source extraction
        if (release == 3) clear_all_links(&target); // victim extraction
        assert(!IS_AFFECTED2(&target, AFF2_MAJOR_PARALYSIS));
        assert(!caster.linked && !target.linking);
        plant_attacks_paralysis(&caster, &other, CMD_DEATH, nullptr);
        assert(check_freedom_of_movement(&other));
        assert(check_freedom_of_movement(&target) == (release == 0));
    }
}
static void web() {
    for (bool protected_target : {false, true}) for (bool success : {false, true}) {
        reset(); obj_data wall{};
        if (protected_target) freedom(&target);
        message_count = 0; moved = success;
        assert(web_wall(&wall, &target)); // failed move still consumes the command
        assert(moves == 1 && target.in_room == (success ? 1 : 0));
        assert(dispels == int(success) && position_updates == int(success));
        assert(bool(IS_AFFECTED2(&target, AFF2_MINOR_PARALYSIS)) == (success && !protected_target));
        assert(success || message_count == 0);
        assert(check_freedom_of_movement(&target) == protected_target);
    }
    reset(); moved = true; saved = true; obj_data wall{};
    web_wall(&wall, &target);
    assert(dispels == 1 && !target.affected);
}
static void entangle() {
    for (int release = 0; release < 3; ++release) {
        reset();
        spell_entangle(50, &caster, nullptr, 0, &target, nullptr);
        assert(IS_AFFECTED(&target, AFF_BOUND));
        assert(affected_by_spell(&target, SPELL_ENTANGLE));
        assert(target.affected->duration == -1);
        if (release == 0) freedom(&target);
        if (release == 1) { char name[] = "target"; do_unbind(&caster, name, 0); }
        if (release == 2) cut_bindings(&caster, &target, 100);
        assert(!IS_AFFECTED(&target, AFF_BOUND));
        assert(!affected_by_spell(&target, SPELL_ENTANGLE));
        all_affects(&target, true);
        assert(!IS_AFFECTED(&target, AFF_BOUND)); // no resurrection on recalculation
    }
    reset(); roll = 100;
    spell_entangle(50, &caster, nullptr, 0, &target, nullptr);
    assert(IS_AFFECTED2(&target, AFF2_MINOR_PARALYSIS));
    freedom(&target);
    assert(!IS_AFFECTED2(&target, AFF2_MINOR_PARALYSIS));
    assert(!affected_by_spell(&target, SPELL_ENTANGLE));
    // Raw capture/rope bindings are not attributed to entangle and must survive.
    reset(); SET_BIT(target.specials.affected_by, AFF_BOUND);
    freedom(&target);
    assert(IS_AFFECTED(&target, AFF_BOUND));
    reset(); SET_BIT(target.specials.affected_by, AFF_BOUND);
    spell_entangle(50, &caster, nullptr, 0, &target, nullptr);
    assert(affected_by_spell(&target, SPELL_ENTANGLE));
    assert(!IS_SET(target.affected->bitvector, AFF_BOUND));
    freedom(&target);
    assert(IS_AFFECTED(&target, AFF_BOUND));
    assert(!affected_by_spell(&target, SPELL_ENTANGLE));
    // Freeing a rope must not also cure the ordinary, non-binding entangle.
    for (bool damage : {false, true}) {
        reset(); roll = 100;
        spell_entangle(50, &caster, nullptr, 0, &target, nullptr);
        SET_BIT(target.specials.affected_by, AFF_BOUND);
        if (damage) cut_bindings(&caster, &target, 100);
        else { char name[] = "target"; do_unbind(&caster, name, 0); }
        assert(!IS_AFFECTED(&target, AFF_BOUND));
        assert(IS_AFFECTED2(&target, AFF2_MINOR_PARALYSIS));
        assert(affected_by_spell(&target, SPELL_ENTANGLE));
    }
}
int main(int argc, char **argv) {
    initialize_plant_link();
    if (argc == 1 || !strcmp(argv[1], "beholder")) behold();
    if (argc == 1 || !strcmp(argv[1], "soulshield")) soulshield();
    if (argc == 1 || !strcmp(argv[1], "armor")) armor();
    if (argc == 1 || !strcmp(argv[1], "plant")) plant();
    if (argc == 1 || !strcmp(argv[1], "web")) web();
    if (argc == 1 || !strcmp(argv[1], "entangle")) entangle();
    reset();
    puts("Freedom of Movement: proc, binding and source-specific plant cleanup regressions passed");
}
'''


def main():
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="freedom-procs-", dir=build) as directory:
        cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
        cpp.write_text(PRELUDE + production() + DRIVER)
        subprocess.run([
            "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-parameter", "-ftrivial-auto-var-init=pattern",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-ffunction-sections", "-fdata-sections", "-I" + str(ROOT / "src"),
            str(cpp), str(HARNESS_STUBS), "-Wl,--gc-sections", "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, env={**os.environ,
            "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})


if __name__ == "__main__":
    main()
