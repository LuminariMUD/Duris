from _paths import SRC
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
structs = (SRC / "structs.h").read_text()
actoth = (SRC / "actoth.c").read_text()
nanny = (SRC / "nanny.c").read_text()
sql_player = (SRC / "sql_player.c").read_text()

assert "constexpr int DEFAULT_SCREEN_LENGTH = 40;" in structs

assert "ch->only.pc->screen_length = DEFAULT_SCREEN_LENGTH;" in nanny
assert "ch->only.pc->screen_length = reset ? DEFAULT_SCREEN_LENGTH : number;" in actoth
assert 'snprintf(Gbuf3, sizeof Gbuf3, "%d", ch->only.pc->screen_length);' in actoth
assert 'snprintf(Gbuf3, MAX_INPUT_LENGTH, "%3d", DEFAULT_SCREEN_LENGTH);' in actoth
assert "Screen length set to default %s lines." in actoth

for runtime_source in (actoth, nanny, sql_player):
    assert "screen_length = 24" not in runtime_source
    assert "default 24 lines" not in runtime_source

print("screen-length default contract passed")


# Exercise accepted/reset/rejected sizes, actual pager boundaries and ANSI layout.
import subprocess
import tempfile
from _paths import extract_function

case = actoth.split('case 21: // Screen length', 1)[1].split('case 22:', 1)[0]
fixture = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include <cassert>
#include <cerrno>
#include <cctype>
#include <cstring>
#include <string>
#include <vector>
#define PAGE_WIDTH 80
char Gbuf3[MAX_STRING_LENGTH];
static std::string output;
void send_to_char(const char *text, P_char) { output += text; }
void UpdateScreen(P_char, int) {}
int IS_MORPH(P_char) { return false; }
''' + \
    extract_function('interp.c', 'char *lohrr_chop(') + \
    extract_function('modify.c', 'char *next_page(') + \
    extract_function('prompt.c', 'void InitScreen(') + \
    'void screensize(P_char ch, char *arg) { P_char send_ch = ch; bool result = false; switch(21) { case 21:' + \
    case + ' } (void)result; }' + r'''
int main() {
    char_data ch{}; pc_only_data pc{}; descriptor_data desc{};
    ch.only.pc = &pc; desc.character = &ch; ch.player.level = 20;
    auto set = [&](const char *value) {
        std::string argument = value; output.clear();
        screensize(&ch, argument.data());
    };
    for (int size : {12,48,96,100}) {
        set(std::to_string(size).c_str());
        assert(pc.screen_length == size && output.empty());
        std::string text;
        for (int line = 0; line < 120; ++line) text += "line\n";
        auto *boundary = next_page(text.data(), &desc);
        assert(boundary && boundary - text.data() == (size - 4) * 5);
        output.clear(); pc.prompt = PROMPT_MANA;
        InitScreen(&ch);
        assert(output.find("\x1b[0;" + std::to_string(size - 4) + "r") != std::string::npos);
        assert(output.find("\x1b[" + std::to_string(size + 1) + ";40H") != std::string::npos);
    }
    for (const char *value : {"11","101","-1","100 junk","12bad","999999999999999999999"}) {
        set(value); assert(pc.screen_length == 100 && output.find("12-100") != std::string::npos);
    }
    for (const char *value : {"","default","off","0"}) {
        set(value); assert(pc.screen_length == 40 && output.empty());
    }
    puts("screen size boundaries, default resets, pager and ANSI infobar layout passed");
}
'''
(ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='issue904-', dir=ROOT / 'bin/tests') as temporary:
    cpp, binary = Path(temporary)/'screen.cpp', Path(temporary)/'screen'
    cpp.write_text(fixture)
    subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-fno-pie','-no-pie','-Isrc',
                    '-I/usr/include/mysql',str(cpp),'-o',str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],check=True)
