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
#include <cerrno>
#include <climits>
#include <deque>
#include <fstream>
#include <map>
#include <unistd.h>

#define WIZLOG "wiz"
command_info cmd_info[CMD_SHUTDOWN + 1] = {};
void sql_log(P_char, const char *, const char *, ...);
static int wipe_calls = 0, restore_calls = 0;
static bool mysql_required = true, wipe_succeeds = true, crossed = false;
bool persistence_mode_requires_mysql() { return mysql_required; }
bool sql_pwipe(int code) { assert(code == 1723699); ++wipe_calls; return wipe_succeeds; }
bool sql_pwipe_crossed_boundary() { return crossed; }
void do_restore(P_char, char *, int) { ++restore_calls; }
int fill_word(char *) { return 0; }
struct tick { nevent_data event{}; event_func function; int delay; bool active = true; };
static std::deque<tick> ticks;
static P_nevent running_tick = nullptr;
static unsigned long long sequence = 0;
nevent_schedule_result add_event(event_func function, int delay, P_char, P_char, P_obj, int, const void *, int)
{
    if (delay < 0) return {nevent_schedule_status::negative_delay, {nullptr, 0}};
    ticks.push_back({{}, function, delay, true});
    ticks.back().event.sequence = ++sequence;
    return {nevent_schedule_status::scheduled, {&ticks.back().event, sequence}};
}
nevent_handle nevent_find_next(event_func_type function)
{
    for (auto &tick : ticks)
        if (tick.active && tick.function == function)
            return {&tick.event, tick.event.sequence};
    return {nullptr, 0};
}
nevent_cancel_result nevent_cancel(nevent_handle handle)
{
    for (auto &tick : ticks)
        if (&tick.event == handle.event && tick.event.sequence == handle.sequence) {
            tick.active = false;
            return nevent_cancel_result::canceled;
        }
    return nevent_cancel_result::stale_handle;
}
static time_t now = 100000;
time_t test_time(time_t *) { return now; }
#define time test_time

