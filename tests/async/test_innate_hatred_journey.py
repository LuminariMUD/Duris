#!/usr/bin/env python3
"""The Hatred journey must reject server crashes, including during client close."""
import signal
import subprocess
import sys
import unittest
from unittest.mock import Mock

from run_innate_hatred_journey import stop


class HatredJourneyShutdown(unittest.TestCase):
    def test_no_process(self):
        client = Mock()
        clients = [client]
        stop(None, clients)
        client.close.assert_called_once_with()
        self.assertEqual(clients, [])

    def test_clean_shutdown(self):
        script = ("import signal, sys; "
                  "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); "
                  "print('ready', flush=True); signal.pause()")
        with subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE,
                              text=True) as process:
            self.assertEqual(process.stdout.readline(), "ready\n")
            clients = [Mock()]
            stop(process, clients)
            self.assertEqual(process.returncode, 0)
            self.assertEqual(clients, [])

    def test_already_crashed(self):
        with subprocess.Popen([sys.executable, "-c", "raise SystemExit(17)"]) as process:
            process.wait(timeout=5)
            with self.assertRaisesRegex(AssertionError, "status 17"):
                stop(process, [])

    def test_crash_during_client_close(self):
        with subprocess.Popen([sys.executable, "-c", "import signal; signal.pause()"]) as process:
            def close():
                process.kill()
                process.wait(timeout=5)

            clients = [Mock(close=close)]
            with self.assertRaisesRegex(AssertionError, f"status {-signal.SIGKILL}"):
                stop(process, clients)
            self.assertEqual(clients, [])


if __name__ == "__main__":
    unittest.main()
