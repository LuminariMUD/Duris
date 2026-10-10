#!/usr/bin/env python3
"""Three log lines a reader can use, on a real server.

- A zone command that does not load (`M`, `F`, `R` with a chance roll that misses) is
  logged with its mob and room vnums. It printed the boot's internal indices, which match
  no vnum, so a builder could not find the command. An `R` that misses after an `M` that
  loaded its rider used to go on with no mount and crash the boot.
- A connection reset before the server accepts it has no peer address. Its host was
  "&+RUNTRACEABLE&n", and the color code went into every log line about it; it is
  "unknown".
- A shutdown writes its kind, issuer and reason to the status log. It wrote the players'
  broadcast, color codes and line ends included.
"""

from __future__ import annotations

import socket
import struct
import tempfile
import time
from pathlib import Path

from test_account_recovery_journey import IsolatedServer, build_flatfile_server, require

MISSED_LOADS = (
    "M 0 11 9 12 0 0 0 0 * a chance of 0 never loads\n"
    "F 0 11 9 12 0 0 0 0\n"
    "R 0 11 9 12 0 0 0 0\n"
    "M 0 12 9 12 100 0 0 0 * a rider that loads\n"
    "R 1 11 9 12 0 0 0 0 * and a mount that does not\n"
)


def missed_loads(run_root: Path) -> None:
    zone = run_root / "areas_mini/mini.zon"
    text = zone.read_text()
    require(text.count("\nS\n") == 1, "minimal zone terminator changed")
    zone.write_text(text.replace("\nS\n", "\n" + MISSED_LOADS + "S\n"))


def log(run_root: Path, name: str) -> str:
    path = run_root / "logs/log" / name
    return path.read_text(errors="replace") if path.exists() else ""


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="duris-log-hygiene-build-") as build:
        binary = build_flatfile_server(Path(build))
        with IsolatedServer(binary, None, missed_loads) as server:
            run_root = server.run_root
            mob_log = log(run_root, "mob")
            for kind in "MFR":
                line = (f"{kind} cmd not executed: mob 11 in room 12, limit 9, "
                        "chance 0%")
                require(line in mob_log, f"no {line!r} in the mob log:\n{mob_log[-4000:]}")

            # Reset before the server accepts it: getpeername() then fails. The server
            # accepts once a pulse, so it can take the connection before the reset; then
            # it is tried again.
            for _ in range(10):
                reset = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                reset.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                reset.connect(("127.0.0.1", server.plain_port))
                reset.close()
                deadline = time.monotonic() + 3
                while ("Losing descriptor without char [host=unknown"
                       not in log(run_root, "debug") and time.monotonic() < deadline):
                    time.sleep(0.1)
                if "Losing descriptor without char [host=unknown" in log(run_root, "debug"):
                    break
            else:
                raise AssertionError("a reset connection was not logged as host=unknown:\n"
                                     + log(run_root, "debug")[-4000:])

            server.shutdown()
            status = log(run_root, "status")
            require("Shutdown by Launcher: signal from launcher" in status,
                    "the status log does not say who stopped the game:\n" + status[-4000:])
            for raw in ("Word of Unmaking", "\r", "&+"):
                require(raw not in status, f"the status log holds {raw!r}:\n{status[-4000:]}")
            require("UNTRACEABLE" not in log(run_root, "debug"), "a host still carries color")
    print("log hygiene journey passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
