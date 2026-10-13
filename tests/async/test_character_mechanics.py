#!/usr/bin/env python3
"""Compile the character identity connections; broader site migration is still open."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, source


build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
inputs = [
    ROOT / "tests/async/character_mechanics_harness.cpp",
    source("character_mechanics.c"), source("common.c"), source("constant.c"),
    source("creation_availability_config.c"), source("specializations.c"), source("utility.c"),
    HARNESS_STUBS,
]
with tempfile.TemporaryDirectory(prefix="character-mechanics-", dir=build) as directory:
    work = Path(directory)
    (work / "lib").mkdir()
    shutil.copyfile(ROOT / "lib/creation_availability.cfg", work / "lib/creation_availability.cfg")
    binary = work / "harness"
    subprocess.run([
        "g++", "-std=c++20", "-g", "-D__NO_MYSQL__", "-ffunction-sections", "-fdata-sections",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-I" + str(ROOT / "src"), "-I" + str(ROOT / "src/no_mysql"),
        *map(str, inputs), "-Wl,--gc-sections", "-lbsd",
        "-o", str(binary),
    ], check=True)
    # Deliberately replace inherited overrides. No .env or running game is used.
    env = dict(os.environ, CHAOS_MUD="FALSE", CREATION_ALL_RACES="FALSE",
               CREATION_ALL_CLASSES="FALSE")
    subprocess.run([str(binary)], cwd=work, env=env, check=True)
    print("Native executable SHA256:", hashlib.sha256(binary.read_bytes()).hexdigest())
