#!/usr/bin/env python3
"""The command log is kept in memory and written when the server exits or crashes.

cmdlog() wrote each player command to logs/log/cmd.debug and flushed it, on the game
thread, before the command ran: a busy disk held the loop for as long as it held that
write (136 ms traced in one). The real cmdlog(), write_cmdlog() and crash handler run
here: nothing is written while the server runs, and an exit, a fault, an abort(), a sent
signal and an overflowed stack each leave the last commands in the file, with the
signal's own exit status.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, source

debug = source("debug.c").read_text()
ring = debug[debug.index("// The last CMDLOG_LINES"):debug.index("void do_debug(")]

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include <cassert>
#include <cstdarg>
#include <fcntl.h>
#include <fstream>
#include <string>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <vector>

bool game_booted = false;
int shutdownflag = 0;
volatile sig_atomic_t tics = 0;
volatile sig_atomic_t signal_shutdown_pending = 0;
void logit(const char *, const char *, ...) {}
void write_queued_log_lines(void) {}
void fatal_boot_error(const char *, const char *, ...) { abort(); }
static room_data rooms[1];
P_room world = rooms;
uint logcount = 0;
''' + ring + r'''
#include "core/signals.c"

static char_data player;
static char name[] = "Tanen";

static void command(const std::string &text)
{
    std::string copy = text;
    cmdlog(&player, copy.data());
}

static int overflow(int depth)
{
    volatile char frame[4096];
    frame[0] = static_cast<char>(depth);
    return overflow(depth + 1) + frame[0];
}

static std::vector<std::string> lines()
{
    std::vector<std::string> found;
    std::ifstream file("logs/log/cmd.debug");
    for (std::string line; std::getline(file, line);)
        found.push_back(line);
    return found;
}

// Runs `scenario` in a child after `commands` commands; returns how the child ended.
template <typename Scenario> static int child(int commands, Scenario scenario)
{
    unlink("logs/log/cmd.debug");
    const pid_t pid = fork();
    assert(pid >= 0);
    if (pid == 0)
    {
        init_cmdlog();
        signal_setup();
        for (int number = 1; number <= commands; ++number)
            command("say " + std::to_string(number));
        // Nothing reaches the file while the server runs.
        if (access("logs/log/cmd.debug", F_OK) == 0)
            _exit(99);
        scenario();
        exit(0);
    }
    int status = 0;
    assert(waitpid(pid, &status, 0) == pid);
    return status;
}

int main(int argc, char **argv)
{
    assert(argc == 2 && chdir(argv[1]) == 0);
    assert(mkdir("logs", 0755) == 0 && mkdir("logs/log", 0755) == 0);
    rooms[0].number = 1200;
    player.player.name = name;
    player.in_room = 0;

    // An exit writes the commands, in order.
    int status = child(3, [] {});
    assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    std::vector<std::string> written = lines();
    assert(written.size() == 3);
    assert(written[0].find(":: [1] Tanen in 1200: say 1") != std::string::npos);
    assert(written[2].find(":: [3] Tanen in 1200: say 3") != std::string::npos);

    // The file holds the last 500, oldest first; a long command is cut and ends its line.
    status = child(619, [] { command("say " + std::string(1000, 'x')); });
    assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    written = lines();
    assert(written.size() == 500);
    assert(written[0].find(":: [121] Tanen in 1200: say 121") != std::string::npos);
    assert(written[498].find(":: [619] Tanen in 1200: say 619") != std::string::npos);
    assert(written[499].find(":: [620] Tanen in 1200: say xxx") != std::string::npos);
    assert(written[499].size() == 254);

    // A crash writes them and dies of its own signal: a fault, an abort(), a signal that
    // was sent, and a stack that overflowed.
    status = child(2, [] { *static_cast<volatile int *>(nullptr) = 1; });
    assert(WIFSIGNALED(status) && WTERMSIG(status) == SIGSEGV && lines().size() == 2);
    status = child(2, [] { abort(); });
    assert(WIFSIGNALED(status) && WTERMSIG(status) == SIGABRT && lines().size() == 2);
    status = child(2, [] { kill(getpid(), SIGBUS); });
    assert(WIFSIGNALED(status) && WTERMSIG(status) == SIGBUS && lines().size() == 2);
    status = child(2, [] { overflow(0); });
    assert(WIFSIGNALED(status) && WTERMSIG(status) == SIGSEGV && lines().size() == 2);
    puts("the command log stays in memory until an exit or a crash writes it");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="command-log-", dir=ROOT / "bin/tests") as tmp:
    test, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
    test.write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                    "-Wno-infinite-recursion", "-I", str(ROOT / "src"), str(test), "-o",
                    str(binary)], check=True)
    run = Path(tmp) / "run"
    run.mkdir()
    subprocess.run([str(binary), str(run)], check=True)
