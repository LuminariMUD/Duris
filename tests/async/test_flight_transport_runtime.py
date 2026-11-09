#!/usr/bin/env python3
"""Production transport, links and nevent lifecycle; world I/O remains isolated.

Exercises the same clear_all_links/disarm boundary used by extract_char(). The
full server journey separately covers the complete character extraction path.
"""
import os
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function
from test_flight_network import base, CASES


def remove_function(text, signature):
    start = text.index(signature)
    depth = 0
    for end in range(text.index('{', start), len(text)):
        if text[end] == '{':
            depth += 1
        elif text[end] == '}':
            depth -= 1
            if not depth:
                return text[:start] + text[end + 1:]
    raise AssertionError(signature)


for signature in ('P_char get_linked_char(', 'P_char get_linking_char(',
                  'char_link_data *link_char(', 'void unlink_char(',
                  'nevent_handle nevent_find_next(', 'nevent_cancel_result nevent_cancel(',
                  'nevent_schedule_result add_event(', 'void run_event('):
    base = remove_function(base, signature)
base = base.replace('assert(!GET_RIDER(ch));\n\tscheduled.erase(ch);',
                    'clear_all_links(ch);\n\tdisarm_char_nevents(ch, nullptr);')

# Exercise production companion placement inside the isolated room-I/O fixture.
base = ('#include "core/prototypes.h"\n'
        '#include "combat/attack_continuation.h"\n'
        'static uint64_t fixture_runtime_id = 0;\n'
        'static bool move_riding_companions(P_char, int, int, bool);\n') + base
base = base.replace('bool char_to_room(P_char ch, int room, int direction)',
                    'bool char_to_room(P_char ch, int room, int direction, bool ordinary_movement)')
base += '\n' + extract_function('handler.c', 'bool char_to_room(P_char ch, int room, int dir)')
base = base.replace('P_char ch = new char_data{};',
                    'P_char ch = new char_data{}; ch->runtime_id = ++fixture_runtime_id;')
base = base.replace('''	if (P_char rider = GET_RIDER(ch))
	{
		char_from_room(rider);
		char_to_room(rider, room, -1);
	}''', '\tif (!move_riding_companions(ch, room, direction, ordinary_movement)) return false;')
movement = extract_function('handler.c', 'static bool move_riding_companions(')

links = '\n'.join(extract_function('affects.c', signature) for signature in (
    'struct char_link_data *link_char_with_affect(', 'struct char_link_data *link_char(',
    'P_char get_linked_char(', 'P_char get_linking_char(', 'void dispose_link(',
    'void clear_all_links(', 'void clear_links(P_char ch, ush_int type)',
    'void internal_unlink_char(', 'void unlink_char(P_char ch, P_char target, ush_int type)',
    'void remove_link(P_char ch, struct char_link_data *clda)'))
behavior = '\n'.join((extract_function('fight.c', 'void set_fighting(P_char ch, P_char vict)'),
                      extract_function('mount.c', 'void stop_riding(P_char ch)'),
                      extract_function('mount.c', 'static double mounted_combat_mount_threshold('),
                      extract_function('mount.c', 'static int mount_try('),
                      extract_function('mount.c', 'static int mount_defense('),
                      extract_function('mount.c', 'static int mount_vitality_cost('),
                      extract_function('mount.c', 'void do_mount(P_char ch, char *argument,')))

