#!/usr/bin/env python3

from _paths import rel
import pathlib
import subprocess
import tempfile
from _paths import HARNESS_STUBS


ROOT = pathlib.Path(__file__).resolve().parents[2]


with tempfile.TemporaryDirectory(prefix="duris-flatfile-help-") as temporary:
    temporary_path = pathlib.Path(temporary)
    binary = temporary_path / "flatfile_help_catalog_test"
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Isrc",
            "tests/async/flatfile_help_catalog_harness.cpp",
            rel("flatfile_help_catalog.c"),
            str(HARNESS_STUBS), "-o",
            str(binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(binary), str(ROOT)], check=True)

    invalid_root = temporary_path / "invalid"
    (invalid_root / "lib/information").mkdir(parents=True)
    with (invalid_root / "lib/information/help_index").open("wb") as source:
        source.truncate(8 * 1024 * 1024 + 1)
    invalid = subprocess.run(
        [str(binary), str(invalid_root)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if invalid.returncode == 0:
        raise AssertionError("oversized help source was accepted")

    runtime_binary = temporary_path / "flatfile_help_runtime_test"
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-D__NO_MYSQL__",
            "-ffunction-sections",
            "-fdata-sections",
            "-Isrc/no_mysql",
            "-Isrc",
            "tests/async/flatfile_help_runtime_harness.cpp",
            rel("wikihelp.c"),
            rel("flatfile_help_catalog.c"),
            "-Wl,--gc-sections",
            str(HARNESS_STUBS), "-o",
            str(runtime_binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(runtime_binary)], cwd=ROOT, check=True)

    mud_info_binary = temporary_path / "flatfile_mud_info_runtime_test"
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-D__NO_MYSQL__",
            "-ffunction-sections",
            "-fdata-sections",
            "-Isrc/no_mysql",
            "-Isrc",
            "tests/async/flatfile_mud_info_runtime_harness.cpp",
            rel("sql.c"),
            rel("flatfile_help_catalog.c"),
            "-Wl,--gc-sections",
            str(HARNESS_STUBS), "-o",
            str(mud_info_binary),
        ],
        cwd=ROOT,
        check=True,
    )
    broken_root = temporary_path / "broken"
    (broken_root / "lib/information/motd").mkdir(parents=True)
    subprocess.run([str(mud_info_binary), str(broken_root)], cwd=ROOT, check=True)

print("flat-file help catalog regression passed")
