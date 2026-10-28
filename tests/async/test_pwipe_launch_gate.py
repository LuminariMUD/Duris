#!/usr/bin/env python3
"""Executable launch policy/configuration tests; no host clock or live data changes."""

import os
from pathlib import Path
import subprocess
import tempfile
import re
import socket
import unittest
from unittest.mock import Mock

from _paths import HARNESS_STUBS, extract_function
from run_pwipe_launch_gate_journey import WebSocketClient, websocket_drained

ROOT = Path(__file__).resolve().parents[2]
OPEN = 1793210400
CONFIG = "enabled=true\nopens_at_utc=2026-10-28T18:00:00Z\nallowed_accounts=mosheh, Test_staff\n"
HARNESS = r'''
#include "account/pwipe_launch.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "account/password_async.h"
#include "net/ansi.h"
#include "net/comm.h"
#include "player/player_load_pipeline.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>

static std::string output;
static int released, cancelled, input_flushed;
void password_async_cancel(P_desc d) { d->password_request = nullptr; }
extern "C" void password_login_release(password_login_job *) {}
bool player_load_pipeline_cancel(uint64_t id) { assert(id == 42); ++cancelled; return true; }
void flush_input_queue(P_desc) { ++input_flushed; }
void item_creation_grant_cancel_batch_before_entry(P_char) {}
void free_char(P_char) { ++released; }
void echo_on(P_desc) {}
void write_to_q(const char *text, struct txt_q *, const int) { output += text; }
void ws_send_auth_failed(P_desc, const char *text) { output += text; }
char greeting_text[] = "ordinary greeting";
char *greetings = greeting_text, *greetinga = greeting_text, *greetinga1 = greeting_text,
     *greetinga2 = greeting_text, *greetinga3 = greeting_text, *greetinga4 = greeting_text;
char valid_term_list[] = "terminal help";
int number(int, int) { return 1; }
char *one_argument(const char *text, char *) { return const_cast<char *>(text); }
void send_account_name_prompt(P_desc) { output += "Account name: "; }

int main(int argc, char **argv)
{
    assert(!pwipe_launch_allows_at("mosheh", 0));
    assert(argc >= 3);
    std::string error;
    if (!pwipe_launch_load(argv[1], error)) {
        assert(!error.empty());
        assert(!pwipe_launch_allows_at("mosheh", 1793210401));
        puts(error.c_str());
        return 2;
    }
    time_t now = static_cast<time_t>(atoll(argv[2]));
    if (argc == 4) {
        if (!strcmp(argv[3], "session")) {
            descriptor_data d = {}, other = {};
            acct_entry account = {};
            char name[] = "public";
            account.acct_name = name;
            char_data body = {}, attached = {};
            other.character = &attached;
            attached.desc = &other;
            d.account = &account;
            d.character = &body;
            body.desc = &d;
            d.connected = CON_ACCT_SELECT_CHAR;
            d.player_load_request_id = 42;
            d.writer_wait_id = 99;
            assert(!pwipe_launch_admit(&d));
            assert(d.connected == CON_FLUSH && !d.character && !d.player_load_request_id);
            assert(!d.writer_wait_id && released == 1 && cancelled == 1 && input_flushed == 1);
            assert(other.character == &attached && attached.desc == &other);
            const std::string once = output;
            assert(!pwipe_launch_admit(&d));
            assert(output == once && output.find("Reconnect at") != std::string::npos);
            puts("denial cancelled pending work and released only its pre-entry body");
        } else if (!strcmp(argv[3], "terminals")) {
            for (const char *choice : {"1", "", "9"}) {
                descriptor_data d = {};
                output.clear();
                select_terminal(&d, choice);
                assert(d.connected == CON_GET_ACCT_NAME);
                assert(output.find("Account name:") != std::string::npos);
                assert(output.find("ordinary greeting") == std::string::npos);
                if (!strcmp(choice, "9"))
                    assert(output.find("THE WORLD REFORGED") == std::string::npos);
                else
                    assert(output.find("THE WORLD REFORGED") != std::string::npos);
                if (!strcmp(choice, "1"))
                    assert(output.find("&+") == std::string::npos);
                output.clear();
                pwipe_launch_deny(&d);
                assert(output.find("THE WORLD REFORGED") != std::string::npos);
                assert(output.find("Reconnect at") != std::string::npos);
            }
            puts("real generic, ANSI and Quick terminal selection/denial passed");
        } else {
            const std::string screen = pwipe_launch_screen(strcmp(argv[3], "plain") != 0);
            char rendered[MAX_STRING_LENGTH];
            AnsiString(screen.c_str()).term(rendered, TL_BLINK);
            fputs(rendered, stdout);
        }
        return 0;
    }
    for (const char *name : {"mosheh", "MoShEh", "test_STAFF", "mos", "moshehmore", "staff", "", static_cast<const char *>(nullptr)})
        printf("%d", pwipe_launch_allows_at(name, now));
    printf("\n%s\n", pwipe_launch_status(now).c_str());
}
'''


