#!/usr/bin/env python3
"""Execute native staff mutations and the late SQL reload callback around a trade."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

harness = r'''#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <functional>
#include <vector>
#define NUM_PORTS 2
#define CARGO_MODS_QUERY "fixture"
struct character {};
using P_char=character *;
using sql_row=std::array<const char *,4>;
using sql_rows=std::vector<sql_row>;
bool busy=false;
uint64_t trade_generation=7;
int writes=0,reads=0,updates=0,shown=0,applied=0;
float ship_cargo_market_mod[2][2]={{2,2},{2,2}};
float ship_contra_market_mod[2][2]={{2,2},{2,2}};
float ship_cargo_market_mod_delayed[2][2]={{2,2},{2,2}};
bool divine_trade_runtime_busy() { return busy; }
bool is_abbrev(const char *a,const char *b) {return !strncmp(a,b,strlen(a));}
void send_to_char(const char *,P_char) {}
void show_cargo_prices(P_char) {++shown;}
void show_contra_prices(P_char) {++shown;}
int read_cargo() {++reads;return true;}
int write_cargo() {++writes;return true;}
void update_cargo(bool) {++updates;}
std::function<void(P_char,const sql_rows&)> callback;
bool sql_read_for(P_char,const char *,std::function<void(P_char,const sql_rows&)> next) {
 ++reads;callback=std::move(next);return true;
}
void apply_cargo_mod(const char *,const char *,const char *,const char *) {++applied;}
// REAL_FUNCTIONS
int main() {
 character actor;
 busy=true;
 reset_cargo();
 assert(ship_cargo_market_mod[0][0]==2);
 for(const char *name : {"reload","reset","save","update"}) {
  char command[32];strcpy(command,name);do_world_cargo(&actor,command);
 }
 assert(!writes && !reads && !updates && ship_cargo_market_mod[0][0]==2);
 char display[]="";do_world_cargo(&actor,display);assert(shown==2);
 busy=false;reset_cargo();assert(ship_cargo_market_mod[0][0]==1);
 char reload[]="reload";do_world_cargo(&actor,reload);assert(reads==1);
#ifndef __NO_MYSQL__
 const sql_rows rows={sql_row{"CARGO","0","0","3"}};
 busy=true;callback(&actor,rows);assert(!applied);
 busy=false;++trade_generation;callback(&actor,rows);assert(!applied);
 --trade_generation;callback(&actor,rows);assert(applied==1);
#endif
}
'''
functions = extract_function("ships/ship_cargo.c", "void reset_cargo()") + "\n" + extract_function("ships/ship_cargo.c", "void do_world_cargo(")
out=ROOT/"bin/tests";out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix="cargo-staff-barrier-",dir=out) as temporary:
    source=Path(temporary)/"staff.cpp";source.write_text(harness.replace("// REAL_FUNCTIONS",functions))
    for mode in ("mariadb","flatfile"):
        binary=Path(temporary)/mode
        subprocess.run(["g++","-std=c++20","-Wall","-Wextra","-Werror","-fsanitize=address,undefined","-fno-pie","-no-pie",*(["-D__NO_MYSQL__"] if mode=="flatfile" else []),str(source),"-o",str(binary)],check=True,cwd=ROOT)
        subprocess.run([str(binary)],check=True,cwd=ROOT)
print("PASS staff cargo reset/save/update/reload barriers and stale SQL callback")
