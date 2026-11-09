#!/usr/bin/env python3
"""Capture the flag leaves the game loop (persistence reset phase 2, step 8).

A capture or a reclaim used to insert its ctf_data row, and `ctf score` read the scores,
on the game thread's connection. The row is queued on the writer now, and the scores are
read there and shown on a later pulse. Only the boot load (ctf_populate_boons) queries.
"""
from _paths import SRC, ROOT, extract_function
from pathlib import Path
import os
import subprocess
import tempfile

mysql = (SRC / "ctf.c").read_text()

entry = mysql[mysql.index("int add_ctf_entry("):mysql.index("void show_ctf(")]
assert "sql_queue(" in entry and "INSERT INTO ctf_data" in entry, entry

score = mysql[mysql.index("void show_ctf_score("):mysql.index("void do_ctf(")]
assert "sql_read_for(ch, dbqry" in score, score

boot = mysql[mysql.index("void ctf_populate_boons()"):mysql.index("int ctf_use_boon(")]
runtime = mysql.replace(boot, "")
for forbidden in ("qry(", "mysql_store_result", "db_query"):
    assert forbidden not in runtime, f"capture the flag still queries the game loop: {forbidden}"

print("capture the flag writer contract passed")

# Execute the real binding code without SQL, rooms, item creation or callbacks.
# A missing flag formerly indexed obj_index[-1] before load_ctf checked it.
HARNESS = r'''
#include "core/prototypes.h"
#include "combat/ctf.h"
#include <cassert>
static index_data indices[2]{};
P_index obj_index = indices;
static bool missing;
int real_object(int vnum) { return missing ? -1 : vnum == 111 ? 0 : vnum == 222 ? 1 : -1; }
int ctf_flag_proc(P_obj, P_char, int, char *) { assert(false); return 0; }
static int untouched(P_obj, P_char, int, char *) { assert(false); return 0; }
ctfData ctfdata[] = {{}, {1, 0, 0, 111, 0, nullptr}, {2, 0, 0, 999, 0, nullptr},
                     {3, 0, 0, 222, 0, nullptr}, {4, 0, 0, 111, 0, nullptr}, {}};
// BINDINGS
int main() {
    indices[0].func.obj = indices[1].func.obj = untouched;
    missing = true;
    assign_ctf_object_procs();
    assert(indices[0].func.obj == untouched && indices[1].func.obj == untouched);
    missing = false;
    assign_ctf_object_procs();
    assert(indices[0].func.obj == ctf_flag_proc && indices[1].func.obj == ctf_flag_proc);
    assert(bind_ctf_flag(999) == -1);
    // Each normal-boot flag is rebound immediately before its construction.
    indices[0].func.obj = untouched;
    assert(bind_ctf_flag(111) == 0 && indices[0].func.obj == ctf_flag_proc);
}
'''
bindings = extract_function("ctf.c", "static int bind_ctf_flag(") + "\n" + \
           extract_function("ctf.c", "void assign_ctf_object_procs()")
load = extract_function("ctf.c", "int load_ctf()")
assert "if ((r_num = bind_ctf_flag(ctfdata[i].flag)) < 0)" in load
build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="ctf-bindings-", dir=build) as tmp:
    source, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
    source.write_text(HARNESS.replace("// BINDINGS", bindings))
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-Isrc",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    "-fno-pie", "-no-pie", str(source), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1"})
print("native CTF bindings: absent/present/repeated flags and index zero passed (ASan/UBSan)")
