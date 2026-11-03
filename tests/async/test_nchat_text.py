#!/usr/bin/env python3
"""Newbie chat preserves message text in terminal, GMCP and log output."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function


HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/gmcp.h"
#include "core/safe_format.h"
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <map>
#include <string>

P_desc descriptor_list;
const racewar_struct racewar_color[MAX_RACEWAR + 2] = {
    {'g', "Good"}, {'g', "Good"}, {'r', "Evil"},
    {'w', "Undead"}, {'w', "Neutral"}, {'w', "Other"}
};
static std::map<P_char, std::string> terminal, packets;
static std::string logged;
bool is_silent(P_char, bool) { return false; }
int SpammingNchat(P_char) { return 0; }
char *PERS(P_char ch, P_char, int) { return GET_NAME(ch); }
char *language_CRYPT(P_char, P_char, char *text) { return text; }
float get_property(const char *, double) { return 1; }
void send_to_char(const char *text, P_char ch) { terminal[ch] += text; }
void send_to_char(const char *text, P_char ch, int) { terminal[ch] += text; }
void gmcp_comm_channel_ex(P_char ch, const char *channel, const char *,
                          const char *text, const char *alignment) {
    assert(std::string(channel) == "nchat");
    assert(std::string(alignment) == "good");
    packets[ch] = text;
}
void logit(const char *, const char *format, ...) {
    char text[MAX_STRING_LENGTH];
    va_list args;
    va_start(args, format);
    vsnprintf(text, sizeof text, format, args);
    va_end(args);
    logged = text;
}
'''

DRIVER = r'''
int main() {
    char_data sender{}, receiver{};
    pc_only_data sender_pc{}, receiver_pc{};
    descriptor_data sender_desc{}, receiver_desc{};
    char sender_name[] = "Sender", receiver_name[] = "Receiver";
    sender.only.pc = &sender_pc;
    receiver.only.pc = &receiver_pc;
    sender.player.name = sender_name;
    receiver.player.name = receiver_name;
    sender.player.racewar = receiver.player.racewar = RACEWAR_GOOD;
    sender.specials.position = receiver.specials.position = POS_STANDING + STAT_NORMAL;
    sender.specials.act2 = receiver.specials.act2 = PLR2_NCHAT;
    sender.specials.act = PLR_ECHO;
    sender.desc = &sender_desc;
    receiver.desc = &receiver_desc;
    sender_desc.character = &sender;
    receiver_desc.character = &receiver;
    sender_desc.next = &receiver_desc;
    descriptor_list = &sender_desc;
    receiver.player.level = 20;

    for (int level : {20, 62}) {
        sender.player.level = level;
        for (const std::string message : {
                 "fucking", "fuckin", "FUCKING awesome",
                 "not bad?! its fucking awesome! the rest stays too",
                 "fucking twice: fucking", "Choron stays literal",
                 "literal %s %n %% and punctuation!"}) {
            std::string input = (level == 62 ? "g " : "") + message;
            const std::string original = input;
            terminal.clear(); packets.clear(); logged.clear();
            do_nchat(&sender, input.data(), 0);
            assert(input == original);
            assert(terminal[&sender].find(message) != std::string::npos);
            assert(terminal[&receiver].find(message) != std::string::npos);
            assert(packets.size() == 2);
            assert(packets[&sender] == message && packets[&receiver] == message);
            assert(logged.find(message) != std::string::npos);
        }
    }
}
'''

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="nchat-text-", dir=build) as directory:
    path = Path(directory)
    source = path / "test.cpp"
    binary = path / "test"
    source.write_text(HARNESS + extract_function("interp.c", "bool is_abbrev(")
                      + extract_function("actwiz.c", "void do_nchat(") + DRIVER)
    subprocess.run([
        "g++", "-std=c++20", "-fsanitize=address,undefined",
        "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-I", str(ROOT / "src"), str(source),
        str(ROOT / "src/core/safe_format.c"), "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True)

print("newbie chat preserves mortal/staff message text under ASan/UBSan")
