#!/usr/bin/env python3
"""Runtime and build-contract tests for the MariaDB-only persistence backend."""

from _paths import SRC
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = SRC / "persistence/persistence_mode.c"
MAKEFILE = (SRC / "Makefile").read_text()

PROBE = r'''
#include "persistence/persistence_mode.h"

#include <cstdio>
#include <cstring>

int main()
{
    char error[2048] = {};
    if (!persistence_mode_configure(error, sizeof(error)))
    {
        std::puts(error);
        return 1;
    }
    return std::strcmp(persistence_mode_name(), "mariadb-primary") ? 2 : 0;
}
'''

assert "PERSISTENCE_BACKEND ?= mariadb" in MAKEFILE
assert "__NO_MYSQL__" not in MAKEFILE
assert "no_mysql" not in MAKEFILE

with tempfile.TemporaryDirectory(prefix="persistence-mode-") as directory:
    temp = Path(directory)
    probe = temp / "probe.cpp"
    binary = temp / "probe"
    probe.write_text(PROBE)
    subprocess.run(
        ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", f"-I{SRC}", str(SOURCE), str(probe),
         "-o", str(binary)],
        check=True,
    )

    def run_probe(mode):
        env = {key: value for key, value in os.environ.items() if key != "PERSISTENCE_MODE"}
        if mode is not None:
            env["PERSISTENCE_MODE"] = mode
        return subprocess.run([str(binary)], env=env, capture_output=True, text=True)

    for accepted in (None, "", "mariadb-primary"):
        assert run_probe(accepted).returncode == 0, accepted

    for rejected in ("flatfile-primary", "mariadb-primary-flatfile-fallback", "automatic"):
        result = run_probe(rejected)
        assert result.returncode == 1, rejected
        assert f"invalid PERSISTENCE_MODE '{rejected}'" in result.stdout, result.stdout
        assert "MariaDB is the only supported backend" in result.stdout, result.stdout

    build = temp / "build"
    build_flags = [f"BIN_ROOT={build}", f"OBJDIR={build / 'objects/server'}",
                   f"DMS_BINARY={build / 'server/dms_new'}", "-n"]
    default_build = subprocess.run(
        ["make", "-C", str(SRC), *build_flags], check=True, capture_output=True, text=True
    ).stdout
    assert "-I/usr/include/mysql" in default_build
    assert "-lmysqlclient" in default_build
    assert "__NO_MYSQL__" not in default_build

    explicit_build = subprocess.run(
        ["make", "-C", str(SRC), "PERSISTENCE_BACKEND=mariadb", *build_flags],
        check=True, capture_output=True, text=True,
    ).stdout
    assert "-lmysqlclient" in explicit_build

    for backend in ("flatfile", "unknown"):
        rejected_build = subprocess.run(
            ["make", "-C", str(SRC), f"PERSISTENCE_BACKEND={backend}", *build_flags],
            capture_output=True, text=True,
        )
        assert rejected_build.returncode != 0, backend
        assert "PERSISTENCE_BACKEND must be mariadb" in rejected_build.stderr, rejected_build.stderr

print("persistence mode runtime and build contract passed")
