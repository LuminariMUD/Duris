#!/usr/bin/env python3
"""Native cap configuration/adoption inputs and shared-policy wiring contracts."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, source

PROBE = r'''
#include "combat/frag_cap_config.h"
#include <cassert>
#include <cstdlib>
void logit(const char *, const char *, ...) {}
int main(int argc, char **argv)
{
    assert(argc == 4);
    boot_frag_cap_config();
    const auto *config = frag_cap_config_get();
    const auto policy = frag_cap_config_policy();
    assert(config->cap_floor_level == atoi(argv[1]));
    assert(FRAG_CAP_INITIAL_LEVEL == 31 && FRAG_CAP_MAXIMUM_LEVEL == 56);
    assert(config->legacy_maximum_level == atoi(argv[2]));
    assert(policy.round_duration == atoll(argv[3]) * FRAG_CAP_HOUR);
    assert(frag_cap_config_hardcore_level_cap(31) == 33);
    assert(frag_cap_config_hardcore_level_cap(55) == 56);
    assert(frag_cap_config_hardcore_level_cap(56) == 56);
}
'''

output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="frag-cap-config-", dir=output) as directory:
    root = Path(directory)
    (root / "lib").mkdir()
    probe = root / "probe.cpp"
    probe.write_text(PROBE)
    binary = root / "probe"
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
                    str(probe), str(source("frag_cap_config.c")), "-o", str(binary)], cwd=ROOT, check=True)

    def check(text, expected):
        if text is not None:
            (root / "lib/frag_cap.cfg").write_text(text)
        subprocess.run([str(binary), *map(str, expected)], cwd=root, check=True)

    check(None, (25,56,72))
    check((ROOT / "lib/frag_cap.cfg").read_text(), (25,56,72))
    check("cap.floor.level=45\ncap.maximum.level=50\ntimer.round.hours=36\n", (45,50,36))
    check("cap.floor.level=57\ncap.maximum.level=57\ntimer.round.hours=0\n", (25,56,72))

maintenance = source("maintenance_repository.c").read_text()
for retired in ("unlock_victim_levels_below", "unlock_minimum_share_points", "killer_allies", "frag_leaderboard", "pkill_info"):
    assert retired not in maintenance
assert "frag_cap_flatfile_tick" in maintenance and "frag_cap_settle" in maintenance
runtime = source("frag_cap_runtime.c").read_text()
assert "persistence_writer_submit" in runtime and "pending->state.revision > published.revision" in runtime
comm = source("comm.c").read_text()
assert "frag_cap_runtime_boot" in comm and "frag_cap_runtime_pulse" in comm
for producer in ("combat_outcome_repository.c", "flatfile_player_domain_repository.c"):
    assert "frag_cap_apply_combat" in source(producer).read_text()
assert "frag_cap_runtime_status" in source("fraglist.c").read_text()
print("PASS frag-cap configuration: real defaults/overrides/validation, legacy floor, Hardcore bounds and shared wiring")
