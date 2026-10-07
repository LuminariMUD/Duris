#!/usr/bin/env python3
"""#14: how late multi-segment casts finish on a real server.

Boots the full world on the flat-file backend (no database), creates a level-56
MindFlayer and has it cast ``adrenaline control`` (three or more segments of up to
four pulses) a number of times with ``DURIS_NEVENT_TRACE_PLAYER=1``. The
``PLAYER EVENT TIMING`` lines in ``logs/log/status`` give, for every segment, the
tick it was due and the tick it ran at. ``--budget-usec`` cuts the event pass's
budget so that it defers work every pulse, which is the load the item describes;
without it the server's default applies.

    python3 tests/async/run_cast_timing_probe.py --server <flat-file dms_new> [--casts 20] [--budget-usec 2000]
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPELL = "adrenaline control"
START = "You begin to focus your will..."
COMPLETE = "Your mental manipulations become a reality..."
FAILURES = (
    "You lost your concentration!",
    "You abort your spell before it's done!",
    "You can't",
    "You don't",
)
TIMING = re.compile(
    r"PLAYER EVENT TIMING: func=event_spellcast sequence=\d+ ch_pid=-?\d+"
    r" due_tick=(\d+) actual_tick=(\d+) late_pulses=(\d+)"
)
WINDOW = re.compile(
    r"NEVENT BUDGET WINDOW: .* deferring_pulses=(\d+) deferred=(\d+) .* max_late_ticks=(\d+)"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def create_mindflayer(client: journey.MudClient) -> None:
    """A new account and a human MindFlayer; chaos mode asks no hardcore question."""
    entry, _ = client.expect_any(("term type", "account name"))
    if entry == "term type":
        client.send("9")
        client.expect("account name")
    client.send("Probeacct")
    client.expect("is this correct?")
    client.send("y")
    client.expect("email address")
    client.send("probe@example.invalid")
    client.expect("is this correct?")
    client.send("y")
    client.expect("enter your password")
    client.send(journey.PASSWORD)
    client.expect("Please re-enter the same password to confirm:  ")
    client.send(journey.PASSWORD)
    client.expect("information correct?")
    client.send("y")
    client.expect("PRESS RETURN")
    client.send("")
    client.expect("Please select an option")
    client.send("2")
    client.expect("Enter your new name")
    client.send("Probecaster")
    client.expect("Is this correct?")
    client.send("y")
    client.expect("meet these criteria?")
    client.send("y")
    client.expect("Your selection")
    client.send("h")
    client.expect("Male or Female")
    client.send("m")
    client.expect("Class Selection")
    client.send("mindflayer")
    client.expect("Alignment only affects")
    client.send("g")
    client.expect("Your selection")
    client.send("p")
    client.expect("Press return to continue")
    client.send("")
    for label in ("first bonus", "second bonus", "third bonus", "fourth bonus"):
        client.expect(label)
        client.send("s")
    client.expect("swap stats")
    client.send("n")
    client.expect("keep this character")
    client.send("y")
    client.expect("PRESS RETURN")
    client.send("")
    client.expect("Pos: standing >", timeout=30)


def casts_from_trace(text: str) -> list[list[tuple[int, int, int]]]:
    """Group the callbacks into casts.

    A segment is due within four pulses of the callback that scheduled it, and the
    client waits longer than that between casts.
    """
    casts: list[list[tuple[int, int, int]]] = []
    previous_actual = None
    for match in TIMING.finditer(text):
        due, actual, late = (int(match.group(i)) for i in (1, 2, 3))
        if previous_actual is None or due - previous_actual > 4:
            casts.append([])
        casts[-1].append((due, actual, late))
        previous_actual = actual
    return casts


def report(status: str, casts_asked: int) -> None:
    casts = casts_from_trace(status)
    require(len(casts) == casts_asked, f"the trace holds {len(casts)} casts, not {casts_asked}")
    require(all(len(cast) > 1 for cast in casts), "a cast had one segment only")
    # The cast time depends on the character's stats and affects. A cast is never
    # shorter than it, and a cast with no late callback takes exactly it.
    pulses = [cast[-1][1] - (cast[0][0] - 4) for cast in casts]
    sums = [sum(segment[2] for segment in cast) for cast in casts]
    lasts = [cast[-1][2] for cast in casts]
    cast_pulses = min(pulses)
    on_time = any(total == 0 for total in sums)
    for cast in casts:
        require(len(cast) == -(-cast_pulses // 4), f"a cast has {len(cast)} segments")
    print(f"{'cast':>4} {'pulses':>6} {'extra':>5} {'sum_late':>8} {'last_late':>9}  lateness per segment")
    for number, cast in enumerate(casts, 1):
        late = [segment[2] for segment in cast]
        print(f"{number:>4} {pulses[number - 1]:>6} {pulses[number - 1] - cast_pulses:>5}"
              f" {sums[number - 1]:>8} {lasts[number - 1]:>9}  {late}")
    windows = [tuple(int(group) for group in match.groups()) for match in WINDOW.finditer(status)]
    print(
        f"load: {len(windows)} budget windows, deferring pulses {sum(w[0] for w in windows)},"
        f" deferred events {sum(w[1] for w in windows)},"
        f" worst callback {max((w[2] for w in windows), default=0)} pulses late"
    )
    extras = [total - cast_pulses for total in pulses]
    print(
        f"casts: {len(casts)} of {cast_pulses} pulses"
        f" ({'a cast with no late callback took that' if on_time else 'the shortest cast; none had every callback on time'}),"
        f" {sum(1 for extra in extras if extra > 0)} finished late,"
        f" extra pulses mean {sum(extras) / len(extras):.2f} max {max(extras)},"
        f" lateness summed mean {sum(sums) / len(sums):.2f} max {max(sums)},"
        f" last segment's mean {sum(lasts) / len(lasts):.2f} max {max(lasts)}"
    )


def run(binary: pathlib.Path, casts: int, budget_usec: int | None, gap: float) -> None:
    with tempfile.TemporaryDirectory(prefix="cast-probe-state-") as state_tmp, \
            tempfile.TemporaryDirectory(prefix="cast-probe-run-") as run_tmp:
        state_root = pathlib.Path(state_tmp)
        run_root = pathlib.Path(run_tmp)
        state_root.chmod(0o700)
        (run_root / "logs/log").mkdir(parents=True)
        for directory in ("areas", "areas_mini", "docs"):
            (run_root / directory).symlink_to(ROOT / directory, target_is_directory=True)
        shutil.copytree(ROOT / "lib", run_root / "lib")
        journey.generate_certificate(run_root)
        (run_root / "journals/players").mkdir(parents=True, mode=0o700)
        (run_root / "journals/critical").mkdir(mode=0o700)
        port, tls_port, websocket_port = journey.available_ports()
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "ENVIRONMENT": "local",
            "PERSISTENCE_MODE": "flatfile-primary",
            "FLATFILE_STATE_DIR": str(state_root),
            "CRITICAL_COMMAND_JOURNAL_DIR": str(run_root / "journals/critical"),
            "LISTEN_ADDRESS": "127.0.0.1",
            "DURIS_TLS_PORT": str(tls_port),
            "DURIS_WEBSOCKET_LISTEN_ADDRESS": "127.0.0.1",
            "DURIS_WEBSOCKET_PORT": str(websocket_port),
            "REDIS": "FALSE",
            # A new character is level 56, so a first-circle spell is never aborted
            # as a top-circle one, and casts through the real will path with mana.
            "CHAOS_MUD": "TRUE",
            "CREATION_ALL_CLASSES": "TRUE",
            "CHAOS_STARTER_EPIC_SKILLS": "TRUE",
            "DURIS_NEVENT_TRACE_PLAYER": "1",
        }
        if budget_usec is not None:
            environment["DURIS_NEVENT_BUDGET_USEC"] = str(budget_usec)
        if runtime_library_path := os.environ.get("LD_LIBRARY_PATH"):
            environment["LD_LIBRARY_PATH"] = runtime_library_path
        output_path = run_root / "server.out"
        with output_path.open("w", encoding="utf-8") as output:
            process = subprocess.Popen(
                [str(binary), "-d", str(run_root), str(port)],
                cwd=run_root, env=environment, text=True, stdout=output, stderr=subprocess.STDOUT,
            )
            client: journey.MudClient | None = None
            try:
                deadline = time.monotonic() + 120
                while "Entering game loop." not in output_path.read_text(errors="replace"):
                    require(process.poll() is None and time.monotonic() < deadline,
                            "the server did not boot:\n" + output_path.read_text(errors="replace")[-8000:])
                    time.sleep(0.1)
                client = journey.MudClient(port)
                create_mindflayer(client)
                client.send("score")
                require("Level: 56" in client.expect("Pos: standing >", timeout=15),
                        "the caster is not level 56")
                for number in range(1, casts + 1):
                    client.send(f"will '{SPELL}'")
                    outcome, text = client.expect_any((START, COMPLETE, *FAILURES), timeout=15)
                    require(outcome == START, f"cast {number} did not start: {outcome!r} in {text!r}")
                    outcome, text = client.expect_any((COMPLETE, *FAILURES), timeout=60)
                    require(outcome == COMPLETE, f"cast {number} did not complete: {outcome!r} in {text!r}")
                    time.sleep(gap)
                client.close()
                client = None
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                require(process.returncode == 0, f"the server stopped with {process.returncode}")
                budget = "default" if budget_usec is None else f"{budget_usec} us"
                print(f"server {binary}, event budget {budget}, {casts} casts of '{SPELL}'")
                report((run_root / "logs/log/status").read_text(errors="replace"), casts)
            except Exception as error:
                raise AssertionError(
                    f"{error}\n--- server output ---\n{output_path.read_text(errors='replace')[-12000:]}"
                ) from error
            finally:
                if client is not None:
                    client.close()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--server", type=pathlib.Path, required=True,
                        help="a flat-file dms_new")
    parser.add_argument("--casts", type=int, default=20)
    parser.add_argument("--budget-usec", type=int,
                        help="DURIS_NEVENT_BUDGET_USEC for the run; unset keeps the default")
    parser.add_argument("--gap", type=float, default=2.0,
                        help="seconds between casts, more than one segment (4 pulses)")
    args = parser.parse_args()
    binary = args.server.resolve()
    require(binary.is_file() and os.access(binary, os.X_OK), f"not an executable: {binary}")
    run(binary, args.casts, args.budget_usec, args.gap)


if __name__ == "__main__":
    main()
