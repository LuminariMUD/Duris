#!/usr/bin/env python3
# Execute the real bridge dispatcher while a cargo trade is pending.
from pathlib import Path
import re
import subprocess
import tempfile
from _paths import ROOT, extract_function

body = extract_function("ships/ship_control.c", "int ship_panel_proc(")
leaves = set(re.findall(r"return\s+(\w+)\(", body)) - {"claim_coffer"}
stubs = chr(10).join(f"#define {name}(...) forbidden_control()" for name in sorted(leaves))
harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "net/comm.h"
#include "ships/ships.h"
#include "economy/divine_trade_runtime.h"
#include <cassert>
#include <cstring>
#include <sstream>
#include <string>
static char arg1[MAX_INPUT_LENGTH], arg2[MAX_INPUT_LENGTH], arg3[MAX_INPUT_LENGTH], tmp_str[MAX_INPUT_LENGTH];
static bool trade_pending = true;
static int notices = 0, mob_orders = 0, coffer_claims = 0;
static std::string forwarded_order;
const ShipTypeData ship_type_data[MAXSHIPCLASS] = {};
ShipObjHash shipObjHash;
ShipObjHash::ShipObjHash() : sz(0) { for (auto &entry : table) entry = nullptr; }
bool ShipObjHash::add(P_ship ship) { table[0] = ship; sz = 1; return true; }
bool ShipObjHash::get_first(visitor &visit) { visit.curr = table[0]; return visit.curr != nullptr; }
bool ShipObjHash::get_next(visitor &) { return false; }
void ShipData::show(P_char) const { std::abort(); }
bool divine_trade_runtime_busy(const ShipData *) { return trade_pending; }
void send_to_char(const char *text, P_char) { if (strstr(text,"settling a cargo trade")) ++notices; }
void do_order(P_char, char *argument, int) { ++mob_orders; forwarded_order = argument; }
void half_chop(char *argument, char *first, char *rest) {
 char *space = strchr(argument,' ');
 if (!space) { strcpy(first,argument); *rest = 0; return; }
 const auto length = static_cast<size_t>(space-argument);
 memcpy(first,argument,length); first[length] = 0; strcpy(rest,space+1);
}
bool isname(const char *word, const char *list) {
 std::istringstream words(list); std::string entry;
 while (words >> entry) if (entry == word) return true;
 return false;
}
bool is_abbrev(const char *word, const char *full) { return *word && !strncmp(full,word,strlen(word)); }
[[noreturn]] static int forbidden_control() { std::abort(); }
static int take_coffer() { ++coffer_claims; return TRUE; }
#define claim_coffer(...) take_coffer()
#define get_char2(...) nullptr
#define num_people_in_ship(...) 0
#define send_to_char_f(...) ((void)0)
#define update_ship_status(...) ((void)0)
#undef IS_TRUSTED
#define IS_TRUSTED(ch) true
''' + stubs + chr(10) + body + r'''
int main() {
 ShipData ship{}; obj_data panel{}; char_data actor{};
 ship.panel=&panel; SET_BIT(ship.flags,LOADED); shipObjHash.add(&ship);
 actor.player.name=const_cast<char *>("Captain");
 char object[]="shield", mob[]="wolf stand", speed[]="speed 0", coins[]="coins";
 assert(ship_panel_proc(&panel,&actor,CMD_GET,object)==FALSE && notices==0);
 assert(ship_panel_proc(&panel,&actor,CMD_ORDER,mob)==TRUE && mob_orders==1 && forwarded_order=="wolf stand" && notices==0);
 assert(ship_panel_proc(&panel,&actor,CMD_ORDER,speed)==TRUE && notices==1);
 assert(ship_panel_proc(&panel,&actor,CMD_GET,coins)==TRUE && notices==2 && coffer_claims==0);
 trade_pending=false;
 assert(ship_panel_proc(&panel,&actor,CMD_GET,coins)==TRUE && coffer_claims==1);
}
'''
output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="ship-panel-trade-", dir=output) as temporary:
    source=Path(temporary) / "router.cpp"
    binary=Path(temporary) / "router"
    source.write_text(harness)
    subprocess.run(["g++","-std=c++20","-g","-Wall","-Wextra","-Werror",
                    "-fsanitize=address,undefined","-fno-pie","-no-pie","-Isrc","-I/usr/include/mysql",
                    str(source),"-o",str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],cwd=ROOT,check=True)
print("PASS: pending trades fence ship controls/coffer and preserve ordinary get/mob orders")
