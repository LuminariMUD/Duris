#!/usr/bin/env python3
"""Contracts for bounded immutable player snapshot capture."""

from _paths import SRC
import re
import subprocess
import tempfile
from pathlib import Path
from _paths import HARNESS_STUBS


ROOT = Path(__file__).resolve().parents[2]
DTO = (SRC / "player_snapshot.h").read_text()
CAPTURE_HEADER = (SRC / "player_snapshot_capture.h").read_text()
CAPTURE = (SRC / "player_snapshot_capture.c").read_text()
CAPTURE_COMPACT = re.sub(r"\s+", "", CAPTURE)
LOAD_ITEMS = (SRC / "player_load_items.c").read_text()
LOAD_ITEMS_COMPACT = re.sub(r"\s+", "", LOAD_ITEMS)


HARNESS = r'''
#include "player/player_snapshot.h"

#include <cassert>
#include <string>
#include <type_traits>

int main()
{
    static_assert(std::is_move_constructible_v<player_snapshot>);
    static_assert(std::is_move_assignable_v<player_snapshot>);
    static_assert(PLAYER_SNAPSHOT_SCHEMA_VERSION == 13);
    static_assert(PLAYER_SNAPSHOT_MAX_BYTES == 4 * 1024 * 1024);
    static_assert(PLAYER_SNAPSHOT_MAX_OBJECTS < PLAYER_SNAPSHOT_MAX_ROWS);
    static_assert(PLAYER_SNAPSHOT_MAX_DEPTH > 0);

    std::string live_name = "original";
    player_snapshot snapshot = {};
    snapshot.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
    snapshot.pid = 42;
    snapshot.revision = 9;
    snapshot.components = PLAYER_COMPONENT_STATUS | PLAYER_COMPONENT_INVENTORY;
    snapshot.status_strings.push_back({player_status_string_field::name, live_name});
    snapshot.items.push_back({});
    snapshot.items[0].parent_index = PLAYER_SNAPSHOT_NO_PARENT;
    snapshot.items[0].name = "container";
    snapshot.items.push_back({});
    snapshot.items[1].parent_index = 0;
    snapshot.items[1].name = "nested";

    live_name[0] = 'X';
    assert(snapshot.status_strings[0].value == "original");
    assert(snapshot.items[0].parent_index == PLAYER_SNAPSHOT_NO_PARENT);
    assert(snapshot.items[1].parent_index == 0);

    player_snapshot sealed = std::move(snapshot);
    assert(sealed.pid == 42);
    assert(sealed.revision == 9);
    assert(sealed.items[1].name == "nested");
    return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-player-snapshot-") as temp_dir:
    source = Path(temp_dir) / "snapshot_test.cpp"
    binary = Path(temp_dir) / "snapshot_test"
    source.write_text(HARNESS)
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-Isrc",
            str(source),
            str(HARNESS_STUBS), "-o",
            str(binary),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run([str(binary)], check=True)

for forbidden in ("P_char", "P_obj", "char_data", "obj_data", "descriptor_data", "room_data"):
    assert forbidden not in DTO, f"live engine type escaped into DTO: {forbidden}"
for required in (
    "schema_version",
    "pid",
    "revision",
    "components",
    "save_intent",
    "room_vnum",
    "encoded_size_bound",
):
    assert required in DTO
for limit in (
    "PLAYER_SNAPSHOT_MAX_BYTES",
    "PLAYER_SNAPSHOT_MAX_ROWS",
    "PLAYER_SNAPSHOT_MAX_OBJECTS",
    "PLAYER_SNAPSHOT_MAX_DEPTH",
    "PLAYER_SNAPSHOT_MAX_STRING_BYTES",
):
    assert limit in DTO and limit in CAPTURE
print("[PASS] DTO metadata and relationships are pointer-free, value-owned, and bounded")

for component in (
    "PLAYER_COMPONENT_STATUS",
    "PLAYER_COMPONENT_LANGUAGES",
    "PLAYER_COMPONENT_INTRODUCTIONS",
    "PLAYER_COMPONENT_TIMERS",
    "PLAYER_COMPONENT_UNDEAD_SLOTS",
    "PLAYER_COMPONENT_FORGED_ITEMS",
    "PLAYER_COMPONENT_GRANTED_COMMANDS",
    "PLAYER_COMPONENT_SKILLS",
    "PLAYER_COMPONENT_AFFECTS",
    "PLAYER_COMPONENT_EQUIPMENT",
    "PLAYER_COMPONENT_INVENTORY",
    "PLAYER_COMPONENT_PETS",
    "PLAYER_COMPONENT_SHAPECHANGES",
    "PLAYER_COMPONENT_TROPHIES",
):
    assert component in CAPTURE
assert "recipes_are_external = true" in CAPTURE
assert "AFFTYPE_NOSAVE" in CAPTURE
assert "ITEM_NORENT" in CAPTURE
for string_flag in ("STRUNG_KEYS", "STRUNG_DESC1", "STRUNG_DESC2", "STRUNG_DESC3"):
    assert string_flag in CAPTURE
assert "save_intent != RENT_CRASH && save_intent != RENT_CRASH2" in CAPTURE
assert "pet->in_room != ch->in_room" in CAPTURE
assert "pet_affects_seen" in CAPTURE
assert "wear_off_message_index" in CAPTURE
assert 'copy_string("SPELLBOOK"' in CAPTURE
assert "spell_ids.push_back" in CAPTURE
print("[PASS] component adapters preserve current replacement, filter, pet, and affect semantics")

for mutation in (
    "unequip_char(",
    "equip_char(",
    "all_affects(",
    "affect_remove(",
    "extract_obj(",
    "obj_from_char(",
    "obj_from_obj(",
):
    assert mutation not in CAPTURE, f"capture mutates live state through {mutation}"
assert "std::unordered_set<const obj_data *> &seen" in CAPTURE
assert "PLAYER_SNAPSHOT_NO_PARENT" in CAPTURE
assert "parent_index" in CAPTURE
assert "row.string_mask=object->str_mask&(STRUNG_KEYS|STRUNG_DESC1|STRUNG_DESC2|STRUNG_DESC3)" in CAPTURE_COMPACT
assert "STRUNG_DESC3|STRUNG_EDESC" in LOAD_ITEMS_COMPACT
capture = CAPTURE[CAPTURE.index("player_snapshot_capture_result player_snapshot_capture("):]
assert capture.count("*snapshot_out = std::move(snapshot);") == 1
assert capture.index("player_snapshot snapshot") < capture.index("*snapshot_out = std::move(snapshot);")
print("[PASS] capture is non-mutating, cycle-aware, and atomically publishes one complete DTO")

for forbidden_route in (
    "sql_run_query",
    "db_query",
    "player_revision_mark",
    "player_revision_queue",
    "writeCharacter",
    "sql_save_player",
):
    assert forbidden_route not in CAPTURE
assert "P_char ch" in CAPTURE_HEADER
assert "player_item_snapshot_list_capture" in CAPTURE_HEADER
assert "player_item_snapshot_tree_capture" in CAPTURE_HEADER
assert "bool omit_norent" in CAPTURE_HEADER
assert "capture_items(owner, items, budget, equipment, inventory," in CAPTURE
assert "omit_norent, false)" in CAPTURE
assert "capture_item_tree(root, PLAYER_SNAPSHOT_NO_PARENT, 0, items" in CAPTURE
assert "*items_out = std::move(items);" in CAPTURE
assert CAPTURE.index("capture_items(owner, items, budget, equipment, inventory,") < CAPTURE.index(
    "*items_out = std::move(items);"
)
assert "P_char" not in DTO
print("[PASS] adapter accepts live state only at capture and performs no I/O or queue cutover")

print("immutable player snapshot capture contracts passed")


# Exercise the production adapter and codec with live engine structures.
# Engine-only services are inert.
HELD_PETS_HARNESS = r"""
#include "core/utils.h"
#include "classes/necromancy.h"
#include "core/files.h"
#include "magic/spells.h"
#include "world/vnum.obj.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_codec.h"
#include "player/pet_restore_runtime.h"
#include "item/item_ownership_runtime.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

bool training_dummy_capture_target_allowed(P_char) { return true; }
void event_short_affect(P_char, P_char, P_obj, void *) {}
int ne_event_time(P_nevent event) { return static_cast<int>(event->due_tick - 1000); }

index_data indexes[3] = {};
P_index obj_index = indexes;
index_data mob_indexes[2] = {};
P_index mob_index = mob_indexes;
room_data rooms[1] = {};
P_room world = rooms;
int top_of_objt = 2;
int top_of_mobt = 1;
extern const int top_of_world = 0;
Skill skills[MAX_SKILLS] = {};
std::vector<std::string> logged;
void logit(const char *, const char *format, ...) { logged.push_back(format); }
bool trace = false;
bool persistence_trace_enabled() { return trace; }
P_char get_linked_char(P_char ch, ush_int type)
{
    for (char_link_data *link = ch->linking; link; link = link->next_linking)
        if (link->type == type) return link->linked;
    return nullptr;
}

int main()
{
    char_data ch = {};
    pc_only_data pc = {};
    ch.only.pc = &pc;
    pc.pid = 42;
    const std::string read_hash(64, 'a');
    pc.quest_origin_room = 16633;
    pc.quest_replacement_due = 1;
    pc.quest_kill_how_many = 4;
    pc.quest_kill_original = 7;
    pc.wallet_revision = 19;
    GET_GOLD(&ch) = 123;
    std::memcpy(pc.last_read_news_hash, read_hash.c_str(), read_hash.size() + 1);
    player_snapshot status;
    assert(player_snapshot_capture(&ch, 99, PLAYER_COMPONENT_STATUS, RENT_CRASH, 22800, &status) == player_snapshot_capture_result::ok);
    assert(status.status_strings.size() == 8);
    assert(status.status_strings.back().field == player_status_string_field::last_read_news_hash);
    pc.last_read_news_hash[0] = '\0';
    assert(status.status_strings.back().value == read_hash);
    assert(status.status_integers.size() == PLAYER_STATUS_INTEGER_COUNT);
    std::vector<uint8_t> status_bytes;
    player_snapshot restored_status;
    assert(player_snapshot_encode(status, &status_bytes) == player_snapshot_codec_result::ok);
    assert(player_snapshot_decode(status_bytes.data(), status_bytes.size(), &restored_status) == player_snapshot_codec_result::ok);
    assert(restored_status.wallet_revision == 19);
    assert(restored_status.quest_values[10] == 4 && restored_status.quest_values[11] == 7);
    bool found_origin = false, found_replacement = false, found_gold = false;
    for (const auto &field : restored_status.status_integers) {
        if (field.field == player_status_field::quest_origin_room)
            found_origin = field.signed_value == 16633;
        if (field.field == player_status_field::quest_replacement_due)
            found_replacement = field.signed_value == 1;
        if (field.field == player_status_field::gold)
            found_gold = field.signed_value == 123;
    }
    assert(found_origin && found_replacement && found_gold);
    // Event-owned Hatred must be recomputed after either backend reloads a player.
    affected_type hatred_combat{}, hatred_spell{}, ordinary{};
    hatred_combat.type = hatred_spell.type = TAG_HATRED;
    hatred_combat.flags = hatred_spell.flags = AFFTYPE_NOSAVE | AFFTYPE_NODISPEL;
    hatred_combat.duration = hatred_spell.duration = -1;
    hatred_combat.modifier = hatred_spell.modifier = -1;
    hatred_combat.location = APPLY_COMBAT_PULSE;
    hatred_spell.location = APPLY_SPELL_PULSE;
    ordinary.type = SPELL_BLESS;
    ordinary.duration = 3;
    hatred_combat.next = &ordinary;
    ordinary.next = &hatred_spell;
    ch.affected = &hatred_combat;
    player_snapshot affects;
    assert(player_snapshot_capture(&ch, 99, PLAYER_COMPONENT_AFFECTS, RENT_QUIT, 22800, &affects) == player_snapshot_capture_result::ok);
    assert(affects.affects.size() == 1 && affects.affects[0].type == SPELL_BLESS);

    // The asynchronous save route bypasses the legacy updateShortAffects call.
    // Capture event time without mutating live state or renewing the original TTL.
    ordinary.flags = AFFTYPE_SHORT;
    ordinary.duration = 2640;
    event_short_affect_data payload{&ch, &ordinary};
    nevent_data expiry{};
    expiry.func = event_short_affect;
    expiry.data = &payload;
    expiry.due_tick = 1800;
    ch.nevents = &expiry;
    assert(player_snapshot_capture(&ch, 100, PLAYER_COMPONENT_AFFECTS, RENT_QUIT, 22800, &affects) == player_snapshot_capture_result::ok);
    assert(affects.affects.size() == 1 && affects.affects[0].duration == 800);
    assert(ordinary.duration == 2640);
    ch.nevents = nullptr;
    ch.affected = nullptr;
    player_held_pet_state held;
    player_pet_snapshot retained = {};
    retained.mob_vnum = 1201; retained.hit = retained.max_hit = 10;
    retained.hold_reason = pet_hold_reason::legacy_summon;
    retained.restore_state = "unknown historical state";
    retained.items.push_back({});
    retained.items[0].parent_index = PLAYER_SNAPSHOT_NO_PARENT;
    retained.items[0].object_uid = 700;
    retained.items[0].vnum = 100;
    held.pets.push_back(retained);
    auto malformed = retained;
    malformed.hold_reason = pet_hold_reason::invalid_state;
    malformed.hit = -1;
    malformed.max_hit = 0;
    malformed.items[0].object_uid = 701;
    held.pets.push_back(malformed);
    pc.held_pets = &held;
    for (int intent : {RENT_CRASH, RENT_QUIT, RENT_DEATH}) {
        player_snapshot saved;
        assert(player_snapshot_capture(&ch, 99, PLAYER_COMPONENT_PETS, intent, 22800, &saved) == player_snapshot_capture_result::ok);
        assert(saved.pets[0].hold_reason == pet_hold_reason::legacy_summon);
        assert(saved.pets[0].items[0].object_uid == 700);
        assert(saved.pets[0].restore_state == retained.restore_state);
        std::vector<uint8_t> encoded;
        assert(player_snapshot_encode(saved, &encoded) == player_snapshot_codec_result::ok);
        player_snapshot restored;
        assert(player_snapshot_decode(encoded.data(), encoded.size(), &restored) == player_snapshot_codec_result::ok);
        assert(restored.pets[0].items[0].object_uid == 700);
        assert(restored.pets.size() == 2);
        assert(restored.pets[1].hold_reason == pet_hold_reason::invalid_state);
        assert(restored.pets[1].hit == -1 && restored.pets[1].max_hit == 0);
        assert(restored.pets[1].items[0].object_uid == 701);
    }
    pc.held_pets = nullptr;
    std::cout << "[PASS] held pet assets survive crash, logout and death saves\n";

    // An item picked up since the last login has no entry in the in-memory ledger until
    // its first save inserts one, and nothing publishes that back: the unowned_object
    // line is a trace, written on each save only with DURIS_PERSISTENCE_TRACE (#11).
    obj_data picked_up = {};
    picked_up.R_num = 1;
    picked_up.obj_uid = 5001;
    indexes[1].virtual_number = 15;
    ch.carrying = &picked_up;
    const auto unowned_lines = [] {
        size_t count = 0;
        for (const std::string &line : logged)
            count += line.find("outcome=unowned_object") != std::string::npos;
        return count;
    };
    for (int save = 0; save < 3; ++save) {
        player_snapshot saved;
        assert(player_snapshot_capture(&ch, 99, PLAYER_COMPONENT_INVENTORY, RENT_QUIT, 22800, &saved) == player_snapshot_capture_result::ok);
        assert(saved.items.size() == 1 && saved.items[0].object_uid == 5001);
    }
    assert(unowned_lines() == 0);
    trace = true;
    for (int save = 0; save < 2; ++save) {
        player_snapshot saved;
        assert(player_snapshot_capture(&ch, 99, PLAYER_COMPONENT_INVENTORY, RENT_QUIT, 22800, &saved) == player_snapshot_capture_result::ok);
    }
    assert(unowned_lines() == 2);
    ch.carrying = nullptr;
    std::cout << "[PASS] a held item with no ledger entry is reported only with the trace on\n";
    player_item_retention retained_items;
    retained_items.rows={{10,0},{11,0}}; retained_items.bytes=128;
    pc.retained_items=&retained_items; ch.carrying=&picked_up;
    player_snapshot sealed;
    assert(player_snapshot_capture(&ch,100,PLAYER_COMPONENT_INVENTORY,RENT_QUIT,22800,&sealed)==player_snapshot_capture_result::ok);
    retained_items.rows[0].source_row_id=90;
    assert(sealed.retained_items.rows[0].source_row_id==10 && sealed.retained_items.bytes==128);
    auto without_retention=sealed; without_retention.retained_items={};
    std::vector<uint8_t> encoded,plain;
    assert(player_snapshot_encode(sealed,&encoded)==player_snapshot_codec_result::ok &&
           player_snapshot_encode(without_retention,&plain)==player_snapshot_codec_result::ok && encoded==plain);
    player_snapshot decoded;
    assert(player_snapshot_decode(encoded.data(),encoded.size(),&decoded)==player_snapshot_codec_result::ok && decoded.retained_items.rows.empty());
    retained_items.bytes=PLAYER_SNAPSHOT_MAX_BYTES;
    player_snapshot untouched; untouched.pid=123;
    assert(player_snapshot_capture(&ch,101,PLAYER_COMPONENT_INVENTORY,RENT_QUIT,22800,&untouched)==player_snapshot_capture_result::limit_exceeded && untouched.pid==123);
    pc.retained_items=nullptr; ch.carrying=nullptr;
    player_snapshot ordinary_status;
    assert(player_snapshot_capture(&ch,102,PLAYER_COMPONENT_STATUS,RENT_CRASH,22800,&ordinary_status)==player_snapshot_capture_result::ok);
    const size_t status_rows=ordinary_status.status_integers.size()+ordinary_status.status_strings.size();
    std::vector<affected_type> crowded_affects(PLAYER_SNAPSHOT_MAX_ROWS-status_rows+1);
    for(size_t i=0;i<crowded_affects.size();++i) {
        crowded_affects[i].type=i==0 ? PLAYER_TRADE_CARGO_AFFECT : 0;
        crowded_affects[i].next=i+1<crowded_affects.size() ? &crowded_affects[i+1] : nullptr;
    }
    ch.affected=crowded_affects.data();
    player_snapshot crowded;
    assert(player_snapshot_capture(&ch,103,PLAYER_COMPONENT_STATUS|PLAYER_COMPONENT_AFFECTS,RENT_QUIT,22800,&crowded)==player_snapshot_capture_result::ok);
    assert(crowded.affects.size()+crowded.status_integers.size()+crowded.status_strings.size()==PLAYER_SNAPSHOT_MAX_ROWS+1);
    crowded_affects[1].type=PLAYER_TRADE_CARGO_AFFECT;
    assert(player_snapshot_capture(&ch,104,PLAYER_COMPONENT_STATUS|PLAYER_COMPONENT_AFFECTS,RENT_QUIT,22800,&crowded)==player_snapshot_capture_result::malformed_source);
    ch.affected=nullptr;
    std::cout << "[PASS] later terminal captures preserve one protected cargo row at the ordinary row limit\n";

    std::cout << "[PASS] immutable retained-source capture, byte bound and versioned wire round trip\n";
}
"""

build = ROOT / "bin/tests/player-held-pet-capture"
build.mkdir(parents=True, exist_ok=True)
source = build / "regression.cpp"
binary = build / "regression"
source.write_text(HELD_PETS_HARNESS)
subprocess.run([
    "g++", "-std=c++20", "-g", "-O1", "-ffunction-sections", "-fdata-sections",
    "-Isrc", str(source), "src/player/player_snapshot_capture.c",
    "src/player/player_snapshot_codec.c", "src/player/pet_restore_state.c",
    "src/player/pet_restore_runtime.c", "src/item/item_ownership_runtime.c",
    "src/item/item_transfer_command.c", "src/persistence/critical_command.c",
    "-Wl,--gc-sections", "-lcrypto", str(HARNESS_STUBS), "-o", str(binary),
], cwd=ROOT, check=True)
subprocess.run([str(binary)], check=True)
