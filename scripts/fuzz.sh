#!/usr/bin/env bash
# fuzz.sh TARGET [SECONDS]: build tests/fuzz/TARGET.cpp with libFuzzer and the sanitizers
# under bin/fuzz/TARGET/, and fuzz it for SECONDS (default 60). `make fuzz FUZZ_TARGET=...
# FUZZ_SECONDS=...` runs it.
#
# The target names what it links on its `// fuzz-sources:` and `// fuzz-libs:` lines, and
# its largest input on `// fuzz-max-len:` (past the limits its code checks; libFuzzer would
# take the corpus's largest, 4 KiB); the shared harness stubs fill in the rest. The fuzzer starts from tests/fuzz/corpus/TARGET/
# and writes the inputs it finds to bin/fuzz/TARGET/corpus/, and a crash to
# bin/fuzz/TARGET/crash-*. Copy a crash, and an input worth keeping, into
# tests/fuzz/corpus/TARGET/ (`-merge=1` picks a small set): tests/async/test_fuzz_corpus.py
# replays that directory in every gate. Needs clang with libFuzzer.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

target=${1:?usage: $0 TARGET [SECONDS]}
seconds=${2:-60}
source=tests/fuzz/$target.cpp
[[ -f "$source" ]] || {
	echo "no fuzz target $source; the targets: $(ls tests/fuzz/*.cpp | xargs -n1 basename)" >&2
	exit 2
}
read -r -a sources <<<"$(sed -n 's#^// fuzz-sources:##p' "$source")"
read -r -a libs <<<"$(sed -n 's#^// fuzz-libs:##p' "$source")"
max_len=$(sed -n 's#^// fuzz-max-len: *\([0-9]*\).*#\1#p' "$source")
out=bin/fuzz/$target
mkdir -p "$out/corpus" "tests/fuzz/corpus/$target"
# clang otherwise picks the newest installed libstdc++, which need not be g++'s. An
# undefined-behaviour report stops the run, as in the replay, so it leaves a crash input.
clang++ --gcc-install-dir="$(dirname "$(g++ -print-libgcc-file-name)")" -std=c++20 -g -O1 \
	-fsanitize=fuzzer,address,undefined -fno-sanitize-recover=all -D__NO_MYSQL__ -Isrc \
	-Isrc/no_mysql \
	"$source" "${sources[@]}" tests/async/harness_stubs.cpp "${libs[@]}" -o "$out/fuzzer"
"$out/fuzzer" -max_total_time="$seconds" -max_len="${max_len:-4096}" -print_final_stats=1 \
	-artifact_prefix="$out/" \
	"$out/corpus" "tests/fuzz/corpus/$target"
