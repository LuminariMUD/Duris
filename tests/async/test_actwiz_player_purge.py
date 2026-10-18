#!/usr/bin/env python3
"""Run the real staff purge command with save/floor services under ASan/UBSan.

The harness injects snapshot rejection and locker/item-movement conditions.
Production container linking and unequip run unchanged; objects and characters are freed,
including merged coins;
external persistence, account teardown and unrelated command modes are stubbed.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

FUNCTIONS = "\n\n".join(extract_function("actwiz.c", signature) for signature in (
    "static void purge_drop_item(",
    "void do_purge(P_char ch, char *argument, int /*cmd*/)",
)) + "\n\n" + "\n\n".join(extract_function("handler.c", signature) for signature in (
    "bool obj_can_nest(", "bool obj_is_in_container(",
    "void obj_to_obj(P_obj obj, P_obj obj_to)", "void obj_from_obj(P_obj obj)",
    "P_obj unequip_char(P_char ch, int pos, bool saving)",
))

HARNESS = r'''
#include "core/prototypes.h"
#include "core/files.h"
#include "core/mm.h"
#include "core/utils.h"
#include "core/utility.h"
#include "net/comm.h"
#include "ships/ships.h"
#include "sql/sql.h"
#include "sql/sql_player.h"
#include "world/vnum.obj.h"
#include "player/player_save_pipeline.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <map>
#include <set>
#include <string>

static room_data rooms[4] = {};
P_room world = rooms;
static index_data indices[3] = {};
P_index obj_index = indices;
int top_of_objt = 100;
struct mm_ds *dead_mob_pool = nullptr, *dead_pconly_pool = nullptr;
ShipObjHash::ShipObjHash() {}
ShipObjHash shipObjHash;
P_ship ShipObjHash::find(P_obj) { abort(); }
bool ShipObjHash::erase(P_ship) { abort(); }
void delete_ship(P_ship, bool) { abort(); }
static P_char victim;
static player_save_pipeline_result save_result = player_save_pipeline_result::queued;
static bool busy, collector_busy, collector_ready = true, snapshot_accepted, redirect, recording = true;
static int saves, extracted, logout_count, offline_count, faction_delta, announcements;
static std::string output;
static std::set<P_obj> live;
static std::map<uint64_t, int> recovered;

char *one_argument(const char *arg, char *name) { strcpy(name, arg); return nullptr; }
P_char get_char_room_vis(P_char, const char *) { return victim; }
P_obj get_obj_in_list_vis(P_char, const char *, P_obj, bool) { abort(); }
int IS_MORPH(P_char) { return false; }
int real_object(const int) { abort(); }
void send_to_char(const char *text, P_char) { output += text; }
void send_to_room(const char *, int) { abort(); }
void act(const char *, int, P_char, P_obj, void *, int) { ++announcements; }
void update_ingame_racewar(int delta) { assert(snapshot_accepted); faction_delta += delta; }
bool item_movement_transaction_player_busy(P_char) { return busy; }
bool collector_transaction_player_busy(P_char) { return collector_busy; }
bool collector_service_recover_player(P_char) { return collector_ready; }
int calculate_save_room(P_char, int type, int room) {
    assert(type == RENT_QUIT && room == NOWHERE); return 1234;
}
player_save_pipeline_result player_save_pipeline_request(P_char ch, player_component_mask_t parts,
                                                         int type, int room) {
    ++saves;
    assert(!collector_busy);
    assert(parts == PLAYER_CHECKPOINT_COMPONENT_ALL && type == RENT_QUIT && room == 1234);
    assert(!rooms[1].contents && !rooms[2].contents);
    assert(!ch->carrying);
    assert(ch->only.pc->prestige == 43);
    for (auto item : ch->equipment) assert(!item);
    assert(!logout_count && !offline_count && !faction_delta && !announcements);
    snapshot_accepted = save_result == player_save_pipeline_result::queued ||
                        save_result == player_save_pipeline_result::coalesced;
    return save_result;
}
void sql_log_player_login(P_char, const char *what) {
    assert(snapshot_accepted && !strcmp(what, "logout")); ++logout_count;
}
void redis_player_offline(P_char) { assert(snapshot_accepted); ++offline_count; }
void unlink_item(P_obj *head, P_obj item) {
    while (*head && *head != item) head = &(*head)->next_content;
    assert(*head == item); *head = item->next_content;
    item->next_content = nullptr; item->loc_p = LOC_NOWHERE; item->loc.inside = nullptr;
}
void obj_from_char(P_obj item) {
    assert(snapshot_accepted || !recording);
    unlink_item(&item->loc.carrying->carrying, item);
}
P_char training_dummy_item_owner(P_obj) { return nullptr; }
void add_weight(P_obj, int) {}
static void resync_reducing_container(P_obj) {}
static void mark_container_dirty(P_obj) {}
void artifact_update_location_sql(P_obj) {}
void writeSavedItem(P_obj) { abort(); }
void item_actions_source_leaving(P_obj) { assert(snapshot_accepted || !recording); }
void clear_links(P_char, P_obj, int) {}
void all_affects(P_char, int) {}
void balance_affects(P_char) {}
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
int encumbrance_weight(int weight) { return weight; }
static void mark_char_or_owner_dirty(P_char) {}
void extract_obj(P_obj item, int) {
    assert(live.count(item));
    if (OBJ_ROOM(item)) unlink_item(&rooms[item->loc.room].contents, item);
    else if (OBJ_INSIDE(item)) obj_from_obj(item);
    while (item->contains) extract_obj(item->contains, TRUE);
    live.erase(item); delete item;
}
void obj_to_room(P_obj item, int room) {
    assert(snapshot_accepted && OBJ_NOWHERE(item));
    // Model the production coin-merge lifetime, and water-room redirection.
    if (OBJ_VNUM(item) == VOBJ_COINS) { extract_obj(item, TRUE); return; }
    if (redirect) room = 2;
    item->loc_p = LOC_ROOM; item->loc.room = room;
    item->next_content = rooms[room].contents; rooms[room].contents = item;
}
void record_tree(P_obj item, int room) {
    assert(!IS_SET(item->extra_flags, ITEM_TRANSIENT));
    if (item->obj_uid) { assert(!recovered.count(item->obj_uid)); recovered[item->obj_uid] = room; }
    for (P_obj child = item->contains; child; child = child->next_content) record_tree(child, room);
}
void redis_log_floor_drop(P_obj item, int room) {
    assert(snapshot_accepted && OBJ_ROOM(item));
    assert(room == world[item->loc.room].number); record_tree(item, room);
}
void extract_char_after_terminal_save(P_char ch) {
    assert(snapshot_accepted && !IS_ROOM(ch->in_room, ROOM_LOCKER));
    assert(!ch->carrying && logout_count == 1 && offline_count == 1);
    assert(ch->only.pc->prestige == 43);
    for (auto item : ch->equipment) assert(!item);
    assert(world[ch->in_room].people == ch);
    world[ch->in_room].people = ch->next_in_room;
    // The real terminal extractor owns account/descriptor cleanup. Free the
    // victim here so any subsequent access in do_purge is caught by ASan.
    if (ch->desc) { ch->desc->character = nullptr; ch->desc = nullptr; }
    delete ch->only.pc; delete ch; victim = nullptr; ++extracted;
}
void extract_char(P_char) { abort(); }
void free_char(P_char) { abort(); }
int checked_snprintf_at(const char *, int, char *, size_t, const char *, ...) { abort(); }
void *_mm_get(mm_ds *, const char *, int) { abort(); }
void ensure_pconly_pool() { abort(); }
char *skip_spaces(char *) { abort(); }
int restoreCharOnly(P_char, char *) { abort(); }
void delete_character(P_char, bool, std::function<void(character_delete_result)>) { abort(); }
''' + FUNCTIONS + r'''

P_obj make_item(uint64_t uid, bool transient = false, int rnum = 1) {
    P_obj item = new obj_data{}; live.insert(item);
    item->obj_uid = uid; item->R_num = rnum; item->loc_p = LOC_NOWHERE;
    item->type = rnum == 2 ? ITEM_MONEY : ITEM_CONTAINER;
    if (transient) SET_BIT(item->extra_flags, ITEM_TRANSIENT);
    return item;
}
int main(int argc, char **argv) {
    assert(argc == 2); const std::string test = argv[1];
    rooms[1].number = 100; rooms[2].number = 200;
    indices[1].virtual_number = 123; indices[2].virtual_number = VOBJ_COINS;
    char_data staff = {}; staff.player.level = OVERLORD; staff.in_room = 1;
    staff.player.name = const_cast<char *>("Staff"); staff.player.racewar = 1;
    descriptor_data descriptor = {};
    victim = new char_data{}; victim->only.pc = new pc_only_data{};
    victim->player.name = const_cast<char *>("Victim"); victim->player.level = 30;
    victim->player.racewar = 2; victim->in_room = 1;
    victim->next_in_room = &staff; world[1].people = victim;
    if (test != "linkdead") { victim->desc = &descriptor; descriptor.character = victim; }
    P_obj worn = make_item(10), bag = make_item(11), transient_bag = make_item(12, true);
    worn->type = test == "nonarmor" ? ITEM_WEAPON : ITEM_ARMOR;
    worn->value[2] = test == "negative_prestige" ? -7 : 7;
    const int original_prestige = 43 + (worn->type == ITEM_ARMOR ? worn->value[2] : 0);
    victim->only.pc->prestige = original_prestige;
    victim->equipment[0] = worn; worn->loc_p = LOC_WORN; worn->loc.wearing = victim;
    bag->loc_p = LOC_CARRIED; bag->loc.carrying = victim; victim->carrying = bag;
    bag->next_content = transient_bag;
    transient_bag->loc_p = LOC_CARRIED; transient_bag->loc.carrying = victim;
    P_obj temporary = make_item(13, true), permanent = make_item(14);
    P_obj promoted = make_item(15), inner = make_item(16, true), deepest = make_item(17);
    obj_to_obj(temporary, bag); obj_to_obj(permanent, bag); obj_to_obj(promoted, temporary);
    obj_to_obj(inner, transient_bag); obj_to_obj(deepest, inner);
    P_obj coin = make_item(18, false, 2); obj_to_obj(coin, transient_bag);
    if (test == "invalid") save_result = player_save_pipeline_result::invalid;
    if (test == "unavailable") save_result = player_save_pipeline_result::unavailable;
    if (test == "capture_failed") save_result = player_save_pipeline_result::capture_failed;
    if (test == "unchanged") save_result = player_save_pipeline_result::unchanged;
    if (test == "coalesced") save_result = player_save_pipeline_result::coalesced;
    if (test == "locker") SET_BIT(rooms[1].room_flags, ROOM_LOCKER);
    if (test == "busy") busy = true;
    if (test == "collector_pending") collector_busy = true;
    if (test == "collector") collector_ready = false;
    if (test == "redirect") redirect = true;
    if (test == "immortal") victim->player.level = MINLVLIMMORTAL;
    const bool refused = test == "invalid" || test == "unavailable" || test == "capture_failed" ||
                         test == "unchanged" || test == "locker" || test == "busy" ||
                         test == "collector" || test == "collector_pending";
    char argument[] = "Victim";
    do_purge(&staff, argument, 0);
    if (refused) {
        assert(victim && world[1].people == victim && victim->next_in_room == &staff);
        assert(victim->desc == &descriptor && descriptor.character == victim);
        assert(victim->equipment[0] == worn && victim->carrying == bag && bag->next_content == transient_bag);
        assert(victim->only.pc->prestige == original_prestige);
        assert(temporary->loc.inside == bag && promoted->loc.inside == temporary);
        assert(deepest->loc.inside == inner && inner->loc.inside == transient_bag);
        assert(live.size() == 9 && recovered.empty());
        assert(!extracted && !faction_delta && !offline_count && !logout_count && !announcements);
        assert(!rooms[1].contents && !rooms[2].contents && output.find("Ok.") == std::string::npos);
        assert(saves == ((test == "locker" || test == "busy" || test == "collector" ||
                         test == "collector_pending") ? 0 : 1));
        recording = false;
        extract_obj(unequip_char(victim, 0, false), TRUE);
        while (victim->carrying) { P_obj item = victim->carrying; obj_from_char(item); extract_obj(item, TRUE); }
        delete victim->only.pc; delete victim;
    } else {
        assert(saves == 1 && extracted == 1 && !victim && world[1].people == &staff);
        assert(!descriptor.character && faction_delta == (test == "immortal" ? 0 : -2));
        assert(output.find("Ok.") != std::string::npos);
        assert(live.size() == 5 && recovered.size() == 5);
        assert(permanent->loc.inside == bag && promoted->loc.inside == bag);
        assert(OBJ_ROOM(deepest));
        for (uint64_t uid : {10, 11, 14, 15, 17}) assert(recovered.at(uid) == (redirect ? 200 : 100));
        for (auto &room : rooms) while (room.contents) extract_obj(room.contents, TRUE);
    }
    assert(live.empty());
    printf("PASS %s\n", argv[1]);
}
'''

build_root = ROOT / "bin" / "tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="player-purge-", dir=build_root) as directory:
    path = Path(directory)
    (path / "test.cpp").write_text(HARNESS, encoding="utf-8")
    for backend in ("mysql", "flatfile"):
        defines = ["-D__NO_MYSQL__", "-Isrc/no_mysql"] if backend == "flatfile" else ["-I/usr/include/mysql"]
        binary = path / backend
        subprocess.run([
            "g++", "-std=c++20", "-g", "-Og", "-Isrc", "-I/usr/include/libxml2", *defines,
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            str(path / "test.cpp"), str(HARNESS_STUBS), "-o", str(binary),
        ], cwd=ROOT, check=True)
        for case in ("collector_pending", "queued", "coalesced", "linkdead", "immortal", "redirect", "invalid",
                     "unavailable", "capture_failed", "unchanged", "locker", "busy", "collector",
                     "negative_prestige", "nonarmor"):
            print(f"{backend}: {case}", flush=True)
            subprocess.run([str(binary), case], check=True, timeout=30)
