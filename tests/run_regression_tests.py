#!/usr/bin/env python3
"""Discover and run Duris' plain-Python regression tests."""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEST_DIRECTORY = ROOT / "tests" / "async"
MAX_AUTOMATIC_JOBS = 8
# A test still running at its deadline is ended with its process group and counted as a
# failure. A pooled test may first build a server artifact (about three minutes); the
# slowest journey measured 309 s on a loaded host.
POOLED_DEADLINE_SECONDS = 900
JOURNEY_DEADLINE_SECONDS = 1800
# How often a line names the tests still running.
PROGRESS_SECONDS = 60
RESOURCE_INTENSIVE_TEST_NAMES = frozenset(
    {
        "test_account_recovery_journey.py",
        "test_creation_prompt_journey.py",
        "test_game_loop_session_journey.py",
        "test_area_coin_pickup.py",
        "test_flatfile_auction_coin_put_journey.py",
        "test_flatfile_boot_preflight.py",
        "test_flatfile_chaos_new_character_kit.py",
        "test_flatfile_combat_journey.py",
        "test_flatfile_newbie_regrant_journey.py",
        "test_flatfile_first_session_currency.py",
        "test_flatfile_full_world_boot.py",
        "test_generated_npc_journey.py",
        "test_item_movement_prompt_runtime.py",
        "test_information_cache_journey.py",
        "test_mysql_combat_journey.py",
    }
)

# These real-runtime probes require explicitly supplied artifacts or helpers
# (test_pet_restart_journey.py a flat-file server; test_mob_gold_dial_runtime.py a
# server and a level promotion helper). The MySQL playtime journey needs a
# disposable database and --server, and invokes its repository probe with that
# database's environment. They are run explicitly, not by the generic test-all runner,
# which invokes every discovered script with no arguments.
MANUAL_ONLY_TEST_NAMES = frozenset(
    {
        "test_mob_gold_dial_runtime.py",
        "test_mysql_playtime_journey.py",
        "test_pet_restart_journey.py",
        "test_playtime_mysql_repository.py",
    }
)


@dataclass(frozen=True)
class TestResult:
    path: Path
    returncode: int
    output: str
    elapsed: float
    timed_out: bool = False

    @property
    def status(self) -> str:
        if self.timed_out:
            return "TIMEOUT"
        if self.returncode < 0:
            try:
                return signal.Signals(-self.returncode).name
            except ValueError:
                return f"SIGNAL {-self.returncode}"
        return "PASS" if self.returncode == 0 else "FAIL"


def discover_tests(match: str | None) -> list[Path]:
    tests = sorted(
        path for path in TEST_DIRECTORY.glob("test_*.py")
        if path.name not in MANUAL_ONLY_TEST_NAMES
    )
    if match:
        tests = [path for path in tests if match in path.name]
    return tests


def automatic_jobs() -> int:
    return min(MAX_AUTOMATIC_JOBS, max(1, os.cpu_count() or 1))


def partition_tests(tests: list[Path]) -> tuple[list[Path], list[Path]]:
    parallel = [path for path in tests if path.name not in RESOURCE_INTENSIVE_TEST_NAMES]
    resource_intensive = [path for path in tests if path.name in RESOURCE_INTENSIVE_TEST_NAMES]
    return parallel, resource_intensive


# The tests now running, so that a runner that is stopped can end them too; once it is
# stopping, a test that a worker starts anyway is ended at once.
running: set[subprocess.Popen] = set()
running_lock = threading.Lock()
stopping = False


def end_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def stop_running_tests() -> None:
    global stopping
    with running_lock:
        stopping = True
        for process in running:
            end_group(process)


def run_test(path: Path, deadline: float) -> TestResult:
    started = time.monotonic()
    # A file, not a pipe: reading it does not wait on a process that outlives the test.
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(
            [sys.executable, str(path)],
            cwd=ROOT,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        with running_lock:
            running.add(process)
            if stopping:
                end_group(process)
        timed_out = False
        try:
            process.wait(timeout=deadline)
        except subprocess.TimeoutExpired:
            timed_out = True
            end_group(process)
            process.wait()
        with running_lock:
            running.discard(process)
        output.seek(0)
        text = output.read().decode(errors="replace")
    return TestResult(
        path=path,
        returncode=process.returncode,
        output=text,
        elapsed=time.monotonic() - started,
        timed_out=timed_out,
    )


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jobs",
        type=int,
        default=0,
        help="parallel workers (0: automatic, capped at 8)",
    )
    parser.add_argument(
        "--match",
        metavar="TEXT",
        help="only run tests whose filename contains TEXT",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list discovered tests without running them",
    )
    args = parser.parse_args()
    if args.jobs < 0:
        parser.error("--jobs must be zero or greater")
    return args


