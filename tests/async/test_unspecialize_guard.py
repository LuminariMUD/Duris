#!/usr/bin/env python3
"""Execute unspecialization guards/completion with the real in-memory epic purchase.

Refresh and spell-forgetting are observed call boundaries here; the full-world
mechanics journey checks actual refreshed/persisted skills and the loaded altar.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, source


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "world/epic.h"
#include "world/epic_transaction.h"
#include "persistence/persistence_checkpoint.h"
#include <cassert>
#include <cstdio>
#include <string>

static std::string output;
static int refreshes, forgotten, ledger_calls, dirty;
static P_char current;
static critical_submit_result ledger_result = critical_submit_result::accepted;

void send_to_char(const char *text, P_char) { output += text; }
void update_skills(P_char ch) {
    assert(ch == current && ch->player.spec == 0 && ch->only.pc->epics == 2);
    ++refreshes;
}
int forget_spells(P_char ch, int spell) {
    assert(ch == current && spell == -1 && refreshes == 1);
    ++forgotten;
    return 0;
}
void mark_player_dirty_components(int pid, player_component_mask_t components) {
    assert(pid == 42 && components == PLAYER_COMPONENT_STATUS);
    ++dirty;
}
critical_submit_result critical_command_coordinator_submit(critical_command command) {
    epic_command_payload payload{};
    assert(epic_command_decode_payload(command, &payload));
    assert(payload.pid == 42 && payload.delta == -10 && payload.reason_id == 0);
    assert(payload.reason == epic_reason_type::specialization_purchase);
    assert(payload.flags == EPIC_COMMAND_REQUIRE_FUNDS);
    // The state mutation, skill refresh and forgetting finish before ledger enqueue.
    assert(current->player.spec == 0 && current->only.pc->epics == 2);
    assert(refreshes == 1 && forgotten == 1);
    ++ledger_calls;
    return ledger_result;
}
'''

DRIVER = r'''
int main() {
    char_data ch{};
    pc_only_data pc{};
    ch.only.pc = &pc;
    current = &ch;
    pc.pid = 42;
    pc.epics = 12;
    unspecialize(&ch, nullptr);
    assert(ch.player.spec == 0 && pc.epics == 12 && ledger_calls == 0);
    assert(output.find("get no response") != std::string::npos);

    ch.player.spec = SPEC_GUARDIAN;
    pc.epics = 9;
    output.clear();
    unspecialize(&ch, nullptr);
    assert(ch.player.spec == SPEC_GUARDIAN && pc.epics == 9 && ledger_calls == 0);
    assert(output.find("need 10 epic points") != std::string::npos);
    assert(refreshes == 0 && forgotten == 0 && dirty == 0);

    // Inject invalid submit input to exercise the existing service-rejection path.
    // A normally loaded mortal has a valid PID; this is not ordinary reachability.
    pc.epics = 12;
    pc.pid = 0;
    output.clear();
    unspecialize(&ch, nullptr);
    assert(ch.player.spec == SPEC_GUARDIAN && pc.epics == 12 && ledger_calls == 0);
    assert(output.find("service is busy") != std::string::npos);
    assert(refreshes == 0 && forgotten == 0);
    pc.pid = 42;

    // Characterize the refusal callback directly. With stable valid input, the
    // ordinary handler's earlier funds check already prevents this purchase.
    unspecialize_committed(&ch, false, {}, 0, nullptr, 0);
    assert(ch.player.spec == SPEC_GUARDIAN && pc.epics == 12);
    assert(refreshes == 0 && forgotten == 0);

    for (auto queue_result : {critical_submit_result::accepted, critical_submit_result::overloaded}) {
        ledger_result = queue_result;
        ch.player.spec = SPEC_GUARDIAN;
        pc.epics = 12;
        pc.epic_revision = 0;
        refreshes = forgotten = ledger_calls = dirty = 0;
        output.clear();
        epic_transaction_reset_for_tests();
        unspecialize(&ch, nullptr);
        assert(ch.player.spec == 0 && pc.epics == 2 && pc.epic_revision == 1);
        assert(refreshes == 1 && forgotten == 1 && ledger_calls == 1 && dirty == 1);
        assert(output.find("old habits fall away") != std::string::npos);
        const auto health = epic_transaction_health_copy();
        assert(health.committed == 1 && health.rejected == 0);
        assert(health.submission_failures == (queue_result == critical_submit_result::overloaded ? 1u : 0u));
        // Repeating the request after completion neither charges nor refreshes again.
        unspecialize(&ch, nullptr);
        assert(pc.epics == 2 && ledger_calls == 1 && refreshes == 1 && forgotten == 1);
    }
    std::puts("unspecialize: invalid state/funds/submit guards, refusal callback, native debit/completion ordering and ledger rejection passed");
}
'''

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="unspecialize-", dir=build) as directory:
    harness, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
    harness.write_text(PRELUDE
        + extract_function("specializations.c", "void unspecialize_committed(")
        + extract_function("specializations.c", "void unspecialize(P_char ch,") + DRIVER)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g", "-D__NO_MYSQL__",
        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined", "-fno-pie", "-no-pie",
        "-ffunction-sections", "-fdata-sections", "-I" + str(ROOT / "src"),
        "-I" + str(ROOT / "src/no_mysql"), str(harness),
        str(source("epic_transaction.c")), str(source("epic_command.c")),
        str(source("critical_command.c")), str(HARNESS_STUBS),
        "-Wl,--gc-sections", "-lcrypto", "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True)
