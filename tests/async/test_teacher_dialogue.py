#!/usr/bin/env python3
"""Execute teacher dialogue with production types and captured output."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function


HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/epic.h"
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>

P_obj object_list = nullptr;
index_data objects[2]{};
P_index obj_index = objects;
zone_data zones[2]{};
zone_data *zone_table = zones;
std::string output;
P_char recipient = nullptr;
int all_level = 51;
int GET_CLASS(P_char ch, unsigned int cls) { return ch->player.m_class & cls; }
int get_property(const char *, int) { return all_level; }
int real_zone0(int vnum) { assert(vnum == 7); return 0; }
int epic_stone(P_obj, P_char, int, char *) { return 0; }
void send_to_char(const char *text, P_char ch) {
    assert(ch == recipient);
    output += text;
}
void send_to_char_f(P_char ch, const char *format, ...) {
    char text[512];
    va_list args;
    va_start(args, format);
    const int count = vsnprintf(text, sizeof(text), format, args);
    va_end(args);
    assert(count >= 0 && static_cast<size_t>(count) < sizeof(text));
    send_to_char(text, ch);
}
'''

CASES = r'''
int main() {
    char_data trainer{}, player{};
    trainer.player.m_class = player.player.m_class = CLASS_CLERIC;
    player.player.level = 20;
    recipient = &player;
    char request[] = "level";
    const std::string prefix = "For your further path of development it is crucial that you visit\n";
    const std::string suffix = " of the magical runestones locates in the following lands:\n";
    auto ask = [&] {
        output.clear();
        assert(teacher(&trainer, &player, CMD_ASK, request));
    };
    ask();
    assert(output == prefix + "one" + suffix);

    obj_data stones[4]{};
    objects[0].func.obj = epic_stone;
    std::string land = "The Quiet Valley";
    zones[0].name = land.data();
    for (int i = 0; i < 4; ++i) {
        stones[i].R_num = 0;
        stones[i].value[2] = 7;
        stones[i].value[3] = 21;
        stones[i].next = i < 3 ? &stones[i + 1] : nullptr;
    }
    stones[1].R_num = 1; // Non-runestone objects do not enter the reply.
    stones[2].value[3] = 22; // Only the player's next level is listed.
    object_list = stones;
    ask();
    assert(output == prefix + "one" + suffix + land + "\n" + land + "\n");

    // Output size is independent of any local accumulation buffer.
    land.assign(600, 'A');
    zones[0].name = land.data();
    ask();
    assert(output == prefix + "one" + suffix + land + "\n" + land + "\n");
    all_level = 21;
    ask();
    assert(output == prefix + "all" + suffix + land + "\n" + land + "\n");

    output.clear();
    assert(!teacher(&trainer, &player, CMD_LOOK, request));
    assert(!teacher(&trainer, &player, CMD_ASK, nullptr));
    assert(!teacher(&trainer, nullptr, CMD_ASK, request));
    player.player.m_class = CLASS_WARRIOR;
    assert(!teacher(&trainer, &player, CMD_ASK, request));
    assert(output.empty());
}
'''


def main() -> None:
    directory = ROOT / "bin" / "tests"
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="teacher-dialogue-", dir=directory) as temporary:
        program = Path(temporary) / "harness.cpp"
        binary = Path(temporary) / "harness"
        program.write_text(HARNESS + extract_function("specs.mobile.c", "int teacher(") + CASES)
        subprocess.run([
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc", "-I/usr/include/mysql",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            str(program), "-o", str(binary),
        ], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True, timeout=10)
    print("teacher dialogue output passed")


if __name__ == "__main__":
    main()
