#!/usr/bin/env python3
"""Allocator corruption must abort at its diagnostic site with live static workers."""

import signal
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function


harness = r'''
#include "core/prototypes.h"
#include "core/structs.h"

#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <sys/resource.h>

std::thread worker;
std::atomic<bool> running{false};
FILE *mem_log = nullptr;
long allocation_list_node_count = 0;

void decrement_mem_used(const char *, size_t) {}

// FATAL_MESSAGE
// PANIC_CORRUPTION
// HEADER_FROM_BODY
// DELMEM

int main() {
    const rlimit no_core{0, 0};
    setrlimit(RLIMIT_CORE, &no_core);
    worker = std::thread([] {
        running.store(true);
        for (;;)
            std::this_thread::sleep_for(std::chrono::seconds(1));
    });
    while (!running.load())
        std::this_thread::yield();

    ALLOCATION_HEADER invalid{};
    invalid.tag = "invalid";
    char *body = reinterpret_cast<char *>(&invalid) + sizeof(invalid);
    delmem(body, "fixture.cpp", 42);
}
'''
harness = harness.replace(
    "// FATAL_MESSAGE", extract_function("common.c", "static void fatal_message_v(")
).replace(
    "// PANIC_CORRUPTION", extract_function("common.c", "void panic_corruption(")
).replace(
    "// HEADER_FROM_BODY", extract_function("memory.c", "static ALLOCATION_HEADER *allocation_header_from_body(")
).replace(
    "// DELMEM", extract_function("memory.c", "void delmem(")
)

build_dir = ROOT / "bin/tests"
build_dir.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory(prefix="memory-corruption-", dir=build_dir) as directory:
    source = Path(directory) / "harness.cpp"
    binary = Path(directory) / "harness"
    source.write_text(harness)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-D_DE_",
        "-I" + str(ROOT / "src"), str(source), "-pthread", "-o", str(binary),
    ], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
    assert result.returncode == -signal.SIGABRT, result
    assert result.stdout == "", result.stdout
    assert result.stderr == "delmem: memory failed check at fixture.cpp:42\n", result.stderr

print("allocator corruption aborts at delmem without running joinable-thread destruction")
