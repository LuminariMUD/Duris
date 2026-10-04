#!/usr/bin/env python3
"""Log lines are written by the log thread, not by the thread that logs them.

logit() opened, appended to and closed its file on the calling thread, so the game loop
waited for the disk inside every command and event that logged a line: beside the database
tests one append in 12,000 took over 50 ms and the slowest 136 ms, and a level 1 `who`,
which logs one line, took 117 ms. The real logit() and log thread run here against a file
that blocks its writer (a FIFO nobody reads): logit() returns at once, lines reach their
files in the order they were logged, the exit log is written before logit() returns, an
exit writes what is queued, and the crash handler writes what a crash leaves queued.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, source

utility = source("utility.c").read_text()
logging = utility[utility.index("static char *format_variadic_message("):
                  utility.index("void ereglog(")]

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdarg>
#include <deque>
#include <fcntl.h>
#include <fstream>
#include <mutex>
#include <string>
#include <sys/stat.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>
#include <utility>
#include <vector>

bool game_booted = false;
int shutdownflag = 0;
volatile sig_atomic_t tics = 0;
volatile sig_atomic_t signal_shutdown_pending = 0;
void fatal_boot_error(const char *, const char *, ...) { abort(); }
void write_cmdlog(void) {}
uint debugcount = 0;
''' + logging + r'''
#include "core/signals.c"

static std::vector<std::string> lines(const char *file)
{
    std::vector<std::string> found;
    std::ifstream in(file);
    for (std::string line; std::getline(in, line);)
        found.push_back(line.substr(line.find("::") + 2));
    return found;
}

static double seconds_for(void (*call)())
{
    const auto started = std::chrono::steady_clock::now();
    call();
    return std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
}

// Queues a line whose write blocks, and returns once the log thread is in that write.
static void hold_log_thread()
{
    logit("blocked", "held by the disk");
    for (;;)
    {
        {
            std::lock_guard<std::mutex> lock(log_mutex);
            if (log_thread_writing)
                return;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}

// Runs `scenario` in a child whose log thread is held in a write; returns how it ended.
template <typename Scenario> static int child(Scenario scenario)
{
    const pid_t pid = fork();
    assert(pid >= 0);
    if (pid == 0)
    {
        signal_setup();
        start_log_writer();
        hold_log_thread();
        scenario();
        exit(0);
    }
    int status = 0;
    assert(waitpid(pid, &status, 0) == pid);
    return status;
}

// Reads what the held write was waiting to hand over.
static void let_go()
{
    char held[256];
    const int fifo = open("blocked", O_RDONLY);
    assert(fifo >= 0 && read(fifo, held, sizeof held) > 0);
    close(fifo);
}

int main(int argc, char **argv)
{
    assert(argc == 2 && chdir(argv[1]) == 0);
    assert(mkfifo("blocked", 0600) == 0);

    // Without a log thread the caller writes the line, parent directory and all.
    logit("logs/log/status", "direct %d", 1);
    assert(lines("logs/log/status") == std::vector<std::string>{"direct 1"});

    // An exit writes what is queued once the disk lets go.
    unlink("logs/log/status");
    std::thread reader([] {
        std::this_thread::sleep_for(std::chrono::milliseconds(300));
        let_go();
    });
    int status = child([] { logit("logs/log/status", "queued at the exit"); });
    reader.join();
    assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    assert(lines("logs/log/status") == std::vector<std::string>{"queued at the exit"});

    // A crash writes what is queued behind the held line, and dies of its own signal.
    unlink("logs/log/status");
    status = child([] {
        logit("logs/log/status", "queued at the crash %d", 1);
        logit("logs/log/status", "queued at the crash %d", 2);
        *static_cast<volatile int *>(nullptr) = 1;
    });
    assert(WIFSIGNALED(status) && WTERMSIG(status) == SIGSEGV);
    assert((lines("logs/log/status") ==
            std::vector<std::string>{"queued at the crash 1", "queued at the crash 2"}));

    // A write the disk holds does not hold the caller, and nothing passes it.
    unlink("logs/log/status");
    start_log_writer();
    hold_log_thread();
    assert(seconds_for([] {
        for (int number = 1; number <= 1000; ++number)
            logit("logs/log/status", "queued %d", number);
    }) < 0.5);
    assert(lines("logs/log/status").empty());
    // The disk lets go: every line is written, in order, and a flush waits for them.
    reader = std::thread(let_go);
    flush_log_writer();
    reader.join();
    std::vector<std::string> written = lines("logs/log/status");
    assert(written.size() == 1000 && written[0] == "queued 1" && written[999] == "queued 1000");

    // A line for the exit log is in its file when logit() returns, behind the lines
    // logged before it.
    for (int number = 1; number <= 100; ++number)
        logit("logs/log/status", "before the exit line %d", number);
    logit(LOG_EXIT, "the last words");
    assert(lines(LOG_EXIT) == std::vector<std::string>{"the last words"});
    assert(lines("logs/log/status").size() == 1100);
    puts("the log thread writes the lines; an exit and a crash write what is queued");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="log-writer-", dir=ROOT / "bin/tests") as tmp:
    test, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
    test.write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror", "-pthread",
                    "-I", str(ROOT / "src"), str(test), "-o", str(binary)], check=True)
    run = Path(tmp) / "run"
    run.mkdir()
    subprocess.run([str(binary), str(run)], check=True, timeout=120)
