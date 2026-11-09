#!/usr/bin/env python3
"""Execute editor object reader/writer and text helpers against B5 records."""
from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT


HARNESS = r'''
#include "types.h"
#include "fh.h"
#include "obj/object.h"
#include "vardef.h"
#include "edesc/edesc.h"
#include "item/item_value.h"
#include "spells.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>

objectType **g_objLookup = nullptr;
variable *g_varHead = nullptr;
bool g_oldObjConv = false, g_madeChanges = false, g_readFromSubdirs = false;
uint g_numbLookupEntries = 1000000, g_numbObjTypes = 0, g_lowestObjNumber = 0, g_highestObjNumber = 0;
void _outtext(const char *text) { std::fputs(text, stderr); }
void displayAllocError(const char *, const char *) { assert(false); }
void displayAnyKeyPromptNoClr(const char *) { assert(false); }
bool changeMaxVnumAutoEcho(uint) { assert(false); return false; }
void setVarBoolVal(variable **, const char *, bool, bool) {}
const char *getEntityTypeStrn(uchar) { return "object"; }
void createPrompt() {}
const char *getMainZoneNameStrn() { return "fixture"; }
const char *plural(int count) { return count == 1 ? "" : "s"; }
Skill skills[MAX_AFFECT_TYPES]{};
static unsigned long long valued_bank5;
bool item_value_has_packed_proc(const item_value_input &) { return false; }
int evaluate_item_value(const item_value_input &input, const item_value_context &, item_value_breakdown *)
{
    valued_bank5 = input.bitvector5;
    return 42;
}

static const char *header =
    "fixture~\na fixture~\nA fixture is here.~\n~\n"
    "11 1 0 0 7 0 0 1 0 0 0\n"
    "0 0 0 0 0 0 0 0\n"
    "1 0 100 0 0 0 0\n";

static void dispose(objectType *object)
{
    deleteStringNodes(object->keywordListHead);
    deleteExtraDescs(object->extraDescHead);
    delete object;
}

int main(int argc, char **argv)
{
    assert(argc == 3);
    if (!std::strcmp(argv[1], "--write-file")) {
        g_lowestObjNumber = 1; g_highestObjNumber = 0;
        writeObjectFile(argv[2]);
        return 0;
    }
    const auto expected = std::strtoull(argv[2], nullptr, 10);
    FILE *input = std::tmpfile(); assert(input);
    std::fprintf(input, "#1300\n%s%s\n", header, argv[1]);
    std::fputs("E\nrune~\nAn old rune.\n~\nA\n1 3\nA\n6 2\nA\n1 -3\nA\n18 -2\nT\n1 2 3 4\n#1301\n", input);
    std::fputs(header, input);
    std::rewind(input);
    char next[512]{};
    objectType *first = readObjectFromFile(input, next, false, false);
    assert(first && first->objNumber == 1300 && first->objApply[0].applyWhere == 1);
    assert(first->objApply[0].applyModifier == 3 && first->extraDescHead && first->trapBits == 1);
    assert(first->affect5Bits == expected && first->objApply[3].applyModifier == -2);
    assert(itemvalue(first) == 42 && valued_bank5 == expected); // Real editor adapter, controlled numeric endpoint.
    objectType *second = readObjectFromFile(input, next, false, false);
    assert(second && second->objNumber == 1301 && second->affect5Bits == 0);
    std::fclose(input);

    FILE *output = std::tmpfile(); assert(output);
    writeObjecttoFile(output, first); writeObjecttoFile(output, second);
    std::fflush(output);
    std::rewind(output);
    std::string written;
    char block[1024];
    while (size_t count = std::fread(block, 1, sizeof(block), output)) written.append(block, count);
    if (expected) {
        const auto position = written.find("B5 " + std::to_string(expected) + "\n");
        assert(position != std::string::npos && position < written.find("E\n"));
    } else assert(written.find("B5 ") == std::string::npos);
    std::rewind(output);
    next[0] = 0;
    objectType *restored = readObjectFromFile(output, next, false, false);
    assert(restored && restored->objApply[0].applyModifier == 3 && restored->extraDescHead);
    assert(restored->affect5Bits == expected && compareObjectType(first, restored));
    objectType *following = readObjectFromFile(output, next, false, false);
    assert(following && following->objNumber == 1301 && following->affect5Bits == 0);
    std::fclose(output);
    objectType *copy = copyObjectType(first, false);
    assert(copy && copy->affect5Bits == expected && compareObjectType(first, copy));
    copy->affect5Bits ^= 1ULL;
    assert(!compareObjectType(first, copy));
    dispose(copy);
    dispose(first); dispose(second); dispose(restored); dispose(following);
}
'''


