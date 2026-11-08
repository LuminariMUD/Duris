#!/usr/bin/env python3
"""Check the SQL extra2 policy for snapshots and live recovery objects."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]

HARNESS = r"""
#include "sql/item_instance_fields.h"
#include <cassert>

int main()
{
    obj_data item{};
    obj_affect original{};
    original.type = TAG_ALTERED_EXTRA2;
    original.extra2 = 0;
    obj_affect bless{};
    bless.type = SPELL_BLESS;
    bless.extra2 = ITEM2_BLESS;
    bless.next = &original;
    item.affects = &bless;
    const auto permanent = ITEM2_ENHANCED | ITEM2_ACCOUNT_BOUND | ITEM2_MONK_PROC;
    item.extra2_flags = ITEM2_BLESS | permanent;

    player_item_snapshot snapshot{};
    snapshot.extra2_flags = item.extra2_flags;
    snapshot.dynamic_affects = {{bless.type, 0, bless.extra2},
                                {original.type, 0, original.extra2}};
    assert(sql_item_permanent_extra2(snapshot) == permanent);
    assert(sql_item_permanent_extra2(item) == permanent);

    original.extra2 = ITEM2_BLESS;
    snapshot.dynamic_affects.back().extra2 = ITEM2_BLESS;
    assert(sql_item_permanent_extra2(snapshot) == item.extra2_flags);
    assert(sql_item_permanent_extra2(item) == item.extra2_flags);
}
"""


def main():
    with tempfile.TemporaryDirectory(dir=ROOT / "bin") as directory:
        source = Path(directory) / "instance_fields.cpp"
        binary = source.with_suffix("")
        source.write_text(HARNESS)
        subprocess.run(
            ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
             str(source), "-o", str(binary)],
            cwd=ROOT, check=True,
        )
        subprocess.run([binary], cwd=ROOT, check=True)
    print("SQL snapshot and recovery object preserve the same permanent extra2 flags")


if __name__ == "__main__":
    main()
