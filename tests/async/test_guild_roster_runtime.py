#!/usr/bin/env python3
"""Guild rosters defer SQL, validate saved indexes, and recheck membership."""
import os
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, source

code = source("assocs.c").read_text()
start = code.index("namespace\n{\n// What the roster shows")
helpers = code[start:code.index("} // namespace", start) + len("} // namespace")]
fixture = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "guild/assocs.h"
#include "guild/alliances.h"
#include "kingdom/kingdom.h"
#include "classes/specializations.h"
#include "sql/sql.h"
#include "sql/sql_async.h"
#include "core/safe_format.h"
#include <cassert>
#include <cstdarg>
#include <map>
#include <string>
extern const mcname multiclass_names[];
extern const race_names race_names_table[];
extern const class_names class_names_table[];
extern const char *specdata[][MAX_SPEC];
P_char character_list = nullptr;
MYSQL *DB = nullptr;
static guild_member offline{};
static Guild *current;
static std::string sent;
static int direct_queries;
static std::function<void(P_char, const sql_rows &)> pending;
Guild::Guild() {
 id_number=77; bits=0; member_count=1;
 prestige=construction=platinum=gold=silver=copper=0; frags={};
 strcpy(name,"Fixture"); strcpy(offline.name,"Offline"); offline.bits=A_NORMAL;
 members=&offline;
 for(int i=0;i<ASC_NUM_RANKS;++i) strcpy(titles[i],"Member");
}
Guild::~Guild() {}
P_Alliance Guild::get_alliance() { return nullptr; }
unsigned int Guild::get_max_members() { return 20; }
void Guild::update_online_members() {}
P_Guild get_guild_from_id(int) { return current; }
int get_real_race(P_char ch) { return ch->player.race; }
void send_to_char(const char *text, P_char) { sent+=text; }
std::string pad_ansi(const char *text,int,bool) { return text ? text : ""; }
std::string strip_ansi(const char *text) { return text ? text : ""; }
char *coin_stringv(int,int) { return const_cast<char *>(""); }
bool kingdom_guild_society_lines(int,char *,size_t) { return false; }
bool qry_at(persistence_query_site,const char *,...) { ++direct_queries; return false; }
std::string sql_format(const char *format,...) {
 char buffer[1024]; va_list args; va_start(args,format);
 vsnprintf(buffer,sizeof(buffer),format,args); va_end(args); return buffer;
}
bool sql_read_for_at(persistence_query_site,P_char,std::string query,
                    std::function<void(P_char,const sql_rows &)> done) {
 assert(query.find("FROM player_data")!=std::string::npos);
 pending=std::move(done); return true;
}
// FUNCTIONS
int main(int argc,char **) {
 if(argc>1) {
  roster_entry entry{}; entry.m_class=CLASS_WARRIOR; entry.spec=999;
  assert(std::string(roster_class(entry,true)).find("Warrior")!=std::string::npos);
  entry.m_class=1U<<30;
  assert(std::string(roster_class(entry,true))=="Unknown Class");
  return 0;
 }
 Guild guild; current=&guild;
 pc_only_data pc{}; char_data viewer{}; viewer.only.pc=&pc;
 viewer.player.name=const_cast<char *>("Viewer"); viewer.player.level=56;
 GET_ASSOC(&viewer)=&guild; GET_A_BITS(&viewer)=A_NORMAL;
 SET_MEMBER(GET_A_BITS(&viewer));
 guild.display(&viewer);
 assert(direct_queries==0 && pending && sent.empty());
 sql_rows rows={sql_row{{"Offline","30","1","0","999","999","0","0"}}};
 auto complete=std::move(pending); complete(&viewer,rows);
 assert(sent.find("Offline")!=std::string::npos && sent.find("Warrior")!=std::string::npos);
 sent.clear(); guild.display(&viewer); complete=std::move(pending);
 GET_ASSOC(&viewer)=nullptr; complete(&viewer,rows); assert(sent.empty());
 GET_ASSOC(&viewer)=&guild; guild.display(&viewer); complete=std::move(pending);
 current=nullptr; complete(&viewer,rows); assert(sent.empty());
 current=&guild; guild.display(&viewer); complete=std::move(pending);
 GET_A_BITS(&viewer)=0; complete(&viewer,rows); assert(sent.empty());
 puts("guild roster: deferred SQL, bounded saved indexes and stale-viewer checks passed");
}
'''
functions = "\n".join((extract_function("utility.c", "int flag2idx(int flag)"), helpers,
                        extract_function("assocs.c", "void Guild::display(P_char member)"),
                        extract_function("assocs.c", "void Guild::display_roster(")))
with tempfile.TemporaryDirectory(prefix="guild-roster-") as temp:
    test = Path(temp) / "roster.cpp"
    binary = test.with_suffix("")
    test.write_text(fixture.replace("// FUNCTIONS", functions))
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                    "-ffunction-sections", "-fdata-sections", "-Isrc", "-I/usr/include/mysql",
                    str(test), "src/core/common.c", "src/core/constant.c", "src/core/safe_format.c",
                    str(HARNESS_STUBS), "-Wl,--gc-sections", "-lmysqlclient", "-o", str(binary)],
                   cwd=ROOT, check=True)
    results = [subprocess.run([str(binary), *args], env=dict(os.environ,
               ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))
               for args in ([], ["bounds"])]
    assert all(result.returncode == 0 for result in results)
