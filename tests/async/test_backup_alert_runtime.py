#!/usr/bin/env python3
"""Execute the notifier and real environment loader without delivering mail."""

import importlib.util
import os
from pathlib import Path
import smtplib
import ssl
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("backup_alert", ROOT / "scripts/backup_alert.py")
alert = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alert)


class SMTP:
    attempts = []
    connections = []
    failure = None

    def __init__(self, host, port, timeout, context=None):
        assert timeout == 30
        self.host, self.port = host, port
        self.tls = context is not None
        self.login_values = None
        self.starttls_calls = 0
        if context:
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        SMTP.connections.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def starttls(self, context):
        assert not self.tls
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        self.starttls_calls += 1
        self.tls = True

    def login(self, username, password):
        assert self.tls
        assert (username, password) == ("fixture-user", "fixture-secret")
        self.login_values = (username, password)

    def send_message(self, message, from_addr, to_addrs):
        assert from_addr == message["From"] == "sender@example.test"
        assert to_addrs == ["recipient@example.test"]
        assert message["To"] == "recipient@example.test"
        assert "fixture-secret" not in message.as_string()
        SMTP.attempts.append(message)
        if SMTP.failure:
            raise SMTP.failure
        return {}


class SMTP_SSL(SMTP):
    def __init__(self, host, port, timeout, context):
        assert port == 465 and context
        super().__init__(host, port, timeout, context)


def journal(command, **kwargs):
    assert command[:3] == ["journalctl", "--user", "-u"]
    assert kwargs["timeout"] == 10 and kwargs["check"]
    return subprocess.CompletedProcess(command, 0, stdout="synthetic backup failure\n")


class BackupAlertRuntime(unittest.TestCase):
    def setUp(self):
        out = ROOT / "bin/tests"
        out.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="backup-alert-", dir=out)
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        self.env = self.home / ".env"
        self.write_config()
        self.stamp = self.home / ".local/state/duris-backup-alert/test-backup"
        SMTP.attempts, SMTP.connections, SMTP.failure = [], [], None
        patches = [patch.dict(os.environ, {"HOME": str(self.home)}, clear=True),
                   patch.object(alert.smtplib, "SMTP", SMTP),
                   patch.object(alert.smtplib, "SMTP_SSL", SMTP_SSL),
                   patch.object(alert.subprocess, "run", side_effect=journal)]
        for replacement in patches:
            replacement.start()
            self.addCleanup(replacement.stop)

    def write_config(self, **overrides):
        values = dict(MAIL_ENABLED="FALSE", MAIL_HOST="smtp.example.test", MAIL_PORT="587",
                      MAIL_TLS="TRUE", MAIL_USERNAME="fixture-user", MAIL_PASSWORD="fixture-secret",
                      MAIL_FROM="sender@example.test")
        values.update(overrides)
        self.env.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
        self.env.chmod(0o600)

    def send(self, unit="test-backup"):
        alert.send_alert(unit, "recipient@example.test", self.env)

    def test_failure_retry_suppression_and_expiry(self):
        SMTP.failure = smtplib.SMTPDataError(550, b"synthetic rejection")
        with self.assertRaises(smtplib.SMTPDataError):
            self.send()
        self.assertFalse(self.stamp.exists())
        SMTP.failure = None
        self.send()
        self.assertEqual(self.stamp.stat().st_mode & 0o777, 0o600)
        accepted = self.stamp.stat().st_mtime_ns
        self.send()
        self.assertEqual(len(SMTP.attempts), 2)
        self.assertEqual(self.stamp.stat().st_mtime_ns, accepted)
        os.utime(self.stamp, (1, 1))
        SMTP.failure = smtplib.SMTPServerDisconnected("synthetic failure")
        with self.assertRaises(smtplib.SMTPServerDisconnected):
            self.send()
        self.assertEqual(self.stamp.stat().st_mtime, 1)
        SMTP.failure = None
        self.send()
        self.assertGreater(self.stamp.stat().st_mtime, 1)
        self.assertEqual(len(SMTP.attempts), 4)
        self.send("test-health")
        self.assertEqual(len(SMTP.attempts), 5)

    def test_transport_and_optional_auth_contract(self):
        for port in (587, 465):
            for authenticated in (True, False):
                with self.subTest(port=port, authenticated=authenticated):
                    self.write_config(MAIL_PORT=str(port),
                                      MAIL_USERNAME="fixture-user" if authenticated else "",
                                      MAIL_PASSWORD="fixture-secret" if authenticated else "")
                    self.send(f"transport-{port}-{authenticated}")
                    connection = SMTP.connections[-1]
                    self.assertIs(type(connection), SMTP_SSL if port == 465 else SMTP)
                    self.assertTrue(connection.tls)
                    self.assertEqual(connection.starttls_calls, 0 if port == 465 else 1)
                    self.assertEqual(bool(connection.login_values), authenticated)
                    self.assertIn("synthetic backup failure", SMTP.attempts[-1].get_content())

    def test_plaintext_is_only_for_unauthenticated_loopback(self):
        self.write_config(MAIL_TLS="FALSE")
        with self.assertRaises(ValueError):
            self.send()
        self.write_config(MAIL_HOST="localhost", MAIL_TLS="FALSE")
        with self.assertRaises(ValueError):
            self.send()
        self.assertFalse(SMTP.connections)
        self.write_config(MAIL_HOST="localhost", MAIL_TLS="FALSE", MAIL_USERNAME="", MAIL_PASSWORD="")
        self.send()
        self.assertFalse(SMTP.connections[-1].tls)
        self.assertIsNone(SMTP.connections[-1].login_values)

    def test_partial_auth_is_rejected(self):
        for key in ("MAIL_USERNAME", "MAIL_PASSWORD"):
            with self.subTest(key=key):
                self.write_config(**{key: ""})
                with self.assertRaises(ValueError):
                    self.send()
        self.assertFalse(SMTP.connections)
        self.assertFalse(self.stamp.exists())

    def test_journal_failure_does_not_suppress_notification(self):
        errors = [subprocess.CalledProcessError(1, "journalctl", stderr="fixture-secret"),
                  subprocess.TimeoutExpired("journalctl", 10), FileNotFoundError("journalctl")]
        for number, error in enumerate(errors):
            with self.subTest(error=type(error).__name__), \
                    patch.object(alert.subprocess, "run", side_effect=error):
                unit = f"missing-journal-{number}"
                self.send(unit)
                body = SMTP.attempts[-1].get_content()
                self.assertIn(unit + " failed", body)
                self.assertIn("Recent journal unavailable", body)
                self.assertIn(type(error).__name__, body)
                self.assertTrue((self.stamp.parent / unit).exists())

    def test_unsafe_environment_file_is_rejected(self):
        from persistence_backup import BackupError
        self.env.chmod(0o644)
        with self.assertRaises(BackupError):
            self.send()
        self.assertFalse(SMTP.connections)
        self.assertFalse(self.stamp.exists())


if __name__ == "__main__":
    unittest.main()