def main() -> int:
    args = parse_args()
    tests = discover_tests(args.match)

    if args.list:
        for path in tests:
            print(relative(path))
        print(f"{len(tests)} test(s)")
        return 0

    if not tests:
        print("error: no regression tests matched", file=sys.stderr)
        return 2

    os.environ.setdefault("DURIS_REGRESSION_BUILD_CACHE", str(ROOT / "bin/regression-artifacts"))
    jobs = args.jobs or automatic_jobs()
    parallel_tests, resource_intensive_tests = partition_tests(tests)
    started = time.monotonic()
    failures: list[TestResult] = []
    completed_count = 0
    print(
        f"Running {len(tests)} Python regression tests with {jobs} worker(s), "
        f"then {len(resource_intensive_tests)} journey(s) side by side"
    )

    def report(result: TestResult) -> None:
        nonlocal completed_count
        completed_count += 1
        print(
            f"[{completed_count:>{len(str(len(tests)))}}/{len(tests)}] "
            f"{result.status} {relative(result.path)} ({result.elapsed:.2f}s)",
            flush=True,
        )
        builds = re.findall(r"SERVER_BUILD (built|reused) build=([0-9.]+)s lookup=([0-9.]+)s", result.output)
        if builds:
            build_time = sum(float(build) for _, build, _ in builds)
            lookup_time = sum(float(lookup) for _, _, lookup in builds)
            print(f"    server artifacts: {', '.join(status for status, _, _ in builds)}; "
                  f"build {build_time:.3f}s; validation {lookup_time:.3f}s; "
                  f"journey/other {max(0, result.elapsed - build_time - lookup_time):.3f}s", flush=True)
        if result.status != "PASS":
            failures.append(result)
            print(f"--- {relative(result.path)} output ---")
            print(result.output.rstrip() or "(no output)", flush=True)

    def run_all(paths: list[Path], workers: int, deadline: float) -> None:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            try:
                futures: dict[Future[TestResult], Path] = {
                    executor.submit(run_test, path, deadline): path for path in paths
                }
                pending = set(futures)
                last_progress = time.monotonic()
                while pending:
                    done, pending = wait(pending, timeout=PROGRESS_SECONDS, return_when=FIRST_COMPLETED)
                    for future in done:
                        report(future.result())
                    if pending and time.monotonic() - last_progress >= PROGRESS_SECONDS:
                        names = sorted(relative(futures[future]) for future in pending if future.running())
                        print(f"    still running: {', '.join(names)}", flush=True)
                        last_progress = time.monotonic()
            except BaseException:
                # Ctrl-C or SIGTERM: start nothing more, and end what is running.
                executor.shutdown(wait=False, cancel_futures=True)
                stop_running_tests()
                raise

    run_all(parallel_tests, jobs, POOLED_DEADLINE_SECONDS)
    # These wait on game time, not on the CPU, so they run together after the pool.
    run_all(resource_intensive_tests, max(1, len(resource_intensive_tests)), JOURNEY_DEADLINE_SECONDS)

    if failures:
        print("\nFailed:")
        for result in failures:
            print(f"    {result.status} {relative(result.path)}")
    elapsed = time.monotonic() - started
    timeouts = sum(result.timed_out for result in failures)
    signals = sum(not result.timed_out and result.returncode < 0 for result in failures)
    passed = len(tests) - len(failures)
    print(
        f"\n{passed} passed, {len(failures)} failed "
        f"({timeouts} timed out, {signals} ended by a signal) in {elapsed:.2f}s"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    # A SIGTERM (a supervisor, `timeout`) unwinds like Ctrl-C, which ends the running tests.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(128 + signal.SIGTERM))
    raise SystemExit(main())
