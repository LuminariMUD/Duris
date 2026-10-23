#!/usr/bin/env python3
"""Account population and actual player-input observation; telemetry stays optional."""

import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function


output_root = ROOT / "bin" / "tests"
output_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="divine-boon-activity-", dir=output_root) as directory:
    binary = f"{directory}/activity"
    harness = Path(directory) / "activity.cpp"
    harness.write_text((ROOT / "tests/async/divine_boon_activity_harness.cpp").read_text().replace(
        "// MORPH_POLICY", extract_function("utility.c", "int IS_MORPH(")).replace(
        "// ITEM_COMMAND_POLICY", extract_function("interp.c", "bool cmd_depends_on_item_movement(")))
    subprocess.run(
        ["g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
         "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
         "-ffunction-sections", "-fdata-sections", "-Isrc",
         str(harness), "src/economy/divine_boon_activity.c",
         str(HARNESS_STUBS), "-Wl,--gc-sections", "-o", binary],
        cwd=ROOT, check=True,
    )
    subprocess.run([binary], cwd=ROOT, check=True)

dispatch = extract_function("comm.c", "static void dispatch_playing_command(")
assert dispatch.index("divine_boon_activity_begin(") < dispatch.index("command_interpreter(")
assert dispatch.index("command_interpreter(") < dispatch.index("divine_boon_activity_end(")
activity = (ROOT / "src/economy/divine_boon_activity.c").read_text()
assert "telemetry" not in activity
