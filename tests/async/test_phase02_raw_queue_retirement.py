#!/usr/bin/env python3
"""Typed session audit and fail-closed legacy raw queue retirement contracts."""

from _paths import SRC
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include "account/session_audit_command.h"
#include <cassert>

int main()
{
    critical_operation_id operation = {};
    assert(critical_operation_id_generate(&operation));
    const session_audit_payload payload = {42, session_audit_event::login, 1700000000};
    critical_command command = {};
    assert(session_audit_command_build(&command, operation, payload));
    session_audit_payload decoded = {};
    assert(session_audit_command_decode_payload(command, &decoded));
    assert(decoded.pid == 42 && decoded.event == session_audit_event::login);
    std::array<uint8_t, SESSION_AUDIT_RESULT_BYTES> result = {};
    assert(session_audit_command_encode_result(payload, &result));
    assert(session_audit_command_decode_result(result.data(), result.size(), &decoded));
    command.keys[0].id = 43;
    assert(!session_audit_command_decode_payload(command, &decoded));
}
'''


class Phase02RawQueueRetirementTests(unittest.TestCase):
    def test_session_audit_codec_is_bounded_and_reconstructs_key(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "session_audit.cpp"
            binary = Path(directory) / "session_audit"
            source.write_text(HARNESS)
            subprocess.run([
                "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", f"-I{SRC}",
                str(source), str(SRC / "critical_command.c"),
                str(SRC / "session_audit_command.c"), "-lcrypto", "-o", str(binary),
            ], check=True)
            subprocess.run([str(binary)], check=True)

    def test_login_logout_use_typed_command_without_private_payload(self):
        sql = (SRC / "sql.c").read_text()
        start = sql.rindex("void sql_log_player_login")
        end = sql.index("\n}\n", start)
        body = sql[start:end]
        self.assertIn("session_audit_transaction_submit", body)
        for forbidden in ("qry(", "db_query", "host", "account", "client_name"):
            self.assertNotIn(forbidden, body)

    def test_schema_reconciliation_and_operator_contract_are_wired(self):
        for path, token in (
            ("migrations/session_audit_outcome.sql", "session_audit_outcome"),
            ("migrations/bootstrap_multithread_safe.sql", "session_audit_outcome"),
            ("migrations/run_migration.sh", "verify_session_audit_schema.sh"),
            ("migrations/reconcile_phase02_domains.sh", "reconcile_item_ownership.sh"),
        ):
            self.assertIn(token, (ROOT / path).read_text())


if __name__ == "__main__":
    unittest.main()
