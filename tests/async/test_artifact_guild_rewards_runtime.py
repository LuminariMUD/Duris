#!/usr/bin/env python3
"""Live artifact/guild awards through the real capture and submission path."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from _paths import ROOT, HARNESS_STUBS

out = ROOT / 'bin/tests'
out.mkdir(parents=True, exist_ok=True)
# The pre-cutover boot cache is a fixture boundary, not a second implementation.
# This lets check_tests_catch run the same observable assertions on old sources.
legacy = 'bool hydrated = false;' in (ROOT / 'src/guild/artifact_guild_state.c').read_text()


class ArtifactGuildRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = tempfile.TemporaryDirectory(prefix='artifact-rewards-', dir=out)
        cls.addClassCleanup(directory.cleanup)
        cls.binary = Path(directory.name) / 'runtime'
        subprocess.run([
            'g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-pthread',
            '-fsanitize=undefined', '-fno-sanitize-recover=undefined',
            '-ffunction-sections', '-fdata-sections',
            '-Isrc', '-I/usr/include/mysql', f'-DLEGACY_HYDRATION={int(legacy)}',
            'tests/async/artifact_guild_rewards_runtime.cpp',
            'src/guild/artifact_guild_transaction.c', 'src/guild/artifact_guild_command.c',
            'src/guild/assocs.c', 'src/core/safe_format.c', 'src/persistence/critical_command.c',
            'src/world/zone_touch_transaction.c', 'src/world/zone_touch_command.c',
            'src/world/epic_command.c',
            str(HARNESS_STUBS), '-Wl,--gc-sections', '-lcrypto', '-o', str(cls.binary),
        ], cwd=ROOT, check=True)
        # Setup errors are never converted to expected failures. Only exit 2
        # means the native harness completed with an unmet identity contract.
        cls.identity_results = {}
        for case in ('duplicate', 'cross-player'):
            result = subprocess.run(
                [str(cls.binary), case], stderr=subprocess.PIPE, text=True, timeout=30)
            if result.returncode not in (0, 2) or result.stderr:
                raise AssertionError(
                    f'{case} harness failed (exit {result.returncode}):\n{result.stderr}')
            cls.identity_results[case] = result.returncode

    def test_existing_live_rewards(self):
        subprocess.run([str(self.binary)], check=True, timeout=30)

    # AR-01 pins the desired behavior before the identity implementation. These
    # must become normal passing regressions with AR-02/AR-05; an unexpected
    # success fails this suite so the markers cannot silently survive a repair.
    @unittest.expectedFailure
    def test_duplicate_excludes_only_conflicting_artifact(self):
        self.assertEqual(self.identity_results['duplicate'], 0)

    @unittest.expectedFailure
    def test_cross_player_copy_preserves_unrelated_rewards(self):
        self.assertEqual(self.identity_results['cross-player'], 0)


if __name__ == '__main__':
    unittest.main()
