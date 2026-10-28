#!/usr/bin/env python3
"""Execute real Studio action/trigger handling across actor lifetime changes.

Game services are controlled fixtures. Production sp_execute, sp_expand,
sp_fire and sp_run are compiled under ASan/UBSan, including actions after an
extraction or a legitimate redirect and transfer continuation.
"""

import os
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


def structure(name):
    return extract_function("studioproc.c", f"struct {name}") + ";"


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "net/comm.h"
#include "combat/damage.h"
#include "mob/studioproc.h"
#include <cassert>
#include <cstring>
#include <cstdlib>
#include <new>
#include <string>
#include <vector>

extern P_room world;
extern int top_of_world;
extern P_index mob_index, obj_index;
'''

FIXTURE = r'''
#define SP_X_FIRED 1
#define SP_X_SELFGONE 2
static room_data rooms[3]{};
P_room world = rooms;
int top_of_world = 2;
static index_data indices[2]{};
P_index mob_index = indices, obj_index = indices;
P_char character_list = nullptr;
uint64_t character_removal_generation = 0;
static int sp_depth, callback_mode, transfer_mode, placements, commands, object_checks, echo_extract;
static std::vector<std::string> output;

enum { ordinary, name_freed, actor_deleted, actor_replaced, redirected, unrelated };
enum { transfer_normal, transfer_redirect, transfer_veto, transfer_delete, transfer_replace };

int char_in_list(const P_char ch) { return ch && ch == character_list; }
static int sp_room_of(sp_ctx *ctx) { return ctx->self_room; }
static const char *sp_self_name(sp_ctx *) { return "room"; }
static int sp_conds_pass(sp_trig *, sp_ctx *) { return true; }
static int sp_keyword_match(const char *, const char *) { return true; }
static int sp_char_get(P_char, int, int) { return 0; }
static void sp_char_set(P_char, int, int, int) {}
static int sp_state_get(sp_ctx *, int, int) { return 0; }
static void sp_state_set(sp_ctx *, int, int, int) {}
static int sp_obj_get(P_obj, int, int) { return 0; }
static void sp_obj_set(P_obj, int, int, int) {}
static P_char sp_mob_instance(int) { return nullptr; }
static P_obj sp_obj_instance(int) { return nullptr; }
static P_char sp_find_ally(sp_ctx *) { return nullptr; }
static void sp_execute_item_ability(sp_trig *, sp_ctx *, sp_action *) {}
static void sp_do_attack(sp_ctx *, sp_action *, int) {}
int number(int low, int) { return low; }
int dice(int, int) { return 1; }
int real_room(int vnum) { return vnum == 102 ? 2 : -1; }
int real_mobile(int) { return -1; }
int real_object(int) { ++object_checks; return -1; }
P_char read_mobile(int, int) { return nullptr; }
P_obj read_object_for_creation(int, int) { return nullptr; }
P_obj find_live_object(P_obj, uint64_t) { return nullptr; }
void obj_to_room(P_obj, int) {}
void obj_to_char(P_obj, P_char) {}
void extract_obj(P_obj, int) {}
void extract_char(P_char) {}
static void destroy_actor(P_char actor, bool delete_storage, bool replace);
void send_to_room(const char *text, int)
{
    output.emplace_back(text);
    if (echo_extract && character_list)
    {
        const int mode = echo_extract;
        echo_extract = 0;
        destroy_actor(character_list, mode == 2, mode == 3);
    }
}
void send_to_zone(int, const char *) {}
void send_to_char(const char *, P_char) {}
void do_say(P_char, char *, int) {}
void do_emote(P_char, char *, int) {}
void do_look(P_char, char *, int) {}
void act(const char *, int, P_char, P_obj, void *, int) {}
void CAP(char *text) { if (*text >= 'a' && *text <= 'z') *text -= 'a' - 'A'; }
bool MobCastSpell(P_char, P_char, P_obj, int, int) { return false; }
int raw_damage(P_char, P_char, double, unsigned int, damage_messages *, int *) { return 0; }
bool saves_spell(P_char, int) { return false; }
bool affected_by_spell(P_char, int) { return false; }
affected_type *affect_to_char(P_char, affected_type *) { return nullptr; }
void affect_from_char(P_char, int) {}
void update_pos(P_char) {}

static void destroy_actor(P_char actor, bool delete_storage, bool replace)
{
    ++character_removal_generation;
    std::free(actor->player.name);
    if (replace)
    {
        actor->~char_data();
        new (actor) char_data{};
        actor->runtime_id = 2;
        actor->in_room = 0;
        SET_POS(actor, POS_STANDING + STAT_NORMAL);
        actor->player.name = ::strdup("replacement");
        character_list = actor;
    }
    else if (delete_storage)
    {
        character_list = nullptr;
        delete actor;
    }
    else
    {
        SET_POS(actor, STAT_DEAD);
        character_list = nullptr;
    }
}

