"""Contracts for the repository-level build and regression harness."""

import contextlib
import importlib.util
import io
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
RUNNER = ROOT / "tests" / "run_regression_tests.py"

assert MAKEFILE.is_file(), "the repository root Makefile is missing"
makefile = MAKEFILE.read_text()
for target in (
    "build",
    "build-server",
    "build-editor",
    "build-area-tools",
    "build-deps-package",
    "world",
    "test",
    "test-all",
    "test-python",
    "test-native",
    "test-list",
    "test-db",
    "clean-all",
):
    assert re.search(rf"^{re.escape(target)}(?:\s*:|:)", makefile, re.MULTILINE), (
        f"root Makefile target is missing: {target}"
    )

assert "tests/run_regression_tests.py" in makefile
assert "tests/async/run_signal_handlers.sh" in makefile
# test-all builds both profiles: the production one compiles at -O2, where the
# warning profile reports what the development build does not see.
assert re.search(r"^test-all:\s*build build-production\s*$", makefile, re.MULTILINE)
assert "BUILD_PROFILE=production" in makefile
assert "$(MAKE) test" in makefile

runner_spec = importlib.util.spec_from_file_location("duris_regression_runner", RUNNER)
assert runner_spec is not None and runner_spec.loader is not None
runner = importlib.util.module_from_spec(runner_spec)
sys.modules[runner_spec.name] = runner
runner_spec.loader.exec_module(runner)
expected_resource_intensive = {
    "test_account_recovery_journey.py",
    "test_connection_limit_journey.py",
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
assert runner.RESOURCE_INTENSIVE_TEST_NAMES == expected_resource_intensive
assert runner.MANUAL_ONLY_TEST_NAMES == {
    "test_mob_gold_dial_runtime.py",
    "test_mysql_playtime_journey.py",
    "test_pet_restart_journey.py",
    "test_playtime_mysql_repository.py",
}
discovered = {path.name for path in runner.discover_tests(None)}
assert not (runner.MANUAL_ONLY_TEST_NAMES & discovered)
assert {
    "test_player_playtime_capture.py", "test_playtime_checkpoint.py",
    "test_playtime_flatfile.py",
} <= discovered
sample_tests = [
    Path("test_fast.py"),
    Path("test_flatfile_combat_journey.py"),
    Path("test_flatfile_auction_coin_put_journey.py"),
    Path("test_account_recovery_journey.py"),
    Path("test_mysql_combat_journey.py"),
    Path("test_information_cache_journey.py"),
    Path("test_creation_prompt_journey.py"),
]
parallel_tests, resource_intensive_tests = runner.partition_tests(sample_tests)
assert parallel_tests == [Path("test_fast.py")]
assert resource_intensive_tests == sample_tests[1:]


def gone(pid: int) -> bool:
    # A process reaped between the open and the read fails the read with ESRCH.
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z"
    except (FileNotFoundError, ProcessLookupError):
        return True


def all_gone(pids: list[int]) -> bool:
    deadline = time.monotonic() + 5
    while not all(gone(pid) for pid in pids) and time.monotonic() < deadline:
        time.sleep(0.05)
    return all(gone(pid) for pid in pids)


# A test that hangs, or whose child does, is ended at its deadline with everything it
# started, and the run goes on; a failure keeps its output.
with tempfile.TemporaryDirectory(prefix="duris-runner-") as scratch:
    tests_dir = Path(scratch) / "tests" / "async"
    tests_dir.mkdir(parents=True)
    scripts = {
        "test_sleeps.py": "import os, pathlib, time\n"
        "pathlib.Path(__file__).with_suffix('.pids').write_text(str(os.getpid()))\n"
        "time.sleep(600)\n",
        "test_child_sleeps.py": "import os, pathlib, subprocess, sys\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'])\n"
        "pathlib.Path(__file__).with_suffix('.pids').write_text(f'{os.getpid()} {child.pid}')\n"
        "child.wait()\n",
        "test_fails.py": "print('synthetic failure output')\nraise SystemExit(1)\n",
        "test_passes.py": "print('fine')\n",
        "test_signalled.py": "import os, signal\nos.kill(os.getpid(), signal.SIGTERM)\n",
        "test_crashes.py": "import os, pathlib, signal, subprocess, sys\n"
        "server = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'])\n"
        "pathlib.Path(__file__).with_suffix('.pids').write_text(str(server.pid))\n"
        "os.kill(os.getpid(), signal.SIGKILL)\n",
    }
    for name, source in scripts.items():
        (tests_dir / name).write_text(source)

    for name in ("test_sleeps.py", "test_child_sleeps.py"):
        result = runner.run_test(tests_dir / name, 1)
        assert result.timed_out and result.status == "TIMEOUT", result
        assert result.elapsed < 10, result
        pids = [int(pid) for pid in (tests_dir / name).with_suffix(".pids").read_text().split()]
        assert all_gone(pids), f"{name} left a process behind: {pids}"
    result = runner.run_test(tests_dir / "test_fails.py", 1)
    assert result.status == "FAIL" and "synthetic failure output" in result.output, result
    # However a test ends, what it left running goes with it: here the server of a test
    # that died before it could stop it.
    result = runner.run_test(tests_dir / "test_crashes.py", 10)
    assert result.status == "SIGKILL" and result.elapsed < 10, result
    server = int((tests_dir / "test_crashes.pids").read_text())
    assert all_gone([server]), f"test_crashes.py left its server running: {server}"

    # Through main(): a failure's output comes when it fails, a line names what is still
    # running, and the summary counts timeouts and signals apart.
    output = io.StringIO()
    with mock.patch.object(runner, "ROOT", Path(scratch)), \
         mock.patch.object(runner, "TEST_DIRECTORY", tests_dir), \
         mock.patch.object(runner, "POOLED_DEADLINE_SECONDS", 2), \
         mock.patch.object(runner, "PROGRESS_SECONDS", 0.5), \
         mock.patch.object(sys, "argv", ["runner", "--jobs", "5"]), \
         mock.patch.dict(os.environ), \
         contextlib.redirect_stdout(output):
        assert runner.main() == 1
    text = output.getvalue()
    summary = "1 passed, 5 failed (2 timed out, 2 ended by a signal) in "
    assert summary in text, text
    assert text.index("synthetic failure output") < text.index("\nFailed:") < text.index(summary), text
    assert "still running: tests/async/test_child_sleeps.py, tests/async/test_sleeps.py" in text, text
    for line in ("TIMEOUT tests/async/test_sleeps.py", "TIMEOUT tests/async/test_child_sleeps.py",
                 "FAIL tests/async/test_fails.py", "SIGTERM tests/async/test_signalled.py",
                 "SIGKILL tests/async/test_crashes.py"):
        assert f"    {line}\n" in text, text

    # Stopping the runner, by Ctrl-C or by a SIGTERM from a supervisor or `timeout`, ends
    # the test it is running with everything it started, and starts no other.
    shutil.copy(RUNNER, tests_dir.parent / RUNNER.name)
    for stop, status in ((signal.SIGINT, -signal.SIGINT), (signal.SIGTERM, 128 + signal.SIGTERM)):
        for pids in tests_dir.glob("*.pids"):
            pids.unlink()
        # A shell's background job inherits SIGINT ignored; a terminal's runner does not.
        process = subprocess.Popen(
            [sys.executable, str(tests_dir.parent / RUNNER.name), "--jobs", "1", "--match", "sleeps"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL))
        started = tests_dir / "test_child_sleeps.pids"
        deadline = time.monotonic() + 10
        while len(started.read_text().split() if started.exists() else ()) < 2:
            assert time.monotonic() < deadline, "the runner did not start test_child_sleeps.py"
            time.sleep(0.05)
        process.send_signal(stop)
        assert process.wait(timeout=10) == status, (stop, process.returncode)
        pids = [int(pid) for pid in started.read_text().split()]
        assert all_gone(pids), f"{stop.name} left a test running: {pids}"
        assert not (tests_dir / "test_sleeps.pids").exists(), f"a test started after {stop.name}"

editor_makefile = (ROOT / "areas" / "de" / "src" / "Makefile").read_text()
assert re.search(r"^CXX_STANDARD\s*=\s*-std=c\+\+20$", editor_makefile, re.MULTILINE)
for flags in ("CCFLAGS", "CFLAGS"):
    assert re.search(rf"^{flags}\s*=.*\$\(CXX_STANDARD\)", editor_makefile, re.MULTILINE), (
        f"the area editor {flags} must compile shared server headers as C++20"
    )
assert re.search(r"^de:\s*\$\(DE_BINARY\)$", editor_makefile, re.MULTILINE)
assert re.search(
    r"^\$\(DE_BINARY\):\s*\$\(OBJS\)\s+\$\(C_OBJS\)\s+\|\s+message$",
    editor_makefile,
    re.MULTILINE,
), (
    "the area editor status target must not force an unchanged relink"
)

listed = subprocess.run(
    [sys.executable, str(RUNNER), "--list", "--match", Path(__file__).name],
    cwd=ROOT,
    check=True,
    stdout=subprocess.PIPE,
    text=True,
).stdout.splitlines()
assert listed == ["tests/async/test_root_test_harness.py", "1 test(s)"]

dry_run = subprocess.run(
    ["make", "-n", "test-list", "TEST_MATCH=root_test_harness"],
    cwd=ROOT,
    check=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
).stdout
assert "run_regression_tests.py --list" in dry_run

workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text()
assert "make test-all" in workflow, "CI does not exercise the root test gate"
assert "make -j`nproc` -C src" not in workflow, "CI duplicates the root build harness"
# A step that names a deleted file fails its job, and the job's later steps never run.
for workflow_path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
    for path in sorted(set(re.findall(r"\b(?:tests|scripts|migrations)/[\w./-]+\.(?:py|sh)\b",
                                      workflow_path.read_text()))):
        assert (ROOT / path).is_file(), f"{workflow_path.name} runs a missing file: {path}"

testing_doc = (ROOT / "docs" / "guides" / "TESTING.md").read_text()
assert "make test-all" in testing_doc
assert "TEST_MATCH" in testing_doc

for wrapper in (ROOT / "tests" / "async").glob("run_*.sh"):
    assert os.access(wrapper, os.X_OK), f"test wrapper is not executable: {wrapper.name}"
    source = wrapper.read_text()
    if "docker rm -f" in source:
        assert "docker run --rm -d" not in source, (
            f"{wrapper.name} races Docker auto-removal against its cleanup trap"
        )
        # The database images keep their data in an anonymous volume, which only
        # `docker rm -v` removes with the container.
        assert "docker rm -f " not in source, (
            f"{wrapper.name} leaks its container's volume: use docker rm -fv"
        )

for script in ("m_slow", "m_quick", "make_all", "moveall", "make_lookup"):
    lines = (ROOT / "areas" / script).read_text().splitlines()
    assert lines[:2] == ["#!/bin/sh", "set -eu"], (
        f"areas/{script} must stop when a generation step fails"
    )

# A removed source (an optional areas/trg or areas/qst file, say) changes only its
# directory, so make world must compare directories with its stamp, not files alone.
world_target = makefile[makefile.index("\nworld:"):makefile.index("Combined world data is up to date")]
assert '-newer "$$stamp"' in world_target and "-type f" not in world_target, (
    "make world must regenerate after an area source is removed"
)

print("root build and test harness contracts passed")
