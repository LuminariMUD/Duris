#!/usr/bin/env python3
"""Round-trip native selectors through ordinary racewar targeting, including ordinals."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/handler.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <sstream>
#include <string>
#undef CAN_DAYPEOPLE_SEE
#define CAN_DAYPEOPLE_SEE(room) true
static room_data rooms[2]{};
P_room world=rooms;
static struct { const char *normal; } race_names_table[LAST_RACE+1]{};
static P_char hidden, introduced;
bool ac_can_see(P_char, P_char target, bool) { return target!=hidden; }
int is_introd(P_char target, P_char) { return target==introduced; }
bool has_innate(P_char, int) { return false; }
bool racewar(P_char a, P_char b) { return a->player.racewar!=b->player.racewar; }
bool isname(const char *word, const char *names) {
    if (!word || !names) return 0;
    std::istringstream input(names); std::string token;
    while(input>>token) if(!strcasecmp(word,token.c_str())) return 1;
    return 0;
}
char *one_argument(const char *text, char *word) {
    while(*text==' ') ++text;
    while(*text && *text!=' ') *word++=*text++;
    *word=0; return const_cast<char *>(text);
}
int get_number(char **text) {
    char *dot=strchr(*text,'.'); if(!dot) return 1;
    const int n=atoi(*text); *text=dot+1; return n;
}
// PRODUCTION
int main() {
    char_data viewer{}, npc{}, ally{}, enemy{}, second{}, invisible{}, elevated{};
    pc_only_data pc{};
    for(P_char ch : {&viewer,&npc,&ally,&enemy,&second,&invisible,&elevated}) {
        ch->only.pc=&pc; ch->player.level=56; ch->player.race=RACE_HUMAN;
        ch->player.racewar=RACEWAR_EVIL;
    }
    viewer.player.name=const_cast<char *>("Viewer"); viewer.player.race=RACE_GREY;
    viewer.player.racewar=ally.player.racewar=RACEWAR_GOOD;
    npc.player.name=const_cast<char *>("guard human"); SET_BIT(npc.specials.act,ACT_ISNPC);
    ally.player.name=const_cast<char *>("Friend"); enemy.player.name=const_cast<char *>("Enemy");
    second.player.name=const_cast<char *>("Second"); invisible.player.name=const_cast<char *>("Hidden");
    elevated.player.name=const_cast<char *>("Above"); elevated.specials.z_cord=1;
    viewer.next_in_room=&npc; npc.next_in_room=&ally; ally.next_in_room=&enemy;
    enemy.next_in_room=&second; second.next_in_room=&invisible; invisible.next_in_room=&elevated;
    rooms[0].people=&viewer; hidden=&invisible;
    race_names_table[RACE_HUMAN].normal="Human";
    race_names_table[RACE_GREY].normal="Grey Elf";
    race_names_table[RACE_ORC].normal="Orc";
    char selector[128];
    assert(get_char_room_vis(&viewer,"Enemy")==nullptr); // actual names don't bypass racewar
    assert(get_char_room_target(&viewer,&enemy,selector,sizeof(selector)));
    assert(!strcmp(selector,"3.Human") && get_char_room_vis(&viewer,selector)==&enemy);
    assert(get_char_room_target(&viewer,&second,selector,sizeof(selector)));
    assert(!strcmp(selector,"4.Human") && get_char_room_vis(&viewer,selector)==&second);
    assert(get_char_room_target(&viewer,&ally,selector,sizeof(selector)));
    assert(!strcmp(selector,"1.Friend") && get_char_room_vis(&viewer,selector)==&ally);
    assert(!get_char_room_target(&viewer,&invisible,selector,sizeof(selector)));
    assert(!get_char_room_target(&viewer,&elevated,selector,sizeof(selector)));
    viewer.next_in_room=&ally; // removal changes ordinals; never reuse an earlier room selector
    assert(get_char_room_target(&viewer,&second,selector,sizeof(selector)));
    assert(!strcmp(selector,"3.Human") && get_char_room_vis(&viewer,selector)==&second);
    introduced=&second;
    assert(!get_char_room_target(&viewer,&second,selector,sizeof(selector)));
    introduced=nullptr;
    enemy.disguise.active_npc=true; enemy.disguise.race=RACE_ORC;
    enemy.disguise.title=const_cast<char *>("masked traveller");
    assert(get_char_room_target(&viewer,&enemy,selector,sizeof(selector)));
    assert(!strcmp(selector,"1.Orc") && get_char_room_vis(&viewer,selector)==&enemy);
    enemy.in_room=1;
    assert(!get_char_room_target(&viewer,&enemy,selector,sizeof(selector)));
    assert(!get_char_room_target(&viewer,&ally,selector,2));
    puts("native room selectors: racewar, same-side names, NPC/PC ordinal collisions, movement, visibility, height and disguise passed");
}
'''
native = "\n".join(extract_function("handler.c", signature) for signature in
                    ("static bool room_target_matches(", "bool get_char_room_target(", "P_char get_char_room_vis("))
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="room-selectors-", dir=ROOT / "bin/tests") as directory:
    path, binary = Path(directory) / "test.cpp", Path(directory) / "test"
    path.write_text(harness.replace("// PRODUCTION", native))
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                    "-Isrc", str(path), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
