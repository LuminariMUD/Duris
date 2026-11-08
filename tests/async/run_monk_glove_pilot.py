#!/usr/bin/env python3
"""Measure actual proc-point entries and activations for the four authored gloves.

GDB only counts the real terminal hook; it never changes RNG, damage or admission.
Disposable players/world, no .env, no live server and no production data changes.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import tempfile

import test_flatfile_combat_journey as journey
from run_item_pilot_journey import Server, configure, set_properties, object_records
from run_monk_glove_journey import command
from run_weapon_actions_journey import drain
from test_monk_glove_pilot import PILOT, record

ROOT = Path(__file__).resolve().parents[2]
ACTOR = "Valeron"
TARGET = "Verenal"
SPARK = "as your barehand strike lands!"
CASES = ((1, 0, "plain"), (30, 0, "plain"), (56, 1, "Dragon"),
         (56, 2, "Snake"), (56, 3, "Chi"))


def run(binary, seconds, verify_only=False):
    with tempfile.TemporaryDirectory(prefix="monk-pilot-game-", dir=ROOT / "bin/tests") as temporary:
        root = Path(temporary) / "runtime"; state = Path(temporary) / "state"
        root.mkdir(); state.mkdir(mode=0o700); (state / "domains").mkdir(mode=0o700)
        subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)
        configure(root, "studio", False)
        set_properties(root, {"hitpoints.class.Monk": 5000, "hitpoints.class.Warrior": 5000})
        objects = root / "areas_mini/mini.obj"
        records = object_records(objects.read_text())
        for vnum, source, _ in PILOT:
            records[vnum] = record(vnum, source)
        objects.write_text("".join(records[key] for key in sorted(records)) + "$~\n")
        zone = root / "areas_mini/mini.zon"
        zone.write_text(re.sub(r"^E .*\n", "", zone.read_text(), flags=re.M))
        for suffix in ("obj", "zon"):
            (root / f"areas/world.{suffix}").write_text((root / f"areas_mini/mini.{suffix}").read_text())
        executable = root / "server"; shutil.copy2(binary, executable)
        pid_path = root / "inferior.pid"
        gdb_path = root / "pilot.gdb"
        gdb_path.write_text(f"""set pagination off
