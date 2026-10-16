#!/usr/bin/env python3
"""Execute the notifier and real environment loader without delivering mail."""

import base64
from email import policy
from email.parser import BytesParser
import hmac
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
RUN = subprocess.run


class SMTP(smtplib.SMTP):
    attempts = []
    connections = []
    failure = None
    auth_methods = "CRAM-MD5 PLAIN LOGIN"
    auth_reject = ()
    extra_challenge = False

    def __init__(self, host, port, timeout, context=None):
        assert timeout == 30
        self.host, self.port = host, port
        self.tls = context is not None
        self.login_values = None
        self.starttls_calls = 0
        self.ehlo_resp = b"fixture relay"
        self.esmtp_features = {"auth": SMTP.auth_methods} if SMTP.auth_methods else {}
        self.auth_commands = []
        self.auth_responses = []
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

    def docmd(self, command, args=""):
        assert self.tls
        assert (command + args).isascii()
        if command == "*":
            return 501, b"Authentication cancelled"
        if command == "AUTH":
            mechanism, _, initial = args.partition(" ")
            assert mechanism in self.esmtp_features["auth"].split()
            self.auth_commands.append(mechanism)
            self.auth_responses = []
            if mechanism in SMTP.auth_reject:
                return 535, b"Synthetic authentication rejection"
            if not initial:
                return 334, base64.b64encode(b"fixture challenge")
            command = initial
        self.auth_responses.append(base64.b64decode(command, validate=True))
        if SMTP.extra_challenge:
            return 334, base64.b64encode(b"fixture challenge")
        username = os.environ["MAIL_USERNAME"]
        password = os.environ["MAIL_PASSWORD"]
        if self.auth_commands[-1] == "CRAM-MD5":
            digest = hmac.new(password.encode(), b"fixture challenge", "md5").hexdigest()
            expected = [(username + " " + digest).encode()]
        elif self.auth_commands[-1] == "PLAIN":
            expected = [("\0" + username + "\0" + password).encode()]
        else:
            expected = [username.encode(), password.encode()]
        assert self.auth_responses == expected[:len(self.auth_responses)]
        if len(self.auth_responses) < len(expected):
            return 334, base64.b64encode(b"fixture challenge")
        self.login_values = (username, password)
        return 235, b"Authentication accepted"

    def sendmail(self, from_addr, to_addrs, payload, mail_options=(), rcpt_options=()):
        # Keep smtplib's real serialization and reject data a 7-bit relay cannot accept.
        assert payload.isascii()
        assert not mail_options and not rcpt_options
        message = BytesParser(policy=policy.default).parsebytes(payload)
        assert from_addr == message["From"] == "sender@example.test"
        assert to_addrs == ["recipient@example.test"]
        assert message["To"] == "recipient@example.test"
        assert "fixture-secret" not in message.as_string()
        if os.environ.get("MAIL_PASSWORD"):
            assert os.environ["MAIL_PASSWORD"] not in message.get_content()
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
        temporary = tempfile.TemporaryDirectory(prefix="backup alert's-", dir=out)
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        self.env = self.home / ".env"
        self.write_config()
        self.stamp = self.home / ".local/state/duris-backup-alert/test-backup"
        SMTP.attempts, SMTP.connections, SMTP.failure = [], [], None
        SMTP.auth_methods = "CRAM-MD5 PLAIN LOGIN"
        SMTP.auth_reject, SMTP.extra_challenge = (), False
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

    def test_utf8_credentials_reach_each_auth_mechanism(self):
        for port in (465, 587):
            for method in ("CRAM-MD5", "PLAIN", "LOGIN"):
                for username, password in (("utilisateur-é", "fixture-secret"),
                                           ("fixture-user", "密碼-é"),
                                           ("utilisateur-é", "密碼-é")):
                    with self.subTest(port=port, method=method, username=username, password=password):
                        SMTP.auth_methods = method
                        self.write_config(MAIL_PORT=str(port), MAIL_USERNAME=username, MAIL_PASSWORD=password)
                        self.send(f"auth-{port}-{method}-{len(SMTP.connections)}")
                        self.assertEqual(SMTP.connections[-1].login_values, (username, password))

    def test_auth_fallback_and_failure_leave_submission_retryable(self):
        self.write_config(MAIL_USERNAME="utilisateur-é", MAIL_PASSWORD="密碼-é")
        SMTP.auth_reject = ("CRAM-MD5",)
        self.send("fallback")
        self.assertEqual(SMTP.connections[-1].auth_commands, ["CRAM-MD5", "PLAIN"])
        for methods, rejected, extra, error in (
                ("CRAM-MD5 PLAIN LOGIN", ("CRAM-MD5", "PLAIN", "LOGIN"), False, smtplib.SMTPAuthenticationError),
                ("", (), False, smtplib.SMTPNotSupportedError),
                ("XOAUTH2", (), False, smtplib.SMTPException),
                ("PLAIN", (), True, smtplib.SMTPException)):
            with self.subTest(methods=methods, extra=extra):
                SMTP.auth_methods, SMTP.auth_reject, SMTP.extra_challenge = methods, rejected, extra
                with self.assertRaises(error):
                    self.send()
                self.assertFalse(self.stamp.exists())
                self.assertEqual(len(SMTP.attempts), 1)

    def test_recovery_command_uses_configured_checkout(self):
        scripts = self.home / "scripts"
        scripts.mkdir()
        status = scripts / "backup_pfiles.sh"
        status.write_text('#!/bin/sh\nprintf "%s\\n" "$PWD" "$@"\n')
        status.chmod(0o700)
        self.send()
        command = next(line.removeprefix("Check with: ")
                       for line in SMTP.attempts[-1].get_content().splitlines()
                       if line.startswith("Check with: "))
        with subprocess.Popen(["bash", "-c", command], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) as process:
            output, error = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, error)
        self.assertEqual(output.splitlines(), [str(self.home), "status", "--require-drill"])

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

    def test_undecodable_journal_still_submits_notification(self):
        for stream in ("stdout", "stderr"):
            def malformed_journal(command, **kwargs):
                self.assertEqual(command[:3], ["journalctl", "--user", "-u"])
                return RUN([sys.executable, "-c",
                            f"import sys; sys.{stream}.buffer.write(b'\\xff')"], **kwargs)

            with self.subTest(stream=stream), \
                    patch.object(alert.subprocess, "run", side_effect=malformed_journal):
                unit = f"undecodable-journal-{stream}"
                self.send(unit)
                body = SMTP.attempts[-1].get_content()
                self.assertIn(unit + " failed", body)
                self.assertIn("Recent journal unavailable (UnicodeDecodeError)", body)
                self.assertTrue((self.stamp.parent / unit).exists())

    def test_utf8_journal_is_safe_for_seven_bit_relays(self):
        from persistence_backup import load_environment
        journal_text = "Backup failed: caf\u00e9 \u4e16\u754c\n"
        # A short checkout avoids EmailMessage's incidental encoding of long lines.
        # Load the real private fixture while exercising that configured path.
        with patch("persistence_backup.load_environment", side_effect=lambda _: load_environment(self.env)), \
                patch.object(alert.subprocess, "run", return_value=subprocess.CompletedProcess(
                    [], 0, stdout=journal_text)):
            alert.send_alert("test-backup", "recipient@example.test", Path("/opt/duris/.env"))
        self.assertIn(journal_text.rstrip("\n"), SMTP.attempts[-1].get_content().splitlines())
        self.assertTrue(self.stamp.exists())

    def test_unsafe_environment_file_is_rejected(self):
        from persistence_backup import BackupError
        self.env.chmod(0o644)
        with self.assertRaises(BackupError):
            self.send()
        self.assertFalse(SMTP.connections)
        self.assertFalse(self.stamp.exists())


if __name__ == "__main__":
    unittest.main()
