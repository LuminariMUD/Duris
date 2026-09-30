#!/usr/bin/env python3
"""The in-memory character name index (persistence reset phase 2, step 8).

MariaDB answers sql_player_exists(), sql_get_player_pid() and sql_get_player_name() from
an index read at boot and kept current by entry, renames and deletion, so a lookup never
waits on the database. This links the production index functions and checks its rules:
case-insensitive lookups, only an active character has a name by pid, entry under a
name deactivates the other characters of that name, a rename moves the name, and a
deleted character is forgotten.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import SRC

ROOT = Path(__file__).resolve().parents[2]
source = (SRC / "sql_player.c").read_text()
mysql = source[source.index("\n// globals\n"):]
start = mysql.index("namespace\n{\n// Every player_data row's pid, name and active flag")
end = mysql.index("\nbool sql_player_names_load(void)", start)
index = mysql[start:end]
functions = mysql[mysql.index("\nvoid sql_player_names_set(int pid, const char *name)"):]
functions = functions[:functions.index("\nbool sql_player_exists(const char *name)")]
exists = mysql[mysql.index("\nbool sql_player_exists(const char *name)\n{"):]
exists = exists[:exists.index("\n}\n") + 3]
get_pid = mysql[mysql.index("\nint sql_get_player_pid(const char *name)\n{"):]
get_pid = get_pid[:get_pid.index("\n}\n") + 3]

harness = f'''
#include <cassert>
#include <cctype>
#include <cstring>
#include <string>
#include <unordered_map>

#define LOWER(c) ((char)std::tolower((unsigned char)(c)))
void sql_player_names_forget(int pid);

{index}
{functions}
{exists}
{get_pid}

int main()
{{
    sql_player_names_set(7, "Alpha");
    assert(sql_player_exists("ALPHA") && sql_get_player_pid("alpha") == 7);
    assert(!strcmp(sql_get_player_name(7), "Alpha"));
    assert(!sql_player_exists("Beta") && sql_get_player_pid("Beta") == -1);

    // Another character entering under the name takes it; the first loses its name.
    sql_player_names_set(9, "alpha");
    assert(sql_get_player_pid("Alpha") == 9 && !sql_get_player_name(7));

    // A rename moves the name.
    sql_player_names_set(9, "Gamma");
    assert(sql_get_player_pid("gamma") == 9 && !strcmp(sql_get_player_name(9), "Gamma"));
    assert(!sql_player_exists("alpha"));

    // A deleted character is forgotten.
    sql_player_names_forget(9);
    assert(!sql_player_exists("Gamma") && !sql_get_player_name(9));
    return 0;
}}
'''
build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="player-names-", dir=build) as directory:
    cpp = Path(directory) / "index.cpp"
    cpp.write_text(harness)
    exe = Path(directory) / "index"
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print("player names index passed")
