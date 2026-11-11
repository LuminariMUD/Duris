#!/usr/bin/env python3
"""Execute Deaths Door's inspection, portal level, achievement and cooldown gates."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function


fixture = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "magic/spells.h"
#include <cassert>
#include <string>
static bool earned, cooldown;
static int portals, waits, timers;
static std::string output;
bool affected_by_spell(P_char, int type) {
    return type == ACH_DEATHSDOOR ? earned : type == TAG_DEATHSDOOR && cooldown;
}
void act(const char *text, int, P_char, P_obj, void *, int) { output += text; }
void send_to_char(const char *text, P_char) { output += text; }
affected_type *affect_to_char(P_char, affected_type *af) {
    assert(af->type == TAG_DEATHSDOOR && af->duration == 15 && af->flags == AFFTYPE_NODISPEL);
    ++timers; cooldown = true; return nullptr;
}
void spell_corpse_portal(int level, P_char, char *, int, P_char, P_obj) {
    assert(level == 60); ++portals;
}
void CharWait(P_char, int lag) { assert(lag == 5 * WAIT_SEC); ++waits; }
''' + extract_function('specs.gellz.c', 'void do_deaths_door(') + r'''
int main() {
    char_data ch{};
    SET_POS(&ch, STAT_NORMAL + POS_STANDING);
    ch.base_stats.Str = 95; ch.base_stats.Int = 97;
    auto run = [&](int level, bool achievement, const char *argument) {
        ch.player.level = level; earned = achievement; output.clear();
        std::string args = argument;
        do_deaths_door(&ch, args.data(), 0);
        return output;
    };
    for (int level : {1,19,20,24,25}) {
        const auto text = run(level, false, "");
        assert((text.find("You still need") != std::string::npos) == (level >= 20));
        if (level >= 20) {
            assert(text.find("5 &+LStr") != std::string::npos);
            assert(text.find("3 &+LInt") != std::string::npos);
        }
        run(level, false, "door");
        assert(!portals && !waits && !timers);
    }
    for (int level : {1,19,20,24}) {
        assert(run(level, true, "door").find("level 25") != std::string::npos);
        assert(!portals && !waits && !timers && !cooldown);
    }
    run(25, true, "");
    assert(!portals && !timers);
    run(25, true, "door");
    assert(portals == 1 && timers == 1 && waits == 1 && cooldown);
    assert(run(25, true, "door").find("longer") != std::string::npos);
    assert(portals == 1 && timers == 1 && waits == 1);
    cooldown = false;
    run(56, true, "door");
    assert(portals == 2 && timers == 2 && waits == 2);
    puts("Deaths Door inspection 20, portal 25, achievement, cooldown and action delay pass");
}
'''
(ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='issue904-', dir=ROOT / 'bin/tests') as temporary:
    source, binary = Path(temporary) / 'door.cpp', Path(temporary) / 'door'
    source.write_text(fixture)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                    '-Isrc', '-I/usr/include/mysql', str(source), 'src/core/safe_format.c',
                    '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
