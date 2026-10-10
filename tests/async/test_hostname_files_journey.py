#!/usr/bin/env python3
"""lib/etc/hosts keeps no address past its connection (ADR 0003), on a real server.

The reverse-DNS lookup of each connection writes lib/etc/hosts/<descriptor>.<address>.
Nothing removed those files, so every client's address and name stayed there for good.
A cold boot now clears the directory, which takes what a lookup finished after its
connection closed, and a connection's files go when it closes. The directory's
.gitignore stays.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from test_account_recovery_journey import IsolatedServer, MudClient, build_flatfile_server, require


def hostname_files(run_root: Path) -> set[str]:
    return {path.name for path in (run_root / "lib/etc/hosts").iterdir()} - {".gitignore"}


def stale_files(run_root: Path) -> None:
    hosts = run_root / "lib/etc/hosts"
    hosts.mkdir(parents=True, exist_ok=True)
    (hosts / ".gitignore").write_text("/*\n!.gitignore\n")
    (hosts / "7.192.0.2.1").write_text("left.behind.example\n")
    (hosts / ".7.192.0.2.1.42.tmp").write_text("half written\n")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="duris-hostname-files-build-") as build:
        binary = build_flatfile_server(Path(build))
        with IsolatedServer(binary, None, stale_files) as server:
            run_root = server.run_root
            require(hostname_files(run_root) == set(),
                    f"the boot left {sorted(hostname_files(run_root))} in lib/etc/hosts")
            require((run_root / "lib/etc/hosts/.gitignore").is_file(),
                    "the boot removed lib/etc/hosts/.gitignore")

            client = MudClient(server.plain_port)
            deadline = time.monotonic() + 30
            while not hostname_files(run_root) and time.monotonic() < deadline:
                time.sleep(0.05)
            written = hostname_files(run_root)
            require(len(written) == 1 and next(iter(written)).endswith(".127.0.0.1"),
                    f"the lookup of 127.0.0.1 wrote {sorted(written)}")
            client.close()
            deadline = time.monotonic() + 30
            while hostname_files(run_root) and time.monotonic() < deadline:
                time.sleep(0.05)
            require(hostname_files(run_root) == set(),
                    f"a closed connection left {sorted(hostname_files(run_root))}")
            server.shutdown()
    print("hostname files journey passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
