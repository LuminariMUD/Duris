#!/usr/bin/env python3
"""Both auction backends withhold artifacts decoded from old ordinary listings."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function

harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "economy/auction_command.h"
#include "persistence/persistence_checkpoint.h"
#include "sql/sql_player.h"
#include <cassert>
#include <string>
static obj_data item;
static int mode, delivered, extracted, alerts, dirty;
static std::string output;
P_obj read_one_object(char *) {
    item = {};
    if (mode == 2) return nullptr;
    item.extra_flags = mode == 1 ? ITEM_ARTIFACT : 0;
    item.short_description = const_cast<char *>("hammer");
    return &item;
}
void extract_obj(P_obj object, int) { assert(object == &item); ++extracted; }
void obj_to_char(P_obj object, P_char) {
    assert(object == &item && !IS_ARTIFACT(object) && object->obj_uid == 42);
    ++delivered;
}
void send_to_char(const char *message, P_char) { output += message; }
void send_to_char_f(P_char, const char *, ...) {}
void persistence_alert(int, const char *, const char *, const char *, const char *,
                       const char *reason, const char *, ...) {
    assert(std::string(reason) == (mode == 1 ? "artifact_withheld" : "deserialize_failed"));
    ++alerts;
}
void mark_player_dirty_components(int, player_component_mask_t) { ++dirty; }
'''
for name in ('flat_item_claim_completed', 'auction_item_claim_completed'):
    harness += extract_function('auction_houses.c', 'void ' + name + '(')
harness += r'''
int main() {
    char_data actor = {};
    pc_only_data pc = {};
    actor.only.pc = &pc;
    auction_command_payload payload = {};
    auction_command_result result = {};
    result.item_count = 1;
    result.item_uids[0] = 42;
    for (auto callback : {flat_item_claim_completed, auction_item_claim_completed}) {
        for (mode = 0; mode < 3; ++mode) {
            delivered = extracted = alerts = dirty = 0; output.clear();
            callback(&actor, false, result, 0, payload);
            assert(!delivered && !extracted && !alerts && !dirty);
            callback(&actor, true, result, 0, payload);
            assert(delivered == (mode == 0) && extracted == (mode == 1));
            assert(alerts == (mode != 0) && dirty == 1);
            if (mode == 1) assert(output.find("immortal assistance") != std::string::npos);
        }
        callback(nullptr, true, result, 0, payload);
    }
}
'''
build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='auction-artifact-', dir=build) as directory:
    cpp = Path(directory) / 'test.cpp'
    binary = Path(directory) / 'test'
    cpp.write_text(harness)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                    '-Isrc', '-I/usr/include/mysql', str(cpp), str(HARNESS_STUBS),
                    '-o', str(binary)],
                   cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
print('auction artifact claims: both backends passed')
