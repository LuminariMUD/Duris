#!/usr/bin/env python3
"""Execute the production durable first-kit binding across reopen and corruption."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT

HARNESS = r'''
#include "item/starter_kit_intent.h"
#include "item/item_transfer_command.h"
#include <cassert>
#include <fstream>
#include <cerrno>
#include <sys/stat.h>
extern "C" int __real_fsync(int);
bool fail_directory_sync = false;
extern "C" int __wrap_fsync(int fd) {
    struct stat state{};
    if (fail_directory_sync && fstat(fd, &state) == 0 && S_ISDIR(state.st_mode)) {
        fail_directory_sync = false; errno = EIO; return -1;
    }
    return __real_fsync(fd);
}

int main(int argc, char **argv) {
    assert(argc == 2 && starter_kit_intent_init(argv[1]));
    critical_operation_id id{};
    assert(critical_operation_id_generate(&id));
    item_transfer_payload payload{};
    payload.from_owner = {item_owner_type::system, 0, 0};
    payload.to_owner = {item_owner_type::player, 42, 0};
    payload.reason = item_transfer_reason::creation;
    payload.multi_root = true;
    payload.item_count = 1;
    payload.items[0] = {100, 100, 0, ITEM_TRANSFER_ABSENT_REVISION, 500,
                        item_custody_state::absent};
    payload.item_blob_size = 1;
    payload.item_blob[0] = 1;
    critical_command command, stored;
    assert(item_transfer_command_build(&command, id, payload, critical_source_site::command,
                                       critical_deadline_class::interactive));
    command.accepted_at_usec = 123;
    assert(starter_kit_intent_read(42, &stored) == starter_kit_state::absent);
    assert(!starter_kit_intent_bind(43, command));
    assert(starter_kit_intent_bind(42, command));
    starter_kit_intent_shutdown();
    assert(starter_kit_intent_init(argv[1]));
    assert(starter_kit_intent_read(42, &stored) == starter_kit_state::pending);
    assert(critical_command_equal(command, stored));
    assert(starter_kit_intent_bind(42, command));
    auto changed = command;
    changed.operation_id.bytes[0] ^= 1;
    assert(!starter_kit_intent_bind(42, changed));
    assert(!starter_kit_intent_finish(42, changed, true));
    fail_directory_sync = true;
    assert(!starter_kit_intent_finish(42, command, true));
    assert(starter_kit_intent_read(42, &stored) == starter_kit_state::committed);
    assert(starter_kit_intent_finish(42, command, true));
    assert(starter_kit_intent_finish(42, command, true));
    assert(!starter_kit_intent_finish(42, command, false));
    assert(!starter_kit_intent_bind(42, command));
    starter_kit_intent_shutdown();
    assert(starter_kit_intent_init(argv[1]));
    assert(starter_kit_intent_read(42, &stored) == starter_kit_state::committed);
    assert(critical_command_equal(command, stored));
    assert(!starter_kit_intent_bind(42, changed));
    std::fstream file(std::string(argv[1]) + "/starter-kits/42.kit", std::ios::in|std::ios::out|std::ios::binary);
    file.put(0); file.close(); // Changing the result without its checksum is refused.
    assert(starter_kit_intent_read(42, &stored) == starter_kit_state::invalid);
    assert(!starter_kit_intent_bind(42, command));
    payload.to_owner.id = 44;
    assert(critical_operation_id_generate(&id));
    assert(item_transfer_command_build(&command, id, payload, critical_source_site::command,
                                       critical_deadline_class::interactive));
    command.accepted_at_usec = 124;
    assert(starter_kit_intent_bind(44, command));
    fail_directory_sync = true;
    assert(!starter_kit_intent_finish(44, command, false));
    assert(starter_kit_intent_finish(44, command, false));
    assert(!starter_kit_intent_finish(44, command, true));
    assert(starter_kit_intent_read(44, &stored) == starter_kit_state::rejected);
    assert(!starter_kit_intent_bind(44, command));
    starter_kit_intent_shutdown();
}
'''

def main():
    with tempfile.TemporaryDirectory(prefix="starter-intent-") as tmp:
        source = Path(tmp) / "test.cpp"
        binary = Path(tmp) / "test"
        state = Path(tmp) / "state"
        state.mkdir()
        source.write_text(HARNESS)
        subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                        "-Isrc", str(source), "src/item/starter_kit_intent.c",
                        "src/item/item_transfer_command.c", "src/persistence/critical_command.c",
                        "src/flatfile/flatfile_store.c", "-lcrypto", "-Wl,--wrap=fsync", "-o", str(binary)],
                       cwd=ROOT, check=True)
        subprocess.run([str(binary), str(state)], check=True)
    print("PASS durable starter operation/UID binding, restart, refusal and corruption")

if __name__ == "__main__":
    main()
