#!/usr/bin/env python3
"""Replay every fuzz target's committed corpus once, without a fuzzing engine.

Each tests/fuzz/<target>.cpp is built with g++, the address and undefined-behaviour
sanitizers, the sources its `// fuzz-sources:` line names, the shared harness stubs and a
main() that feeds it each file of tests/fuzz/corpus/<target>/. A crash or sanitizer report
that a fuzzing run found, once its input is committed, fails here until it is fixed.
scripts/fuzz.sh (make fuzz) is the fuzzing itself.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import HARNESS_STUBS, ROOT

REPLAY_MAIN = r'''
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <vector>
extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);
int main(int argc, char **argv)
{
	for (int index = 1; index < argc; ++index)
	{
		std::ifstream file(argv[index], std::ios::binary);
		const std::vector<uint8_t> input{std::istreambuf_iterator<char>(file), {}};
		LLVMFuzzerTestOneInput(input.data(), input.size());
	}
	std::printf("%d inputs replayed\n", argc - 1);
}
'''

targets = sorted((ROOT / "tests/fuzz").glob("*.cpp"))
assert targets, "no fuzz targets"
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="fuzz-corpus-", dir=ROOT / "bin/tests") as build:
    main = Path(build) / "replay_main.cpp"
    main.write_text(REPLAY_MAIN)
    for target in targets:
        text = target.read_text()
        line = lambda key: next(line.split(":", 1)[1].split() for line in text.splitlines()
                                if line.startswith(f"// fuzz-{key}:"))
        corpus = sorted((ROOT / "tests/fuzz/corpus" / target.stem).glob("*"))
        assert corpus, f"{target.stem} has no committed corpus"
        binary = Path(build) / target.stem
        subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                        "-fno-sanitize-recover=all", "-D__NO_MYSQL__", "-Isrc", "-Isrc/no_mysql",
                        str(target), *line("sources"), str(HARNESS_STUBS), str(main),
                        *line("libs"), "-o", str(binary)], cwd=ROOT, check=True)
        result = subprocess.run([str(binary), *map(str, corpus)], cwd=ROOT, text=True,
                                capture_output=True, timeout=300)
        assert result.returncode == 0, f"{target.stem}:\n{result.stdout}{result.stderr[-4000:]}"
        print(f"{target.stem}: {result.stdout.strip()}", flush=True)
