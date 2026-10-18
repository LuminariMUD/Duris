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
            '-fsanitize=undefined', '-fno-sanitize-recover=undefined', '-ffunction-sections', '-fdata-sections',
            '-Isrc', '-I/usr/include/mysql', f'-DLEGACY_HYDRATION={int(legacy)}',
            'tests/async/artifact_guild_rewards_runtime.cpp',
            'src/guild/artifact_guild_transaction.c', 'src/guild/artifact_guild_command.c',
            'src/guild/assocs.c', 'src/core/safe_format.c', 'src/persistence/critical_command.c',
            'src/world/zone_touch_transaction.c', 'src/world/zone_touch_command.c',
            'src/world/epic_command.c',
            str(HARNESS_STUBS), '-Wl,--gc-sections', '-lcrypto', '-o', str(cls.binary),
        ], cwd=ROOT, check=True)

    def test_existing_live_rewards(self):
        subprocess.run([str(self.binary)], check=True, timeout=30)

    def test_drain_releases_writer_capacity(self):
        subprocess.run([str(self.binary), 'drain-capacity'], check=True, timeout=30)

    def test_flatfile_rewards_publish_without_sql_history(self):
        subprocess.run([str(self.binary), 'flatfile'], check=True, timeout=30)

    def test_duplicate_excludes_only_conflicting_artifact(self):
        for scenario in ('duplicate', 'duplicate-reversed', 'same-uid', 'guild-only'):
            with self.subTest(scenario=scenario):
                subprocess.run([str(self.binary), scenario], check=True, timeout=30)

    def test_cross_player_copy_preserves_unrelated_rewards(self):
        for scenario in ('cross-player', 'wrong-custody', 'missing-uid', 'rejected-copy',
                         'canonical-copy', 'canonical-copy-reversed', 'canonical-alias-slot'):
            with self.subTest(scenario=scenario):
                subprocess.run([str(self.binary), scenario], check=True, timeout=30)


if __name__ == '__main__':
    unittest.main()