RUNTIME = r'''
#include "combat/training_dummy.h"
#include "economy/collector_presence.h"
#include "net/gmcp.h"
#include "telemetry/telemetry_runtime.h"
#include "classes/dreadlord.h"
P_char find_character_by_runtime_id(uint64_t id) {
    for (P_char ch = character_list; ch; ch = ch->next)
        if (ch->runtime_id == id) return ch;
    return nullptr;
}
bool is_dragoon_mounted(P_char) { return false; }
void telemetry_combat_context_changed(P_char) {}
bool training_dummy_is(P_char) { return false; }
bool training_dummy_target_allowed(P_char, P_char) { return true; }
void training_dummy_retarget_nonpet(P_char, P_char) { abort(); }
bool collector_presence_is_npc(P_char) { return false; }
bool SanityCheck(P_char ch, const char *) { return ch != nullptr; }
int IS_MORPH(P_char) { return false; }
int GET_CHAR_SKILL_P(P_char, int) { return 0; }
int GET_CLASS(P_char, uint) { return 0; }
int on_front_line(P_char) { return true; }
bool can_hit_target(P_char, P_char) { return true; }
bool AdjacentInRoom(P_char, P_char) { return true; }
P_char PickTarget(P_char) { abort(); }
bool is_linked_to(P_char, P_char, ush_int) { return true; }
int number(int low, int) { return low; }
int LINKED_OBJECTS::Visible_Type() { abort(); }
void StartRegen(P_char, regen_resource) {}
void CharWait(P_char, int) { abort(); }
void stop_memorizing(P_char, memorization_stop_reason) {}
void stop_fighting(P_char) { abort(); }
void affect_from_char(P_char, int) { abort(); }
affected_type *get_spell_from_char(P_char, int, void *, int) { return nullptr; }
bool DragonCombat(P_char, int) { abort(); }
void remember(P_char, P_char) { abort(); }
bool ac_can_see(P_char, P_char, bool) { return true; }
void do_wake(P_char, char *, int) { abort(); }
void do_dread_wrath(P_char, P_char) { abort(); }
void do_innate_anti_evil(P_char, P_char) { abort(); }
void do_innate_decrepify(P_char, P_char) { abort(); }
void appear(P_char, bool) {}
void stop_meditation(P_char) { abort(); }
void show_string(P_desc, const char *) { abort(); }
void gmcp_combat_target(P_char, P_char) {}
telemetry_capture_result telemetry_runtime_game_encounter_begin(P_char, telemetry_encounter_mode) { return {}; }
void gmcp_mark_room_dirty(int) {}
P_char combat_list = nullptr;
#include "world/new_events.c"
struct link_description link_types[LNK_MAX + 1] = {};
static mm_ds link_pool = {};
struct mm_ds *dead_link_pool = &link_pool;
static mm_ds event_pool = {};
// Like production mm pools, retain released storage for stale-handle inspection.
static std::vector<void *> pool_storage;
void *_mm_get(mm_ds *pool, const char *, int) {
    ++pool->objs_used;
    void *value = calloc(1, pool == &link_pool ? sizeof(char_link_data) : sizeof(nevent_data));
    pool_storage.push_back(value);
    return value;
}
void mm_release(mm_ds *pool, void *) {
    --pool->objs_used;
}
mm_ds *mm_create(const char *, size_t, size_t, unsigned) { abort(); }
bool nevent_periodic_event_is_valid(P_nevent) { return true; }
long nevent_periodic_integrity_errors(bool) { return 0; }
void nevent_periodic_complete(P_nevent) {}
void __free(void *value, const char *, int) { free(value); }
void *__malloc(size_t size, const char *, const char *, int) { return calloc(1, size); }
bool after_events_call = false;
const char *event_name_registry_lookup(const void *) { return "flight-runtime"; }
void affect_remove(P_char, affected_type *) { abort(); }
void wear_off_message(P_char, affected_type *) { abort(); }
#define UNUSED_CALLBACK(name) void name(P_char, P_char, P_obj, void *) { abort(); }
UNUSED_CALLBACK(event_autosave)
UNUSED_CALLBACK(event_memorize)
UNUSED_CALLBACK(event_spellcast)
UNUSED_CALLBACK(event_balance_affects)
UNUSED_CALLBACK(event_item_action_active)
UNUSED_CALLBACK(event_wait)
UNUSED_CALLBACK(event_move_regen)
UNUSED_CALLBACK(event_hit_regen)
UNUSED_CALLBACK(event_ward_regen)
UNUSED_CALLBACK(release_mob_mem)
#undef UNUSED_CALLBACK

void run_event(P_char carrier) {
    P_nevent event = carrier->nevents;
    assert(event && !event->victim && !event->cld);
    current_nevent = event;
    event->func(event->ch, event->victim, event->obj, event->data);
    nevent_destroy(event);
    current_nevent = nullptr;
    nevent_process_pending_cancellations();
    assert(check_nevents());
}
'''
# The isolated fixture and transport use the mutable world-size declaration.
RUNTIME = RUNTIME.replace('#include "world/new_events.c"',
                          (ROOT / 'src/world/new_events.c').read_text().replace(
                              'extern const int top_of_world;', 'extern int top_of_world;'))

driver = CASES[:CASES.index('    visit(1);')]
driver = driver.replace('P_char ch = new char_data{};',
                        'P_char ch = new char_data{}; ch->runtime_id = ++fixture_runtime_id;')
