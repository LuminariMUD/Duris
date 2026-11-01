#!/usr/bin/env python3
"""Clean cold boots may restock; crashes and recovery never grant that permission."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = r'''
#include "economy/shopkeeper_boot.h"
#include <cassert>
#include <cstdio>
#include <string>
int main(int argc, char **argv) {
    assert(argc == 3);
    std::string error;
    const std::string mode = argv[2];
    if (mode == "invalid") {
        assert(!shopkeeper_boot_begin(argv[1], false, &error));
        assert(!shopkeeper_boot_restock() && !error.empty());
        assert(!shopkeeper_boot_finish(argv[1], &error));
        return 0;
    }
    assert(shopkeeper_boot_begin(argv[1], mode == "recovery", &error));
    puts(shopkeeper_boot_restock() ? "refill" : "preserve");
    if (mode == "clean" || mode == "recovery") {
        assert(shopkeeper_boot_finish(argv[1], &error));
        assert(!shopkeeper_boot_restock());
        assert(!shopkeeper_boot_finish(argv[1], &error));
    } else if (mode == "write-failure") {
        assert(rename(argv[1], "moved") == 0);
        assert(!shopkeeper_boot_finish(argv[1], &error));
        assert(!shopkeeper_boot_restock() && !error.empty());
    }
}
'''

output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="shopkeeper-boot-", dir=output) as temporary:
    directory = Path(temporary)
    source = directory / "test.cpp"
    binary = directory / "test"
    source.write_text(PROGRAM)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-I", str(ROOT / "src"), str(source),
        str(ROOT / "src/economy/shopkeeper_boot.c"),
        str(ROOT / "src/flatfile/flatfile_store.c"), "-o", str(binary),
    ], check=True)
    state = directory / "boot"

    def run(mode, expected=""):
        result = subprocess.check_output([str(binary), str(state), mode], cwd=directory,
                                         text=True, timeout=15, env={
            **os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
        })
        assert result.strip() == expected, (mode, result, expected)

    run("clean", "preserve")  # Upgrade/first boot has no proven clean predecessor.
    run("leave", "refill")
    assert (state / "state").read_bytes() == b"R"
    run("leave", "preserve")  # New process after an unclean stop, no Redis required.
    run("clean", "preserve")
    run("recovery", "preserve")  # Both copyover and Redis world recovery use this path.
    run("clean", "refill")
    run("write-failure", "refill")
    assert (directory / "moved/state").read_bytes() == b"R"
    state.mkdir(mode=0o700)
    for invalid in (b"", b"X", b"CC"):
        (state / "state").write_bytes(invalid)
        (state / "state").chmod(0o600)
        run("invalid")
    (state / "state").unlink()
    (state / "state").symlink_to(directory / "moved/state")
    run("invalid")
    assert (directory / "moved/state").read_bytes() == b"R"

# Keep the permission consumed before world boot and granted only after a normal
# game-loop shutdown. These checks supplement the executable file/process cases.
comm = (ROOT / "src/net/comm.c").read_text()
assert comm.index('shopkeeper_boot_begin("shopkeeper-boot"') < comm.index(
    "const int game_exit_status = run_the_game(port, sslport)")
assert "copyover_boot || redis_world_recovery_boot_active()" in comm
assert comm.index('shopkeeper_boot_finish("shopkeeper-boot"') > comm.index("shutdown_mysql();")
assert "!mini_mode && shutdownflag && !_copyover &&" in comm
assert "game_exit_status == 0 || game_exit_status == 52 || game_exit_status == 54" in comm
print("Shopkeeper boot classification: clean, unclean, recovery, upgrade, invalid state, and write failure passed")
