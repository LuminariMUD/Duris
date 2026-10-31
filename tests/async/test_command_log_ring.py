#!/usr/bin/env python3
"""The command log is kept in memory and written when the server exits or crashes.

cmdlog() wrote each player command to logs/log/cmd.debug and flushed it, on the game
thread, before the command ran: a busy disk held the loop for as long as it held that
write (136 ms traced in one). The real cmdlog(), write_cmdlog() and crash handler run
here: nothing is written while the server runs, and an exit, a fault, an abort(), a sent
signal and an overflowed stack each leave the last commands in the file, with the
signal's own exit status. A conversation command keeps its word and loses its text
(ADR 0003). A one-letter command is recorded, and an empty line is not.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, source, extract_function
from _paths import HARNESS_STUBS

debug = source("debug.c").read_text()
ring = debug[debug.index("// The last CMDLOG_LINES"):debug.index("void do_debug(")]

HARNESS = r'''
#include "cmd/interp.h"
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "sql/sql.h"
#include "net/comm.h"
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
void write_queued_log_lines(void) {}
void fatal_boot_error(const char *, const char *, ...) { abort(); }
static room_data rooms[1];
P_room world = rooms;
uint logcount = 0;
// COMMAND_PARSER
''' + ring + r'''
#include "core/signals.c"

static char_data player;
static char name[] = "Tanen";

static void type(const std::string &text)
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
            type("look " + std::to_string(number));
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

static char_data victim;
P_desc descriptor_list;
int forced_command = 0;
static std::vector<std::string> force_logs, executed_commands;
static void capture_log(const char *format, va_list args)
{
    char text[4096];
    vsnprintf(text, sizeof(text), format, args);
    force_logs.emplace_back(text);
}
void logit(const char *, const char *format, ...)
{
    va_list args; va_start(args, format); capture_log(format, args); va_end(args);
}
void wizlog(int, const char *format, ...)
{
    va_list args; va_start(args, format); capture_log(format, args); va_end(args);
}
void sql_log(P_char, const char *, const char *format, ...)
{
    va_list args; va_start(args, format); capture_log(format, args); va_end(args);
}
void send_to_room(const char *, int) {}
P_char get_char_vis(P_char, const char *) { return &victim; }
void command_interpreter(P_char who, char *text)
{
    assert(who == &victim && forced_command);
    executed_commands.emplace_back(text);
}
// FORCE_PRODUCTION

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
    assert(written[0].find(":: [1] Tanen in 1200: look 1") != std::string::npos);
    assert(written[2].find(":: [3] Tanen in 1200: look 3") != std::string::npos);

    // The file holds the last 500, oldest first; a long command is cut and ends its line.
    status = child(619, [] { type("look " + std::string(1000, 'x')); });
    assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    written = lines();
    assert(written.size() == 500);
    assert(written[0].find(":: [121] Tanen in 1200: look 121") != std::string::npos);
    assert(written[498].find(":: [619] Tanen in 1200: look 619") != std::string::npos);
    assert(written[499].find(":: [620] Tanen in 1200: look xxx") != std::string::npos);
    assert(written[499].size() == 254);

    // Conversation keeps its command word and loses its text; "'" is say with the text
    // glued on. Other commands are kept whole.
    status = child(0, [] {
        type("say a secret");
        type("'a secret");
        type("  tell Bob a secret");
        type("look at the secret");
    });
    assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    written = lines();
    assert(written.size() == 4);
    assert(written[0].find(": say <text withheld>") != std::string::npos);
    assert(written[1].find(": ' <text withheld>") != std::string::npos);
    assert(written[2].find(":   tell <text withheld>") != std::string::npos);
    assert(written[3].find(": look at the secret") != std::string::npos);
    for (int i = 0; i < 3; ++i)
        assert(written[i].find("secret") == std::string::npos);

    // Credentials stay out of the persisted ring, including command abbreviations,
    // the equipment parser's filler words, and commands wrapped by staff/order.
    status = child(0, [] {
        type("open vault open-secret");
        type("OP vault abbreviated-secret");
        type("eq chest create vault create-secret");
        type("equip chest p vault password-secret");
        type("equipment with chest password vault filler-secret");
        type("at 1200 open vault at-secret");
        type("force Tanen eq chest password vault force-secret");
        type("force From open vault filler-target-secret");
        type("order follower at 1200 open vault nested-secret");
        type("eq sort wield");
        type("force Tanen look around");
    });
    assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    written = lines();
    assert(written.size() == 11);
    for (int i = 0; i < 9; ++i) {
        assert(written[i].find("secret") == std::string::npos);
        assert(written[i].find("<text withheld>") != std::string::npos);
    }
    assert(written[9].find("eq sort wield") != std::string::npos);
    assert(written[10].find("force Tanen look around") != std::string::npos);

    // A one-letter command is kept; an empty line leaves no entry. cmdlog() tested the
    // byte after the first, so it dropped "n" and read stale bytes past an empty line.
    status = child(0, [] {
        type("n");
        type("");
        type("k bob");
    });
    assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    written = lines();
    assert(written.size() == 2);
    assert(written[0].find(":: [1] Tanen in 1200: n") != std::string::npos);
    assert(written[1].find(":: [2] Tanen in 1200: k bob") != std::string::npos);

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
    // Force logs withhold credentials in every sink while execution receives
    // the original command. Ordinary staff command diagnostics remain complete.
    player.player.level = 61;
    victim.player.level = 1;
    victim.player.name = const_cast<char *>("Victim");
    descriptor_data session{}; session.character = &victim;
    session.connected = CON_PLAYING; descriptor_list = &session;
    for (const char *target : { "Victim", "all", "From" })
        for (const char *payload : { "eq chest password vault force-secret",
                                    "at 1200 open vault routed-secret", "look at floor",
                                    "say public words", "'public words" }) {
            force_logs.clear(); executed_commands.clear();
            std::string request = std::string(target) + " " + payload;
            do_force(&player, request.data(), CMD_FORCE);
            assert(executed_commands == std::vector<std::string>{payload});
            assert(force_logs.size() == 3);
            for (const auto &entry : force_logs) {
                if (std::string(payload).find("secret") == std::string::npos)
                    assert(entry.find(payload) != std::string::npos);
                else {
                    assert(entry.find("secret") == std::string::npos);
                    assert(entry.find("<text withheld>") != std::string::npos);
                }
            }
        }
    puts("command ring/crash logging and forced command sinks preserve privacy and execution");
}
'''

interpreter = source("interp.c").read_text()
start = interpreter.index("const char *command[MAX_CMD] = {")
parser = interpreter[start:interpreter.index("\n};", start) + 3]
start = interpreter.index("const char *fill_words[]")
parser += "\n" + interpreter[start:interpreter.index(";", start) + 1]
parser += "\n" + "\n".join(extract_function(path, signature) for path, signature in (
    ("interp.c", "int old_search_block("), ("interp.c", "int search_block("),
    ("interp.c", "int fill_word("), ("interp.c", "char *one_argument("),
    ("interp.c", "void half_chop("),
    ("utility.c", "int strn_cmp("),
))
HARNESS = HARNESS.replace("// COMMAND_PARSER", parser)
HARNESS = HARNESS.replace("// FORCE_PRODUCTION", extract_function("actwiz.c", "void do_force("))

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="command-log-", dir=ROOT / "bin/tests") as tmp:
    test, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
    test.write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                    "-Wno-infinite-recursion", "-I", str(ROOT / "src"), "-I/usr/include/mysql", str(test), str(HARNESS_STUBS), "-o",
                    str(binary)], check=True)
    run = Path(tmp) / "run"
    run.mkdir()
    subprocess.run([str(binary), str(run)], check=True)
