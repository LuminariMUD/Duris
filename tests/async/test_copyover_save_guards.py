#!/usr/bin/env python3
"""Fail-closed copyover ordering and live-process recovery contracts."""

from _paths import SRC, extract_function
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
copyover = (SRC / "copyover.c").read_text()
comm = (SRC / "comm.c").read_text()
db = (SRC / "db.c").read_text()

body = copyover[copyover.index("bool copyover_save("):copyover.index(
    "static P_char copyover_load_player", copyover.index("bool copyover_save(")
)]
recover = copyover[copyover.index("static P_char copyover_load_player"):]
# Compile the descriptor writer itself, not unrelated helpers inserted before
# write_mob_entry (telemetry wire helpers have their own executable regression).
descriptor_start = copyover.index("static int write_desc_entry(")
descriptor_end = copyover.index("{", descriptor_start) + 1
depth = 1
while depth:
    depth += (copyover[descriptor_end] == "{") - (copyover[descriptor_end] == "}")
    descriptor_end += 1
descriptor_capture = copyover[descriptor_start:descriptor_end]
linkdead_saves = body[body.index("\tfor (ch = character_list;", body.index("// Neither handoff")):
                      body.index("\t// Preserve custom shop item state")]
save = body.index("persistence_save_character_terminal")
flush = body.index("persistence_flush_all_character_saves")
drain = body.index("player_save_pipeline_drain")
publish = body.index("renameat2(AT_FDCWD, copyover_tmp")
prepare_client = body.index("fd_flags.prepare(d->descriptor, inherit)")
finish_compression = body.index("compress_end(d, 1)")
progress_notice = body.index("If disconnected, please reconnect")
execute = body.index("execl(")

checks = {
    "copyover returns failure": body.count("return false;") >= 10,
    "copyover refuses sessions that cannot survive exec before any save or close":
        body.index("non-preservable connection") < save and
        "d->connected == CON_PLAYING" in body[:save],
    "ships precede characters": body.index("drain_pending_ship_saves") < save,
    "lockers precede characters": body.index("locker_async_drain") < save,
    "connected saves precede remaining flush": save < flush,
    "copyover terminal saves require database acknowledgement":
        "persistence_save_character_terminal_database_acknowledged(" in body and
        "persistence_save_character_terminal(d->character" not in body,
    "both modes save descriptorless PCs before publication":
        body.index("if (!IS_NPC(ch) && !ch->desc") < flush and
        "if (!copyover_preserve_world)" not in body[save:flush],
    "all saves precede publication": flush < publish,
    "pipeline drain precedes publication": flush < drain < publish,
    "pipeline drain is bounded": "player_save_pipeline_drain(30000)" in body,
    "copyover abort reopens pipeline": "player_save_pipeline_resume();" in
                                       copyover[copyover.index("static void notify_copyover_failure"):
                                                copyover.index("static int write_desc_entry", copyover.index("static void notify_copyover_failure"))],
    "no premature descriptor close": "close(d->descriptor)" not in body,
    "prepared fds and drained MCCP precede publication": prepare_client < finish_compression < publish,
    "publication precedes progress notice": publish < progress_notice < execute,
    "replacement validates listeners and commits Redis before accepting commands":
        comm.index("copyover_recover(&recovered_mother_desc") <
        comm.index("redis_world_discard_for_copyover()") < comm.index("copyover_commit_boot()") <
        comm.index('fprintf(stderr, "Entering game loop.'),
    "failed exec retires its own publication": execute < body.rindex("consume_copyover_image(published_path, validated)"),
    "failure says server remains live": "server remains live" in body,
    "copyover runs inside live game loop": "copyover_save(s, S, WS)" in
                                           comm[comm.index("void game_loop("):],
    "typed workers stop only after game loop returns": "critical_command_coordinator_shutdown();" in
                                                       comm[comm.index("game_loop(port, sslport);"):],
    "legacy raw workers are not stopped at shutdown": "persistence_stop_scalar_event_worker();" not in
                                                       comm,
    "failure resumes game loop": "goto resume_game_loop;" in comm,
    "failed recovery uses graceful shutdown":
        "copyover recovery failed; requesting graceful cold restart" in comm and
        "_reboot = 1;" in comm and
        "exit(1);" not in comm[comm.index("// Copyover recovery needs the descriptor pool."):
                               comm.index("// redis crash recovery - restore world state")],
    "copyover defers SQL corpse restoration":
        "if (!copyover_restores_world())" in db[db.index("-- Player corpses") - 500:
                                     db.index("Reloading SavedItems")],
    "copyover defers SQL saved-ground restoration":
        "if (!copyover_restores_world())" in db[db.index("Saved ground/storage objects"):
                                     db.index("-- Shopkeepers")],
    "shutdown names what it could not write":
        "report_unwritten_saves(player_save_pipeline_finish(" in comm and "not_written" in comm,
    "no destructive restart fallback": "refusing fallback exit" in comm,
    "copyover reloads durable player inventory and pets":
        "request.include_items = true;" in recover and
        "request.include_pets = true;" in recover and
        "restoreItemsOnly(ch, 0)" not in recover,
    "copyover refreshes artifact custody after an overlapping writer":
        recover.index("player_load_pipeline_wait(") <
        recover.index("!player_load_items_read_current(result)") <
        recover.index("persistence_writer_wait_idle(remaining)") <
        recover.index("player_load_pipeline_execute_sync(") <
        recover.index("player_load_materialize(player, result)"),
    "copyover places the materialized pet graph": "player_load_pets_place(ch);" in recover,
    "copyover does not rebuild descriptor pets as permanent prototypes":
        "setup_pet(pet, ch, -1" not in recover and
        "desc_entry.pet_vnums[p]" not in recover,
    "copyover keeps materialized inventory attached": "reset_char(ch);" not in recover,
    "descriptor capture requires the player's actual pet link":
        "GET_MASTER(f->follower) == ch" in descriptor_capture,
    "world mob capture excludes every linked pet":
        "copyover_world_mob(ch)" in body and "!GET_MASTER(mob)" in copyover,
    "minimal copyover preserves its world dataset":
        'execl(DMS_RUNTIME_BINARY, "dms", "--minimal", "-C", exec_buf' in body,
}

