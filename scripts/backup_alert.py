#!/usr/bin/env python3
"""Send one backup unit failure using the existing protected MAIL_* settings."""

import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
import os
from pathlib import Path
import smtplib
import socket
import ssl
import subprocess
import sys
import time


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
    if not all(os.environ.get(key) for key in
               ("MAIL_HOST", "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_FROM")):
        raise ValueError("MAIL_* configuration is incomplete")
    if os.environ.get("MAIL_TLS", "TRUE").upper() != "TRUE":
        raise ValueError("backup alerts require MAIL_TLS=TRUE")
    port = int(os.environ.get("MAIL_PORT", "587"))
    if not 1 <= port <= 65535:
        raise ValueError("MAIL_PORT is invalid")

    journal = subprocess.run(
        ["journalctl", "--user", "-u", unit, "-n", "20", "-o", "cat", "--no-pager"],
        capture_output=True, text=True, check=True, timeout=10)
    message = EmailMessage()
    message["From"] = os.environ["MAIL_FROM"]
    message["To"] = recipient
    message["Subject"] = f"[duris.sbs] {unit} failed on {socket.getfqdn()}"
    now = datetime.now(timezone.utc).strftime("%F %T UTC")
    message.set_content(
        f"{unit} failed at {now}. Its last lines:\n\n{journal.stdout}\n"
        "Check with: cd ~/duris && scripts/backup_pfiles.sh status --require-drill\n"
        "This alert is sent at most once an hour per unit.\n")
    with smtplib.SMTP(os.environ["MAIL_HOST"], port, timeout=30) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(os.environ["MAIL_USERNAME"], os.environ["MAIL_PASSWORD"])
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
