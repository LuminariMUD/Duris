#!/usr/bin/env python3
"""A failed auction-journey boot must reap cooperative and uncooperative children."""
import ast
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace


source = Path(__file__).with_name("test_flatfile_auction_coin_put_journey.py")
boots = [node for node in ast.walk(ast.parse(source.read_text()))
         if isinstance(node, ast.FunctionDef) and node.name == "boot"]
assert len(boots) == 1
boot_code = compile(ast.Module(body=boots, type_ignores=[]), str(source), "exec")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


with tempfile.TemporaryDirectory(prefix="auction-boot-cleanup-") as temporary:
    runtime = Path(temporary)
    executable = runtime / "server"
    output_path = runtime / "server.out"
    for ignore_term in (False, True):
        output_path.unlink(missing_ok=True)
        executable.write_text(
            f"#!{sys.executable}\nimport signal, time\n"
            + ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" if ignore_term else "")
            + "print('CHILD_READY', flush=True)\nwhile True: time.sleep(1)\n")
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
                namespace["boot"]()
            except AssertionError as error:
                assert "server did not boot" in str(error), error
            else:
                raise AssertionError("a server without the ready marker passed boot")
            assert len(children) == 1 and children[0].returncode is not None, \
                "failed boot left its child running or unreaped"
            assert children[0].returncode == -(signal.SIGKILL if ignore_term else signal.SIGTERM)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                subprocess.Popen.wait(child, timeout=10)

print("failed auction boots reap cooperative and SIGTERM-ignoring children")
