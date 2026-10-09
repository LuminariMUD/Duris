#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="$ROOT/src"
TEST="$ROOT/tests/async/test_signal_handlers.cpp"
OUT="$ROOT/bin/tests/test_signal_handlers"

mkdir -p "$(dirname "$OUT")"
g++ -std=c++20 -I"$SRC" "$TEST" "$ROOT/tests/async/harness_stubs.cpp" -o "$OUT"
"$OUT"