def main():
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    editor = ROOT / "areas/de/src"
    sources = ["obj/readobj.cpp", "obj/writeobj.cpp", "readfile.cpp", "misc/strings.cpp",
               "misc/strnnode.cpp", "misc/keywords.cpp", "edesc/readexd.cpp",
               "edesc/writeexd.cpp", "edesc/edesc.cpp", "obj/object.cpp"]
    with tempfile.TemporaryDirectory(prefix="editor-object-io-", dir=build) as tmp:
        source, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
        source.write_text(HARNESS)
        subprocess.run([
            "g++", "-std=c++20", "-g", "-O1", "-D_DE_", "-D__UNIX__", "-DGODMODE=1",
            "-ffunction-sections", "-fdata-sections", "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-Isrc", "-I" + str(editor), str(source),
            *(str(editor / path) for path in sources), "-Wl,--gc-sections", "-o", str(binary),
        ], cwd=ROOT, check=True)
        env = {**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
               "UBSAN_OPTIONS": "halt_on_error=1"}
        valid = [("", 0), ("B5 0", 0), ("B5 +0001", 1), ("B5\n1", 1),
                 (" B5\t1 ", 1), ("\tB5\t1\t", 1), ("B5 4294967295", 2**32 - 1),
                 (f"B5 {2**64 - 1}", 2**64 - 1)]
        valid += [(f"B5 {1 << bit}", 1 << bit) for bit in range(64)]
        for record, mask in valid:
            result = subprocess.run([str(binary), record, str(mask)], capture_output=True,
                                    text=True, env=env)
            assert result.returncode == 0, (record, result.stdout, result.stderr)
        for record in ("B5 -1", "B5 no", "B5 1x", "B5 0x10", "B5 1 2", "B5 +",
                       "B5", "B5 1\nB5 2", f"B5 {2**64}", "B5 " + "9" * 510):
            result = subprocess.run([str(binary), record, "0"], capture_output=True,
                                    text=True, env=env)
            assert result.returncode == 1, (record, result.stderr)
            assert "Error:" in result.stderr and "Aborting" in result.stderr, result.stderr
            assert "Sanitizer" not in result.stderr and "runtime error:" not in result.stderr, result.stderr
        print("editor native B5 I/O: 72 valid round trips including all 64 bits, clone/equality and following records")
        print("editor native B5 I/O: malformed, duplicate, overflow and overlong masks rejected without sanitizer errors")
        # Exercise the full file writer too: the filename and its progress text
        # must not overflow the old 512-byte buffers.
        long_path = Path(tmp)
        for index in range(6):
            long_path /= str(index) * 90
            long_path.mkdir()
        target = long_path / "fixture"
        result = subprocess.run([str(binary), "--write-file", str(target)], capture_output=True,
                                text=True, env=env)
        assert result.returncode == 0 and target.with_suffix(".obj").is_file(), result.stderr
        assert str(target) + ".obj" in result.stderr, result.stderr
        result = subprocess.run([str(binary), "--write-file", "x" * 600], capture_output=True,
                                text=True, env=env)
        assert result.returncode == 0 and "Couldn't open" in result.stderr, result.stderr
        assert "Sanitizer" not in result.stderr and "runtime error:" not in result.stderr, result.stderr
        print("editor native file writer: long nested paths and oversized filenames handled without buffer overflow")


if __name__ == "__main__":
    main()
