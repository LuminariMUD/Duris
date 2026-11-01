#!/usr/bin/env python3
"""Color stripping accepts truncated authored/player text without reading past it."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include <cassert>
#include <cstring>
#include <memory>
#include <string>
'''
driver = r'''
int main() {
    for (const auto &[input, expected] : {
        std::pair{"", ""}, {"&", "&"}, {"&+", "&+"}, {"&-", "&-"},
        {"&=", "&="}, {"&=L", "&=L"}, {"red&+", "red&+"},
        {"&+Rred&n", "red"}, {"&=LWwhite&N", "white"},
        {"a &+Rred&n blade", "a red blade"}
    }) {
        const size_t size = strlen(input) + 1;
        auto bytes = std::make_unique<char[]>(size);
        memcpy(bytes.get(), input, size);
        assert(strip_ansi(bytes.get()) == expected);
    }
}
'''
build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="strip-ansi-", dir=build) as directory:
    source = Path(directory) / "harness.cpp"
    binary = Path(directory) / "harness"
    source.write_text(prelude + extract_function("utility.c", "string strip_ansi(") + driver)
    subprocess.run(["g++", "-std=c++20", "-g", "-fsanitize=address,undefined",
                    "-fno-sanitize-recover=all", "-fno-pie", "-no-pie", "-Isrc",
                    str(source), "-o", str(binary)], cwd=ROOT, check=True, timeout=120)
    subprocess.run([str(binary)], check=True, timeout=30)
print("truncated color sequences and normal color stripping passed")
