// Reflection regression harness: compiles the unchanged production spell function
// from TEST_REFLECTION_INCLUDE with thin implementations of its runtime dependencies.
// Important limitation: this does NOT boot the MUD or exercise actual scheduler/groups.
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <cstdint>
#include <string>
#include <vector>
#include <algorithm>
#include <iostream>

using std::string;
constexpr int MAX_STRING_LENGTH = 8192;
constexpr int STRUNG_KEYS = 1, STRUNG_DESC1 = 2, STRUNG_DESC2 = 4;
constexpr int LNK_PET = 6, TITAN_NUMBER = 650, REAL = 0, PET_NOCASH = 1;
constexpr int PET_NOORDER=2, PET_RESTORE=4, PET_NOAGGRO=8;
constexpr int AFF_CHARM=16, AFFTYPE_NODISPEL=32, SPELL_CHARM_PERSON=104;
constexpr int INNATE_UNHOLY_ALLIANCE=99;
constexpr int AFF_DETECT_INVISIBLE = 4, ACT_MEMORY = 8;
constexpr int LOG_DEBUG = 1, FALSE = 0, TO_ROOM = 1;
struct char_data;
using P_char = char_data*;
using P_obj = void*;
struct npc_only_data { int str_mask = 0; int R_num = 0; int64_t pet_charm_expires_at=0; int summon_kind=0; };
struct affected_type { affected_type *next; int bitvector, flags, type, duration; };
struct char_link_data { int type=0; P_char linking=nullptr; char_link_data *next_linked=nullptr; };
struct follow_type { P_char follower=nullptr; follow_type *next=nullptr; };
struct Player { const char *name=nullptr, *short_descr=nullptr, *long_descr=nullptr, *title=nullptr; int race=0, level=1; };
struct Points { int base_hit=0, max_hit=0, hit=0, cha=15, platinum=0, gold=0, silver=0, copper=0, exp=0; };
struct Specials { int act=0, affected_by=0; };
struct char_data {
  bool npc=false, alive=true, owned=false;
  int in_room=-1, vnum=0, racewar=0, sex=0, alignment=0, size=0;
  Player player;
  Points points;
  Specials specials;
  struct { npc_only_data* npc=nullptr; } only;
  affected_type *affected=nullptr;
  char_link_data *linked=nullptr;
  follow_type *followers=nullptr;
  P_char owner=nullptr, opponent=nullptr;
  P_char next_in_room=nullptr;
};
struct Room { P_char people=nullptr; };
static Room world[2];
struct RaceName { const char* normal; };
static RaceName race_names_table[] = {{"Human"},{"Kobold"},{"Gnome"}};
static char *prototype_name=nullptr, *prototype_short=nullptr, *prototype_long=nullptr;
static std::vector<P_char> all_images;
static unsigned rng=0x12345678;
#define IS_NPC(c) ((c)->npc)
#define IS_PC(c) (!(c)->npc)
#define IS_PC_PET(c) ((c)->npc && (c)->owner && !(c)->owner->npc)
#define IS_ALIVE(c) ((c)!=nullptr && (c)->alive)
#define GET_VNUM(c) ((c)->vnum)
#define GET_NAME(c) ((c)->player.name)
#define GET_TITLE(c) ((c)->player.title)
#define GET_RACE(c) ((c)->player.race)
#define GET_RACEWAR(c) ((c)->racewar)
#define GET_SEX(c) ((c)->sex)
#define GET_ALIGNMENT(c) ((c)->alignment)
#define GET_SIZE(c) ((c)->size)
#define GET_C_CHA(c) ((c)->points.cha)
#define GET_LEVEL(c) ((c)->player.level)
#define GET_PLATINUM(c) ((c)->points.platinum)
#define GET_GOLD(c) ((c)->points.gold)
#define GET_SILVER(c) ((c)->points.silver)
#define GET_COPPER(c) ((c)->points.copper)
#define GET_EXP(c) ((c)->points.exp)
#define GET_MAX_HIT(c) ((c)->points.max_hit)
#define GET_HIT(c) ((c)->points.hit)
#define GET_OPPONENT(c) ((c)->opponent)
#define IS_FIGHTING(c) ((c)->opponent != nullptr)
#define IS_SET(bits,flag) (((bits)&(flag)) != 0)
#define SET_BIT(bits,flag) ((bits) |= (flag))
#define BOUNDED(lo,n,hi) std::min((hi),std::max((lo),(n)))

