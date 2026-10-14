#!/usr/bin/env python3
"""Run the shutdown command, countdown and broadcast against isolated player queues.

The real shutdown-info writer runs only in the harness's temporary directory;
no game server, database or live shutdown is needed.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import HARNESS_STUBS, ROOT, extract_function


harness = r'''
#include "core/structs.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include <bsd/string.h>
#include <cassert>
#include <cctype>
#include <fstream>
#include <map>
#include <unistd.h>

#define WIZLOG "wiz"
void sql_log(P_char, const char *, const char *, ...);
bool sql_pwipe(int) { abort(); }
bool sql_pwipe_crossed_boundary() { abort(); }
void do_restore(P_char, char *, int) {}
int fill_word(char *) { return 0; } // None of the commands below uses filler words.
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int)
{
    return {nevent_schedule_status::scheduled, {nullptr, 0}};
}
static time_t now = 100000;
time_t test_time(time_t *) { return now; }
#define time test_time

int shutdownflag = 0, _reboot = 0, _copyover = 0, _autoboot = 0, _pwipe = 0;
TimedShutdownData shutdownData = {0, -1, TimedShutdownData::NONE, "", ""};
P_desc descriptor_list = nullptr;
std::map<txt_q *, std::string> output;
void write_to_q(const char *text, txt_q *queue, const int) { output[queue] += text; }
'''

for filename, signature in (
    ("interp.c", "char *one_argument("),
    ("comm.c", "void send_to_all("),
    ("actwiz.c", "static const char *scheduled_shutdown_type_name("),
    ("actwiz.c", "static void log_shutdown("),
    ("actwiz.c", "void write_shutdown_info("),
    ("actwiz.c", "void timedShutdown("),
    ("actwiz.c", "void do_shutdown("),
):
    harness += "\n" + extract_function(filename, signature) + "\n"

harness += r'''
int main()
{
    char_data issuer = {};
    char name[] = "Zusuk";
    issuer.player.name = name;
    issuer.player.level = OVERLORD;
    descriptor_data first = {}, second = {}, menu = {};
    first.connected = second.connected = CON_PLAYING;
    menu.connected = CON_MAIN_MENU;
    first.next = &second;
    second.next = &menu;
    descriptor_list = &first;

    auto command = [&](std::string text) {
        char verb[MAX_INPUT_LENGTH];
        char *argument = one_argument(text.data(), verb);
        assert(!strcmp(verb, "shutdown"));
        do_shutdown(&issuer, argument, 0);
    };
    auto reset = [&]() {
        shutdownData = {0, -1, TimedShutdownData::NONE, "", ""};
        shutdownflag = _reboot = _copyover = _autoboot = _pwipe = 0;
        output.clear();
        unlink("logs/shutdown_info.txt");
    };
    auto saved = [&]() {
        std::ifstream file("logs/shutdown_info.txt");
        std::string line;
        std::getline(file, line);
        return line;
    };

    const std::string reason = "Zusuk has new code incoming, brace for impact!";
    command("shutdown reboot 3 " + reason);
    assert(shutdownData.eShutdownType == TimedShutdownData::REBOOT);
    assert(shutdownData.reboot_time == now + 180);
    assert(shutdownData.Reason == reason);
    const std::string announcement = reason + "&n\r\n";
    assert(output[&first.output].find(announcement) != std::string::npos);
    assert(output[&first.output].find("REBOOT in 3 minutes") != std::string::npos);
    assert(output[&first.output] == output[&second.output]);
    assert(output[&menu.output].empty());
    assert(!shutdownflag);

    // The reason is announced once; the usual countdown and saved reason survive.
    output.clear();
    now += 60;
    timedShutdown(nullptr, nullptr, nullptr, nullptr);
    assert(output[&second.output].find("REBOOT in 2 minutes") != std::string::npos);
    assert(output[&second.output].find(reason) == std::string::npos);
    now += 120;
    timedShutdown(nullptr, nullptr, nullptr, nullptr);
    timedShutdown(nullptr, nullptr, nullptr, nullptr);
    assert(shutdownflag && _reboot);
    assert(saved() == "Zusuk|" + reason);

    for (const char *kind : {"ok", "reboot", "copyover"})
    {
        // Both immediate and timed commands announce the supplied text verbatim.
        for (const char *delay : {"", "3 "})
        {
            reset();
            const std::string message = "Patch is 100% ready: " + std::string(300, 'x');
            command(std::string("shutdown ") + kind + " " + delay + message);
            assert(output[&first.output].find(message + "&n\r\n") != std::string::npos);
            assert(output[&first.output] == output[&second.output]);
        }
        reset();
        command(std::string("shutdown ") + kind + " 3");
        assert(output[&second.output].find("No reason given") == std::string::npos);
        assert(output[&second.output].find("&n\r\n") == std::string::npos);
        shutdownData.reboot_time = 0;
        timedShutdown(nullptr, nullptr, nullptr, nullptr);
        assert(saved() == "Zusuk|No reason given");
    }

    reset();
    command("shutdown reboot 3 " + reason);
    output.clear();
    command("shutdown");
    assert(shutdownData.eShutdownType == TimedShutdownData::NONE);
    assert(output[&second.output].find("cancelled") != std::string::npos);
    assert(output[&second.output].find(reason) == std::string::npos);
    output.clear();
    command("shutdown invalid 3 " + reason);
    assert(output[&second.output].empty());
    puts("Shutdown reasons reach playing clients once; countdown, cancellation and saved reasons pass");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="shutdown-broadcast-", dir=ROOT / "bin/tests") as tmp:
    directory = Path(tmp)
    source = directory / "test.cpp"
    binary = directory / "test"
    source.write_text(harness)
    (directory / "logs").mkdir()
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-I", str(ROOT / "src"),
        str(source), str(HARNESS_STUBS), "-lbsd", "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], cwd=directory, check=True)