def check_websocket_drain():
    checks = unittest.TestCase()
    # Exercise the journey's real frame reader without booting a game server.
    for payload, eof, failure in (
        (b"", False, socket.timeout),
        (b"", True, None),
        (b"\x88\x00", False, None),
        (b'\x81\x13{"status":"failed"}\x88\x00', False, None),
        (b'\x81\x13{"status":"failed"}', False, socket.timeout),
        (b"\x81\x00", False, ValueError),
        (b"\x81\x7e\x00", False, socket.timeout),
    ):
        receiver, sender = socket.socketpair()
        with receiver, sender:
            receiver.settimeout(.05)
            client = WebSocketClient.__new__(WebSocketClient)
            client.socket, client.buffer, client.messages = receiver, bytearray(), []
            sender.sendall(payload)
            if eof:
                sender.shutdown(socket.SHUT_WR)
            if failure:
                with checks.assertRaises(failure):
                    websocket_drained(client)
            else:
                websocket_drained(client)
    for status in ("success", "created", "reconnected"):
        with checks.assertRaises(AssertionError):
            websocket_drained(Mock(receive=Mock(side_effect=[{"status": status}, ConnectionResetError()])))
    websocket_drained(Mock(receive=Mock(side_effect=ConnectionResetError())))
    for error in (OSError("unexpected socket failure"), AssertionError("WebSocket not closed")):
        with checks.assertRaises(type(error)):
            websocket_drained(Mock(receive=Mock(side_effect=error)))
    print("PASS: WebSocket drain requires close/EOF/reset; idle/partial-frame timeouts and invalid responses fail")


