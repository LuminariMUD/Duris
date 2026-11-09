#!/usr/bin/env python3
"""Exercise flatfile_information_read(), the catalog function the server still uses."""

from _paths import rel
import pathlib
import subprocess
import tempfile
from _paths import HARNESS_STUBS


ROOT = pathlib.Path(__file__).resolve().parents[2]


with tempfile.TemporaryDirectory(prefix="duris-flatfile-help-") as temporary:
    binary = pathlib.Path(temporary) / "flatfile_help_catalog_test"
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

print("flat-file information read regression passed")
