#!/usr/bin/env python3
"""Executable launch policy/configuration tests; no host clock or live data changes."""

import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OPEN = 1793210400
CONFIG = "enabled=true\nopens_at_utc=2026-10-28T18:00:00Z\nallowed_accounts=mosheh, Test_staff\n"
HARNESS = r'''
#include "account/pwipe_launch.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>

int main(int argc, char **argv)
{
    assert(!pwipe_launch_allows_at("mosheh", 0));
    assert(argc == 3);
    std::string error;
    if (!pwipe_launch_load(argv[1], error)) {
        assert(!error.empty());
        assert(!pwipe_launch_allows_at("mosheh", 1793210401));
        puts(error.c_str());
        return 2;
    }
    time_t now = static_cast<time_t>(atoll(argv[2]));
    for (const char *name : {"mosheh", "MoShEh", "test_STAFF", "mos", "moshehmore", "staff", "", static_cast<const char *>(nullptr)})
        printf("%d", pwipe_launch_allows_at(name, now));
    printf("\n%s\n%s\n", pwipe_launch_opens_utc().c_str(), pwipe_launch_status(now).c_str());
}
'''


def run():
    build_root = ROOT / "bin/tests"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pwipe-launch-policy-", dir=build_root) as temporary:
        root = Path(temporary)
        harness, binary, config = root / "harness.cpp", root / "policy", root / "launch.cfg"
        harness.write_text(HARNESS)
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                        "-Isrc", str(harness), "src/account/pwipe_launch.c", "-o", str(binary)],
                       cwd=ROOT, check=True)

        def check(text, now=OPEN - 1, expected="11100000", valid=True, timezone="UTC"):
            config.write_text(text)
            result = subprocess.run([str(binary), str(config), str(now)], capture_output=True,
                                    text=True, env=dict(os.environ, TZ=timezone))
            assert result.returncode == (0 if valid else 2), result.stdout + result.stderr
            if valid:
                assert result.stdout.splitlines()[0] == expected, result.stdout
                assert "opens_at_utc=" in result.stdout and "allowed_accounts=" in result.stdout
            return result.stdout

        for tz in ("UTC", "Asia/Jerusalem", "America/New_York"):
            check(CONFIG, timezone=tz)
            check(CONFIG, OPEN, "11111111", timezone=tz)
            check(CONFIG, OPEN + 1, "11111111", timezone=tz)
        check(CONFIG.replace("enabled=true", "enabled=false"), expected="11111111")
        check(CONFIG.replace("enabled=true", "enabled=false").replace("mosheh, Test_staff", ""),
              expected="11111111")
        for invalid in (
            CONFIG + "enabled=true\n", CONFIG + "extra=true\n", CONFIG + "bad line\n",
            CONFIG.replace("enabled=true\n", ""), CONFIG.replace("enabled=true", "enabled=TRUE"),
            CONFIG.replace("mosheh, Test_staff", ""), CONFIG.replace("mosheh, Test_staff", "m"),
            CONFIG.replace("mosheh, Test_staff", "mos*"), CONFIG.replace("mosheh, Test_staff", "mos heh"),
            CONFIG.replace("mosheh, Test_staff", "mosheh,"),
            CONFIG.replace("mosheh, Test_staff", "mosheh,MOSHEH"),
            CONFIG.replace("mosheh, Test_staff", "abcdefghijklmnop"),
            CONFIG.replace("mosheh, Test_staff", "mosheh\0hidden"),
        ):
            check(invalid, valid=False)
        for date in ("2026-02-29T18:00:00Z", "2026-10-32T18:00:00Z", "2026-13-28T18:00:00Z",
                     "2026-10-28T24:00:00Z", "2026-10-28T18:60:00Z", "2026-10-28T18:00:60Z",
                     "2026-10-28T18:00:00+00:00", "2026-10-28 18:00:00Z", "2026-1-28T18:00:00Z",
                     "2026-10-28T18:00:00Z trailing", "1969-12-31T23:59:59Z"):
            check(CONFIG.replace("2026-10-28T18:00:00Z", date), valid=False)
        check(CONFIG.replace("2026-10-28T18:00:00Z", "2028-02-29T18:00:00Z"))
        result = subprocess.run([str(binary), str(root / "missing.cfg"), str(OPEN)], capture_output=True)
        assert result.returncode == 2
        print("PASS: fail-closed config, exact identities, disabled mode, UTC dates and launch boundary")


if __name__ == "__main__":
    run()
