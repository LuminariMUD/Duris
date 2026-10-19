#!/usr/bin/env python3
"""The PvP log verifier keeps the runner's connection trust policy."""
import unittest
import test_telemetry_migration_tls as tls


class PkillLogMigrationTlsTest(tls.TelemetryMigrationTlsTest):
    verifier = tls.ROOT / "migrations/immutable/0041_pkill_log_capacity.sh"
    failure_prefix = "FAILED: pkill log verifier"


if __name__ == "__main__":
    unittest.main()
