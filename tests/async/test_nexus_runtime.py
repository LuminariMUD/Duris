#!/usr/bin/env python3
"""Run the real Nexus sage and guardian lifecycle paths with ASan/UBSan."""
from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, rel

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="nexus-runtime-", dir=build) as temporary:
    directory = Path(temporary)
    utility = directory / "char_stat.cpp"
    utility.write_text('#include "core/prototypes.h"\n#include "core/defines.h"\n' +
                       extract_function("utility.c", "sh_int *char_stat("))
    binary = directory / "nexus_runtime"
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
        "-ffunction-sections", "-fdata-sections", "-D__NO_MYSQL__",
        "-Isrc", "-Isrc/no_mysql", "-Isrc/ships", "-I/usr/include/libxml2",
        "tests/async/nexus_runtime_harness.cpp", rel("nexus_stones.c"),
        rel("flatfile_nexus_repository.c"), rel("flatfile_store.c"),
        str(utility), str(HARNESS_STUBS), "-Wl,--gc-sections", "-lcrypto", "-pthread",
        "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary), str(directory / "state")], cwd=ROOT, check=True,
                   env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
                        "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})

print("Nexus sage and guardian runtime regression passed (ASan/UBSan).")
