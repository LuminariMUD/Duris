#!/usr/bin/env python3
"""Exercise lohrr_chop's quoted-word fallback and input boundary under ASan/UBSan."""
import os
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include <cassert>
#include <string>
#include <vector>

TOKENIZER

static void check(const std::string &input, const std::string &word, const std::string &rest) {
    std::vector<char> text(input.begin(), input.end()); text.push_back('\0');
    char output[MAX_INPUT_LENGTH];
    char *remainder = lohrr_chop(text.data(), output);
    assert(output == word);
    assert(remainder == rest);
}

int main() {
    // An unmatched quote falls back to one unquoted word, including the opening quote.
    check("'" + std::string(MAX_INPUT_LENGTH - 2, 'A'),
          "'" + std::string(MAX_INPUT_LENGTH - 2, 'a'), "");
    check("'HELLO", "'hello", "");
    check("'TWO words", "'two", " words");
    check("'", "'", "");
    check("'TWO words' tail", "two words", " tail");
    check("'TWO words'tail", "two words", "tail");
    check("  WoRd\tNext", "word", "\tNext");
    check("WITH tail", "with", " tail");
    check("", "", "");
    check("   ", "", "");
    char output[1] = {'x'};
    assert(lohrr_chop(nullptr, output) == nullptr && output[0] == '\0');
    puts("argument tokenizer passed: quoted, unmatched, empty and maximum-length words");
}
'''


def main():
    output = ROOT / "bin/tests"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="argument-tokenizer-", dir=output) as directory:
        work = Path(directory)
        harness = work / "harness.cpp"
        harness.write_text(HARNESS.replace("TOKENIZER", extract_function(
            "interp.c", "char *lohrr_chop(char *string, char *arg1)")))
        binary = work / "argument-tokenizer"
        subprocess.run([
            "g++", "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer", "-I" + str(ROOT / "src"), str(harness),
            "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, timeout=30,
                       env=dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
                                UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1"))


if __name__ == "__main__":
    main()
