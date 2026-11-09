#!/usr/bin/env python3
"""A locker is saved with the character inside it.

writeCharacter() runs the locker's post-save hook, which saves the locker its occupant
is in and applies the locker's idle rule. Queued saves (the 30-second checkpoint, every
terminal save and writeCharacter()'s own queued branch) returned before it, so a locker
was saved only when its occupant walked out: what a player dropped in it was lost if
the session ended inside (shutdown, idle rent, link loss) or the server crashed. Each
queued save now runs the hook. The locker slot keeps the user by pid and the locker
by name, since a terminal save's caller extracts the user straight after.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

SRC = Path(__file__).resolve().parents[2] / "src"


def body(text, signature):
    start = text.index(signature)
    return text[start:text.index("\n}\n", start) + 3]


# Execute the production save entry point and both locker hooks. Token checks
# previously depended on the exact spelling of the queued-save condition.
harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/files.h"
#include "economy/collector_service.h"
#include "player/player_save_pipeline.h"
#include <cassert>
#include <vector>

static room_data rooms[1]{};
P_room world = rooms;
static std::vector<int> calls;
static bool recover = true;
static int intent;
static player_save_pipeline_result result;
int IS_MORPH(P_char) { return false; }
bool collector_service_recover_player(P_char) { return recover; }
int calculate_save_room(P_char, int type, int room) {
    assert(type == intent && room == 41); calls.push_back(2); return 1234;
}
player_save_pipeline_result player_save_pipeline_request(
    P_char, player_component_mask_t components, int type, int room) {
    assert(components == PLAYER_CHECKPOINT_COMPONENT_ALL && type == intent && room == 1234);
    calls.push_back(3); return result;
}
static int hook(int room, P_char, int command, char *) {
    assert(room == 0 && (command == -80 || command == -81));
    calls.push_back(command == -80 ? 1 : 4); return 41;
}
/* PRODUCTION */
int main() {
    char_data ch{};
    pc_only_data pc{};
    ch.only.pc = &pc; pc.pid = 7;
    ch.player.name = const_cast<char *>("Fixture"); ch.in_room = 0;
    rooms[0].room_flags = ROOM_LOCKER; rooms[0].funct = hook;
    for (int type : {RENT_QUIT, RENT_INN, RENT_CAMPED, RENT_LINKDEAD, RENT_DEATH}) {
        intent = type;
        for (auto outcome : {player_save_pipeline_result::queued,
                            player_save_pipeline_result::coalesced,
                            player_save_pipeline_result::unchanged,
                            player_save_pipeline_result::invalid,
                            player_save_pipeline_result::capture_failed,
                            player_save_pipeline_result::unavailable}) {
            result = outcome; calls.clear();
            assert(writeCharacter(&ch, type, 41) ==
                   (outcome == player_save_pipeline_result::queued ||
                    outcome == player_save_pipeline_result::coalesced));
            assert((calls == std::vector<int>{1, 2, 3, 4}));
        }
    }
    // Invalid actors and pending collector materialization never queue a save.
    calls.clear(); assert(!writeCharacter(nullptr, intent, 41));
    ch.player.name = nullptr; assert(!writeCharacter(&ch, intent, 41));
    ch.player.name = const_cast<char *>("Fixture");
    recover = false; assert(!writeCharacter(&ch, intent, 41)); assert(calls.empty());
    recover = true; pc.pid = 0; ch.in_room = NOWHERE;
    assert(!writeCharacter(&ch, intent, 41)); assert(calls.empty());
    pc.pid = 7; ch.player.name = const_cast<char *>("Fixture.locker");
    assert(!writeCharacter(&ch, intent, 41)); assert(calls.empty());
    ch.player.name = const_cast<char *>("Fixture"); ch.in_room = 0;
    rooms[0].room_flags = 0; calls.clear(); result = player_save_pipeline_result::queued;
    assert(writeCharacter(&ch, intent, 41)); assert((calls == std::vector<int>{2, 3}));
}
'''
production = extract_function("files.c", "void locker_post_save_hook(") + "\n" + \
    extract_function("files.c", "int writeCharacter(")
build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="locker-save-", dir=build) as temporary:
    source = Path(temporary) / "save.cpp"
    binary = Path(temporary) / "save"
    source.write_text(harness.replace("/* PRODUCTION */", production))
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
                    "-I/usr/include/mysql", str(source), str(HARNESS_STUBS), "-o", str(binary)],
                   cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
print("[PASS] terminal save outcomes queue complete snapshots and invoke locker hooks in order")

terminal = body((SRC / "cmd/actoth.c").read_text(), "bool persistence_save_character_terminal(P_char ch, int type)")
assert terminal.index("player_save_pipeline_request(") < terminal.index("locker_post_save_hook(ch);")
checkpoint = (SRC / "persistence/persistence_checkpoint.c").read_text()
assert checkpoint.count("player_save_pipeline_checkpoint_dirty(") == \
    checkpoint.count("locker_post_save_hook(character);") == 1
print("[PASS] terminal saves and checkpoints save the locker a character is in")

locker = (SRC / "persistence/locker_async.c").read_text()
slot = locker[locker.index("struct locker_async_slot\n{"):locker.index("};", locker.index("struct locker_async_slot\n{"))]
assert "P_char" not in slot
start = body(locker, "static int start_one_snapshot(")
assert "chLocker = find_locker_char_by_name(s->locker_name);" in start
assert "chUser = find_char_by_pid(s->user_pid);" in start
print("[PASS] a locker slot holds no character pointer across pulses")
