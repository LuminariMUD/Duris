#!/usr/bin/env python3
"""Execute the actual bag workflow and locker sorting bodies with controlled endpoints."""
from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, extract_function


HARNESS = r'''
#include "core/config.h"
#include "core/defines.h"
#include "world/vnum.obj.h"
#include <algorithm>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <new>
#include <set>
#include <string>
#include <utility>
#include <vector>
#define REMOVE_BIT(value,bit) ((value)&=~(bit))
#define GET_NAME(ch) ((ch)->player.name)
#ifndef LOG_DEBUG
#define LOG_DEBUG "debug"
#endif
struct object_data {
    int score=0, R_num=0, type=ITEM_WORN;
    unsigned wear_flags=ITEM_TAKE, extra_flags=0;
    const char *name="fixture", *short_description="a fixture";
    object_data *contains=nullptr,*next_content=nullptr;
    bool carried=true,extracted=false;
};
using P_obj=object_data *;
using object_template=object_data;
struct character { struct { int level=60; const char *name="Tester"; } player; int in_room=NOWHERE; };
using P_char=character *;
struct { int number=1; } world[1];
struct index { int virtual_number; } obj_index[8];
int top_of_objt=7;
static object_template prototypes[8];
static object_data grant;
static bool refuse_read,refuse_delivery;
static P_obj delivered;
static int choice,rolls,loads,valuations,removals;
static std::string output;
int itemvalue(P_obj object) { ++valuations; return object->score; }
int itemvalue(const object_template &object) { ++valuations; return object.score; }
const object_template *find_object_template(int vnum) {
    for(int slot=0;slot<=top_of_objt;++slot) if(obj_index[slot].virtual_number==vnum) return &prototypes[slot];
    return nullptr;
}
object_data inspect_object_template(const object_template &object) { return object; }
bool isname(const char *part,const char *name) { return !strcmp(part,name); }
int number(int low,int high) { ++rolls; assert(choice>=low && choice<=high); return choice; }
P_obj read_object(int vnum,int) { ++loads; if(refuse_read)return nullptr; grant=*find_object_template(vnum); return &grant; }
void send_to_char(const char *text,P_char) { output+=text; }
void act(const char *,int,P_char,P_obj,void *,int) {}
void statuslog(int,const char *,...) {}
void logit(const char *,const char *,...) {}
void set_obj_extra_flags(P_obj object,unsigned flags) { object->extra_flags=flags; }
bool obj_to_char(P_obj object,P_char) { if(refuse_delivery){object->extracted=true;return false;} delivered=object; return true; }
void obj_from_char(P_obj object) { object->carried=false; ++removals; }
void extract_obj(P_obj object,int) { object->extracted=true; }
struct LockerChest { P_obj m_pChestObject; LockerChest *m_pNextInChain=nullptr; };
struct StorageLocker { bool m_bIValue=true; LockerChest *m_pChestList=nullptr; void SortIValues(); };
// PRODUCTION
static void reset_bag() {
    const int scores[]={0,24,25,49,50,125,126,90};
    for(int i=0;i<8;++i) { prototypes[i]={}; prototypes[i].score=scores[i]; prototypes[i].R_num=i; obj_index[i].virtual_number=1300+i; }
    obj_index[7].virtual_number=140000; choice=rolls=loads=valuations=removals=0;
    refuse_read=refuse_delivery=false; delivered=nullptr; output.clear();
}
static void bag_cases() {
    reset_bag();
    for(int rank=0;rank<5;++rank) { choice=rank; assert(faerie_reward_vnum(REG_FAERIE_BAG_VNUM)==1301+rank); }
    assert(rolls==5 && loads==0);
    for(int rank=0;rank<5;++rank) { choice=rank; assert(faerie_reward_vnum(RARE_FAERIE_BAG_VNUM)==1302+rank); }
    for(int rank=0;rank<3;++rank) { choice=rank; assert(faerie_reward_vnum(EXCEPT_FAERIE_BAG_VNUM)==1304+rank); }
    for(auto &prototype:prototypes) prototype.extra_flags=ITEM_NORENT;
    rolls=0; assert(!faerie_reward_vnum(REG_FAERIE_BAG_VNUM) && !rolls && !loads);
    reset_bag(); prototypes[1].type=ITEM_KEY; prototypes[2].wear_flags=0;
    prototypes[3].name="_noquest_"; prototypes[4].extra_flags=ITEM_ARTIFACT;
    assert(faerie_reward_vnum(REG_FAERIE_BAG_VNUM)==1305);
    character actor;
    for(int failure:{0,1,2}) {
        reset_bag(); object_data bag; bag.R_num=7;
        if(failure==0) for(auto &prototype:prototypes) prototype.score=0;
        refuse_read=failure==1; refuse_delivery=failure==2;
        open_reward(&actor,&bag,REG_FAERIE_BAG_VNUM);
        assert(bag.carried && !bag.extracted && !removals && !delivered && !output.empty());
        assert(loads==(failure ? 1 : 0));
    }
    reset_bag(); object_data bag; bag.R_num=7;
    open_reward(&actor,&bag,REG_FAERIE_BAG_VNUM);
    assert(!bag.carried && bag.extracted && removals==1 && loads==1 && delivered && delivered->score==24);
    std::puts("bag: uniform eligible-vnum ranks, 25/50/125 edges, empty catalog and read/delivery failures preserve source");
}
static void sort_cases() {
    object_data chest,other_chest;
    object_data a,b,c,d,e; a.score=20;b.score=10;c.score=20;d.score=10;e.score=5;
    chest.contains=&a;a.next_content=&b;b.next_content=&c;c.next_content=&d;
    other_chest.contains=&e;
    LockerChest second{&other_chest},first{&chest,&second}; StorageLocker locker;locker.m_pChestList=&first;
    valuations=0; locker.SortIValues();
    assert(valuations==5 && !locker.m_bIValue && chest.contains==&d && d.next_content==&b && b.next_content==&c && c.next_content==&a && !a.next_content);
    assert(other_chest.contains==&e && !e.next_content);
    chest.contains=nullptr;locker.m_bIValue=true;valuations=0;locker.SortIValues();assert(valuations==1 && !chest.contains);
    std::vector<object_data> many(10000);for(size_t i=0;i<many.size();++i){many[i].score=static_cast<int>(many.size()-i);many[i].next_content=i+1<many.size()?&many[i+1]:nullptr;}
    first.m_pNextInChain=nullptr;chest.contains=many.data();locker.m_bIValue=true;valuations=0;
    const auto start=std::chrono::steady_clock::now();locker.SortIValues();
    const auto elapsed=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-start).count();
    std::set<P_obj> seen;int last=-1;for(P_obj object=chest.contains;object;object=object->next_content){assert(object->score>=last && seen.insert(object).second);last=object->score;}
    assert(seen.size()==many.size() && valuations==10000);
    std::printf("locker: empty/single/tied/10000 objects, legacy tie order, chest boundaries; %d valuations in %lld us\n",valuations,(long long)elapsed);
}
int main(){bag_cases();sort_cases();}
'''


