#!/usr/bin/env python3
"""Check bounded page output and execute the WebSocket-to-pager input path."""

import os
from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT, SRC, extract_function

source = (SRC / "modify.c").read_text()
start = source.index("void show_string(")
end = source.index("\n//--------------------------------------------------------------------", start)
show_string = source[start:end]

assert "d->showstr_vector[d->showstr_page + 1]" in show_string
assert "memcpy(buffer" in show_string
assert "buffer[page_length] = '\\0';" in show_string
assert "strlcpy(buffer, d->showstr_vector[d->showstr_page], sizeof buffer)" not in show_string

print("pager bounded-copy contract passed")

# Compile unchanged production bodies with the real descriptor types and cJSON.
# Only unrelated command handlers and world/output/telemetry boundaries are stubbed.
dispatcher = extract_function("ws_handlers.c", "void ws_handle_command(")
handlers = set(re.findall(r'\{ "[^"]+", (ws_cmd_\w+) \}', dispatcher))
assert "ws_cmd_game" in handlers
functions = [
    f"void {name}(P_desc, cJSON *) {{ assert(false); }}"
    for name in sorted(handlers - {"ws_cmd_game"})
]
functions.append(extract_function("interp.c", "const char *fill_words[]") + ";")
for filename, signatures in [
    ("utility.c", ["int strn_cmp("]),
    ("interp.c", ["int search_block(", "int fill_word(", "char *one_argument("]),
    ("comm.c", ["int get_from_q(", "void write_to_q(",
                "static session_input_route select_session_input(",
                "static void dispatch_session_input("]),
    ("modify.c", ["void free_paging_data(", "void show_string("]),
    ("ws_handlers.c", ["void ws_cmd_game("]),
]:
    functions.extend(extract_function(filename, signature) for signature in signatures)
functions.append(dispatcher)

build_root = ROOT / "bin/tests"
build_root.mkdir(parents=True, exist_ok=True)
flags = (["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie"]
         if os.environ.get("SANITIZE") == "1" else [])
with tempfile.TemporaryDirectory(prefix="websocket-pager-", dir=build_root) as directory:
    build = Path(directory)
    (build / "production_pager.inc").write_text("\n\n".join(functions))
    binary = build / "harness"
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Og", "-g",
        "-D__NO_MYSQL__", *flags, f"-I{ROOT / 'src'}", f"-I{ROOT / 'src/no_mysql'}",
        f"-I{build}", str(ROOT / "tests/async/websocket_pager_harness.cpp"),
        "-lcjson", "-o", str(binary),
    ], cwd=ROOT, check=True, timeout=120)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30, env={
        **os.environ,
        "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
        "UBSAN_OPTIONS": "halt_on_error=1",
    })