static char* str_dup(const char *p) { assert(p); return strdup(p); }
static void str_free(const char *p) { free(const_cast<char*>(p)); }
static void logit(int, const char*,...) {}
static void send_to_char(const char*, P_char) {}
static void act(const char*, int, P_char, void*, P_char, int) {}
static int real_mobile(int vnum) {return vnum;}
static int number(int a, int b) {
  assert(a<=b);
  rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
  return a + static_cast<int>(rng%static_cast<unsigned>(b-a+1));
}
static P_char read_mobile(int vnum, int) {
  assert(vnum==250);
  auto *c = new char_data();
  c->npc=true; c->owned=true; c->vnum=250;
  c->player.name=prototype_name;
  c->player.short_descr=prototype_short;
  c->player.long_descr=prototype_long;
  c->only.npc=new npc_only_data();
  all_images.push_back(c);
  return c;
}
static void char_from_room(P_char c) {
  if (c->in_room<0) return;
  P_char *link=&world[c->in_room].people;
  while (*link && *link!=c) link=&(*link)->next_in_room;
  assert(*link==c);
  *link=c->next_in_room; c->next_in_room=nullptr; c->in_room=-1;
}
static bool char_to_room(P_char c, int room, int) {
  assert(room==0);
  assert(c->in_room==-1);
  c->in_room=room; c->next_in_room=world[room].people; world[room].people=c;
  return true;
}
static void stop_fighting(P_char c) { if(c) c->opponent=nullptr; }
static void StopAllAttackers(P_char c) {
  for(P_char r=world[0].people;r;r=r->next_in_room) if(r->opponent==c)r->opponent=nullptr;
}
static void set_fighting(P_char c, P_char target) {c->opponent=target;}
static void affect_remove(P_char c, affected_type *which) {
  affected_type **link=&c->affected;
  while(*link && *link!=which)link=&(*link)->next;
  assert(*link==which);
  *link=which->next;
  delete which;
}
static void clearMemory(P_char) {}
static void balance_affects(P_char) {}
static void remove_plushit_bits(P_char) {}

static bool collector_presence_is_npc(P_char) {return false;}
static bool training_dummy_capture_target_allowed(P_char) {return true;}
static P_obj get_globe(P_char) {return nullptr;}
static bool has_innate(P_char,int) {return false;}
static void remember(P_char,P_char) {}
static void linked_affect_to_char(P_char mob,affected_type *af,P_char owner,int type) {
  assert(type==LNK_PET && mob->affected==nullptr);
  mob->affected=new affected_type(*af);
  owner->linked=new char_link_data{LNK_PET,mob,owner->linked};
  mob->owner=owner;
}
#ifndef TEST_SETUP_PET_INCLUDE
#error Pass the real setup_pet production function
#endif
#include TEST_SETUP_PET_INCLUDE
static void add_follower(P_char child,P_char leader) {
  auto *node = new follow_type{child,leader->followers};
  leader->followers=node;
}
static void extract_char(P_char c) {
  assert(c && c->owned && c->npc && c->only.npc);
  char_from_room(c);
  P_char parent=c->owner;
  if(parent) {
    follow_type **n=&parent->followers;
    while(*n && (*n)->follower != c)n=&(*n)->next;
    if(*n){auto *dead=*n;*n=dead->next;delete dead;}
    char_link_data **p=&parent->linked;
    while(*p && (*p)->linking!=c)p=&(*p)->next_linked;
    if(*p){auto *dead=*p;*p=dead->next_linked;delete dead;}
  }
  if (IS_SET(c->only.npc->str_mask,STRUNG_KEYS))str_free(c->player.name);
  if (IS_SET(c->only.npc->str_mask,STRUNG_DESC1))str_free(c->player.long_descr);
  if (IS_SET(c->only.npc->str_mask,STRUNG_DESC2))str_free(c->player.short_descr);
  if(c->player.title)str_free(c->player.title);
  while(c->affected)affect_remove(c,c->affected);
  c->alive=false;
  delete c->only.npc;
  auto it=std::find(all_images.begin(),all_images.end(),c);
  if(it!=all_images.end())*it=nullptr;
  delete c;
}
#ifndef TEST_REFLECTION_INCLUDE
#error Pass a local production-function include path
#endif
#include TEST_REFLECTION_INCLUDE

