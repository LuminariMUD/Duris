#!/usr/bin/env python3
"""Two studio-proc records for one target: the boot binds the first and logs and skips
the second. The engine dispatches one record per target, and a second bind would lose
the target's own C proc, so the second was dead and the C proc switched off."""
import argparse
from pathlib import Path
import tempfile

import run_item_pilot_journey as pilot
import test_mariadb_combat_journey as journey

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--server", type=Path, required=True)
binary = parser.parse_args().server.resolve()
with tempfile.TemporaryDirectory(prefix="duris-studioproc-run-") as run, \
        journey.mariadb_authority() as (environment, _):
    root = Path(run)
    pilot.configure(root, "studio", True)
    (root / "areas/world.trg").write_text("#22800 R\nT ENTER\necho first\n~\nS\n"
                                          "#22800 R\nT ENTER\necho second\n~\nS\n#~\n")
    (root / "logs/log").mkdir(parents=True, exist_ok=True)
    server = pilot.Server(binary, root, None, "studio", environment)
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