static int sp_do_command(P_char actor, const char *)
{
    ++commands;
    if (callback_mode == name_freed) destroy_actor(actor, false, false);
    else if (callback_mode == actor_deleted) destroy_actor(actor, true, false);
    else if (callback_mode == actor_replaced) destroy_actor(actor, false, true);
    else if (callback_mode == redirected) actor->in_room = 1;
    else if (callback_mode == unrelated) ++character_removal_generation;
    return true;
}

void char_from_room(P_char actor)
{
    switch (transfer_mode)
    {
    case transfer_normal: actor->in_room = NOWHERE; break;
    case transfer_redirect: actor->in_room = 1; break;
    case transfer_veto: break;
    case transfer_delete: destroy_actor(actor, true, false); break;
    case transfer_replace: destroy_actor(actor, false, true); break;
    }
}
bool char_to_room(P_char actor, int room, int)
{
    assert(actor && actor->in_room == NOWHERE);
    ++placements;
    actor->in_room = room;
    return true;
}
'''

DRIVER = r'''
static P_char make_actor()
{
    auto *actor = new char_data{};
    actor->runtime_id = 1;
    actor->in_room = 0;
    actor->player.name = ::strdup("alice");
    SET_POS(actor, POS_STANDING + STAT_NORMAL);
    character_list = actor;
    return actor;
}
static void cleanup(P_char actor, bool deleted)
{
    if (!deleted)
    {
        if (character_list == actor) std::free(actor->player.name);
        delete actor;
    }
    character_list = nullptr;
}
static void reset()
{
    output.clear();
    callback_mode = ordinary;
    transfer_mode = transfer_normal;
    placements = 0;
    commands = 0;
    object_checks = 0;
    echo_extract = 0;
    sp_depth = 0;
    character_removal_generation = 0;
}
static sp_trig action_trigger(int action)
{
    sp_trig t{};
    t.event = SP_EV_ENTER;
    t.chance = 100;
    t.num_actions = 3;
    t.actions[0].op = action;
    t.actions[0].who = SP_WHO_ACTOR;
    t.actions[0].num = 102;
    t.actions[0].text = const_cast<char *>("quit");
    t.actions[1].op = SP_A_ECHO;
    t.actions[1].text = const_cast<char *>("$n enters");
    t.actions[2].op = SP_A_BLOCK;
    return t;
}
static sp_ctx context(P_char actor)
{
    sp_ctx cx{};
    cx.targ = SP_T_ROOM;
    cx.self_room = 0;
    cx.actor = actor;
    return cx;
}
int main()
{
    for (int mode : {name_freed, actor_deleted, actor_replaced, redirected, unrelated})
    {
        reset();
        P_char actor = make_actor();
        sp_trig trigger = action_trigger(SP_A_DO);
        sp_ctx cx = context(actor);
        callback_mode = mode;
        assert(sp_execute(&trigger, &cx) & SP_X_FIRED);
        assert(cx.blocked && output.size() == 1);
        if (mode == redirected || mode == unrelated)
        {
            assert(cx.actor == actor);
            assert(output[0].find("alice enters") != std::string::npos);
            assert(actor->in_room == (mode == redirected ? 1 : 0));
        }
        else
        {
            assert(cx.actor == nullptr);
            assert(output[0].find("someone enters") != std::string::npos);
        }
        cleanup(actor, mode == actor_deleted);
    }
    for (int mode : {transfer_normal, transfer_redirect, transfer_veto,
                     transfer_delete, transfer_replace})
    {
        reset();
        P_char actor = make_actor();
        sp_trig trigger = action_trigger(SP_A_TRANSFER);
        trigger.num_actions = 5;
        trigger.actions[1].op = SP_A_DO;
        trigger.actions[1].who = SP_WHO_ACTOR;
        trigger.actions[1].text = const_cast<char *>("noop");
        trigger.actions[2].op = SP_A_GIVE;
        trigger.actions[3].op = SP_A_ECHO;
        trigger.actions[3].text = const_cast<char *>("$n enters");
        trigger.actions[4].op = SP_A_BLOCK;
        sp_ctx cx = context(actor);
        transfer_mode = mode;
        assert(sp_execute(&trigger, &cx) & SP_X_FIRED);
        assert(cx.blocked && output.size() == 1);
        if (mode == transfer_normal)
        {
            assert(cx.actor == actor && actor->in_room == 2 && placements == 1);
            assert(commands == 1 && object_checks == 1);
            assert(output[0].find("alice enters") != std::string::npos);
        }
        else
        {
            assert(cx.actor == nullptr && placements == 0);
            assert(commands == 0 && object_checks == 0);
            assert(output[0].find("someone enters") != std::string::npos);
            if (mode == transfer_redirect || mode == transfer_veto)
                assert(actor->in_room == (mode == transfer_redirect ? 1 : 0));
        }
        cleanup(actor, mode == transfer_delete);
    }
    for (int mode : {actor_deleted, actor_replaced})
    {
        reset();
        P_char actor = make_actor();
        sp_ctx cx = context(actor);
        sp_trig trigger = action_trigger(SP_A_ONEOF);
        trigger.num_actions = 5;
        trigger.actions[0].count = 2;
        trigger.actions[1].op = SP_A_DO;
        trigger.actions[1].who = SP_WHO_ACTOR;
        trigger.actions[1].text = const_cast<char *>("quit");
        trigger.actions[2].op = SP_A_BLOCK;
        trigger.actions[3].op = SP_A_ECHO;
        trigger.actions[3].text = const_cast<char *>("$n enters");
        trigger.actions[4].op = SP_A_BLOCK;
        callback_mode = mode;
        assert(sp_execute(&trigger, &cx) & SP_X_FIRED);
        assert(cx.actor == nullptr && cx.blocked && output.size() == 1);
        assert(output[0].find("someone enters") != std::string::npos);
        cleanup(actor, mode == actor_deleted);
    }
    // Kill triggers can start with a dead but still-linked victim. Both actions
    // in one trigger see its name, while the next trigger sees no actor.
    reset();
    P_char dead = make_actor();
    SET_POS(dead, STAT_DEAD);
    sp_ctx dead_cx = context(dead);
    sp_trig dead_first = action_trigger(SP_A_ECHO);
    sp_trig dead_second = action_trigger(SP_A_ECHO);
    dead_first.event = dead_second.event = SP_EV_KILL;
    dead_first.num_actions = 2;
    dead_first.actions[0].text = const_cast<char *>("$n falls");
    dead_first.actions[1].op = SP_A_ECHO;
    dead_first.actions[1].text = const_cast<char *>("$n is defeated");
    dead_second.num_actions = 1;
    dead_second.actions[0].text = const_cast<char *>("$n remains");
    dead_first.next = &dead_second;
    sp_rec dead_record{};
    dead_record.trigs = &dead_first;
    assert(sp_run(&dead_record, SP_EV_KILL, &dead_cx, nullptr, 0) & SP_X_FIRED);
    assert(output.size() == 3);
    assert(output[0].find("alice falls") != std::string::npos);
    assert(output[1].find("alice is defeated") != std::string::npos);
    assert(output[2].find("someone remains") != std::string::npos);
    cleanup(dead, false);

    // Removal or reuse of a dead victim between actions must still be detected.
    for (int mode : {1, 2, 3})
    {
        reset();
        P_char actor = make_actor();
        SET_POS(actor, STAT_DEAD);
        sp_ctx cx = context(actor);
        sp_trig trigger = action_trigger(SP_A_ECHO);
        trigger.num_actions = 2;
        trigger.actions[0].text = const_cast<char *>("$n falls");
        trigger.actions[1].op = SP_A_ECHO;
        trigger.actions[1].text = const_cast<char *>("$n is defeated");
        echo_extract = mode;
        assert(sp_execute(&trigger, &cx) & SP_X_FIRED);
        assert(cx.actor == nullptr && output.size() == 2);
        assert(output[0].find("alice falls") != std::string::npos);
        assert(output[1].find("someone is defeated") != std::string::npos);
        cleanup(actor, mode == 2);
    }
    reset();
    P_char actor = make_actor();
    sp_ctx cx = context(actor);
    sp_trig first = action_trigger(SP_A_DO), second = action_trigger(SP_A_ECHO);
    first.num_actions = 1;
    second.num_actions = 1;
    second.actions[0].text = const_cast<char *>("$n enters");
    first.next = &second;
    sp_rec record{};
    record.trigs = &first;
    callback_mode = actor_deleted;
    assert(sp_run(&record, SP_EV_ENTER, &cx, nullptr, 0) & SP_X_FIRED);
    assert(cx.actor == nullptr && output.size() == 1);
    assert(output[0].find("someone enters") != std::string::npos);
    cleanup(actor, true);
    std::puts("Studio action and trigger actor lifetime: extraction, replacement, redirects and transfer cases passed");
}
'''

parts = [
    PRELUDE,
    *(structure(name) for name in ("sp_cond", "sp_action", "sp_trig", "sp_rec", "sp_ctx")),
    FIXTURE,
    extract_function("studioproc.c", "static void sp_cat("),
    extract_function("studioproc.c", "static void sp_expand("),
    extract_function("studioproc.c", "static void sp_revalidate_actor("),
    extract_function("studioproc.c", "static int sp_execute("),
    extract_function("studioproc.c", "static int sp_fire("),
    extract_function("studioproc.c", "static int sp_run("),
    DRIVER,
]

build_root = Path(os.environ.get("BIN_ROOT", ROOT / "bin")) / "tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="studio-actor-lifetime-", dir=build_root) as directory:
    harness = Path(directory) / "harness.cpp"
    binary = Path(directory) / "harness"
    harness.write_text("\n".join(parts), encoding="utf-8")
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-ffunction-sections", "-fdata-sections", f"-I{ROOT / 'src'}",
        str(harness), str(HARNESS_STUBS), "-Wl,--gc-sections", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
