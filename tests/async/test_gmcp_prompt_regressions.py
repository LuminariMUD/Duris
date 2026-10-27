#!/usr/bin/env python3
"""Regression coverage for GMCP preference and prompt lifecycle boundaries."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source


ACTOTH = source("actoth.c").read_text(encoding="utf-8")
GMCP = source("gmcp.c").read_text(encoding="utf-8")
PROMPT = source("prompt.c").read_text(encoding="utf-8")


def test_source_contracts() -> None:
    """Keep each fix on the intended shared boundary."""
    assert '{ "&+WGMCP&N data streaming disabled.\\r\\n", "&+WGMCP&N data streaming enabled.\\r\\n" }' in ACTOTH
    gmcp_case = ACTOTH.split("case 64: /* gmcp */", 1)[1].split("case 65:", 1)[0]
    assert "result = plr_tog(PLR3_FLAGS(ch), PLR3_NOGMCP, arg, 1);" in gmcp_case
    assert "GMCP_ENABLED(d->character)" in GMCP
    prompt_guard = PROMPT.split("if (!t_ch_p)", 1)[1].split("\n\t}", 1)[0]
    assert "point->prompt_mode = FALSE;" in prompt_guard


def test_gmcp_toggle_state_matrix() -> None:
    """Exercise production GMCP-toggle semantics for every accepted boolean form."""
    prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include <cassert>
#include <cstring>
'''
    production = "\n".join(
        (
            extract_function("actoth.c", "static int plr_tog("),
            extract_function("interp.c", "char *lohrr_chop("),
            extract_function("interp.c", "bool is_abbrev("),
            extract_function("utility.c", "int yes_no("),
        )
    )
    driver = r'''
int main()
{
    for (const char *value : {"on", "yes"})
    {
        unsigned int flags = PLR3_NOGMCP;
        assert(plr_tog(flags, PLR3_NOGMCP, value, 1) == 1 && !(flags & PLR3_NOGMCP));
    }
    for (const char *value : {"off", "no"})
    {
        unsigned int flags = 0;
        assert(plr_tog(flags, PLR3_NOGMCP, value, 1) == 0 && (flags & PLR3_NOGMCP));
    }

    unsigned int flags = 0;
    assert(plr_tog(flags, PLR3_NOGMCP, "", 1) == 0 && (flags & PLR3_NOGMCP));
    assert(plr_tog(flags, PLR3_NOGMCP, "", 1) == 1 && !(flags & PLR3_NOGMCP));
    assert(plr_tog(flags, PLR3_NOGMCP, "invalid", 1) == -1 && !(flags & PLR3_NOGMCP));
}
'''
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gmcp-toggle-", dir=build) as directory:
        directory_path = Path(directory)
        source_path = directory_path / "harness.cpp"
        binary_path = directory_path / "harness"
        source_path.write_text(prelude + production + driver, encoding="utf-8")
        subprocess.run(
            [
                "g++",
                "-std=c++20",
                "-Wall",
                "-Wextra",
                "-Werror",
                f"-I{ROOT / 'src'}",
                str(source_path),
                "-o",
                str(binary_path),
            ],
            cwd=ROOT,
            check=True,
            timeout=120,
        )
        subprocess.run([str(binary_path)], cwd=ROOT, check=True, timeout=30)


if __name__ == "__main__":
    test_source_contracts()
    test_gmcp_toggle_state_matrix()
    print("GMCP toggle and prompt regressions passed")
