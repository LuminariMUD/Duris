#!/usr/bin/env python3
"""Contract and native output-failure checks for the static composition report."""
from _paths import SRC, HARNESS_STUBS, rel
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
report = (SRC / "material_rarity.c").read_text()
header = (SRC / "material_rarity.h").read_text()
comm = (SRC / "comm.c").read_text()
db = (SRC / "db.c").read_text()

# These shared APIs avoid a copied parser/formula. They do not establish full
# valuation-context parity, which is tracked separately in the ival plan (F07).
assert "cache_object_template" in report and "itemvalue(*obj)" in report
assert "material_start_vnum" in report
assert "read_object(" not in report and "extract_obj(" not in report

# The executable mode is offline/read-only: boot the object database, write the
# report, and exit before listening for player connections.
assert "--material-rarity-report" in comm
assert "boot_material_rarity_objects" in comm
offline = db[db.index("bool boot_material_rarity_objects("):db.index("/** Load world data")]
assert "initialize_property_values()" in offline and "assign_spell_pointers()" in offline
assert "ne_init_event_pool" not in offline and "mm_create" not in offline
assert "write_material_rarity_report" in comm
assert comm.index("if (material_rarity_report_mode)") < comm.index("initialize_mysql")
assert "bool write_material_rarity_report" in header

# Preserve source data for auditability and make the percentage denominator
# explicit. Unknown/unmapped material families must be reported, not silently
# folded into a default material family.
assert "material-rarity-summary.csv" in report
assert "material-rarity-recipes.csv" in report
assert "material-rarity-exclusions.csv" in report
assert "unmapped-material-family" in report
assert "total_material_units" in report
assert "share_percent" in report

print("material rarity report contract passed")

# Compile the actual writer and command branch, controlling only the object boot
# and unused valuation endpoints. An empty catalog isolates report I/O from the
# known missing-context problem; no database, socket or live item is needed.
HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/material_rarity.h"
#include "item/item_value.h"
#include "world/object_template.h"
#include <cassert>
#include <cstdlib>

static bool unbuffered = false;
extern "C" FILE *__real_fopen(const char *, const char *);
extern "C" FILE *__wrap_fopen(const char *path, const char *mode)
{
    FILE *file = __real_fopen(path, mode);
    if (file && unbuffered) assert(setvbuf(file, nullptr, _IONBF, 0) == 0);
    return file;
}

P_index obj_index = nullptr;
int top_of_objt = -1;
int mini_mode = 1;
int no_specials = 0;
bool boot_material_rarity_objects(int mode) { assert(mode == 1); return true; }
bool cache_object_template(int) { assert(std::getenv("BAD_TEMPLATE")); return false; }
const object_template *find_object_template(int) { assert(false); return nullptr; }
int itemvalue(const object_template &, item_value_breakdown *) { assert(false); return 0; }
int material_start_vnum(int) { assert(false); return 0; }

int main(int argc, char **argv)
{
    assert(argc == 2 || argc == 3);
    unbuffered = argc == 3;
    bool material_rarity_report_mode = true;
    const char *material_rarity_report_dir = argv[1];
    int mini_mode = 1;
    if (std::getenv("BAD_TEMPLATE")) {
        static index_data index{};
        index.virtual_number = 123;
        obj_index = &index;
        top_of_objt = 0;
    }
    // COMMAND
    assert(false); // The report branch must exit before ordinary boot.
}
'''


def check_output_failures():
    start = comm.index("\tif (material_rarity_report_mode)\n\t{")
    branch = comm[start:comm.index('\n\tlogit(LOG_STATUS, "Running game on port', start)]
    build = root / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    filenames = ("material-rarity-summary.csv", "material-rarity-recipes.csv",
                 "material-rarity-exclusions.csv", "material-rarity-README.txt")
    with tempfile.TemporaryDirectory(prefix="material-report-io-", dir=build) as tmp:
        base = Path(tmp)
        source, binary = base / "test.cpp", base / "test"
        source.write_text(HARNESS.replace("// COMMAND", branch))
        subprocess.run([
            "g++", "-std=c++20", "-g", "-O1", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-Isrc", str(source), rel("material_rarity.c"), str(HARNESS_STUBS),
            "-Wl,--wrap=fopen", "-lcrypto", "-o", str(binary),
        ], cwd=root, check=True)
        env = {**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
               "UBSAN_OPTIONS": "halt_on_error=1"}

        def run(target, success, diagnostic, unbuffered=False):
            command = [str(binary), str(target)] + (["unbuffered"] if unbuffered else [])
            result = subprocess.run(command, capture_output=True,
                                    text=True, env=env, cwd=base)
            assert result.returncode == (0 if success else 1), result.stderr
            assert diagnostic in result.stderr, result.stderr
            assert "runtime error:" not in result.stderr and "AddressSanitizer" not in result.stderr
            return result

        good = base / "good"
        run(good, True, "written to")
        assert all((good / name).is_file() for name in filenames)
        assert "count_mode=one-per-required-material" in (good / filenames[3]).read_text()
        assert "formula_revision=ival-v5-zero-neutral" in (good / filenames[3]).read_text()
        bad = subprocess.run([str(binary), str(base / "bad-template")], capture_output=True,
                             text=True, env={**env, "BAD_TEMPLATE": "1"}, cwd=base)
        assert bad.returncode == 1 and "cannot parse object template 123" in bad.stderr
        (base / "areas/world.trg").mkdir(parents=True)
        run(base / "bad-fingerprint", False, "fingerprint failed")
        (base / "areas/world.trg").rmdir()
        # An existing directory is supported (the report may be regenerated).
        run(good, True, "written to")
        run(base / "missing-parent" / "output", False, "cannot create")
        blocker = base / "file"
        blocker.write_text("not a directory")
        run(blocker, False, "cannot open")
        for index, name in enumerate(filenames):
            output = base / f"open-failure-{index}"
            output.mkdir()
            (output / name).mkdir()
            run(output, False, "cannot open")
            # Force a buffered write/close failure for each stream individually.
            full = base / f"full-{index}"
            full.mkdir()
            (full / name).symlink_to("/dev/full")
            result = run(full, False, "discard partial files")
            assert "written to" not in result.stderr
            # Unbuffered writes fail before close: fclose alone misses these.
            run(full, False, "discard partial files", unbuffered=True)
        # Output paths must not silently truncate to the former 512-byte buffers.
        long_path = base
        for index in range(6):
            long_path /= str(index) * 90
            long_path.mkdir()
        run(long_path, True, "written to")
        assert all((long_path / name).is_file() for name in filenames)
    print("native report I/O: success, creation/open/write failures and long paths passed")


check_output_failures()
