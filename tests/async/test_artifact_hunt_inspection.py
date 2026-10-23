#!/usr/bin/env python3
"""Actual artifact hunt report must not construct or reconcile physical items."""
from pathlib import Path
import os
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function

report = extract_function("artifact.c", "static auto artifact_row_for_uid(") + "\n" + extract_function("artifact.c", "static void arti_hunt_owner(")
source = r"""
#include "core/prototypes.h"
#include "core/utils.h"
#include "player/player_load_repository.h"
#include "guild/artifact_identity.h"
#include "persistence/dupe_log.h"
#include <cassert>
#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <map>
#include <string>
#include <vector>
static size_t mutations=0, constructions=0;
static std::string output, logged;
static obj_data live_copy={};
struct inspected_artifact { uint64_t canonical_item_uid=0; artifact_identity_state identity_state=artifact_identity_state::unresolved; std::vector<uint64_t> rejected_item_uids={}; };
std::map<int,inspected_artifact> artifact_rows;
index_data indexes[1]={}; P_index obj_index=indexes;
room_data rooms[1]={}; P_room world=rooms;
void send_to_char(const char *text,P_char) { output+=text; }
void send_to_char_f(P_char,const char *format,...) {
 char text[8192]; va_list args; va_start(args,format); std::vsnprintf(text,sizeof(text),format,args); va_end(args); output+=text;
}
void logit(const char *,const char *format,...) {
 char text[8192]; va_list args; va_start(args,format); std::vsnprintf(text,sizeof(text),format,args); va_end(args); logged+=text; logged+='\n';
}
P_obj artifact_find(int) { return &live_copy; }
void artifact_update_sql(P_obj,char,time_t) { ++mutations; }
void artifact_update_location_sql(P_obj) { ++mutations; }
void extract_obj(P_obj object,int) { if(object==&live_copy) ++mutations; }
void extract_char(P_char) { ++constructions; }
P_char read_mobile(int,int) { ++constructions; return nullptr; }
int real_room0(int) { return 0; }
// OWNER_LABEL
// REPORT
int main() {
 char_data staff={};
 indexes[0].virtual_number=900; rooms[0].name=const_cast<char *>("Fixture ground");
 live_copy.R_num=0; live_copy.obj_uid=70000; live_copy.extra_flags=ITEM_ARTIFACT;

 artifact_rows[900]={70000,artifact_identity_state::present};
 artifact_rows[902]={70002,artifact_identity_state::retired};
 // CALL
 assert(mutations==0 && "artifact hunt changed live artifacts while inspecting");
 assert(constructions==0 && "artifact hunt constructed or freed gameplay objects");
 assert(artifact_rows.at(900).canonical_item_uid==70000 && artifact_rows.at(900).identity_state==artifact_identity_state::present);
}
""".replace("// REPORT", report)
source = source.replace("// CALL", r"""
 player_load_result cut={}; cut.pid=77; cut.outcome=player_load_outcome::applied;
 auto raw=[&](uint64_t row,int vnum,uint64_t uid,uint64_t parent,uint64_t quantity,bool flags_present,uint32_t flags) {
  player_load_source_item item; item.row_id=row; item.vnum=vnum; item.item_uid=uid;
  item.parent_row_id=parent; item.quantity=quantity; item.quantity_present=true; item.extra_flags_present=flags_present; item.extra_flags=flags;
  cut.item_sources.push_back(item);
 };
 raw(1,900,0,0,7,true,ITEM_ARTIFACT);
 raw(2,902,70002,1,1,true,ITEM_ARTIFACT);
 raw(3,900,70000,0,1,true,ITEM_ARTIFACT);
 raw(4,900,70003,0,1,true,0);
 raw(5,900,70004,0,1,false,0);
 raw(6,903,70005,0,1,true,0);
 cut.item_sources[2].custody_found=cut.item_sources[2].custody_owner_revision_found=true;
 cut.item_sources[2].custody={70000,70000,0,{item_owner_type::room,2300,0},2,3,900,item_custody_state::active};
 arti_hunt_owner(&staff,"Offline",cut);
 assert(output.find("read-only")!=std::string::npos && output.find("vnum=900 uid=0 row=1")!=std::string::npos);
 assert(output.find("quantity=7")!=std::string::npos && output.find("vnum=902 uid=70002 row=2 parent_row=1")!=std::string::npos);
 assert(output.find("state=retired")!=std::string::npos && output.find("canonical_uid=70000 state=present")!=std::string::npos);
 assert(output.find("flags=ordinary")!=std::string::npos && output.find("flags=missing")!=std::string::npos);
 assert(output.find("owner=2300")!=std::string::npos && output.find("row=6")==std::string::npos);
 assert(output.find("audit complete")!=std::string::npos);
 output.clear(); logged.clear();
 for(int index=0;index<20;++index) raw(10+index,900,80000+index,0,1,true,ITEM_ARTIFACT);
 arti_hunt_owner(&staff,"Offline",cut);
 assert(output.find("candidates=25 displayed=16")!=std::string::npos);
 assert(output.find("row=29")==std::string::npos && logged.find("row=29")!=std::string::npos);
 output.clear(); logged.clear();
 cut.item_sources.clear(); raw(100,903,123456,0,1,true,0);
 arti_hunt_owner(&staff,"Clean",cut);
 assert(output.empty() && logged.empty());
 cut.item_sources[0].custody_found=true;
 cut.item_sources[0].custody={123456,123456,0,{item_owner_type::player,88,0},1,0,900,item_custody_state::active};
 cut.item_sources[0].quantity_present=false;
 arti_hunt_owner(&staff,"CustodyOnly",cut);
 assert(output.find("vnum=903 uid=123456")!=std::string::npos && output.find("custody_vnum=900")!=std::string::npos);
 assert(output.find("quantity=missing")!=std::string::npos && output.find("owner_revision=unavailable")!=std::string::npos);
 output.clear(); logged.clear();
 cut.item_sources[0].quantity=0; cut.item_sources[0].quantity_present=true;
 cut.item_sources[0].custody_owner_revision_found=true;
 arti_hunt_owner(&staff,"Zero",cut);
 assert(output.find("quantity=0")!=std::string::npos && output.find("owner_revision=0")!=std::string::npos);
 output.clear(); logged.clear();
 cut.item_sources[0].custody_found=false; cut.item_sources[0].item_uid=70000;
 arti_hunt_owner(&staff,"CanonicalUID",cut);
 assert(output.find("canonical_uid=70000")!=std::string::npos);
 output.clear(); artifact_rows[900].rejected_item_uids={70001};
 cut.item_sources[0].item_uid=70001;
 arti_hunt_owner(&staff,"RejectedUID",cut);
 assert(output.find("canonical_uid=70000")!=std::string::npos);
 assert(artifact_rows.at(900).rejected_item_uids==std::vector<uint64_t>{70001});
 output.clear(); cut.outcome=player_load_outcome::timed_out;
 arti_hunt_owner(&staff,"Offline",cut);
 assert(output.find("source unavailable")!=std::string::npos && output.find("audit complete")==std::string::npos);
 """)

source = source.replace("// OWNER_LABEL", extract_function("dupe_log.c", "const char *item_owner_type_label("))

with tempfile.TemporaryDirectory(prefix="duris-artifact-hunt-") as temporary:
    cpp=Path(temporary)/"test.cpp"; binary=Path(temporary)/"test"; cpp.write_text(source)
    subprocess.run(["g++","-std=c++20","-Wall","-Wextra","-Werror","-D__NO_MYSQL__","-Isrc",
                    "-ffunction-sections","-fdata-sections","-fsanitize=address,undefined",
                    "-fno-sanitize-recover=all","-fno-pie","-no-pie",str(cpp),str(HARNESS_STUBS),
                    "-Wl,--gc-sections","-o",str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],cwd=ROOT,check=True,timeout=20,env={**os.environ,"ASAN_OPTIONS":"detect_leaks=1"})
print("native artifact source hunt preserves physical objects and canonical state")
