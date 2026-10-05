#!/usr/bin/env python3
"""Static and codec evidence for the bounded Phase 02 25-200 client gate."""

from _paths import SRC
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include "account/session_audit_command.h"
#include <cassert>
#include <set>
#include <string>
#include <vector>

int main()
{
    for (unsigned int clients : {25U, 50U, 100U, 200U})
    {
        std::set<std::string> ids;
        size_t retained = 0;
        for (unsigned int index = 1; index <= clients; ++index)
        {
            critical_operation_id operation = {};
            assert(critical_operation_id_generate(&operation));
            char hex[CRITICAL_COMMAND_ID_HEX_SIZE] = {};
            assert(critical_operation_id_to_hex(operation, hex, sizeof(hex)));
            assert(ids.insert(hex).second);
            critical_command command = {};
            assert(session_audit_command_build(
                &command, operation,
                {index, session_audit_event::login, 1700000000 + index}));
            command.accepted_at_usec = 1700000000000000ULL + index;
            std::vector<uint8_t> encoded;
            assert(critical_command_encode(command, &encoded) ==
                   critical_command_codec_result::ok);
            retained += encoded.size();
        }
        assert(ids.size() == clients);
        assert(clients <= 1024);
        assert(retained < 64U * 1024U * 1024U);
    }
}
'''


class Phase02CapacityCrashGateTests(unittest.TestCase):
    def test_25_to_200_client_codec_load_is_within_global_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "phase02_capacity.cpp"
            binary = Path(directory) / "phase02_capacity"
            source.write_text(HARNESS)
            subprocess.run([
                "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", f"-I{SRC}",
                str(source), str(SRC / "critical_command.c"),
                str(SRC / "session_audit_command.c"), "-lcrypto", "-o", str(binary),
            ], check=True)
            subprocess.run([str(binary)], check=True)

    def test_runtime_caps_cover_200_without_unbounded_fanout(self):
        coordinator = (SRC / "critical_command_coordinator.h").read_text()
        self.assertGreaterEqual(int(re.search(
            r"CRITICAL_COORDINATOR_MAX_OPERATIONS = (\d+)", coordinator).group(1)), 200)
        self.assertIn("CRITICAL_COORDINATOR_MAX_BYTES = 64 * 1024 * 1024", coordinator)
        self.assertIn("ZONE_TOUCH_MAX_PARTICIPANTS = 15",
                      (SRC / "zone_touch_command.h").read_text())
        self.assertIn("BOON_REWARD_MAX_RESULTS = 32",
                      (SRC / "boon_reward_command.h").read_text())

    def test_crash_matrix_covers_every_required_boundary(self):
        pipeline = (ROOT / "docs/persistence/CRITICAL_COMMAND_PIPELINE.md").read_text()
        matrix = pipeline[pipeline.index("## Failure behavior"):
                          pipeline.index("## Reconciliation")].lower()
        for boundary in ("admission", "db acquire", "db apply", "db commit", "completion",
                         "outbox", "duplicate", "crash", "copyover", "shutdown"):
            self.assertIn(f"| {boundary}", matrix)
        for result in ("reject before gameplay success", "same operation id",
                       "already_applied", "nothing is replayed"):
            self.assertIn(result.lower(), matrix)
        self.assertIn("nothing executes sql text", pipeline.lower())


if __name__ == "__main__":
    unittest.main()
