#!/usr/bin/env python3
"""Capture immutable login identity before queueing, including journal compatibility."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS

HARNESS = r'''
#include "account/account.h"
#include "account/session_audit_transaction.h"
#include "persistence/critical_command_coordinator.h"
#include "core/utils.h"
#include <cassert>
#include <cstdio>

static critical_command captured;
critical_submit_result critical_command_coordinator_submit(critical_command command)
{
    captured = std::move(command);
    return critical_submit_result::accepted;
}

int main()
{
    char_data ch = {};
    descriptor_data descriptor = {};
    acct_entry account = {};
    char name[] = "Alice";
    account.acct_name = name;
    descriptor.account = &account;
    ch.desc = &descriptor;
    pc_only_data pc = {};
    pc.pid = 123;
    ch.only.pc = &pc;
    ch.player.level = 56;
    assert(session_audit_transaction_submit(&ch, session_audit_event::login));
    // Change the live character before decoding the queued work.
    name[0] = 'Z';
    ch.player.level = MINLVLIMMORTAL;
    session_audit_payload decoded = {};
    assert(session_audit_command_decode_payload(captured, &decoded));
    assert(decoded.account_name == "alice" && !decoded.is_staff);
    assert(decoded.pid == 123 && decoded.event == session_audit_event::login);
    assert(decoded.occurred_at > 0);
    assert(session_audit_transaction_submit(&ch, session_audit_event::login));
    assert(session_audit_command_decode_payload(captured, &decoded));
    assert(decoded.account_name == "zlice" && decoded.is_staff);

    std::array<uint8_t, SESSION_AUDIT_RESULT_BYTES> receipt = {};
    assert(session_audit_command_encode_result(decoded, &receipt));
    auto legacy = captured;
    legacy.payload_version = 1;
    legacy.payload.resize(13);
    assert(session_audit_command_decode_payload(legacy, &decoded));
    assert(decoded.account_name.empty() && !decoded.is_staff);
    std::array<uint8_t, SESSION_AUDIT_RESULT_BYTES> old_receipt = {};
    assert(session_audit_command_encode_result(decoded, &old_receipt));
    assert(receipt == old_receipt);

    for (size_t size = 0; size < captured.payload.size(); ++size) {
        auto truncated = captured;
        truncated.payload.resize(size);
        assert(!session_audit_command_decode_payload(truncated, &decoded));
    }
    auto invalid = captured;
    invalid.payload[13] = 2; // Invalid staff flag.
    assert(!session_audit_command_decode_payload(invalid, &decoded));
    invalid = captured;
    invalid.payload.push_back(0);
    assert(!session_audit_command_decode_payload(invalid, &decoded));
    invalid = captured;
    invalid.payload_version = 3;
    assert(!session_audit_command_decode_payload(invalid, &decoded));

    ch.desc = nullptr;
    assert(session_audit_transaction_submit(&ch, session_audit_event::logout));
    assert(session_audit_command_decode_payload(captured, &decoded));
    assert(decoded.account_name.empty());
    puts("session identity capture, immutable queue payload, v1 replay and malformed payloads passed");
}
'''

output = ROOT / 'bin/tests'
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='session-snapshot-', dir=output) as directory:
    harness = Path(directory) / 'harness.cpp'
    binary = Path(directory) / 'harness'
    harness.write_text(HARNESS)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-pthread',
                    '-I', str(ROOT / 'src'), str(harness), str(HARNESS_STUBS),
                    str(ROOT / 'src/account/session_audit_command.c'),
                    str(ROOT / 'src/account/session_audit_transaction.c'),
                    str(ROOT / 'src/persistence/critical_command.c'),
                    '-lcrypto', '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
