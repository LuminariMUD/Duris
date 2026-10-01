#!/usr/bin/env python3
"""Run production corpse bulk gets: selection, coins, publication and the haul report.

The world and wallet are stubs, not a substitute for a server journey. Real
selection, pickup and reporting functions execute under ASan and UBSan.
"""
from pathlib import Path
import subprocess
import tempfile
from _paths import SRC, extract_function

source = (SRC / 'actobj.c').read_text()
def take(signature):
    return extract_function('actobj.c', signature)

prelude = r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdarg>
#include <cctype>
#include <cerrno>
#include <climits>
#include <string>
#include <unordered_map>
#include <vector>
#include <utility>
#define TRUE 1
#define FALSE 0
#define MAX_STRING_LENGTH 65536
#define TO_CHAR 1
#define TO_ROOM 2
#define USE_SPACE 0
#define CURRENCY_DENOMINATION_COUNT 4
#define ITEM_CORPSE 24
#define ITEM_MONEY 1
#define PC_CORPSE 1
#define CORPSE_FLAGS 1
#define CORPSE_PID 2
#define CORPSE_SAVEID 3
#define AVATAR 60
#define LOG_FILE 0
#define LOWEST_MAT_VNUM 1000
#define HIGHEST_MAT_VNUM 2000
#define ITEM2_ACCOUNT_BOUND 1
#define ITEM2_NOLOOT 2
#define GET_PID(ch) (assert(!(ch)->npc), (ch)->pid)
#define GET_ITEM_TYPE(obj) ((obj)->type)
#define IS_PC(ch) (!(ch)->npc)
#define IS_SET(a,b) ((a)&(b))
#define OBJ_ROOM(o) ((o)->location == 1)
#define OBJ_INSIDE(o) ((o)->location == 2)
#define OBJ_CARRIED_BY(o,ch) ((o)->location == 3 && (o)->carrier == (ch))
#define OBJ_WORN_BY(o,ch) false
#define OBJ_VNUM(obj) 0
#define CAN_SEE_OBJ(ch,obj) ((obj)->visible)
#define CAN_CARRY_N(ch) ((ch)->count_limit)
#define CAN_CARRY_W(ch) ((ch)->weight_limit)
#define IS_CARRYING_N(ch) 0
#define GET_OBJ_WEIGHT(obj) ((obj)->weight)
#define IS_OBJ_STAT2(obj,flag) ((obj)->flags & (flag))
#define IS_TRUSTED(ch) false
#define OBJS(obj,ch) ((obj)->short_description)
#define PERS(victim,ch,hide) "a horse"
#define J_NAME(ch) "tester"
#define CAP(text) ((text)[0] = toupper((text)[0]))
#define PLAYER_COMPONENT_STATUS 1
#define PLAYER_COMPONENT_INVENTORY 2
struct char_data { int pid=42; bool npc=false; int in_room=1; int count_limit=3; int weight_limit=10; };
using P_char = char_data *;
struct obj_data {
 uint64_t obj_uid=0; int type=0, location=0; int value[8]={};
 struct { P_obj_unused_placeholder; } unused;
 const char *short_description="a dagger", *name="dagger";
 int weight=1, condition=1, flags=0; bool visible=true;
 P_char carrier=nullptr, hitched_to=nullptr;
 obj_data *next_content=nullptr, *contains=nullptr;
 struct { int room=0; obj_data *inside=nullptr; } loc;
};
using P_obj = obj_data *;
static struct { P_obj contents=nullptr; } world[8];
static int top_of_objt=50;
static std::unordered_map<uint64_t, P_obj> objects;
static std::unordered_map<int, std::string> rooms;
static std::string output;
static int coin_attempts=0;
static bool fail_delivery=false;
static bool item_get_ack_publication=false, item_get_rejected=false;
static P_obj find_live_item_uid(uint64_t uid) { auto i=objects.find(uid); return i==objects.end()?nullptr:i->second; }
static void send_to_char(const char *s,P_char) { output+=s; }
static void act(const char *s,int,P_char ch,P_obj,void *,int target) {
 if(target==TO_ROOM) rooms[ch->in_room]+=s; else output+=s;
}
static void obj_from_obj(P_obj o) { o->location=0; }
static void obj_to_char(P_obj o,P_char ch) {
 if(fail_delivery) { objects.erase(o->obj_uid); return; }
 o->location=3; o->carrier=ch;
}
static bool item_movement_transaction_player_busy(P_char) { return false; }
static bool isname(const char *a,const char *b) { return !strcmp(a,b); }
static bool account_bound_reward_owner(P_char,P_obj) { return false; }
static bool item_command_object_is_takeable(P_char,P_obj o) { return o->weight>=0; }
static bool checkgetput(P_char,P_obj) { return false; }
static int64_t total_carried_weight(P_char) { return 0; }
static void checked_snprintf(char *b,size_t n,const char *f,...) { va_list a; va_start(a,f); vsnprintf(b,n,f,a); va_end(a); }
static int scrap_attempts=0;
static void MakeScrap(P_char,P_obj) { ++scrap_attempts; }
static void writeCorpse(P_obj) {}
static int wallet=0;
static bool credit_coins(P_char,int64_t value) { wallet+=static_cast<int>(value); return value>0; }
static void extract_obj(P_obj o,int) { objects.erase(o->obj_uid); o->location=0; }
static void add_coins(P_obj,int,int,int,int) {}
static const char *coins_to_string(int p,int g,int s,int c,const char *) {
 static char b[100]; snprintf(b,sizeof(b),"%dp %dg %ds %dc",p,g,s,c); return b;
}
'''.replace(' struct { P_obj_unused_placeholder; } unused;\n','')

finalizers = r'''
static void do_get_finalize_container_success(P_char ch,P_char,P_obj container,P_obj object,
 int &total,bool &found,bool,const char *,const coin_get_submission_options *options=nullptr) {
 item_get_rejected=false;
 if(object->type==ITEM_MONEY) {
  ++coin_attempts;
  // The production finalizer takes a selected corpse pile in memory.
  item_get_rejected=!(options && options->has_amount_limit &&
                      take_coins(ch,object,container,TRUE,*options));
  return;
 }
 publish_container_get(ch,object,container,TRUE,false); ++total; found=true;
}
static void do_get_finalize_room_item(P_char ch,P_obj o,bool &found,int &total) {
 obj_to_char(o,ch); ++total; found=true;
}
'''

driver = r'''
static void reset() {
 bulk_gets.clear(); objects.clear(); rooms.clear(); output.clear();
 coin_attempts=scrap_attempts=0; fail_delivery=false; wallet=0;
}
static void setup(P_char ch,P_obj corpse,P_obj dagger,P_obj coins) {
 ch->in_room=1; corpse->obj_uid=50; corpse->type=ITEM_CORPSE;
 corpse->location=1; corpse->loc.room=1; corpse->short_description="the corpse of a frost giant";
 corpse->contains=dagger; objects[50]=corpse;
 dagger->obj_uid=51; dagger->location=2; dagger->loc.inside=corpse; dagger->next_content=coins;
 objects[51]=dagger;
 if(coins) { coins->obj_uid=52; coins->type=ITEM_MONEY; coins->value[2]=4;
  coins->location=2; coins->loc.inside=corpse; objects[52]=coins; }
}
int main() {
 for(bool player_corpse : {false,true}) {
  reset(); char_data actor; obj_data corpse,dagger,coins; setup(&actor,&corpse,&dagger,&coins);
  start_bulk_get(&actor,&corpse,nullptr,player_corpse);
  assert(output.find("You begin pulling") == 0 && !rooms[1].empty());
  assert(OBJ_CARRIED_BY(&dagger,&actor) && coin_attempts==1 && wallet==400);
  assert(output.find("You finish sorting your haul from the corpse of a frost giant.")!=std::string::npos);
  assert(output.find("Haul:\r\n  a dagger\r\n")!=std::string::npos);
  assert(output.find("  0p 4g 0s 0c")!=std::string::npos);
  assert(output.find("Some contents were not acquired.")==std::string::npos);
  assert(bulk_gets.empty());
 }
 // A ruined item is scrapped where it lies; the rest of the haul still comes.
 {
  reset(); char_data actor; obj_data corpse,scrap,coins,dagger; setup(&actor,&corpse,&scrap,&coins);
  scrap.condition=0; dagger.obj_uid=53; dagger.location=2; dagger.loc.inside=&corpse;
  dagger.next_content=&scrap; corpse.contains=&dagger; objects[53]=&dagger;
  start_bulk_get(&actor,&corpse,nullptr,false);
  assert(scrap_attempts==1 && OBJ_CARRIED_BY(&dagger,&actor) && coin_attempts==1 && wallet==400);
  assert(bulk_gets.empty());
 }
 char_data actor; obj_data corpse,dagger,coins;
 reset(); setup(&actor,&corpse,&dagger,nullptr); actor.count_limit=0;
 start_bulk_get(&actor,&corpse,nullptr,false);
 assert(output=="You can't carry any more.\r\n"); actor.count_limit=3;
 // Several rejected roots still produce one count-limit notice. The scan
 // must reach a later coin pile for either NPC or player corpses.
 for(bool player_corpse : {false,true}) {
  reset(); char_data full_actor; full_actor.count_limit=0;
  obj_data full_corpse, first_item, second_item, later_coins;
  setup(&full_actor,&full_corpse,&first_item,&later_coins);
  second_item.obj_uid=53; second_item.location=2; second_item.loc.inside=&full_corpse;
  first_item.next_content=&second_item; second_item.next_content=&later_coins;
  objects[53]=&second_item;
  start_bulk_get(&full_actor,&full_corpse,nullptr,player_corpse);
  assert(coin_attempts==1 && wallet==400);
  assert(output.find("  0p 4g 0s 0c")!=std::string::npos);
  assert(output.find("You can't carry any more.\r\n")!=std::string::npos);
  assert(output.find("You can't carry any more.\r\n") ==
         output.rfind("You can't carry any more.\r\n"));
  assert(OBJ_INSIDE(&first_item) && OBJ_INSIDE(&second_item));
  assert(bulk_gets.empty());
 }
 // A bounded malformed sibling cycle does not multiply the typed notice;
 // neither a hidden direct child nor a nested descendant is disclosed.
 reset(); char_data cycle_actor; cycle_actor.count_limit=0;
 obj_data cycle_corpse, visible_root, hidden_root, nested_secret;
 setup(&cycle_actor,&cycle_corpse,&visible_root,nullptr);
 hidden_root.obj_uid=53; hidden_root.location=2; hidden_root.loc.inside=&cycle_corpse;
 hidden_root.visible=false; hidden_root.short_description="a hidden gem";
 nested_secret.short_description="a nested pearl";
 visible_root.contains=&nested_secret;
 visible_root.next_content=&hidden_root; hidden_root.next_content=&visible_root;
 objects[53]=&hidden_root;
 start_bulk_get(&cycle_actor,&cycle_corpse,nullptr,false);
 assert(output=="You can't carry any more.\r\n" && bulk_gets.empty());
 assert(OBJ_INSIDE(&visible_root) && OBJ_INSIDE(&hidden_root));
 // A failed live delivery is never listed in the haul.
 reset(); setup(&actor,&corpse,&dagger,nullptr); fail_delivery=true;
 start_bulk_get(&actor,&corpse,nullptr,false);
 assert(output.find("  a dagger")==std::string::npos);
 // Coin-only and mixed operations take the selected coins in memory and list them
 // in the one haul report.
 for(bool mixed : {false,true}) {
  reset(); setup(&actor,&corpse,&dagger,&coins);
  if(!mixed) corpse.contains=&coins;
  start_bulk_get(&actor,&corpse,nullptr,false);
  assert(coin_attempts==1 && wallet==400);
  assert(output.find("  0p 4g 0s 0c")!=std::string::npos && bulk_gets.empty());
 }
 // A later pile with nothing to take keeps the delivered equipment and first pile,
 // reports once, and never lists the rejected second pile.
 reset(); setup(&actor,&corpse,&dagger,&coins); obj_data later;
 later.obj_uid=53; later.type=ITEM_MONEY; later.location=2; later.loc.inside=&corpse;
 coins.next_content=&later; objects[53]=&later;
 start_bulk_get(&actor,&corpse,nullptr,false);
 assert(coin_attempts==2 && wallet==400);
 assert(output.find("  a dagger")!=std::string::npos && output.find("  0p 4g 0s 0c")!=std::string::npos);
 assert(output.find("Some contents were not acquired.")!=std::string::npos && bulk_gets.empty());
 // The helper is PC-only. The strict PID macro above aborts for a real NPC,
 // so this also protects every container/coin/artifact publication caller.
 reset(); char_data scavenger; scavenger.npc=true; obj_data npc_bag,npc_loot;
 setup(&scavenger,&npc_bag,&npc_loot,nullptr);
 assert(corpse_bulk_get(nullptr,npc_bag.obj_uid)==nullptr);
 assert(corpse_bulk_get(&scavenger,npc_bag.obj_uid)==nullptr);
 item_get_ack_publication=true;
 publish_container_get(&scavenger,&npc_loot,&npc_bag,TRUE,false);
 item_get_ack_publication=false;
 assert(OBJ_CARRIED_BY(&npc_loot,&scavenger) && bulk_gets.empty());
 puts("corpse haul: report, coins, scrap, count cap, cycle bound, failed delivery and strict NPC publication passed");
}
'''

# The forward declaration precedes the definition; select the latter explicitly.
_coins = source.index('static bool take_coins(', source.index('// Take the selected coins'))
take_coins = source[_coins:source.index('P_obj find_live_item_uid(', _coins)]
parts = [prelude, take('struct synchronous_get_item')+';', take('struct bulk_get_state')+';',
         take('struct coin_get_submission_options')+';',
         'static std::unordered_map<uint32_t,bulk_get_state> bulk_gets;',
         take('static bulk_get_state *corpse_bulk_get('),
         take('static void announce_corpse_bulk_get('), take_coins,
         take('static void publish_container_get('), finalizers]
for name in ['static bool bulk_get_source_matches(', 'static void report_bulk_get(',
             'static void finish_bulk_get(', 'static P_obj resolve_synchronous_get_item(',
             'static void take_bulk_get_items(', 'static void reject_bulk_get_object(',
             'static bool select_bulk_get_item(', 'static void start_bulk_get(']:
    parts.append(take(name))
parts += [driver]
with tempfile.TemporaryDirectory(prefix='corpse-haul-') as directory:
    cpp=Path(directory)/'test.cpp'; binary=Path(directory)/'test'
    cpp.write_text('\n'.join(parts))
    subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
                    '-Wno-missing-field-initializers','-fsanitize=address,undefined','-g',str(cpp),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