set confirm off
handle SIGTERM nostop noprint pass
tbreak main
commands
silent
python open({str(pid_path)!r}, 'w').write(str(gdb.selected_inferior().pid))
continue
end
break dispatch_monk_glove_proc
commands
silent
if continuation.actor_runtime_id != 0
printf "MONK_OPPORTUNITY %llu\\n", continuation.actor_runtime_id
end
continue
end
run
""")
        launcher = root / "debug-server"
        launcher.write_text("#!/bin/sh\nexec gdb --batch --return-child-result -x " +
            shlex.quote(str(gdb_path)) + " --args " + shlex.quote(str(executable)) + ' "$@"\n')
        launcher.chmod(0o700)
        server = Server(launcher, root, state, "studio")
        connections = []

        def stop():
            if server.process and server.process.poll() is None and pid_path.exists():
                os.kill(int(pid_path.read_text()), signal.SIGTERM)
                server.process.wait(timeout=30)
            server.stop()

        def staff(text):
            return command(owner, text, .5)

        def stand_actor():
            for _ in range(12):
                command(actor, "wake", .4)
                output = command(actor, "stand", .5)
                if "Pos: standing" in output:
                    return
            raise AssertionError("fixture actor did not stand: " + output)

        results = []
        try:
            server.start()
            owner = server.client = journey.MudClient(server.port)
            journey.create_character(owner)
            command(owner, "save"); command(owner, "quit", 1)
            stop(); journey.make_overlord(state, journey.CHARACTER)
            server.start()
            owner = server.client = journey.reconnect_character(server.port)
            staff("vis 0")
            actor = journey.MudClient(server.port); connections.append(actor)
            journey.create_character(actor, class_name="k", account="Pilotmonk", character=ACTOR,
                                     email="pilot-monk@example.invalid")
            target = journey.MudClient(server.port); connections.append(target)
            journey.create_character(target, account="Pilottarget", character=TARGET,
                                     email="pilot-target@example.invalid")
            command(actor, "remove all"); command(actor, "drop all")
            for name in (ACTOR, TARGET):
                staff(f"setbit char {name} basehit 100000000"); staff(f"restore {name}")
            staff("setbit char sentinel hit 100000000")
            staff(f"setbit char {ACTOR} hitrol 100")
            for name in (TARGET, "sentinel"):
                staff(f"setbit char {name} aff5 'NOT OFFENSIVE' 1")
            for vnum, source, level in PILOT:
                keyword = record(vnum, source).splitlines()[1].split()[0]
                staff(f"load obj {vnum}")
                given = staff(f"give {keyword} {ACTOR}")
                assert "Ok." in given or "You give" in given, given
                worn = command(actor, f"wear {keyword}")
                assert "hands" in worn, worn
                for actor_level, spec, label in (() if verify_only else CASES):
                    staff(f"setbit char {ACTOR} level {actor_level}")
                    staff(f"setbit char {ACTOR} spec {spec}")
                    for kind, enemy in (("PvE", "sentinel"), ("PvP", TARGET)):
                        staff(f"tranquilize {ACTOR}")
                        stand_actor()
                        for name in (ACTOR, TARGET, "sentinel"):
                            staff(f"setbit char {name} hit 100000000")
                        drain(actor, .1); drain(target, .1)
                        offset = server.output_path.stat().st_size
                        output = command(actor, f"hit {enemy}", seconds)
                        staff(f"tranquilize {ACTOR}")
                        output += drain(actor, .2)
                        stand_actor()
                        log = server.output_path.read_text(errors="replace")[offset:]
                        hits = log.count("MONK_OPPORTUNITY ")
                        procs = output.count(SPARK)
                        assert hits > 0 and procs <= hits, (vnum, actor_level, label, kind, log[-1000:], output[-2000:])
                        row = dict(vnum=vnum, level=actor_level, spec=label, mode=kind,
                                   qualifying_strikes=hits, activations=procs, expected=round(hits/60, 3))
                        results.append(row); print(json.dumps(row), flush=True)
                command(actor, f"remove {keyword}")
            # Deterministic effect proof uses only a disposable extra instance;
            # all four authored templates and all samples above remain 1-in-60.
            staff("load obj 76052")
            staff("setbit obj sunstone val7 1")
            staff(f"give sunstone {ACTOR}")
            staff(f"setbit char {ACTOR} level 56")
            stand_actor(); command(actor, "wear sunstone")
            effect = command(actor, "hit sentinel", 6)
            staff(f"tranquilize {ACTOR}"); effect += drain(actor, .2)
            assert SPARK in effect and "You get a good hold of the shocked" in effect, effect
            stand_actor(); command(actor, "remove sunstone")
            print("live effect: actual shocking grasp and player spark message passed on a test-only 1-in-1 instance", flush=True)
            # Real identify preserves the conjurer-only packed spell-name access.
            staff("load obj 76052")
            ordinary = staff("cast 'identify' sunstone") + drain(owner, 2)
            assert "primary hands" in ordinary and "recognize the forces" not in ordinary, ordinary
            staff("setbit char Taverek secondary Conjurer")
            revealed = staff("cast 'identify' sunstone") + drain(owner, 2)
            assert "recognize the forces" in revealed and "shocking grasp" in revealed, revealed
            print("identify: all players see scope; level-56+ conjurers see spell names", flush=True)
            return results
        except Exception:
            for client in connections + ([server.client] if server.client else []):
                print(bytes(client.transcript).decode(errors="replace").replace(journey.PASSWORD, "[REDACTED]")[-5000:])
            print(server.output_path.read_text(errors="replace")[-5000:])
            raise
        finally:
            for client in connections:
                client.close()
            stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=6)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    results = run(args.binary.resolve(), args.seconds, args.verify_only)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
