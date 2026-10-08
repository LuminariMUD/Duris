#!/usr/bin/env python3
"""Two studio-proc records for one target: the boot binds the first and logs and skips
the second. The engine dispatches one record per target, and a second bind would lose
the target's own C proc, so the second was dead and the C proc switched off."""
from pathlib import Path
import tempfile

import run_item_pilot_journey as pilot
import server_build_artifacts

with tempfile.TemporaryDirectory(prefix="duris-studioproc-build-") as build, \
        tempfile.TemporaryDirectory(prefix="duris-studioproc-run-") as run, \
        tempfile.TemporaryDirectory(prefix="duris-studioproc-state-") as state:
    binary = server_build_artifacts.build_flatfile_server(Path(build))
    root, state = Path(run), Path(state)
    state.chmod(0o700)
    (state / "domains").mkdir(mode=0o700)
    pilot.configure(root, "studio", True)
    (root / "areas/world.trg").write_text("#22800 R\nT ENTER\necho first\n~\nS\n"
                                          "#22800 R\nT ENTER\necho second\n~\nS\n#~\n")
    (root / "logs/log").mkdir(parents=True, exist_ok=True)
    server = pilot.Server(binary, root, state, "studio")
    try:
        server.start()
    finally:
        server.stop()
    status = [line for line in (root / "logs/log/status").read_text(errors="replace").splitlines()
              if "STUDIOPROC" in line]
    assert any("parse error zone 228 vnum 22800 line 6: duplicate record" in line
               for line in status), status
    assert any("STUDIOPROC: 1 records, 1 triggers, 1 bound (0 mob, 0 obj, 1 room)" in line
               for line in status), status

print("a second studio-proc record for one target is logged and skipped")
