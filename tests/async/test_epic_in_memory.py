#!/usr/bin/env python3
"""Epic points move in memory: at once, completed before the submit returns, then recorded.

Links the production epic transaction with the command codec and records what the
coordinator is given, in order with the completion.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, rel
from _paths import HARNESS_STUBS


HARNESS = r'''
#include "world/epic_transaction.h"
#include "persistence/persistence_checkpoint.h"
#include "core/utils.h"

#include <cassert>
#include <cerrno>
#include <cstdlib>
#include <limits>
#include <string>
#include <vector>

// The completion and the ledger command, in the order they happen.
static std::vector<std::string> order;
static int dirty = 0;

void mark_player_dirty_components(int, player_component_mask_t) { ++dirty; }
critical_submit_result critical_command_coordinator_submit(critical_command command)
{
    epic_command_payload payload = {};
    assert(epic_command_decode_payload(command, &payload));
    order.push_back("ledger:" + std::to_string(payload.delta));
    return critical_submit_result::accepted;
}

static bool last_committed = false;
static unsigned int last_error = 0;
static epic_command_result last_result = {};
static void completion(P_char, bool committed, const epic_command_result &result,
                       unsigned int error_code, const uint8_t *, size_t)
{
    last_committed = committed;
    last_error = error_code;
    last_result = result;
    order.push_back("completion");
}

int main()
{
    char_data ch = {};
    pc_only_data pc = {};
    ch.only.pc = &pc;
    pc.pid = 42;
    pc.epics = 100;

    // An award changes the balance before the submit returns; the ledger row follows.
    assert(epic_transaction_submit(&ch, 25, epic_reason_type::quest_award, 7, 0,
                                   critical_source_site::command,
                                   critical_deadline_class::interactive, completion, nullptr, 0));
    assert(last_committed && pc.epics == 125 && pc.epic_revision == 1 && dirty == 1);
    assert(last_result.balance == 125 && last_result.revision == 1 && last_result.delta == 25);
    assert((order == std::vector<std::string>{"completion", "ledger:25"}));
    order.clear();

    // A purchase the balance cannot cover is refused and records nothing.
    assert(epic_transaction_submit(&ch, -200, epic_reason_type::store_purchase, 0,
                                   EPIC_COMMAND_REQUIRE_FUNDS, critical_source_site::command,
                                   critical_deadline_class::interactive, completion, nullptr, 0));
    assert(!last_committed && last_error == ENOSPC && pc.epics == 125 && pc.epic_revision == 1);
    assert((order == std::vector<std::string>{"completion"}));
    order.clear();

    // A spend without the funds flag may take the balance below zero, as before.
    assert(epic_transaction_submit(&ch, -130, epic_reason_type::admin_adjustment, 0, 0,
                                   critical_source_site::command,
                                   critical_deadline_class::interactive, completion, nullptr, 0));
    assert(last_committed && pc.epics == -5 && pc.epic_revision == 2);
    order.clear();

    // An overflow is refused.
    pc.epics = std::numeric_limits<long>::max() - 1;
    assert(epic_transaction_submit(&ch, 5, epic_reason_type::quest_award, 0, 0,
                                   critical_source_site::command,
                                   critical_deadline_class::interactive, completion, nullptr, 0));
    assert(!last_committed && last_error == ERANGE);
    const epic_transaction_health health = epic_transaction_health_copy();
    assert(health.submitted == 4 && health.committed == 2 && health.rejected == 2);
    return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-epic-in-memory-") as temporary:
    source = Path(temporary) / "harness.cpp"
    binary = Path(temporary) / "harness"
    source.write_text(HARNESS)
    subprocess.run(
        [
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            "-g", "-O1", "-fsanitize=address,undefined", "-ffunction-sections",
            "-fdata-sections", "-Isrc", "-I/usr/include/mysql", str(source),
            rel("epic_transaction.c"), rel("epic_command.c"), rel("critical_command.c"),
            "-Wl,--gc-sections", "-lcrypto", str(HARNESS_STUBS), "-o", str(binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(binary)], check=True, timeout=60)
print("[PASS] an epic award changes the balance before the submit returns; the ledger follows")
print("[PASS] a purchase beyond the balance, and an overflow, are refused and record nothing")