driver = driver.replace('    initialize_transport();', '''    nevent_bind_game_thread();
    ne_dead_event_pool = &event_pool;
    link_types[LNK_RIDING].name = "RIDING";
    link_types[LNK_RIDING].flags = LNKFLG_EXCLUSIVE;
    link_types[LNK_EVENT].name = "EVENT";
    link_types[LNK_EVENT].break_func.ch = event_broken;
    initialize_transport();''', 1)
driver += r'''
    pc.learned_flight_stops = 6;
    GET_COPPER(ch) = 1000000;
    // Normal mount commands cannot board a carrier or attach to its passenger.
    visit(2);
    char mount_argument[] = "carrier";
    do_mount(ch, mount_argument, CMD_MOUNT);
    assert(!GET_MOUNT(ch));
    command(CMD_BUY, "1");
    command(CMD_GIVE, "ticket carrier");
    P_char carrier = recipient;
    recipient = ch;
    char_from_room(other);
    char_to_room(other, ch->in_room, -1);
    do_mount(other, mount_argument, CMD_MOUNT);
    assert(!GET_MOUNT(other) && GET_MOUNT(ch) == carrier);
    recipient = carrier;
    // A paid passenger needs no mounted-combat skill to stay aboard.
    set_fighting(ch, other);
    assert(GET_OPPONENT(ch) == other && GET_MOUNT(ch) == carrier);
    ch->specials.fighting = nullptr;
    ch->specials.next_fighting = nullptr;
    combat_list = nullptr;
    while (carrier->nevents) run_event(carrier);
    // Ordinary ground mounts keep their existing skill-based dismount behavior.
    link_char(ch, other, LNK_RIDING);
    set_fighting(ch, carrier);
    assert(GET_OPPONENT(ch) == carrier && !GET_MOUNT(ch));
    ch->specials.fighting = nullptr;
    ch->specials.next_fighting = nullptr;
    combat_list = nullptr;
    // Ground centaur mounting remains reachable with its normal saddle/consent setup.
    char_from_room(other);
    char_to_room(other, ch->in_room, -1);
    other->player.race = RACE_CENTAUR;
    obj_data saddle = {};
    other->equipment[WEAR_HORSE_BODY] = &saddle;
    GET_VITALITY(ch) = 100;
    recipient = other;
    do_mount(ch, mount_argument, CMD_MOUNT);
    assert(GET_MOUNT(ch) == other);
    unlink_char(ch, other, LNK_RIDING);
    other->equipment[WEAR_HORSE_BODY] = nullptr;
    other->player.race = 0;
    recipient = carrier;
    pc.learned_flight_stops = 6;
    GET_COPPER(ch) = 1000000;
    for (int interruption = 0; interruption < 4; ++interruption) {
        visit(2);
        command(CMD_BUY, "1");
        command(CMD_GIVE, "ticket carrier");
        assert(GET_MOUNT(ch) == recipient && ne_event_counter == 1);
        run_event(recipient);
        assert(recipient->in_room != 2);
        if (interruption == 0) {
            // This is the production passenger-extraction link teardown.
            clear_all_links(ch);
            disarm_char_nevents(ch, nullptr);
            assert(ne_event_counter == 1 && recipient->nevents);
        } else if (interruption == 1) {
            unlink_char(ch, recipient, LNK_RIDING);
        } else if (interruption == 2) {
            clear_all_links(ch);
            char_from_room(ch);
            char_to_room(ch, 4, -1);
        } else {
            // Generic victim events must still cancel; the carrier event survives.
            assert(add_event(event_wait, 10, other, ch, nullptr, 0, nullptr, 0));
            assert(ne_event_counter == 2);
            clear_all_links(ch);
            assert(ne_event_counter == 1 && !other->nevents);
        }
        int callbacks = 0;
        while (recipient->nevents) {
            assert(++callbacks < 40);
            run_event(recipient);
        }
        assert(ne_event_counter == 0 && event_pool.objs_used == 0);
        assert(recipient->in_room == 2 && TRANSPORT_STATE(recipient) == TRANSPORT_STATE_WAITING);
        assert(recipient->specials.z_cord == 0 && !GET_MOUNT(ch));
        assert(link_pool.objs_used == 0);
    }
    visit(2);
    command(CMD_BUY, "1");
    command(CMD_GIVE, "ticket carrier");
    while (recipient->nevents) run_event(recipient);
    assert(ch->in_room == 1 && ch->specials.z_cord == 0);
    // Free the passenger between callbacks and inside recursive room entry.
    for (bool during_move : {false, true}) {
        visit(2);
        command(CMD_BUY, "1");
        command(CMD_GIVE, "ticket carrier");
        if (during_move) {
            entry_hook = [](P_char actor) {
                if (IS_PC(actor)) {
                    entry_hook = nullptr;
                    extract_char(actor);
                }
            };
        }
        run_event(recipient);
        if (!during_move) extract_char(ch);
        while (recipient->nevents) run_event(recipient);
        assert(recipient->in_room == 2 && recipient->specials.z_cord == 0);
        assert(TRANSPORT_STATE(recipient) == TRANSPORT_STATE_WAITING);
        ch = player(&pc, "Explorer");
        GET_COPPER(ch) = 1000000;
    }
    // Owner extraction still disarms the carrier's continuation.
    visit(2);
    command(CMD_BUY, "1");
    command(CMD_GIVE, "ticket carrier");
    clear_all_links(recipient);
    disarm_char_nevents(recipient, nullptr);
    assert(ne_event_counter == 0 && event_pool.objs_used == 0 && link_pool.objs_used == 0);
    // Room specials may extract the carrier during occupied or empty movement.
    for (bool empty_return : {false, true}) {
        transport_land_at_home(recipient, 2);
        visit(2);
        command(CMD_BUY, "1");
        command(CMD_GIVE, "ticket carrier");
        if (empty_return) {
            while (GET_MOUNT(ch)) run_event(recipient);
        }
        entry_hook = [](P_char actor) {
            if (IS_NPC(actor)) {
                entry_hook = nullptr;
                extract_char(actor);
            }
        };
        run_event(recipient);
        assert(ne_event_counter == 0 && event_pool.objs_used == 0 && link_pool.objs_used == 0);
        initialize_transport();
        visit(2);
        recipient->specials.position = STAT_NORMAL;
    }
    pc.learned_flight_stops |= uint64_t{1} << 4;
    // Refused departure/placement must retain one home-recovery continuation.
    for (bool empty_return : {false, true}) {
        for (bool refuse_entry : {false, true}) {
            visit(2);
            command(CMD_BUY, "2");
            command(CMD_GIVE, "ticket carrier");
            if (empty_return) while (GET_MOUNT(ch)) run_event(recipient);
            else run_event(recipient);
            if (refuse_entry) refused_entry = recipient;
            else departure_hook = [](P_char actor) -> int {
                return IS_NPC(actor) ? ROOM_PROC_LEAVE_VETO : FALSE;
            };
            run_event(recipient);
            assert(TRANSPORT_STATE(recipient) == TRANSPORT_STATE_MOVING);
            assert(TRANSPORT_ROUTE(recipient) == -1 && recipient->nevents);
            assert(ne_event_counter == 1 && !GET_RIDER(recipient));
            run_event(recipient); // A persistent veto/refusal still retains one retry.
            assert(ne_event_counter == 1 && TRANSPORT_STATE(recipient) == TRANSPORT_STATE_MOVING);
            refused_entry = nullptr;
            departure_hook = nullptr;
            while (recipient->nevents) run_event(recipient);
            assert(recipient->in_room == 2 && recipient->specials.z_cord == 0);
            assert(TRANSPORT_STATE(recipient) == TRANSPORT_STATE_WAITING);
            assert(!GET_MOUNT(ch) && ne_event_counter == 0);
        }
    }
    // Source hooks may redirect, remove, or replace the occupied/empty carrier.
    for (bool empty_return : {false, true}) {
        for (int outcome = 0; outcome < 3; ++outcome) {
            visit(2);
            command(CMD_BUY, "2");
            command(CMD_GIVE, "ticket carrier");
            if (empty_return) while (GET_MOUNT(ch)) run_event(recipient);
            else run_event(recipient);
            const int source = recipient->in_room;
            departure_hook = outcome == 0 ? +[](P_char actor) -> int {
                if (IS_NPC(actor)) {
                    departure_hook = nullptr;
                    char_from_room(actor);
                    char_to_room(actor, 6, -1);
                }
                return FALSE;
            } : outcome == 1 ? +[](P_char actor) -> int {
                if (IS_NPC(actor)) {
                    departure_hook = nullptr;
                    extract_char(actor);
                }
                return FALSE;
            } : +[](P_char actor) -> int {
                if (IS_NPC(actor)) {
                    departure_hook = nullptr;
                    clear_all_links(actor);
                    disarm_char_nevents(actor, nullptr);
                    ++character_removal_generation;
                    ++actor->runtime_id; // Same storage now belongs to another character.
                    TRANSPORT_STATE(actor) = TRANSPORT_STATE_WAITING;
                    TRANSPORT_ROUTE(actor) = -1;
                    TRANSPORT_STEP(actor) = 0;
                }
                return FALSE;
            };
            run_event(recipient);
            assert(ne_event_counter == 0 && event_pool.objs_used == 0 && link_pool.objs_used == 0);
            if (outcome == 0) {
                assert(recipient->in_room == 2 && TRANSPORT_STATE(recipient) == TRANSPORT_STATE_WAITING);
            } else if (outcome == 1) {
                assert(!char_in_list(recipient));
                initialize_transport();
            } else {
                assert(recipient->in_room == source && TRANSPORT_STEP(recipient) == 0);
                assert(TRANSPORT_ROUTE(recipient) == -1);
                transport_land_at_home(recipient, 2);
            }
            visit(2);
        }
    }
    // A legacy chain's earlier leave hook may remove a later queued traveler.
    visit(2);
    command(CMD_BUY, "2");
    command(CMD_GIVE, "ticket carrier");
    run_event(recipient);
    char_from_room(other);
    char_to_room(other, ch->in_room, -1);
    link_char(other, ch, LNK_RIDING);
    other->specials.z_cord = 10;
    departure_hook = [](P_char actor) -> int {
        if (IS_PC(actor)) {
            departure_hook = nullptr;
            extract_char(find_player_by_name("Other"));
        }
        return FALSE;
    };
    run_event(recipient);
    assert(!char_in_list(other));
    assert(ch->in_room == 2 && ch->specials.z_cord == 0 && !GET_MOUNT(ch));
    assert(recipient->in_room == 2 && TRANSPORT_STATE(recipient) == TRANSPORT_STATE_WAITING);
    assert(ne_event_counter == 0 && link_pool.objs_used == 0);
    other = player(&other_pc, "Other");
    // Recursive occupied movement and home landing revalidate both actors.
    for (bool home_recovery : {false, true}) {
        for (bool remove_carrier : {false, true}) {
            visit(2);
            command(CMD_BUY, "2");
            command(CMD_GIVE, "ticket carrier");
            run_event(recipient);
            if (home_recovery) TRANSPORT_STEP(recipient) = -1;
            departure_hook = remove_carrier ? +[](P_char actor) -> int {
                if (IS_PC(actor)) {
                    departure_hook = nullptr;
                    extract_char(recipient);
                }
                return FALSE;
            } : +[](P_char actor) -> int {
                if (IS_PC(actor)) {
                    departure_hook = nullptr;
                    extract_char(actor);
                }
                return FALSE;
            };
            run_event(recipient);
            while (char_in_list(recipient) && recipient->nevents) run_event(recipient);
            assert(ne_event_counter == 0 && event_pool.objs_used == 0 && link_pool.objs_used == 0);
            if (remove_carrier) {
                assert(ch->in_room != NOWHERE && !GET_MOUNT(ch));
                assert(!char_in_list(recipient));
                initialize_transport();
            } else {
                assert(recipient->in_room == 2 && TRANSPORT_STATE(recipient) == TRANSPORT_STATE_WAITING);
                ch = player(&pc, "Explorer");
                GET_COPPER(ch) = 1000000;
            }
        }
    }
    visit(2);
    command(CMD_BUY, "1");
    command(CMD_GIVE, "ticket carrier");
    while (recipient->nevents) run_event(recipient);
    assert(ch->in_room == 1 && ch->specials.z_cord == 0);
    clear_world();
    for (void *value : pool_storage) free(value);
    puts("production flight links, passenger teardown, victim cancellation and owner disarm passed");
}
'''

build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='flight-runtime-', dir=build) as temporary:
    source = Path(temporary) / 'harness.cpp'
    source.write_text(base + RUNTIME + links + movement + behavior + driver)
    binary = Path(temporary) / 'harness'
    subprocess.run(['g++', '-std=c++20', '-g', '-O1', '-ffunction-sections', '-fdata-sections',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                    '-I', str(ROOT / 'src'), '-I/usr/include/mysql', '-I/usr/include/libxml2',
                    str(source), str(ROOT / 'src/world/world_singletons.c'),
                    str(ROOT / 'src/combat/attack_continuation.c'),
                    '-Wl,--gc-sections', '-lbsd', str(HARNESS_STUBS), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True,
                   env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                        'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'})
