#!/usr/bin/env python3
"""Execute real SQL/flat Nexus loading, including empty and failed catalogues."""
import os
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, source

production = source("nexus_stones.c").read_text()
production = production[:production.index("int init_nexus_stones()")]
for signature in (
    "int init_nexus_stones()", "int load_nexus_stones(", "bool nexus_stone_info(",
    "P_char load_guardian(", "bool load_nexus_stone(",
):
    production += "\n" + extract_function("nexus_stones.c", signature) + "\n"
fixture = (ROOT / "tests/async/nexus_loader_harness.cpp").read_text()
assert fixture.count("// PRODUCTION_CODE") == 1
build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="nexus-loader-", dir=build) as temporary:
    directory = Path(temporary)
    path = directory / "nexus_loader.cpp"
    path.write_text(fixture.replace("// PRODUCTION_CODE", production))
    for backend in ("mysql", "flatfile"):
        binary = directory / backend
        flags = ["-D__NO_MYSQL__", "-Isrc/no_mysql"] if backend == "flatfile" else ["-I/usr/include/mysql"]
        subprocess.run([
            "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            "-Isrc", "-Isrc/ships", "-I/usr/include/libxml2", *flags,
            str(path), str(HARNESS_STUBS), "-o", str(binary),
        ], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True, env={
            **os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1",
        })
        print(f"{backend}: real Nexus boot/loader failure cases passed (ASan/UBSan).", flush=True)
