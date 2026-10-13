#!/usr/bin/env python3
"""Issue #259: exercise real status capture with deterministic session clocks."""
from pathlib import Path
import subprocess
import tempfile
from _paths import HARNESS_STUBS, extract_function

ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include "core/utils.h"
#include "core/files.h"
#include "core/config.h"
#include "cmd/interp.h"
#include "player/character_mechanics.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_codec.h"
#include <cassert>
#include <climits>
#include <iostream>

bool training_dummy_capture_target_allowed(P_char) { return true; }

index_data indexes[1] = {};
P_index obj_index = indexes;
P_index mob_index = indexes;
room_data rooms[1] = {};
P_room world = rooms;
int top_of_objt = 0;
int top_of_mobt = 0;
extern const int top_of_world = 0;
Skill skills[MAX_SKILLS] = {};
static time_t now = 10000;
extern "C" time_t __wrap_time(time_t *out) {
    if (out) *out = now;
    return now;
}

// This fixture isolates the room procedure's obligation to preserve the
// resident session across its reset service. The full-world mechanics journey
// exercises the actual do_start and before/after persisted totals.
int get_property(const char *key, int fallback) {
    return !strcmp(key, "multiclass.epic.req.min") ? 0 : fallback;
}
void do_multiclass(P_char, char *, int) { std::abort(); }
bool can_char_multi_to_class(P_char, int cls) { return cls == 6; }
void do_start(P_char ch, int cmd) {
    assert(cmd == CMD_MULTICLASS);
    ch->player.level = 1;
    ch->player.time.played = 0;
    ch->player.time.logon = now;
}
void do_restore(P_char, char *, int) {}
int forget_spells(P_char, int) { return 0; }
void refund_epic_skills(P_char) {}
void clear_zone_trophy(P_char) {}

/* PRODUCTION_MULTICLASS */

