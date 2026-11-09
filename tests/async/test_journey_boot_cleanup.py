#!/usr/bin/env python3
"""Journey boots must detect readiness and reap failed cooperative or stubborn children."""
import ast
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check_boot(source_name, takes_arguments, runtime):
    source = Path(__file__).with_name(source_name)
    boots = [node for node in ast.walk(ast.parse(source.read_text()))
             if isinstance(node, ast.FunctionDef) and node.name == "boot"]
    assert len(boots) == 1
    boot_code = compile(ast.Module(body=boots, type_ignores=[]), str(source), "exec")
    executable = runtime / "server"
    output_path = runtime / "server.out"
    for ignore_term, ready in ((False, False), (True, False), (False, True)):
        output_path.unlink(missing_ok=True)
        if ready:
            output_path.write_text("\u00e9" * 4096, encoding="utf-8")
        executable.write_text(
            f"#!{sys.executable}\nimport signal, time\n"
            + ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" if ignore_term else "")
            + "print('CHILD_READY', flush=True)\n"
            + ("print('Entering game loop.', flush=True)\n" if ready else "")
            + "while True: time.sleep(1)\n")
        executable.chmod(0o700)
        children = []

        def spawn(*args, **kwargs):
            child = subprocess.Popen(*args, **kwargs)
            children.append(child)
            # Start the synthetic boot deadline only after the child has installed
            # its signal disposition, so the kill fallback is exercised reliably.
            deadline = time.monotonic() + 5
            while b"CHILD_READY" not in output_path.read_bytes():
                assert child.poll() is None and time.monotonic() < deadline
                time.sleep(.01)
            actual_wait = child.wait
            wait_calls = 0

            def wait(timeout=None):
                nonlocal wait_calls
                wait_calls += 1
                return actual_wait(timeout=.1 if ignore_term and wait_calls == 1 else timeout)

            child.wait = wait
            return child

        clock = iter((0, 181))
        namespace = dict(
            output_path=output_path, executable=executable, runtime=runtime, plain=20000,
            env=None, journey=SimpleNamespace(require=require),
            time=SimpleNamespace(monotonic=lambda: next(clock), sleep=time.sleep),
            subprocess=SimpleNamespace(Popen=spawn, STDOUT=subprocess.STDOUT,
                                       TimeoutExpired=subprocess.TimeoutExpired),
        )
        exec(boot_code, namespace)
        try:
            try:
                result = namespace["boot"](*((executable, runtime, None, 20000) if takes_arguments else ()))
            except AssertionError as error:
                assert not ready, "ready server rejected after a Unicode log"
                assert "server did not boot" in str(error), error
            else:
                assert ready and result is children[0], "a server without the ready marker passed boot"
            if ready:
                assert children[0].returncode is None, "successful boot lost its live child"
            else:
                assert len(children) == 1 and children[0].returncode is not None, \
                    "failed boot left its child running or unreaped"
                assert children[0].returncode == -(signal.SIGKILL if ignore_term else signal.SIGTERM)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                subprocess.Popen.wait(child, timeout=10)

with tempfile.TemporaryDirectory(prefix="journey-boot-cleanup-") as temporary:
    runtime = Path(temporary)
    check_boot("test_flatfile_auction_coin_put_journey.py", False, runtime)
    check_boot("test_flatfile_locker_journey.py", True, runtime)
print("auction and locker boots detect appended readiness and reap failed children")