for name, passed in checks.items():
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")
assert all(checks.values())

HARNESS = r'''
#include "core/utils.h"
#include "core/files.h"
#include "account/account.h"
#include "ships/ships.h"
#include "net/mxp.h"
#include "persistence/copyover.h"
#include <cassert>
#include <cstdlib>
#include <cstdio>

index_data mob_indexes[2] = {};
P_index mob_index = mob_indexes;
bool copyover_preserve_world = true;
room_data rooms[4] = {};
P_room world = rooms;
const int top_of_world = 3;
static ShipData ship = {};
static bool ship_exists = true;
P_ship get_ship_from_char(P_char) { return &ship; }
P_ship find_ship_by_database_id(uint32_t id)
{
    return ship_exists && id == 42 ? &ship : nullptr;
}
int real_room(int vnum)
{
    for (int room = 0; room <= top_of_world; ++room)
        if (rooms[room].number == vnum) return room;
    return NOWHERE;
}

int panic_corruption_int(const char *, const char *, ...)
{
    std::abort();
}

P_char get_linked_char(P_char ch, ush_int type)
{
    for (char_link_data *link = ch->linking; link; link = link->next_linking)
        if (link->type == type) return link->linked;
    return nullptr;
}
static int saved_pid, save_calls;
static bool save_ok = true, notified;
P_char character_list;
bool persistence_save_character_terminal_database_acknowledged(P_char ch, int intent)
{
    assert(intent == RENT_CRASH);
    saved_pid = GET_PID(ch);
    ++save_calls;
    return save_ok;
}
static void notify_copyover_failure(const char *) { notified = true; }
static bool save_linkdead_players()
{
    P_char ch;
''' + linkdead_saves + r'''
    return true;
}
''' + extract_function('player_snapshot_capture.c', 'int player_save_room_vnum(') + '\n' + \
    descriptor_capture + '\n' + extract_function('copyover.c', 'static int copyover_player_room(') + r'''
int main()
{
    {
        char_data locker = {}, linkdead = {}, connected = {}, npc = {};
        pc_only_data locker_pc = {}, linkdead_pc = {}, connected_pc = {};
        locker.only.pc = &locker_pc;
        linkdead.only.pc = &linkdead_pc;
        connected.only.pc = &connected_pc;
        locker.player.name = const_cast<char *>("account.fixture.1.locker");
        linkdead_pc.pid = 77;
        connected_pc.pid = 78;
        descriptor_data descriptor = {};
        connected.desc = &descriptor;
        SET_BIT(npc.specials.act, ACT_ISNPC);
        character_list = &locker;
        locker.next = &npc;
        npc.next = &connected;
        connected.next = &linkdead;
        assert(save_linkdead_players());
        assert(save_calls == 1 && saved_pid == 77 && !notified);
        save_ok = false;
        assert(!save_linkdead_players());
        assert(save_calls == 2 && saved_pid == 77 && notified);
        character_list = nullptr;
    }
    char_data owner = {}, pet = {}, unrelated = {};
    pc_only_data owner_pc = {};
    npc_only_data pet_npc = {}, unrelated_npc = {};
    owner.only.pc = &owner_pc;
    owner.player.name = const_cast<char *>("owner");
    owner.in_room = pet.in_room = unrelated.in_room = 0;
    pet.only.npc = &pet_npc;
    unrelated.only.npc = &unrelated_npc;
    SET_BIT(pet.specials.act, ACT_ISNPC);
    SET_BIT(unrelated.specials.act, ACT_ISNPC);
    pet_npc.R_num = 0;
    unrelated_npc.R_num = 1;
    mob_indexes[0].virtual_number = 1201;
    mob_indexes[1].virtual_number = 1202;
    GET_HIT(&pet) = GET_MAX_HIT(&pet) = 100;
    GET_HIT(&unrelated) = GET_MAX_HIT(&unrelated) = 100;
    char_link_data pet_link = {};
    pet_link.type = LNK_PET;
    pet_link.linking = &pet;
    pet_link.linked = &owner;
    pet.linking = &pet_link;
    follow_type unrelated_follow{&unrelated, nullptr};
    follow_type pet_follow{&pet, &unrelated_follow};
    owner.followers = &pet_follow;
    descriptor_data descriptor = {};
    descriptor.descriptor = 10;
    descriptor.character = &owner;
    acct_entry account = {};
    account.acct_name = const_cast<char *>("testaccount");
    descriptor.account = &account;
    rooms[0].number = VROOM_SHIPS_START;
    rooms[1].number = 100;
    rooms[2].number = VROOM_SHIPS_START + 1;
    ship.anchor = 100;
    ship.room_count = 1;
    ship.room[0].roomnum = rooms[0].number;
    ship.db_id = 42;
    SET_BIT(ship.flags, LOADED);
    descriptor.gmcp_supports = 7;
    descriptor.gmcp_interests = 2;
    descriptor.gmcp_session_generation = 9007199254740993ULL;
    descriptor.gmcp_session_body_revision = 3;
    descriptor.gmcp_input_sequence = 12345678901234567890ULL;
    descriptor.gmcp_command_receipts = true;
    strcpy(descriptor.gmcp_session_context,"0123456789abcdef0123456789abcdef");
    FILE *file = tmpfile();
    assert(file);
    assert(write_desc_entry(file, &descriptor));
    rewind(file);
    copyover_desc saved = {};
    assert(fread(&saved, sizeof(saved), 1, file) == 1);
    fclose(file);
    assert(saved.num_pets == 1);
    assert(saved.gmcp_supports == 7 && saved.gmcp_interests == 2);
    assert(saved.gmcp_session_generation == 9007199254740993ULL && saved.gmcp_session_body_revision == 3);
    assert(saved.gmcp_input_sequence == 12345678901234567890ULL && saved.gmcp_command_receipts == 1);
    assert(!strcmp(saved.gmcp_session_context, descriptor.gmcp_session_context));

    assert(saved.pet_vnums[0] == 1201);
    assert(!strcmp(saved.account_name, "testaccount"));
    assert(saved.ship_id == 42 && saved.ship_room_slot == 0 && saved.room == 100);
    ship.room[0].roomnum = rooms[2].number;
    assert(copyover_player_room(saved, 20, false, &owner) == 2);
    assert(copyover_player_room(saved, 20, true, &owner) == 2);
    ship_exists = false;
    assert(copyover_player_room(saved, 20, false, &owner) == 1);
    ship_exists = true;
    saved.ship_room_slot = 2;
    assert(copyover_player_room(saved, 20, true, &owner) == 1);
    saved.room = 1;
    assert(copyover_player_room(saved, 19, true, &owner) == 1);
    rooms[2].number = 65201;
    rooms[2].room_flags = ROOM_LOCKER;
    room_direction_data door = {};
    door.to_room = 1;
    rooms[2].dir_option[0] = &door;
    owner.in_room = 2;
    for (bool preserve : {false, true})
    {
        copyover_preserve_world = preserve;
        file = tmpfile();
        assert(file && write_desc_entry(file, &descriptor));
        rewind(file);
        assert(fread(&saved, sizeof(saved), 1, file) == 1);
        fclose(file);
        assert(saved.room == 100 && !saved.ship_id);
        assert(copyover_player_room(saved, 20, preserve, &owner) == 1);
    }
    puts("Copyover cabin identity survives pool reassignment and falls back ashore");
}
'''
with tempfile.TemporaryDirectory(prefix="duris-copyover-pet-owner-") as directory:
    source = Path(directory) / "copyover_pet_owner.cpp"
    binary = Path(directory) / "copyover_pet_owner"
    source.write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
                    str(source), "-lbsd", "-o", str(binary)], cwd=root, check=True)
    subprocess.run([str(binary)], check=True)

print("copyover save guards passed")

# A completed SQL writer is not proof that the ship transaction committed.
assert copyover.index("player_save_pipeline_drain(30000)") < copyover.index("if (!sql_ship_write_pulse())") < copyover.index("/* Terminal player saves can dirty a locker")