static int images(P_char owner) {
  int count=0;
  for(auto* link=owner->followers;link;link=link->next)
    if(link->follower->vnum==250) ++count;
  return count;
}
static void verify(P_char owner, int expected, const char *image_of=nullptr) {
  if (!image_of) image_of=owner->player.name;
  assert(images(owner)==expected);
  int n=0;
  for(auto* link=owner->followers;link;link=link->next) {
    const P_char c=link->follower;
    if(c->vnum!=250)continue;
    ++n;
    assert(c->only.npc->str_mask==(STRUNG_KEYS|STRUNG_DESC1|STRUNG_DESC2));
    assert(strncmp(c->player.name,"image ",6)==0);
    assert(strcmp(c->player.short_descr,image_of)==0);
    assert(strstr(c->player.long_descr,"stands here")!=nullptr);
    assert(c->points.cha==1);
    assert(c->owner==owner);
  }
  assert(n==expected);
  // These reads must remain safe after every image creation and replacement.
  assert(strcmp(prototype_name,"base reflection")==0);
  assert(strcmp(prototype_short,"a mirror image")==0);
  assert(strcmp(prototype_long,"a base mirror image stands here")==0);
}
static void scenario(int level,int pets,bool in_combat,bool title) {
  char_data owner{};
  owner.player.name="Kobold_Necromancer";
  owner.player.title=title ? "the Magnificent" : nullptr;
  owner.player.race=1;
  owner.player.level=level;
  char_to_room(&owner,0,-2);
  char_data attacker{};
  if(in_combat){attacker.player.name="Enemy";char_to_room(&attacker,0,-2);attacker.opponent=&owner;owner.opponent=&attacker;}
  for(int i=0;i<pets;i++) {
    auto *pet=new char_data();pet->npc=true;pet->owned=true;pet->vnum=777+i;
    pet->only.npc=new npc_only_data{STRUNG_KEYS,777+i};
    pet->player.name=str_dup("zombie");
    char_to_room(pet,0,0);
    pet->owner=&owner;
    owner.linked=new char_link_data{LNK_PET,pet,owner.linked};
    add_follower(pet,&owner);
  }
  const int expected=BOUNDED(1,(level-26)/5,4);
  for(int round=0;round<8;round++) {
    if(in_combat){attacker.opponent=&owner;owner.opponent=&attacker;}
    spell_reflection(level,&owner,nullptr,0,&owner,nullptr);
    verify(&owner,expected);
  }
  // Existing unrelated pets must survive replacements intact.
  int alive_pets=0;
  for(auto *link=owner.followers;link;link=link->next)
    if(link->follower->vnum!=250)++alive_pets;
  assert(alive_pets==pets);
  while(owner.followers) {
    P_char child=owner.followers->follower;
    StopAllAttackers(child);
    extract_char(child);
  }
  assert(!owner.linked);
  if(in_combat)char_from_room(&attacker);
  char_from_room(&owner);
  assert(world[0].people==nullptr);
  std::printf("PASS level=%d undead_pets=%d combat=%d title=%d (8 repeat casts)\n",level,pets,in_combat,title);
}
static void cast_on_another_player() {
  char_data caster{}, victim{};
  caster.player.name="Caster"; caster.player.race=1; caster.player.level=56;
  victim.player.name="Target"; victim.player.race=0; victim.player.level=56;
  char_to_room(&caster,0,-2);
  char_to_room(&victim,0,-2);
  for(int i=0;i<8;i++) {
    spell_reflection(56,&caster,nullptr,0,&victim,nullptr);
    verify(&caster,4,"Target");
    assert(!victim.followers);
  }
  while(caster.followers)extract_char(caster.followers->follower);
  assert(!caster.linked);
  char_from_room(&caster);
  char_from_room(&victim);
  assert(world[0].people==nullptr);
  std::puts("PASS illusionist reflection on another player (8 repeat casts)");
}
static void titan_preflight() {
  char_data owner{}; owner.player.name="Kobold_Necromancer"; owner.player.race=1;
  char_data titan{}; titan.npc=true;titan.vnum=650;
  char_link_data link{LNK_PET,&titan,nullptr};owner.linked=&link;
  char_to_room(&owner,0,-2);
  spell_reflection(56,&owner,nullptr,0,&owner,nullptr);
  assert(images(&owner)==0);
  char_from_room(&owner);
  assert(world[0].people==nullptr);
  std::puts("PASS existing titan rejection");
}
int main() {
  prototype_name=str_dup("base reflection");
  prototype_short=str_dup("a mirror image");
  prototype_long=str_dup("a base mirror image stands here");
  for(int level : {31,35,36,40,41,45,46,56}) {
    for(int pets : {0,1,4}) {
      scenario(level,pets,false,false);
      scenario(level,pets,true,true);
    }
  }
  cast_on_another_player();
  titan_preflight();
  for(auto *c:all_images) assert(c==nullptr);
  str_free(prototype_name);str_free(prototype_short);str_free(prototype_long);
  std::puts("PASS all reflection image allocation/replacement/cleanup checks");
}
