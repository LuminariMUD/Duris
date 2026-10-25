#!/usr/bin/env python3
"""ASan/UBSan: execute real single/bulk put boundaries across trap callbacks."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function

functions = extract_function("actobj.c", "struct bulk_put_state") + ";\n"
functions += "\n".join(extract_function("actobj.c", signature) for signature in (
    "static bool get_can_continue(", "void save_filled_container(", "void report_bulk_put(",
    "bool bulk_put_destination_available(", "void start_bulk_put(",
    "static bool reject_put_trap(", "bool put(P_char ch,",
))
harness = (ROOT / "tests/async/put_trap_lifecycle_harness.cpp").read_text()
harness = harness.replace("// PUT_FUNCTIONS", functions)
build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="put-trap-lifecycle-", dir=build) as directory:
    source = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    source.write_text(harness)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-pie", "-no-pie",
        "-Isrc", "-I/usr/include/mysql", str(source), str(HARNESS_STUBS), "-o", str(binary)
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
print("single/bulk put: permissions, trap rejection, extraction and earlier destination saves passed")