int main() {
    char_data ch = {};
    pc_only_data pc = {};
    ch.only.pc = &pc;
    pc.pid = 42;
    assert(pc.learned_flight_stops == 0);
    pc.learned_flight_stops = (uint64_t{1} << 26) | 1;
    GET_EXP(&ch) = 12345;
    ch.player.time.played = 3600;
    ch.player.time.logon = 9400;
    ch.player.time.saved = 9000;
    player_revision_t revision = 0;
    auto capture = [&](int intent = RENT_CRASH) {
        const auto before = ch.player.time;
        player_snapshot snapshot;
        assert(player_snapshot_capture(&ch, ++revision, PLAYER_COMPONENT_STATUS,
                                       intent, 1, &snapshot) == player_snapshot_capture_result::ok);
        assert(ch.player.time.played == before.played);
        assert(ch.player.time.logon == before.logon);
        assert(ch.player.time.saved == before.saved);
        std::vector<uint8_t> bytes;
        assert(player_snapshot_encode(snapshot, &bytes) == player_snapshot_codec_result::ok);
        player_snapshot decoded;
        assert(player_snapshot_decode(bytes.data(), bytes.size(), &decoded) == player_snapshot_codec_result::ok);
        bool found_flights = false, found_exp = false;
        for (const auto &row : decoded.status_integers) {
            if (row.field == player_status_field::learned_flight_stops) {
                assert(row.is_unsigned && row.unsigned_value == pc.learned_flight_stops);
                found_flights = true;
            }
            if (row.field == player_status_field::experience) {
                assert(row.signed_value == GET_EXP(&ch));
                found_exp = true;
            }
        }
        assert(found_flights && found_exp);
        for (const auto &row : decoded.status_integers)
            if (row.field == player_status_field::played_time)
                return row.is_unsigned ? row.unsigned_value : static_cast<uint64_t>(row.signed_value);
        std::abort();
    };
    assert(capture() == 4200); // The current-session ten minutes must be durable.
    assert(capture() == 4200); // Repeated capture cannot compound elapsed time.
    now += 15;
    assert(capture() == 4215);
    assert(capture(RENT_DEATH) == 4215); // Terminal/death uses the same clock contract.
    now += 30;
    assert(capture(RENT_LINKDEAD) == 4245); // Resident linkdead time still counts.
    now -= 30;
    ch.player.time.played = capture(); // Simulate loading the acknowledged total.
    now += 86400; // Offline time is not played time.
    ch.player.time.logon = now;
    assert(capture() == 4215);
    now += 10;
    assert(capture() == 4225);
    ch.player.time.logon = now + 10; // Backward clock jump must not underflow.
    assert(capture() == 4215);
    ch.player.time.logon = 0; // Uninitialized creation/offline fixture.
    assert(capture() == 4215);
    ch.player.time.logon = -1;
    assert(capture() == 4215);
    ch.player.time.logon = 10;
    now = -1; // time() failure must not grant time or underflow.
    assert(capture() == 4215);
    ch.player.time.played = INT_MAX - 5;
    ch.player.time.logon = 10;
    now = 100;
    assert(capture() == INT_MAX); // Durable SQL column is signed INT.
    ch.player.time.played = UINT_MAX; // A corrupt unsigned baseline cannot wrap a save.
    assert(capture() == INT_MAX);
    now = 10000;
    ch.player.time.logon = 9400;
#ifdef EQ_WIPE
    ch.player.time.played = EQ_WIPE + 3600;
    assert(capture() - EQ_WIPE == 4200); // Existing display offset remains intact.
    ch.player.time.played = EQ_WIPE + 2 * 3600; // Staff-set two-hour baseline.
    assert(capture() - EQ_WIPE == 2 * 3600 + 600);
#endif
    const auto baseline = ch.player.time.played;
    for (int race : {RACE_HUMAN, RACE_ORC}) {
        now = 10000;
        ch.player.name = const_cast<char *>("Playtimefixture");
        ch.player.race = race;
        ch.player.m_class = CLASS_WARRIOR;
        ch.player.secondary_class = 0;
        ch.player.level = 50;
        ch.player.time.played = baseline;
        ch.player.time.logon = 9400;
        const auto before_multi = capture();
        char choice[] = "cleric";
        assert(multiclass_proc(0, &ch, CMD_MULTICLASS, choice));
        assert(ch.player.level == 1 && ch.player.secondary_class == CLASS_CLERIC);
        assert(ch.player.time.played == baseline && ch.player.time.logon == 9400);
        assert(capture() == before_multi);
        now += 10;
        assert(capture() == before_multi + 10);
    }
    std::cout << "[PASS] active time, repeat saves, terminal capture, reload, clock guards, SQL range; live fields unchanged\n";
    std::cout << "[PASS] Human/Orc multiclass retains baseline and session clock through real status capture\n";
}
'''

HARNESS = HARNESS.replace("/* PRODUCTION_MULTICLASS */", "\n".join([
    extract_function("common.c", "const struct class_names class_names_table[] =") + ";",
    extract_function("interp.c", "bool is_abbrev("),
    extract_function("utility.c", "int IS_MORPH("),
    extract_function("specs.room.c", "int multiclass_proc("),
]))

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="duris-playtime-", dir=build) as temporary:
    source = Path(temporary) / "playtime.cpp"
    binary = Path(temporary) / "playtime"
    source.write_text(HARNESS)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-O1", "-ffunction-sections", "-fdata-sections",
        "-Isrc", str(source), "src/player/player_snapshot_capture.c",
        "src/player/player_snapshot_codec.c", "src/player/pet_restore_state.c",
        "src/player/pet_restore_runtime.c", "src/item/item_ownership_runtime.c",
        "src/item/item_transfer_command.c", "src/persistence/critical_command.c",
        "-Wl,--gc-sections", "-Wl,--wrap=time", "-lcrypto", str(HARNESS_STUBS), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
