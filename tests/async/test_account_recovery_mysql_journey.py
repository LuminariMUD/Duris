#!/usr/bin/env python3
"""Recovery commits, failures, concurrency and restart on disposable MariaDB.

Run through with_disposable_mariadb.sh. All accounts, mail, locks and faults belong
to this loopback fixture; no checkout .env or external SMTP relay is used.
"""
import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

import test_account_recovery_journey as journey
import test_flatfile_combat_journey as combat
from test_character_stat_choice_journey import WebSocketClient


def choose_password(client, code, password):
    client.send(code)
    client.expect(journey.CODE_ACCEPTED)
    client.expect(journey.NEW_PASSWORD_PROMPT)
    client.send(password)
    client.expect(journey.VERIFY_PASSWORD_PROMPT)
    client.send(password)


def run(binary):
    database = "recovery_test_" + uuid.uuid4().hex[:12]
    host = os.environ["TEST_DB_HOST"]
    assert host == "127.0.0.1", "use the disposable loopback database runner"
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "ENVIRONMENT": "local",
        "DB_HOST": host, "DB_PORT": os.environ["TEST_DB_PORT"], "DB_NAME": database,
        "DB_USER": os.environ["TEST_DB_USER"], "DB_PASSWD": os.environ["TEST_DB_PASSWORD"],
        "DB_ALLOWED_TARGETS": host + "/" + database, "MYSQL_PWD": os.environ["TEST_DB_PASSWORD"],
        "DB_TLS": "FALSE", "DB_SOCKET": "", "PERSISTENCE_MODE": "mariadb-primary",
        "DURIS_WEBSOCKET": "TRUE",
    }
    mysql = ["mysql", "--protocol=tcp", "--skip-ssl", "-h", host,
             "-P", environment["DB_PORT"], "-u", environment["DB_USER"], "-N", "-B"]

    def sql(text, selected=True):
        return subprocess.check_output(mysql + ([database] if selected else []), input=text,
                                       text=True, env=environment, timeout=120).strip()

    def stored_password():
        return sql(f"SELECT password FROM accounts WHERE account_name='{journey.ACCOUNT}'")

    @contextmanager
    def account_lock():
        lock = subprocess.Popen(mysql + ["--unbuffered", database], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True, env=environment, bufsize=1)
        try:
            lock.stdin.write("START TRANSACTION; SELECT account_name FROM accounts "
                             f"WHERE account_name='{journey.ACCOUNT}' FOR UPDATE;\n")
            lock.stdin.flush()
            assert lock.stdout.readline().strip() == journey.ACCOUNT
            yield lock
        finally:
            lock.communicate("COMMIT;\n", timeout=10)
            assert lock.returncode == 0

    def wait_for_reset_write():
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if sql("SELECT COUNT(*) FROM information_schema.PROCESSLIST "
                   f"WHERE DB='{database}' AND INFO LIKE 'SELECT password,email,blocked FROM accounts%'") == "1":
                return
            time.sleep(0.05)
        raise AssertionError("reset never reached its transaction")

    @contextmanager
    def boot(extra_environment=None):
        def prepare(runtime):
            # Match the other gameplay journeys' short, isolated camping timer.
            properties = runtime / "lib/duris.properties"
            text = properties.read_text()
            assert "camp.timer=9.000" in text
            properties.write_text(text.replace("camp.timer=9.000", "camp.timer=2.000"))

        smtp = journey.FakeSmtpServer()
        try:
            with journey.IsolatedServer(binary, dict(environment, MAIL_ENABLED="TRUE",
                    MAIL_HOST=host, MAIL_PORT=str(smtp.port), MAIL_TLS="FALSE",
                    MAIL_FROM=journey.MAIL_FROM, **(extra_environment or {})),
                    prepare_run_root=prepare) as server:
                try:
                    yield server, smtp
                    server.shutdown()
                except Exception:
                    # Logs contain only synthetic fixture data; do not print client input.
                    print(server.server_output()[-6000:])
                    print(server.runtime_logs()[-6000:])
                    raise
        finally:
            smtp.close()

    def reset_client(server, smtp):
        client = journey.MudClient(server.plain_port)
        journey.request_reset(client)
        payload = smtp.wait_for_payloads(1, timeout=20)[0]
        return client, journey.extract_reset_code(payload)

    sql("CREATE DATABASE " + database + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", False)
    try:
        sql((journey.ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
        for args in (("adopt", "--kind", "fresh_bootstrap"), ("run",)):
            subprocess.run(["python3", "scripts/migration_runner.py", *args], cwd=journey.ROOT,
                           env=environment, check=True, capture_output=True)

        with boot() as (server, smtp):
            other = journey.MudClient(server.plain_port)
            journey.create_account(other, journey.OLD_PASSWORD)
            original = stored_password()
            # Legacy SQL NULL has the same unblocked meaning as account loading.
            sql(f"UPDATE accounts SET blocked=NULL WHERE account_name='{journey.ACCOUNT}'")
            sql("CREATE TRIGGER reject_reset BEFORE UPDATE ON accounts FOR EACH ROW "
                "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic recovery write failure'")
            client, code = reset_client(server, smtp)
            try:
                choose_password(client, code, journey.NEW_PASSWORD)
                client.expect("Your new password could not be saved.")
                client.expect(journey.ENABLED_PROMPT)
                assert stored_password() == original, "failed reset changed the saved password"
                other.send("")
                other.expect("Please select an option")
                sql("DROP TRIGGER reject_reset")
                client.send("?")
                client.expect(journey.CODE_PROMPT)
                choose_password(client, code, journey.NEW_PASSWORD)
                client.expect(journey.PASSWORD_CHANGED)
                client.expect(journey.ENABLED_PROMPT)
                assert stored_password() != original, "success preceded durable storage"
                other.expect("password for this account was just reset")
                journey.login_to_menu(client, journey.NEW_PASSWORD)
                journey.leave_account_menu(client)
                journey.require_no_new_connection(smtp, 1)
                journey.require_no_secret_leak(server, (code, code.replace("-", ""), journey.EMAIL))
            finally:
                client.close()
                other.close()
        print("PASS: telnet write failure, same-code retry, durable success and session revocation", flush=True)

        # Restart loads the committed password. WebSocket uses the same durable callback.
        with boot() as (server, smtp):
            client = journey.MudClient(server.plain_port)
            journey.enter_account_name(client)
            client.expect(journey.ENABLED_PROMPT)
            client.send(journey.OLD_PASSWORD)
            client.expect(journey.INVALID_PASSWORD)
            client.close()
            ws = WebSocketClient(server.websocket_port)
            try:
                result = ws.command("login", {"account": journey.ACCOUNT,
                                    "password": journey.NEW_PASSWORD}, "auth")
                assert result["status"] == "success", "committed reset did not survive restart"
                ws.close()
                ws = WebSocketClient(server.websocket_port)
                result = ws.command("request_reset", {"account": journey.ACCOUNT}, "account")
                assert result["action"] == "reset_requested"
                code = journey.extract_reset_code(smtp.wait_for_payloads(1, timeout=20)[0])
                fields = {"account": journey.ACCOUNT, "code": code, "newPassword": journey.OLD_PASSWORD}
                sql("CREATE TRIGGER reject_reset BEFORE UPDATE ON accounts FOR EACH ROW "
                    "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic recovery write failure'")
                result = ws.command("complete_reset", fields, "account")
                assert result["action"] == "error", "WebSocket acknowledged failed storage"
                sql("DROP TRIGGER reject_reset")
                result = ws.command("complete_reset", fields, "account")
                assert result["action"] == "reset_completed"
                result = ws.command("complete_reset", fields, "account")
                assert result["action"] == "error", "completed code was reusable"
                result = ws.command("login", {"account": journey.ACCOUNT,
                                    "password": journey.OLD_PASSWORD}, "auth")
                assert result["status"] == "success"
                journey.require_no_secret_leak(server, (code, code.replace("-", ""), journey.EMAIL))
            finally:
                ws.close()
        print("PASS: restart persistence and WebSocket failure, retry, login and single use", flush=True)

        with boot() as (server, smtp):
            client, code = reset_client(server, smtp)
            original = stored_password()
            try:
                with account_lock() as lock:
                    choose_password(client, code, journey.NEW_PASSWORD)
                    wait_for_reset_write()
                    # The loop remains responsive while storage is blocked.
                    probe = journey.MudClient(server.plain_port)
                    try:
                        prompt, _ = probe.expect_any(("term type", "account name"), timeout=3)
                        if prompt == "term type":
                            probe.send("9")
                            probe.expect("account name", timeout=3)
                    finally:
                        probe.close()
                    # A fence committed after the initial read must still win.
                    lock.stdin.write(f"UPDATE accounts SET blocked=1 WHERE account_name='{journey.ACCOUNT}';\n")
                    lock.stdin.flush()
                client.expect("Your reset code stopped being valid")
                assert stored_password() == original, "reset ignored a newer account fence"
                sql(f"UPDATE accounts SET blocked=0 WHERE account_name='{journey.ACCOUNT}'")
            finally:
                client.close()
        print("PASS: delayed transaction keeps the game responsive and rechecks account fences", flush=True)

        build = journey.ROOT / "bin/tests"
        build.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="recovery-commit-", dir=build) as tmp:
            runtime = Path(tmp)
            preload = runtime / "commit-fault.so"
            subprocess.run(["cc", "-shared", "-fPIC", "-Wall", "-Wextra", "-Werror",
                            "tests/async/account_recovery_commit_fault.c", "-ldl", "-o", str(preload)],
                           cwd=journey.ROOT, check=True)
            arm = runtime / "commit-fault"
            reached = Path(str(arm) + ".reached")
            for mode, old, new in (("before", journey.OLD_PASSWORD, journey.NEW_PASSWORD),
                                   ("after", journey.NEW_PASSWORD, journey.OLD_PASSWORD)):
                with boot({"LD_PRELOAD": str(preload),
                           "DURIS_TEST_RECOVERY_COMMIT_FAULT": str(arm)}) as (server, smtp):
                    other = journey.MudClient(server.plain_port)
                    journey.enter_account_name(other)
                    other.expect(journey.ENABLED_PROMPT)
                    journey.login_to_menu(other, old)
                    client, code = reset_client(server, smtp)
                    original = stored_password()
                    try:
                        arm.write_text(mode)
                        choose_password(client, code, new)
                        deadline = time.monotonic() + 20
                        while not reached.exists():
                            assert time.monotonic() < deadline, "COMMIT fault was not reached"
                            time.sleep(0.05)
                        committed = stored_password()
                        assert (committed == original) == (mode == "before")
                        # A successful database write alone cannot acknowledge the
                        # reset or disconnect its other session before reconciliation.
                        other.send("")
                        other.expect("Please select an option")
                        client._receive()
                        assert journey.PASSWORD_CHANGED.encode() not in client.transcript
                        arm.unlink()
                        client.expect(journey.PASSWORD_CHANGED)
                        client.expect(journey.ENABLED_PROMPT)
                        other.expect("password for this account was just reset")
                        if mode == "after":
                            assert stored_password() == committed, "replay replaced the submitted hash"
                        else:
                            assert stored_password() != original
                        journey.login_to_menu(client, new)
                        journey.leave_account_menu(client)
                        # The code is consumed only after the reconciled completion.
                        retry = journey.MudClient(server.plain_port)
                        try:
                            journey.enter_account_name(retry)
                            retry.expect(journey.ENABLED_PROMPT)
                            retry.send("?")
                            retry.expect(journey.CODE_PROMPT)
                            retry.send(code)
                            retry.expect("That code was not accepted")
                        finally:
                            retry.close()
                    finally:
                        arm.unlink(missing_ok=True)
                        reached.unlink(missing_ok=True)
                        client.close()
                        other.close()
        print("PASS: lost COMMIT replies before/after application reconcile and revoke sessions", flush=True)

        with boot() as (server, smtp):
            other = combat.MudClient(server.plain_port)
            combat.create_character(other, expected_room=None, account=journey.ACCOUNT,
                                    existing_account=True)
            other.send("save")
            other.expect(f"Save complete for {combat.CHARACTER}.")
            other.send("look")
            other.expect("Obvious exits")
            sql(f"UPDATE accounts SET last_good_char=FROM_UNIXTIME(1) "
                f"WHERE account_name='{journey.ACCOUNT}'")
            client, code = reset_client(server, smtp)
            original = stored_password()
            with account_lock():
                choose_password(client, code, journey.NEW_PASSWORD)
                wait_for_reset_write()
                departed_at = int(time.time())
                other.send("quit")
                other.expect("ACCOUNT MENU", timeout=60)
                # Departure must persist after both connections are gone, without
                # queueing a stale password snapshot behind the reset.
                other.send("0")
                other.expect("Thank you for playing!")
                other.close()
                client.close()
            server.wait_for_status_line("account password reset by email completed")
            assert stored_password() != original, "disconnect lost the accepted write"
            client = journey.MudClient(server.plain_port)
            try:
                journey.enter_account_name(client)
                client.expect(journey.ENABLED_PROMPT)
                journey.login_to_menu(client, journey.NEW_PASSWORD)
                assert int(sql("SELECT UNIX_TIMESTAMP(last_good_char) FROM accounts "
                               f"WHERE account_name='{journey.ACCOUNT}'")) >= departed_at
            finally:
                client.close()
        print("PASS: concurrent character departure preserves its cooldown timestamp and reset password", flush=True)
    finally:
        sql("DROP DATABASE " + database, False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    run(parser.parse_args().server.resolve())
