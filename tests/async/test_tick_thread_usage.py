#!/usr/bin/env python3
"""A slow-tick record says whether the game thread was computing or waiting (#1057).

The "MUD TICK TOOK TOO LONG" record times phases by wall clock, so a host
paging stall and a CPU-heavy code path look alike. It now ends with the game
thread's own CPU time and page-fault and context-switch counts for the tick.

Compiles the production src/persistence/latency_trace.c and checks that the
formatted interval reports busy work as CPU time, a sleep as off-CPU time with
a voluntary switch, touching fresh memory as minor faults, and unreadable
counters as "-".
"""

import re
import subprocess
import tempfile
from pathlib import Path

from _paths import SRC

HARNESS = r'''
#include "persistence/latency_trace.h"
#include <cstdio>
#include <cstring>
#include <sys/mman.h>
#include <unistd.h>

static void report(const char *name, const latency_trace_thread_usage *begin)
{
	char line[160];
	latency_trace_format_thread_usage(begin, line, sizeof line);
	std::printf("%s%s\n", name, line);
}

int main()
{
	latency_trace_thread_usage begin;

	latency_trace_thread_usage_now(&begin);
	const uint64_t until = latency_trace_monotonic_us() + 100000;
	volatile unsigned long spin = 0;
	while (latency_trace_monotonic_us() < until)
		spin = spin + 1;
	report("busy", &begin);

	latency_trace_thread_usage_now(&begin);
	usleep(300000);
	report("sleep", &begin);

	// Fresh anonymous memory, without huge pages, faults in one 4 KiB page at a time.
	const size_t bytes = 8u << 20;
	char *fresh = static_cast<char *>(
		mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
	madvise(fresh, bytes, MADV_NOHUGEPAGE);
	latency_trace_thread_usage_now(&begin);
	std::memset(fresh, 1, bytes);
	report("touch", &begin);
	munmap(fresh, bytes);

	latency_trace_thread_usage unreadable = { 0, -1, -1, -1, -1 };
	report("unreadable", &unreadable);
}
'''

with tempfile.TemporaryDirectory(prefix="duris-tick-thread-usage-") as directory:
    temporary = Path(directory)
    harness = temporary / "thread_usage.cpp"
    binary = temporary / "thread_usage"
    harness.write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g", "-O1", "-D_GNU_SOURCE",
                    "-fsanitize=address,undefined", "-I", str(SRC), str(harness),
                    str(SRC / "persistence" / "latency_trace.c"), "-pthread", "-o", str(binary)],
                   check=True)
    output = subprocess.run([str(binary)], check=True, capture_output=True, text=True).stdout

lines = {line.split(" ", 1)[0]: line for line in output.splitlines()}
pattern = re.compile(r" thread_cpu_us=(\S+) majflt=(\S+) minflt=(\S+) vcsw=(\S+) ivcsw=(\S+)$")
fields = {name: pattern.search(line).groups() for name, line in lines.items()}

busy_cpu = int(fields["busy"][0])
assert busy_cpu >= 60_000, lines["busy"]  # most of a 100 ms spin is CPU, even on a busy host

sleep_cpu, _, _, sleep_vcsw, _ = fields["sleep"]
assert int(sleep_cpu) < 50_000 and int(sleep_vcsw) >= 1, lines["sleep"]  # waited, not computed

assert int(fields["touch"][2]) >= 1000, lines["touch"]  # 8 MiB of new pages fault in

assert fields["unreadable"] == ("-", "-", "-", "-", "-"), lines["unreadable"]
print("tick thread usage separates CPU work, off-CPU waits and page faults")
