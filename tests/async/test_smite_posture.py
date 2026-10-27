#!/usr/bin/env python3
"""Automatic smite honors posture and keeps its periodic check armed."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

HARNESS = r'''
#include <cassert>
#include <cstdio>
struct Character { bool awake=true, immobile=false, sword=true, evil=false, alive=true;
    int hp=100, maxhp=100, racewar=1, in_room=0; Character *next_in_room=nullptr; };
using P_char=Character *;
using P_obj=void *;
struct Room { P_char people; } world[1];
using event_func=void(*)(P_char,P_char,P_obj,void *);
#define IS_AWAKE(c) ((c)->awake)
#define IS_IMMOBILE(c) ((c)->immobile)
#define IS_ALIVE(c) ((c)->alive)
#define IS_EVIL(c) ((c)->evil)
#define GET_HIT(c) ((c)->hp)
#define GET_MAX_HIT(c) ((c)->maxhp)
#define GET_RACEWAR(c) ((c)->racewar)
#define GET_CHAR_SKILL(c,s) 100
constexpr int SKILL_SMITE_EVIL=1, WAIT_SEC=4, TO_NOTVICT=2, TO_CHAR=3, TO_VICT=1, FALSE=0;
int attacks=0, scheduled=0;
bool is_wielding_paladin_sword(P_char ch) { return ch->sword; }
bool grouped(P_char a,P_char b) { return a==b; }
bool notch_skill(P_char,int,int) { return false; }
int number(int low,int) { return low; }
int get_property(const char *,int fallback) { return fallback; }
void act(const char *,int,P_char,P_obj,P_char,int) {}
void damage(P_char,P_char,int,int) { ++attacks; }
void add_event(event_func,int,P_char,P_char,P_obj,int,void *,int) { ++scheduled; }
// PRODUCTION
int main() {
    Character actor, enemy; enemy.evil=true; enemy.racewar=2; enemy.hp=5; world[0].people=&enemy;
    actor.awake=false; event_smite_evil(&actor,nullptr,nullptr,nullptr); assert(!attacks && scheduled==1);
    actor.awake=true; actor.immobile=true;
    event_smite_evil(&actor,nullptr,nullptr,nullptr); assert(!attacks && scheduled==2);
    actor.immobile=false;
    event_smite_evil(&actor,nullptr,nullptr,nullptr); assert(attacks==1 && scheduled==3);
    actor.sword=false;
    event_smite_evil(&actor,nullptr,nullptr,nullptr); assert(attacks==1 && scheduled==4);
    puts("automatic smite: asleep/immobile actors cannot attack; waking resumes the armed check");
}
'''
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="smite-posture-", dir=ROOT / "bin/tests") as directory:
    source, binary = Path(directory) / "test.cpp", Path(directory) / "test"
    source.write_text(HARNESS.replace("// PRODUCTION", extract_function("paladins.c", "void event_smite_evil(")))
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g", "-fsanitize=address,undefined",
                    str(source), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