def main():
    names = {"REG_FAERIE_BAG_VNUM", "RARE_FAERIE_BAG_VNUM", "EXCEPT_FAERIE_BAG_VNUM",
             "TURKEY_INNARDS_VNUM", "TURKEY_WING_CAPE_VNUM", "TURKEY_FOOD_VNUM",
             "VIRTUAL", "TO_ROOM", "TO_CHAR"}
    macros = "\n".join(line for path in ("economy/tradeskill.h", "world/db.h", "net/comm.h")
                       for line in (ROOT / "src" / path).read_text().splitlines()
                       if line.startswith("#define ") and line.split()[1] in names)
    assert len(macros.splitlines()) == len(names)
    opener = extract_function("actmove.c", "void do_open(")
    start = opener.index("P_obj robj = nullptr;")
    end = opener.index("\n\t\tREMOVE_BIT(obj->value[1]", start)
    body = opener[start:end]
    body = body[:body.rfind("return;") + len("return;")]
    production = macros + "\n" + "\n".join((
        extract_function("actmove.c", "static bool faerie_reward_candidate("),
        extract_function("actmove.c", "static int faerie_reward_vnum("),
        "void open_reward(P_char ch,P_obj obj,int door) {\n" + body + "\n}",
        extract_function("storage_lockers.c", "void StorageLocker::SortIValues(")))
    with tempfile.TemporaryDirectory(prefix="ival-consumers-", dir=ROOT / "bin/tests") as directory:
        source, binary = Path(directory) / "test.cpp", Path(directory) / "test"
        source.write_text(HARNESS.replace("// PRODUCTION", production))
        subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-Isrc", "-fno-pie", "-no-pie",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                        str(source), "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True, env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1"})


if __name__ == "__main__":
    main()
