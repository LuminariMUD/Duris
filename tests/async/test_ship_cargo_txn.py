#!/usr/bin/env python3
"""Execute the real market capture and ordinary cargo-sale persistence paths."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

HARNESS = r'''#include <array>
#include <cassert>
#include <cerrno>
#include <climits>
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <functional>
#include <map>
#include <regex>
#include <string>
#include <tuple>
#include <vector>
#define TRUE 1
#define FALSE 0
#define NUM_PORTS 2
#define MAXSLOTS 16
#define SLOT_EMPTY 0
#define SLOT_CARGO 2
#define SLOT_CONTRABAND 3
#define INNATE_SEADOG 1
#define NEXUS_BONUS_CARGO 1
#define AIP_CARGOCOUNT 1
#define LOG_SHIP 1
#define SOLD_CARGO 1
#define SOLD_CONTRA 2
struct MYSQL {};
using sql_work = std::function<unsigned int(MYSQL *)>;
uint64_t trade_generation = 0, stored_generation = 0;
unsigned generation_reads = 0;
std::vector<sql_work> jobs;
std::vector<std::string> applied_sql;
float ship_cargo_market_mod[NUM_PORTS][NUM_PORTS] = {{1,1},{1,1}};
float ship_contra_market_mod[NUM_PORTS][NUM_PORTS] = {{2,2},{2,2}};
bool zero_quotes = false, overflow_quotes = false, sea_bonus = false;
int cargo_sell_price(int port) { return zero_quotes ? 0 : 100+port*10; }
int cargo_buy_price(int port,int type) { return overflow_quotes ? INT_MAX : zero_quotes ? 0 : 100+port*10+type; }
int contra_sell_price(int port) { return zero_quotes ? 0 : 200+port*10; }
int contra_buy_price(int port,int type) { return overflow_quotes ? INT_MAX : zero_quotes ? 0 : 200+port*10+type; }
std::string sql_format(const char *format, ...) {
 char text[512]; va_list args; va_start(args,format);
 vsnprintf(text,sizeof(text),format,args);va_end(args);return text;
}
bool sql_queue_work(sql_work work) {jobs.push_back(std::move(work));return true;}
bool divine_trade_sql_generation(MYSQL *,uint64_t *value,bool) {++generation_reads;*value=stored_generation;return true;}
unsigned mysql_errno(MYSQL *) {return 0;}
int mysql_real_query(MYSQL *,const char *sql,size_t size) {applied_sql.emplace_back(sql,size);return 0;}
struct ShipSlot {
 char desc[32]{},status[32]{};
 int type=0,index=-1,position=-1,timer=0,val0=-1,val1=-1,val2=-1,val3=-1,val4=-1;
 void clear();
};
struct crew {
 int raises=0;
 void sail_skill_raise(float) {++raises;}
 void rpar_skill_raise(float) {++raises;}
};
struct character {int in_room=0,money=0;};
struct ship {int location=0; ShipSlot slot[MAXSLOTS]; struct crew crew; bool save_pending=false;};
using P_char=character *; using P_ship=ship *;
struct room {int number=7;} world[1];
struct port {int loc_room=7; const char *loc_name="Port";} ports[NUM_PORTS];
struct affected_type {int modifier=0;} achievement;
char buf[4096];
#define GET_NAME(ch) "Trader"
#define IS_WARSHIP(ship) false
#define ADD_MONEY(ch,amount) ((ch)->money+=(amount))
bool has_eq_diplomat(P_ship) {return false;}
bool has_innate(P_char,int) {return sea_bonus;}
void send_to_char(const char *,P_char) {}
void send_to_char_f(P_char,const char *,...) {}
void statuslog(int,const char *,...) {}
void logit(int,const char *,...) {}
const char *cargo_type_name(int) {return "cargo";}
const char *contra_type_name(int) {return "contraband";}
const char *coin_stringv(int) {return "coins";}
std::string strip_ansi(const char *text) {return text;}
void adjust_ship_market(int,int,int,int) {}
affected_type *get_spell_from_char(P_char,int) {return &achievement;}
affected_type *apply_achievement(P_char,int) {return &achievement;}
double nexus_multiplier=1;
bool check_nexus_bonus_preview(P_char,int value,int,int *result) {
 const double total=value*nexus_multiplier;
 if(!std::isfinite(total) || total>INT_MAX)return false;
 *result=total;return true;
}
int check_nexus_bonus(P_char,int value,int) {assert(value*nexus_multiplier<=INT_MAX);return value*nexus_multiplier;}
void update_crew(P_ship) {}
void update_ship_status(P_ship) {}
void queue_ship_save(P_ship value,const char *) {value->save_pending=true;}
// REAL_FUNCTIONS
int main() {
 MYSQL db;
 assert(write_cargo() && jobs.size()==1 && applied_sql.empty() && generation_reads==0);
 assert(jobs[0](&db)==0 && applied_sql.size()==6 && generation_reads==1);
 std::map<std::tuple<std::string,int,int>,int> prices;
 const std::regex row("\\('(CARGO|CONTRABAND)',[ ]*([0-9]+),[ ]*([0-9]+),[ ]*([0-9]+)\\)");
 for (size_t statement=2;statement<4;++statement)
  for (auto i=std::sregex_iterator(applied_sql[statement].begin(),applied_sql[statement].end(),row);i!=std::sregex_iterator();++i)
   prices[{(*i)[1],std::stoi((*i)[2]),std::stoi((*i)[3])}]=std::stoi((*i)[4]);
 assert(prices.size()==8);
 assert((prices[{"CARGO",0,1}]==101 && prices[{"CONTRABAND",0,1}]==201));
 assert((prices[{"CARGO",1,1}]==110 && prices[{"CONTRABAND",1,1}]==210));
 applied_sql.clear();stored_generation=1;
 assert(jobs[0](&db)==0 && applied_sql.empty());
 for (int goods : {SLOT_CARGO,SLOT_CONTRABAND})
  for (bool zero : {false,true})
   for (bool all : {false,true}) {
    character ch; ship boat; achievement.modifier=0;zero_quotes=zero;
    boat.slot[0].type=goods;boat.slot[0].index=1;boat.slot[0].val0=10;boat.slot[0].val1=1000;
    if (goods==SLOT_CARGO) sell_cargo(&ch,&boat,all ? -1 : 0);
    else sell_contra(&ch,&boat,all ? -1 : 0);
    assert(boat.slot[0].type==SLOT_EMPTY && boat.save_pending);
    assert(ch.money==(zero ? 0 : goods==SLOT_CARGO ? 1010 : 2010));
    assert(boat.crew.raises==(zero ? 0 : 2));
    assert(achievement.modifier==(goods==SLOT_CARGO ? 10 : 0));
   }
 // Batch overflow must retain the unpayable slot and pay the accepted slot.
 for(int goods : {SLOT_CARGO,SLOT_CONTRABAND}) {
  character trader;ship boat;zero_quotes=false;overflow_quotes=true;
  achievement.modifier=INT_MAX;
  for(int i=0;i<2;++i) {
   boat.slot[i].type=goods;boat.slot[i].index=0;
   boat.slot[i].val0=1;boat.slot[i].val1=1;
  }
  if(goods==SLOT_CARGO)sell_cargo(&trader,&boat,-1);
  else sell_contra(&trader,&boat,-1);
  assert(trader.money==INT_MAX && boat.slot[0].type==SLOT_EMPTY &&
         boat.slot[1].type==goods && boat.slot[1].val0==1 && boat.save_pending);
  assert(achievement.modifier==INT_MAX);
  // Include the Nexus premium in refusal, before any slot is consumed.
  character boosted;ship unpayable;nexus_multiplier=1.1;
  unpayable.slot[0].type=goods;unpayable.slot[0].index=0;
  unpayable.slot[0].val0=1;unpayable.slot[0].val1=1;
  if(goods==SLOT_CARGO)sell_cargo(&boosted,&unpayable,-1);
  else sell_contra(&boosted,&unpayable,-1);
  assert(!boosted.money && unpayable.slot[0].type==goods && !unpayable.save_pending);
  nexus_multiplier=1;overflow_quotes=false;
 }
 character ch;ship empty;
 sell_cargo(&ch,&empty,-1);sell_contra(&ch,&empty,-1);
 assert(!empty.save_pending && !ch.money);
 // Invalid indices and corrupt ship slots must be refused before pricing,
 // clearing a slot, changing the market or queueing persistence.
 for (int goods : {SLOT_CARGO,SLOT_CONTRABAND}) {
  character trader;ship invalid;
  invalid.slot[0].type=goods;invalid.slot[0].index=0;invalid.slot[0].val0=10;
  const auto sell=[&](int slot,int port) {
   return goods==SLOT_CARGO ? sell_cargo_slot(&trader,&invalid,slot,port)
                            : sell_contra_slot(&trader,&invalid,slot,port);
  };
  auto refused=[&](int slot,int port) {
   const auto pending=jobs.size();
   assert(sell(slot,port)==0 && invalid.slot[0].type==goods);
   assert(!invalid.save_pending && !trader.money && jobs.size()==pending);
  };
  refused(-1,0);refused(MAXSLOTS,0);
  refused(0,-1);refused(0,NUM_PORTS);
  invalid.slot[0].index=-1;refused(0,0);
  invalid.slot[0].index=NUM_PORTS;refused(0,0);
  invalid.slot[0].index=0;invalid.slot[0].val0=-10;refused(0,0);
  invalid.slot[0].val0=10;
  invalid.slot[0].type=goods==SLOT_CARGO ? SLOT_CONTRABAND : SLOT_CARGO;
  assert(sell(0,0)==0 && !invalid.save_pending);
  invalid.slot[0].type=goods;invalid.slot[0].val0=2;
  overflow_quotes=true;refused(0,0);overflow_quotes=false;
  if (goods==SLOT_CARGO) {
   // The base multiplication fits, but the seafarer bonus would not.
   invalid.slot[0].val0=1;overflow_quotes=true;sea_bonus=true;
   refused(0,0);sea_bonus=false;overflow_quotes=false;
  }
  // A representable payout can still imply an enormous displayed profit.
  // Sanitizers must not see a float-to-int conversion outside its range.
  character extreme_trader;ship extreme;
  extreme.slot[0].type=goods;extreme.slot[0].index=0;
  extreme.slot[0].val0=1;extreme.slot[0].val1=1;
  overflow_quotes=true;
  const int extreme_paid=goods==SLOT_CARGO ?
   sell_cargo_slot(&extreme_trader,&extreme,0,0) :
   sell_contra_slot(&extreme_trader,&extreme,0,0);
  overflow_quotes=false;
  assert(extreme_paid==INT_MAX && extreme.slot[0].type==SLOT_EMPTY &&
         extreme.save_pending);
  // A genuine zero-crate slot can still be cleared and persisted.
  invalid.slot[0].type=goods;invalid.slot[0].val0=0;
  assert(sell(0,0)==0 && invalid.slot[0].type==SLOT_EMPTY && invalid.save_pending);
 }
 puts("PASS: distinct market quotes, stale capture, paid/zero/empty and invalid sales");
}
'''
functions = "\n".join(extract_function(path, signature) for path, signature in (
    ("ships/ship_cargo.c", "int write_cargo()"),
    ("ships/ship_utils.c", "void ShipSlot::clear()"),
    ("ships/ship_shop.c", "int sell_cargo_slot("),
    ("ships/ship_shop.c", "int sell_cargo("),
    ("ships/ship_shop.c", "int sell_contra_slot("),
    ("ships/ship_shop.c", "int sell_contra("),
))
output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="cargo-producers-", dir=output) as directory:
    source = Path(directory) / "cargo.cpp"
    source.write_text(HARNESS.replace("// REAL_FUNCTIONS", functions))
    binary = str(Path(directory) / "cargo")
    subprocess.run(["g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined,float-cast-overflow", "-fno-omit-frame-pointer",
                    "-fno-pie", "-no-pie", str(source), "-o", binary], cwd=ROOT, check=True)
    subprocess.run([binary], cwd=ROOT, check=True)

# Preserve the existing staff reload boundary: its result returns on the writer.
source_text = (ROOT / "src/ships/ship_cargo.c").read_text()
command = source_text[source_text.index("void do_world_cargo("):]
reload_path = command[command.index('is_abbrev(arg, "reload")'):command.index('is_abbrev(arg, "reset")')]
assert "sql_read_for(ch, CARGO_MODS_QUERY" in reload_path