def run():
    check_websocket_drain()
    build_root = ROOT / "bin/tests"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pwipe-launch-policy-", dir=build_root) as temporary:
        root = Path(temporary)
        harness, binary, config = root / "harness.cpp", root / "policy", root / "launch.cfg"
        harness.write_text(HARNESS + "\n" + extract_function("nanny.c", "void select_terminal("))
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-Isrc", str(harness), "src/account/pwipe_launch.c", "src/net/ansi.c",
                        "src/net/unicode.c", str(HARNESS_STUBS), "-o", str(binary)],
                       cwd=ROOT, check=True)

        def check(text, now=OPEN - 1, expected="11100000", valid=True, timezone="UTC"):
            config.write_text(text)
            result = subprocess.run([str(binary), str(config), str(now)], capture_output=True,
                                    text=True, env=dict(os.environ, TZ=timezone))
            assert result.returncode == (0 if valid else 2), result.stdout + result.stderr
            if valid:
                assert result.stdout.splitlines()[0] == expected, result.stdout
                assert "opens_at_utc=" in result.stdout and "allowed_accounts=" in result.stdout
            return result.stdout

        for tz in ("UTC", "Asia/Jerusalem", "America/New_York"):
            check(CONFIG, timezone=tz)
            check(CONFIG, OPEN, "11111111", timezone=tz)
            check(CONFIG, OPEN + 1, "11111111", timezone=tz)
        check(CONFIG.replace("enabled=true", "enabled=false"), expected="11111111")
        check(CONFIG.replace("enabled=true", "enabled=false").replace("mosheh, Test_staff", ""),
              expected="11111111")
        for invalid in (
            CONFIG + "enabled=true\n", CONFIG + "extra=true\n", CONFIG + "bad line\n",
            CONFIG.replace("enabled=true\n", ""), CONFIG.replace("enabled=true", "enabled=TRUE"),
            CONFIG.replace("mosheh, Test_staff", ""), CONFIG.replace("mosheh, Test_staff", "m"),
            CONFIG.replace("mosheh, Test_staff", "mos*"), CONFIG.replace("mosheh, Test_staff", "mos heh"),
            CONFIG.replace("mosheh, Test_staff", "mosheh,"),
            CONFIG.replace("mosheh, Test_staff", "mosheh,MOSHEH"),
            CONFIG.replace("mosheh, Test_staff", "abcdefghijklmnop"),
            CONFIG.replace("mosheh, Test_staff", "mosheh\0hidden"),
            CONFIG.replace("mosheh, Test_staff", "a_"),
        ):
            check(invalid, valid=False)
        for date in ("2026-02-29T18:00:00Z", "2026-10-32T18:00:00Z", "2026-13-28T18:00:00Z",
                     "2026-10-28T24:00:00Z", "2026-10-28T18:60:00Z", "2026-10-28T18:00:60Z",
                     "2026-10-28T18:00:00+00:00", "2026-10-28 18:00:00Z", "2026-1-28T18:00:00Z",
                     "2026-10-28T18:00:00Z trailing", "1969-12-31T23:59:59Z"):
            check(CONFIG.replace("2026-10-28T18:00:00Z", date), valid=False)
        check(CONFIG.replace("2026-10-28T18:00:00Z", "2028-02-29T18:00:00Z"))
        result = subprocess.run([str(binary), str(root / "missing.cfg"), str(OPEN)], capture_output=True)
        assert result.returncode == 2
        print("PASS: fail-closed config, exact identities, disabled mode, UTC dates and launch boundary")
        config.write_text(CONFIG.replace("2026-10-28", "2099-10-28"))
        subprocess.run([str(binary), str(config), str(OPEN), "session"], check=True, cwd=ROOT)
        subprocess.run([str(binary), str(config), str(OPEN), "terminals"], check=True, cwd=ROOT)
        for mode in ("plain", "ansi"):
            result = subprocess.check_output([str(binary), str(config), str(OPEN), mode], cwd=ROOT)
            assert b"2099-10-28 18:00:00 UTC" in result
            assert b"\x1b" not in result if mode == "plain" else b"\x1b[" in result
            plain = re.sub(rb"\x1b\[[0-9;]*m", b"", result)
            assert b"&+" not in plain and b"&n" not in plain
            assert b"\n" not in plain.replace(b"\r\n", b"")
            assert max(map(len, plain.splitlines())) <= 76
            assert all(byte in (10, 13) or 32 <= byte <= 126 for byte in plain)
            if mode == "ansi":
                assert result.endswith(b"\x1b[m\r\n\r\n"), result[-80:]
            (ROOT / "bin/analysis").mkdir(exist_ok=True)
            (ROOT / "bin/analysis" / ("pwipe-launch-" + mode + ".txt")).write_bytes(result)
        # Missing artwork is optional; the required configuration still closes the gate.
        fallback = subprocess.check_output([str(binary), str(config), str(OPEN), "plain"], cwd=root)
        assert b"DURIS - THE WORLD REFORGED" in fallback and b"2099-10-28" in fallback
        print("PASS: generic/ANSI rendering, width, CRLF, reset and missing-art fallback")

    account = (ROOT / "src/account/account.c").read_text()
    password = extract_function("account.c", "static void finish_account_password(")
    assert password.index("if (!password_valid)") < password.index("pwipe_launch_admit(d)")
    assert password.index("pwipe_launch_admit(d)") < password.index("ACCOUNT_BLOCK_DELETION")
    assert password.index("pwipe_launch_admit(d)") < password.index("// Check for duplicate")
    for signature in ("void display_account_menu(", "void account_select_char(",
                      "void account_confirm_char(", "void account_player_load_complete(",
                      "int is_char_in_game(", "void account_new_char_name("):
        assert "pwipe_launch_admit(d)" in extract_function("account.c", signature), signature
    assert account.index("STATE(reader) = CON_VERIFY_NEW_ACCT_NAME;") < account.index("verify_account_name(reader, NULL);")
    ws_login = extract_function("ws_handlers.c", "void ws_finish_login(")
    assert ws_login.index("if (!password_valid)") < ws_login.index("pwipe_launch_admit(d)") < ws_login.index("/* reconnect check")
    dispatcher = extract_function("ws_handlers.c", "void ws_handle_command(")
    assert dispatcher.index("STATE(d) == CON_FLUSH") < dispatcher.index("static const struct")
    assert "d->login_password_job || d->password_request || d->writer_wait_id" in dispatcher
    restore = extract_function("copyover.c", "static P_char copyover_load_player(")
    assert restore.index("pwipe_launch_allows_at(result.account_name") < restore.index("mm_get(dead_mob_pool)")
    boot = (ROOT / "src/net/comm.c").read_text()
    assert boot.index("if (pwipe_resume_epoch)") < boot.index("pwipe_launch_load(") < boot.index("initialize_mysql()")
    print("PASS: real login, async, creation, reconnect, copyover and startup guard ordering")


if __name__ == "__main__":
    run()
