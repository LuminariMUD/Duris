#!/usr/bin/env python3
"""Execute the production command dispatcher with controlled legacy I/O."""

import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function


HARNESS = r'''
#include <cassert>
#include <cctype>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <functional>
#include <string>
#include <vector>
struct character { bool trusted = true; };
using P_char = character *;
using sql_rows = std::vector<std::vector<const char *>>;
#define IS_TRUSTED(ch) ((ch)->trusted)
#define MAX_STRING_LENGTH 32768
#define MAX_BTYPE 2
#define MAX_BOPT 2
#define BOPT_CTFB 13
#define BN_VOID 6
#define FALSE 0
#define TRUE 1
struct BoonData { int option = 0; };
struct { const char *type; } boon_types[MAX_BTYPE + 1] = { {"none"}, {"exp"}, {"end"} };
struct { const char *option; } boon_options[MAX_BOPT] = { {"none"}, {"zone"} };
static bool open = false, flat = true;
static int lists, shops, creates, extensions, removals, notifications, randoms;
static std::string output;
bool divine_boon_legacy_admissions_allowed() { return open; }
void send_to_char(const char *text, P_char) { output += text; }
void send_to_char_f(P_char, const char *format, ...) {
    char buffer[MAX_STRING_LENGTH];
    va_list args; va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args); va_end(args);
    output += buffer;
}
char *one_argument(const char *text, char *word) {
    while (*text && std::isspace(static_cast<unsigned char>(*text))) ++text;
    while (*text && !std::isspace(static_cast<unsigned char>(*text))) *word++ = *text++;
    *word = 0;
    while (*text && std::isspace(static_cast<unsigned char>(*text))) ++text;
    return const_cast<char *>(text);
}
int boon_display(P_char, char *) { ++lists; return 1; }
void boon_shop(P_char, char *) { ++shops; }
void zero_boon_data(BoonData *data) { *data = {}; }
int parse_boon_args(P_char, BoonData *, char *) { return 1; }
bool ctf_use_boon(BoonData *) { return true; }
int create_boon(BoonData *, P_char) { return ++creates; }
const char *flat_boon_root() { return flat ? "fixture" : nullptr; }
std::string sql_format(const char *, int) { return "fixture"; }
void sql_read_for(P_char ch, const std::string &,
                  std::function<void(P_char, const sql_rows &)> callback) {
    callback(ch, {{"1", "0"}});
}
int remove_boon(int id) { assert(id == 42); ++removals; return 1; }
int is_boon_valid(int) { return 1; }
void boon_notify(int, P_char, int) { ++notifications; }
void boon_notify_snapshot(int, int, int, int) { ++notifications; }
void extend_boon_on_writer(P_char, int, int) { ++extensions; }
int extend_boon(int, int, const char *) { return ++extensions; }
const char *GET_NAME(P_char) { return "staff"; }
void boon_randomize(P_char, char *) { ++randoms; }
bool check_boon_combo(int, int, int) { return false; }
int get_boon_level(int, int) { return 1; }
#define checked_snprintf std::snprintf
// DISPATCHER
int main() {
    character staff;
    auto run = [&](const char *text) {
        char argument[128]; std::strcpy(argument, text); output.clear();
        do_boon(&staff, argument, 0);
    };
    for (bool backend : {true, false}) {
        flat = backend;
        run(""); run("list");
        assert(lists == (backend ? 2 : 4));
        run("help"); assert(output.find("Boon Command Help") != std::string::npos);
        run("?"); assert(output.find("Boon Command Help") != std::string::npos);
        run("remove 42");
        assert(removals == (backend ? 1 : 2) && notifications == removals);
        for (const char *command : {"shop str", "add", "extend 42 60", "random"}) {
            run(command);
            assert(output.find("Legacy boons are closed") != std::string::npos);
        }
        assert(!shops && !creates && !extensions && !randoms);
    }
    open = true;
    run("shop str"); run("add"); run("extend 42 60"); run("random");
    assert(shops == 1 && creates == 1 && extensions == 1 && randoms == 1);
    std::puts("Legacy command inspection/removal survives closed admissions on both backends");
}
'''

outputs = ROOT / "bin/tests"
outputs.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="divine-legacy-commands-", dir=outputs) as directory:
    source = Path(directory) / "commands.cpp"
    binary = Path(directory) / "commands"
    source.write_text(HARNESS.replace("// DISPATCHER", extract_function("boon.c", "void do_boon(")))
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
        "-g", "-Og", "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
        str(source), "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True)
