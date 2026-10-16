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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("backup_alert", ROOT / "scripts/backup_alert.py")
alert = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alert)


class SMTP:
    attempts = []
    failure = None

    def __init__(self, host, port, timeout):
        assert (host, port, timeout) == ("smtp.example.test", 587, 30)
        self.tls = self.authenticated = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def starttls(self, context):
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        self.tls = True

    def login(self, username, password):
        assert self.tls and (username, password) == ("fixture-user", "fixture-secret")
        self.authenticated = True

    def send_message(self, message, from_addr, to_addrs):
        assert self.authenticated
        assert from_addr == message["From"] == "sender@example.test"
        assert to_addrs == ["recipient@example.test"]
        assert message["To"] == "recipient@example.test"
        assert "synthetic backup failure" in message.get_content()
        assert "fixture-secret" not in message.as_string()
        self.attempts.append(message)
        if self.failure:
            raise self.failure
        return {}


def journal(command, **kwargs):
    assert command[:3] == ["journalctl", "--user", "-u"]
    assert kwargs["timeout"] == 10 and kwargs["check"]
    return subprocess.CompletedProcess(command, 0, stdout="synthetic backup failure\n")


out = ROOT / "bin/tests"
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="backup-alert-", dir=out) as temporary:
    home = Path(temporary).resolve()
    env = home / ".env"
    values = ("MAIL_ENABLED=FALSE\nMAIL_HOST=smtp.example.test\nMAIL_PORT=587\n"
              "MAIL_TLS=TRUE\nMAIL_USERNAME=fixture-user\nMAIL_PASSWORD=fixture-secret\n"
              "MAIL_FROM=sender@example.test\n")
    env.write_text(values)
    env.chmod(0o600)
    stamp = home / ".local/state/duris-backup-alert/test-backup"
    with patch.dict(os.environ, {"HOME": str(home)}, clear=True), \
            patch.object(alert.smtplib, "SMTP", SMTP), \
            patch.object(alert.subprocess, "run", journal):
        def send(unit="test-backup"):
            alert.send_alert(unit, "recipient@example.test", env)

        SMTP.failure = smtplib.SMTPDataError(550, b"synthetic rejection")
        try:
            send()
            raise AssertionError("SMTP rejection was ignored")
        except smtplib.SMTPDataError:
            pass
        assert not stamp.exists()
        SMTP.failure = None
        send()
        assert stamp.exists() and stamp.stat().st_mode & 0o777 == 0o600
        accepted = stamp.stat().st_mtime_ns
        send()
        assert len(SMTP.attempts) == 2 and stamp.stat().st_mtime_ns == accepted
        os.utime(stamp, (1, 1))
        SMTP.failure = smtplib.SMTPServerDisconnected("synthetic failure")
        try:
            send()
            raise AssertionError("disconnect was ignored")
        except smtplib.SMTPServerDisconnected:
            pass
        assert stamp.stat().st_mtime == 1
        SMTP.failure = None
        send()
        assert stamp.stat().st_mtime > 1 and len(SMTP.attempts) == 4
        # A different failing unit has its own suppression window.
        send("test-health")
        assert len(SMTP.attempts) == 5
        env.write_text(values.replace("MAIL_TLS=TRUE", "MAIL_TLS=FALSE"))
        try:
            send("invalid-tls")
            raise AssertionError("plaintext SMTP was allowed")
        except ValueError:
            pass
        assert len(SMTP.attempts) == 5
        env.write_text(values)
        env.chmod(0o644)
        try:
            send("unsafe-env")
            raise AssertionError("public environment file was accepted")
        except Exception as error:
            assert type(error).__name__ == "BackupError"
        assert not (stamp.parent / "unsafe-env").exists()
print("PASS backup alert: real MAIL_* loader, verified TLS, sender, failure/retry, per-unit suppression, expiry, and private config")
