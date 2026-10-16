#!/usr/bin/env python3
"""Send one backup unit failure using the existing protected MAIL_* settings."""

import argparse
import base64
from datetime import datetime, timezone
from email.message import EmailMessage
import hmac
import os
from pathlib import Path
import shlex
import smtplib
import socket
import ssl
import subprocess
import sys
import time


def authenticate(smtp, username, password):
    # smtplib.login/auth force ASCII; the shared MAIL_* contract permits UTF-8.
    # Keep login's three mechanisms and preference order, with bounded exchanges.
    smtp.ehlo_or_helo_if_needed()
    advertised = smtp.esmtp_features.get("auth", "").upper().split()
    failure = smtplib.SMTPNotSupportedError("No supported SMTP AUTH mechanism")
    username, password = username.encode("utf-8"), password.encode("utf-8")
    for mechanism in ("CRAM-MD5", "PLAIN", "LOGIN"):
        if mechanism not in advertised:
            continue
        code, reply = smtp.docmd("AUTH", mechanism)
        if code == 334:
            if mechanism == "CRAM-MD5":
                challenge = base64.b64decode(reply, validate=True)
                digest = hmac.new(password, challenge, "md5").hexdigest().encode("ascii")
                responses = [username + b" " + digest]
            elif mechanism == "PLAIN":
                responses = [b"\0" + username + b"\0" + password]
            else:
                responses = [username, password]
            for response in responses:
                if code != 334:
                    break
                code, reply = smtp.docmd(base64.b64encode(response).decode("ascii"))
        if code in (235, 503):
            return
        if code == 334:
            smtp.docmd("*")
            raise smtplib.SMTPException("Unexpected SMTP AUTH challenge")
        failure = smtplib.SMTPAuthenticationError(code, reply)
    raise failure


def send_alert(unit, recipient, env_file):
    if not unit or unit in {".", ".."} or Path(unit).name != unit:
        raise ValueError("invalid unit name")
    state = Path.home() / ".local/state/duris-backup-alert"
    state.mkdir(parents=True, mode=0o700, exist_ok=True)
    stamp = state / unit
    if stamp.exists() and time.time() - stamp.stat().st_mtime < 3600:
        return

    # Also works when the notifier is installed outside the checkout.
    sys.path.insert(0, str(env_file.parent / "scripts"))
    from persistence_backup import load_environment

    load_environment(env_file)
    if not all(os.environ.get(key) for key in ("MAIL_HOST", "MAIL_FROM")):
        raise ValueError("MAIL_* configuration is incomplete")
    host = os.environ["MAIL_HOST"]
    tls_text = (os.environ.get("MAIL_TLS") or "TRUE").upper()
    if tls_text not in {"TRUE", "FALSE"}:
        raise ValueError("MAIL_TLS must be TRUE or FALSE")
    tls = tls_text == "TRUE"
    username = os.environ.get("MAIL_USERNAME", "")
    password = os.environ.get("MAIL_PASSWORD", "")
    if bool(username) != bool(password):
        raise ValueError("MAIL_USERNAME and MAIL_PASSWORD must be set together")
    if not tls and (host.lower() not in {"localhost", "127.0.0.1", "::1", "[::1]"}
                    or username):
        raise ValueError("MAIL_TLS=FALSE requires loopback without credentials")
    port_text = os.environ.get("MAIL_PORT") or "587"
    if not port_text.isascii() or not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
        raise ValueError("MAIL_PORT is invalid")
    port = int(port_text)

    try:
        journal = subprocess.run(
            ["journalctl", "--user", "-u", unit, "-n", "20", "-o", "cat", "--no-pager"],
            capture_output=True, text=True, check=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError) as error:
        journal = f"Recent journal unavailable ({type(error).__name__}).\n"
    message = EmailMessage()
    message["From"] = os.environ["MAIL_FROM"]
    message["To"] = recipient
    message["Subject"] = f"[duris.sbs] {unit} failed on {socket.getfqdn()}"
    now = datetime.now(timezone.utc).strftime("%F %T UTC")
    message.set_content(
        f"{unit} failed at {now}. Its last lines:\n\n{journal}\n"
        f"Check with: cd {shlex.quote(str(env_file.parent))} && "
        "scripts/backup_pfiles.sh status --require-drill\n"
        "This alert is sent at most once an hour per unit.\n")
    context = ssl.create_default_context() if tls or port == 465 else None
    # Match the existing account-recovery MAIL_PORT/TLS/authentication contract.
    host = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    connection = (smtplib.SMTP_SSL(host, port, timeout=30, context=context) if port == 465
                  else smtplib.SMTP(host, port, timeout=30))
    with connection as smtp:
        if tls and port != 465:
            smtp.starttls(context=context)
        if username:
            authenticate(smtp, username, password)
        refused = smtp.send_message(message, from_addr=os.environ["MAIL_FROM"],
                                    to_addrs=[recipient])
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
        # Submission is accepted before QUIT; a later disconnect must not duplicate it.
        stamp.touch(mode=0o600)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("unit")
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--env-file", required=True, type=Path)
    args = parser.parse_args()
    try:
        send_alert(args.unit, args.recipient, args.env_file.absolute())
    except Exception as error:
        # SMTP responses and command arguments can contain private settings/content.
        code = getattr(error, "smtp_code", "unavailable")
        print(f"Backup alert failed: {type(error).__name__}; SMTP status={code}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