int shutdownflag = 0, _reboot = 0, _copyover = 0, _autoboot = 0, _pwipe = 0;
TimedShutdownData shutdownData = {0, -1, TimedShutdownData::NONE, "", ""};
P_desc descriptor_list = nullptr;
std::map<txt_q *, std::string> output;
void write_to_q(const char *text, txt_q *queue, const int) { output[queue] += text; }
void send_to_char(const char *text, P_char character) {
    if (character && character->desc) output[&character->desc->output] += text;
}
'''

for filename, signature in (
    ("interp.c", "char *one_argument("),
    ("utility.c", "int can_exec_cmd("),
    ("comm.c", "void send_to_all("),
    ("actwiz.c", "static const char *scheduled_shutdown_type_name("),
    ("actwiz.c", "static void log_shutdown("),
    ("actwiz.c", "void write_shutdown_info("),
    ("actwiz.c", "static void cancel_shutdown_ticks("),
    ("actwiz.c", "void timedShutdown("),
    ("actwiz.c", "void do_shutdown("),
    ("comm.c", "void request_shutdown("),
):
    harness += "\n" + extract_function(filename, signature) + "\n"

harness += r'''
int main()
{
    pc_only_data issuer_pc = {};
    char_data issuer = {};
    issuer.only.pc = &issuer_pc;
    cmd_info[CMD_SHUTDOWN].minimum_level = FORGER;
    cmd_info[CMD_SHUTDOWN].grantable = 1;
    char name[] = "Zusuk";
    issuer.player.name = name;
    issuer.player.level = OVERLORD;
    descriptor_data first = {}, second = {}, menu = {};
    first.character = &issuer;
    issuer.desc = &first;
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
        wipe_calls = restore_calls = 0; mysql_required = wipe_succeeds = true; crossed = false;
        ticks.clear(); running_tick = nullptr;
        first.connected = CON_PLAYING; first.character = &issuer; first.original = nullptr;
        descriptor_list = &first; issuer.player.level = OVERLORD; issuer.specials.act = 0;
        issuer_pc.numb_gcmd = 0; issuer_pc.gcmd_arr = nullptr;
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
    auto active_ticks = [&]() {
        size_t count = 0;
        for (const auto &tick : ticks) if (tick.active) ++count;
        return count;
    };
    auto fire = [&]() {
        for (auto &tick : ticks) if (tick.active) {
            running_tick = &tick.event;
            tick.function(nullptr, nullptr, nullptr, nullptr);
            tick.active = false; running_tick = nullptr; return;
        }
        assert(false && "no countdown event queued");
    };
    reset();
    command("shutdown reboot 10 retained request");
    const auto retained = shutdownData;
    for (const char *invalid : {"pwipe", "pwipe confirm", "pwipe yes", "pwipe confirm no",
                               "pwipe confirm yes extra", "pwipe confirm the yes", "invalid",
                               "reboot -1", "reboot 2junk", "copyover 99999999999999999999999"}) {
        output.clear();
        command(std::string("shutdown ") + invalid);
        assert(shutdownData.eShutdownType == retained.eShutdownType &&
               shutdownData.reboot_time == retained.reboot_time &&
               !strcmp(shutdownData.Reason, retained.Reason));
        assert(active_ticks() == 1 && !shutdownflag && !wipe_calls);
        assert(output[&second.output].empty());
    }
    for (bool backend : {true, false}) {
        mysql_required = backend;
        issuer.player.level = backend ? FORGER : OVERLORD;
        command("shutdown pwipe confirm yes");
        assert(shutdownData.eShutdownType == retained.eShutdownType && active_ticks() == 1);
    }
    mysql_required = true; issuer.player.level = OVERLORD;
    command("shutdown pwipe CONFIRM\tYES   ");
    assert(shutdownData.eShutdownType == TimedShutdownData::PWIPE &&
           shutdownData.reboot_time == now + 300 && active_ticks() == 1);
    assert(!strcmp(shutdownData.Reason, "Confirmed player wipe"));
    assert(output[&second.output].find("PWIPE in 5 minutes") != std::string::npos);
    command("shutdown pwipe confirm yes");
    assert(active_ticks() == 1);
    // Even an old duplicate cannot execute the reset twice; a late tick stays schedulable.
    add_event(timedShutdown, 1, nullptr, nullptr, nullptr, 0, nullptr, 0);
    now += 305;
    fire(); assert(active_ticks() == 1 && !wipe_calls && restore_calls == 1);
    fire(); assert(wipe_calls == 1 && _pwipe && shutdownflag && active_ticks() == 0);
    timedShutdown(nullptr, nullptr, nullptr, nullptr);
    assert(wipe_calls == 1 && shutdownData.eShutdownType == TimedShutdownData::NONE);

    for (int departure = 0; departure != 4; ++departure) {
        reset(); command("shutdown pwipe confirm yes");
        if (departure == 0) first.connected = CON_MAIN_MENU;
        if (departure == 1) descriptor_list = &second; // linkdead body stays allocated
        if (departure == 2) issuer.player.level = FORGER;
        if (departure == 3) {
            now = shutdownData.reboot_time; fire(); // final armed tick
            first.connected = CON_MAIN_MENU;
        }
        output.clear(); fire();
        assert(shutdownData.eShutdownType == TimedShutdownData::NONE &&
               !wipe_calls && !shutdownflag && !active_ticks());
        assert(output[&second.output].find("cancelled") != std::string::npos);
    }
    for (const char *kind : {"ok", "reboot", "copyover"}) {
        reset(); command(std::string("shutdown ") + kind + " 3");
        first.connected = CON_MAIN_MENU; fire();
        assert(shutdownData.eShutdownType == TimedShutdownData::NONE &&
               !shutdownflag && !active_ticks() && !wipe_calls);
    }
    for (int outcome = 0; outcome != 3; ++outcome) {
        reset(); command("shutdown pwipe confirm yes");
        wipe_succeeds = outcome == 2; crossed = outcome == 1;
        shutdownData.reboot_time = 0;
        fire(); timedShutdown(nullptr, nullptr, nullptr, nullptr);
        assert(wipe_calls == 1 && shutdownData.eShutdownType == TimedShutdownData::NONE);
        assert(shutdownflag == (outcome != 0) && _pwipe == (outcome != 0));
    }
    reset(); command("shutdown pwipe confirm yes");
    char_data body{}; char body_name[] = "Goblin"; body.player.name = body_name;
    body.specials.act = ACT_ISNPC;
    first.character = &body; first.original = &issuer;
    now += 1; fire();
    assert(shutdownData.eShutdownType == TimedShutdownData::PWIPE && active_ticks() == 1);
    for (bool fog : {false, true}) {
        reset(); issuer.player.level = GREATER_G;
        int grant[] = {CMD_SHUTDOWN};
        issuer_pc.gcmd_arr = grant; issuer_pc.numb_gcmd = 1;
        assert(can_exec_cmd(&issuer, CMD_SHUTDOWN));
        command("shutdown reboot 3 granted delegation");
        assert(shutdownData.eShutdownType == TimedShutdownData::REBOOT && active_ticks() == 1);
        command("shutdown pwipe confirm yes"); // A grant never supplies Overlord level.
        assert(shutdownData.eShutdownType == TimedShutdownData::REBOOT);
        if (fog) issuer.specials.act |= PLR_MORTAL;
        else issuer_pc.numb_gcmd = 0;
        assert(!can_exec_cmd(&issuer, CMD_SHUTDOWN));
        fire();
        assert(shutdownData.eShutdownType == TimedShutdownData::NONE &&
               !shutdownflag && !wipe_calls && !active_ticks());
    }
    reset(); command("shutdown autoreboot 5 scheduled automation");
    command("shutdown copyover");
    assert(shutdownData.eShutdownType == TimedShutdownData::AUTOREBOOT_COPYOVER);
    descriptor_list = &second; now += 301; fire(); fire();
    assert(_autoboot && _copyover && !wipe_calls && !active_ticks());
    reset(); command("shutdown pwipe confirm yes"); descriptor_list = &second;
    request_shutdown(2, "Launcher", "signal");
    assert(_reboot && !_pwipe && !wipe_calls && !active_ticks());
    puts("Shutdown parsing/permission/cancellation/deadline/switch/automation/signal checks pass");
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
