#!/usr/bin/env python3
"""Exercise all five displacement handlers with the real forced movement and riding executor.

Combat rolls and room hooks are controlled. Actor bodies, ability functions, door checks,
riding lookup, and implicit companion transport are production code, under ASan/UBSan.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
from _paths import ROOT, extract_function
root=ROOT
prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "world/db.h"
#include "abilities/abilities.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "cmd/interp.h"
#include "item/objmisc.h"
#include "world/buildings.h"
#include "guild/guildhall.h"
#include <cstring>
#include <cassert>
#include <cstdio>
#include <algorithm>
#include <list>
#include <string>
#include <vector>
#include "combat/forced_movement.h"
room_data rooms[3]{};
extern const int top_of_world=2;
zone_data zones[1]{}; zone_data *zone_table=zones;
uint64_t character_removal_generation;
P_room world=rooms;
room_direction_data north{};
static bool castle_wall=false, spell_wall=false;
static char_data actor{}, target{}, mount{}, witness{};
static descriptor_data descriptor{};
static std::vector<P_char> live;
static std::list<char_link_data> links;
static std::vector<std::string> fixture_messages;
static bool lance_present=true, mounted_during_entry;
static bool ranged_charge=false, break_lance=false;
static int damage_calls, reschedules, judgement_limit=4;
static int identity_lookups;
static bool multiple_targets=false;
enum class Hook { none, veto, seal, lose_passdoor, redirect, extract, kill, remove_weapon, remove_actor, redirect_actor, dismount, disarm };
static Hook leave_hook, enter_hook;
static P_char hook_target;
static obj_data lance{};
P_index mob_index=nullptr;
const char *dirs[]={"north","east","south","west","up","down","nw","ne","sw","se"};
const int rev_dir[]={2,3,0,1,5,4,9,8,7,6};
static int placements=0, rng_route=0;
bool check_castle_walls(int,int) { return castle_wall; }
int check_wall(int,int) { return spell_wall; }
void act(const char *text,int,P_char ch,P_obj obj,void *target,int) { assert(!ch || char_in_list(ch)); assert(!target || char_in_list(static_cast<P_char>(target))); assert(obj!=&lance || lance_present); fixture_messages.emplace_back(text); }
void send_to_char(const char *text,P_char ch) { assert(char_in_list(ch)); fixture_messages.emplace_back(text); }
void CharWait(P_char ch,int) { assert(char_in_list(ch) && IS_ALIVE(ch)); }
int number(int low,int high) {
 if(rng_route==4 && low==0 && high==4) return 3;
 if(rng_route==1 && low==0 && high==100) return 100; // fail nexus agility dodge
 return low;
}
int dice(int,int) { return 1; }
const Rolls live_rolls={dice,number};
float get_property(const char *key,double fallback) { return strcmp(key,"spell.judgement.maxAffected")==0 ? judgement_limit : fallback; }
int get_property(const char *,int fallback) { return fallback; }
int panic_corruption_int(const char *,const char *,...) { abort(); }
int BOUNDED(int low,int value,int high) { return std::clamp(value,low,high); }
room_affect *get_spell_from_room(P_room,int) { return nullptr; }
int spell_damage(P_char,P_char,double,int,uint,damage_messages*,int*) { return DAM_NONEDEAD; }
bool should_area_hit(P_char,P_char ch) { return ch==&target || (multiple_targets && ch==&witness); }
void stop_fighting(P_char) {}
bool resists_spell(P_char,P_char) { return false; }
bool NewSaves(P_char,int,int) { return false; }
void die(P_char,P_char) { assert(false); }
void spell_major_paralysis(int,P_char,char*,int,P_char,P_obj) { assert(false); }
void spell_blindness(int,P_char,char*,int,P_char,P_obj) { assert(false); }
void spell_slow(int,P_char,char*,int,P_char,P_obj) { assert(false); }
void spell_dispel_magic(int,P_char,char*,int,P_char,P_obj) { assert(false); }
void astral_banishment(P_char,P_char,int,int) {}
void Stun(P_char,P_char,int,bool) {}
int CanDoFightMove(P_char,P_char) { return rng_route==4; }
bool damage(P_char,P_char,double,int) { return false; }
void update_pos(P_char) {}
int GET_ALT_SIZE(P_char ch) { return ch->player.size; }
void half_chop(char *,char *one,char *two) { strcpy(one,"target"); strcpy(two,ranged_charge?"north":""); }
bool SanityCheck(P_char ch,const char *) { return ch!=nullptr; }
int GET_CHAR_SKILL_P(P_char,int) { return 100; }
bool affected_by_spell(P_char,int) { return false; }

int dir_from_keyword(char *) { return DIR_NORTH; }
P_char get_char_ranged(const char *,P_char,int,int) { return &target; }
P_char ParseTarget(P_char,char *) { return &target; }
void set_short_affected_by(P_char,int,int) {}
float takedown_check(P_char,P_char,float chance,int,ulong) { return chance; }
bool notch_skill(P_char,int,float) { return true; }
int do_simple_move(P_char,int,unsigned int);
int can_enter_room(P_char,int,int) { return true; }

int DamageOneItem(P_char ch,int,P_obj,bool) { if(break_lance) { lance_present=false; ch->equipment[WIELD]=nullptr; } return 0; }
void set_fighting(P_char,P_char) {}
int melee_damage(P_char ch,P_char victim,double,int,damage_messages*,int*) { assert(char_in_list(ch) && char_in_list(victim)); ++damage_calls; return DAM_NONEDEAD; }
void do_remove(P_char,char*,int) { assert(lance_present); }
void do_wield(P_char,char*,int) {}
void update_group_vitals(P_char) {}
void gmcp_char_vitals(P_char) {}



int cast_as_damage_area(P_char ch,void (*spell)(int,P_char,char*,int,P_char,P_obj),int level,P_char,float,float) {
 spell(level,ch,nullptr,0,&target,nullptr); return 1;
}
void zone_spellmessage(int room,bool,const char*,const char*) { assert(room>=0 && room<=top_of_world); }
bool StatSave(P_char,int,int) { assert(false); return true; }
bool make_wet(P_char,int) { assert(false); return false; }
void spell_earthen_rain(int,P_char,char*,int,P_char,P_obj) { assert(false); }
void spell_greater_earthen_grasp(int,P_char,char*,int,P_char,P_obj) { assert(false); }
void spell_scathing_wind(int,P_char,char*,int,P_char,P_obj) { assert(false); }
nevent_schedule_result add_event(event_func,int,P_char ch,P_char,P_obj,int,const void*,int) {
 assert(char_in_list(ch) && IS_ALIVE(ch)); ++reschedules;
 return {nevent_schedule_status::scheduled,{}};
}
void logit(const char*,const char*,...) {}
P_obj find_live_object(P_obj obj,uint64_t uid) { return lance_present && obj==&lance && obj->obj_uid==uid ? obj:nullptr; }
P_char find_character_by_runtime_id(uint64_t id) {
 ++identity_lookups;
 for(P_char ch:live) if(ch->runtime_id==id) return ch;
 return nullptr;
}
int char_in_list(const P_char ch) { return std::find(live.begin(),live.end(),ch)!=live.end(); }
void act_convert(char *out,const char *text,P_char ch,P_char to,P_obj,void *vict,int) {
 assert(ch->in_room>=0 && static_cast<P_char>(vict)->in_room>=0 && to->in_room>=0);
 strcpy(out,text);
}
char_link_data *link_char(P_char ch,P_char target,ush_int type) {
 links.emplace_back(); auto *link=&links.back(); *link={};
 link->linking=ch; link->linked=target; link->type=type;
 link->next_linking=ch->linking; ch->linking=link;
 link->next_linked=target->linked; target->linked=link;
 return link;
}
void unlink_char(P_char ch,P_char target,ush_int type) {
 auto **out=&ch->linking;
 while(*out && ((*out)->linked!=target || (*out)->type!=type)) out=&(*out)->next_linking;
 if(!*out) return;
 auto *link=*out; *out=link->next_linking;
 auto **back=&target->linked;
 while(*back && *back!=link) back=&(*back)->next_linked;
 assert(*back); *back=link->next_linked;
}
static void detach(P_char ch) {
 if(ch->in_room!=NOWHERE) {
  auto **p=&rooms[ch->in_room].people;
  while(*p && *p!=ch) p=&(*p)->next_in_room;
  assert(*p); *p=ch->next_in_room;
  ch->specials.was_in_room=rooms[ch->in_room].number;
 }
 ch->in_room=NOWHERE; ch->next_in_room=nullptr;
}
static void place(P_char ch,int room) {
 detach(ch); ch->in_room=room; ch->next_in_room=rooms[room].people; rooms[room].people=ch;
}
static void forget(P_char ch) {
 if(P_char steed=GET_MOUNT(ch)) unlink_char(ch,steed,LNK_RIDING);
 if(P_char rider=GET_RIDER(ch)) unlink_char(rider,ch,LNK_RIDING);
 detach(ch); live.erase(std::remove(live.begin(),live.end(),ch),live.end()); ++character_removal_generation;
}
int do_simple_move(P_char ch,int,unsigned int) {
 assert(ranged_charge); place(ch,1); place(&mount,1);
 if(enter_hook==Hook::extract) forget(&target);
 if(enter_hook==Hook::redirect) place(&target,2);
 if(enter_hook==Hook::kill) SET_POS(&target,STAT_DEAD);
 if(enter_hook==Hook::remove_actor) forget(&mount);
 if(enter_hook==Hook::redirect_actor) place(ch,2);
 if(enter_hook==Hook::remove_weapon) { lance_present=false; ch->equipment[WIELD]=nullptr; }
 if(enter_hook==Hook::disarm) ch->equipment[WIELD]=nullptr;
 enter_hook=Hook::none; return true;
}
void char_from_room(P_char ch) {
 assert(char_in_list(ch));
 const Hook hook=ch==hook_target ? leave_hook:Hook::none;
 if(hook!=Hook::none) leave_hook=Hook::none;
 if(hook==Hook::veto) return;
 if(hook==Hook::redirect) { place(ch,2); return; }
 if(hook==Hook::extract) { forget(ch); return; }
 if(hook==Hook::kill) { SET_POS(ch,STAT_DEAD); return; }
 detach(ch);
 if(hook==Hook::seal) north.exit_info|=EX_CLOSED|EX_LOCKED|EX_PICKPROOF;
 if(hook==Hook::lose_passdoor) ch->specials.affected_by2=0;
 if(hook==Hook::dismount) {
  if(P_char steed=GET_MOUNT(ch)) unlink_char(ch,steed,LNK_RIDING);
  if(P_char rider=GET_RIDER(ch)) unlink_char(rider,ch,LNK_RIDING);
 }
}

'''
placement = r'''
bool char_to_room(P_char ch,int room,int dir) {
 assert(char_in_list(ch) && room>=0 && room<=top_of_world);
 place(ch,room); if(room==1) ++placements;
 if(dir>=0 && rng_route==4 && ch==&actor) {
  assert(GET_MOUNT(ch)==&mount && GET_RIDER(&mount)==ch);
  mounted_during_entry=true;
 }
 if(!move_riding_companions(ch,room,dir)) return false;
 if(dir>=0 && ch==hook_target) {
  if(rng_route==4 && ch==&actor)
   assert(GET_MOUNT(ch)==&mount && GET_RIDER(&mount)==ch && mount.in_room==ch->in_room);
  const Hook hook=enter_hook; enter_hook=Hook::none;
  if(hook==Hook::seal) north.exit_info|=EX_CLOSED|EX_LOCKED|EX_PICKPROOF;
  if(hook==Hook::redirect) { place(ch,2); return false; }
  if(hook==Hook::extract) { forget(ch); return false; }
  if(hook==Hook::kill) { SET_POS(ch,STAT_DEAD); return false; }
  if(hook==Hook::remove_weapon) lance_present=false;
  if(hook==Hook::disarm) actor.equipment[WIELD]=nullptr;
  if(hook==Hook::remove_actor) forget(&actor);
  if(hook==Hook::redirect_actor) place(&actor,2);
 }
 return true;
}
'''
prelude += re.search(r'struct fury_data\n\{.*?\n};', (root/'src/magic/smagic.c').read_text(), re.S)[0]+'\n'
prelude += re.search(r'^#define BANISHMENT_HOLY_WORD.*$', (root/'src/magic/magic.c').read_text(), re.M)[0]+'\n'
prelude += (root/'src/cmd/actoff.c').read_text().split('#include')[0]
functions=[extract_function('affects.c','P_char get_linked_char('),
           extract_function('affects.c','P_char get_linking_char('),
           extract_function('handler.c','static bool move_riding_companions('), placement]
functions += [extract_function('actmove.c', signature) for signature in
              ['static bool walking_door_allows(', 'static bool leave_walking_group(']]
text=(root/'src/classes/ethermancer.c').read_text()
for m in re.finditer(r'static (?:int|double) (tempest_\w+)\(',text):
 name=m.group(1)
 functions.append(extract_function('ethermancer.c',m.group()))
functions.append(extract_function('ethermancer.c','void spell_single_tempest('))
functions.append(extract_function('ethermancer.c','void spell_tempest('))
functions.append(extract_function('nexus_stones.c','void nexus_guardian_energy_burst('))
functions.append(extract_function('magic.c','void spell_oldjudgement('))
functions.append(extract_function('specs.mobile.c','int conj_specpet_golem('))
text=(root/'src/cmd/actoff.c').read_text()
for m in re.finditer(r'static (?:int|double) (lance_charge_\w+)\(',text):
 functions.append(extract_function('actoff.c',m.group()))
functions.append(extract_function('actoff.c','void lance_charge('))
for signature in ['static int elemental_fury_level(', 'static int elemental_fury_interval(', 'void event_elemental_fury(']:
 functions.append(extract_function('smagic.c',signature))

driver = r'''
static void reset(int route,unsigned flags,unsigned pass_mask) {
 actor={}; target={}; mount={}; witness={}; lance={}; links.clear(); live.clear(); fixture_messages.clear();
 for(auto &room:rooms) room={}; north={}; placements=damage_calls=reschedules=identity_lookups=0; character_removal_generation=0;
 rng_route=route; castle_wall=spell_wall=false; lance_present=true; multiple_targets=false; judgement_limit=4;
 ranged_charge=break_lance=false;
 leave_hook=enter_hook=Hook::none; hook_target=nullptr; mounted_during_entry=false;
 int id=0;
 for(P_char ch:{&actor,&target,&mount,&witness}) {
  ch->in_room=NOWHERE; ch->runtime_id=++id; ch->player.level=56; ch->desc=&descriptor;
  ch->points.hit=ch->points.max_hit=1000;
  SET_POS(ch,STAT_NORMAL+POS_STANDING); live.push_back(ch); place(ch,0);
 }
 for(int i=0;i<3;++i) rooms[i].number=100+i;
 actor.specials.alignment=1000; target.specials.alignment=-1000;
 target.player.size=SIZE_SMALL; target.curr_stats.Luk=100; target.curr_stats.Agi=100;
 actor.specials.affected_by2=(pass_mask&1)?AFF2_PASSDOOR:0;
 target.specials.affected_by2=(pass_mask&2)?AFF2_PASSDOOR:0;
 mount.specials.affected_by2=(pass_mask&4)?AFF2_PASSDOOR:0;
 rooms[0].sector_type=rooms[1].sector_type=SECT_FIELD;
 north.to_room=1; north.exit_info=flags; rooms[0].dir_option[DIR_NORTH]=&north;
 lance.type=ITEM_WEAPON; lance.value[0]=WEAPON_LANCE; lance.value[1]=lance.value[2]=1;
 lance.obj_uid=77; actor.equipment[WIELD]=&lance;
 if(route==4) link_char(&actor,&mount,LNK_RIDING);
}
static void run(int route) {
 if(route==0) spell_tempest(56,&actor,nullptr,0,&target,nullptr);
 else if(route==1) nexus_guardian_energy_burst(&actor,false);
 else if(route==2) spell_oldjudgement(56,&actor,nullptr,nullptr);
 else if(route==3) { actor.specials.fighting=&target; conj_specpet_golem(&actor,nullptr,0,nullptr); }
 else { char arg[]="target"; lance_charge(&actor,arg); }
}
static bool announced() {
 for(const auto &msg:fixture_messages)
  if(msg.find("out of the room")!=std::string::npos || msg.find("throwing from")!=std::string::npos ||
     msg.find("veering out")!=std::string::npos) return true;
 return false;
}
int main() {
 const unsigned sealed=EX_ISDOOR|EX_CLOSED|EX_LOCKED|EX_PICKPROOF;
 int cases=0;
 for(int route=0;route<5;++route) {
  for(const unsigned flags:{0U,unsigned(EX_CLOSED),unsigned(EX_CLOSED|EX_LOCKED),
                             unsigned(EX_CLOSED|EX_PICKPROOF),sealed})
   for(unsigned mask=0;mask<8;++mask) {
    reset(route,flags,mask); run(route); ++cases;
    const bool pass=route==4 ? mask==7 : (mask&2)!=0;
    const bool allowed=!(flags&EX_CLOSED) || (pass && flags!=sealed);
    if(target.in_room!=(allowed?1:0)) fprintf(stderr,"door case route=%d flags=%u mask=%u expected=%d actual=%d\n",route,flags,mask,allowed?1:0,target.in_room);
    assert(target.in_room==(allowed?1:0));
    assert(actor.in_room==((allowed && route==4)?1:0));
    assert(mount.in_room==((allowed && route==4)?1:0));
    assert(announced()==allowed);
    if(route==4) { assert(GET_MOUNT(&actor)==&mount && GET_RIDER(&mount)==&actor); assert(mounted_during_entry==allowed); }
   }
  // Trusted characters retain their own walking exception; they cannot lend it to companions.
  for(unsigned trust=0;trust<8;++trust) {
   reset(route,sealed,route==4?7:0);
   actor.player.level=(trust&1)?60:56;
   target.player.level=(trust&2)?60:56;
   mount.player.level=(trust&4)?60:56;
   run(route); ++cases;
   const bool allowed=route==4 ? trust==7 : (trust&2)!=0;
   assert(target.in_room==(allowed?1:0));
   assert(actor.in_room==((allowed && route==4)?1:0));
   assert(mount.in_room==((allowed && route==4)?1:0));
  }
  for(int wall=0;wall<4;++wall) {
   reset(route,0,7);
   if(wall==0) north.exit_info=EX_SECRET;
   if(wall==1) north.exit_info=EX_BLOCKED;
   if(wall==2) castle_wall=true;
   if(wall==3) spell_wall=true;
   run(route); ++cases;
   assert(placements==0 && target.in_room==0 && actor.in_room==0 && mount.in_room==0 && !announced());
  }
  for(const Hook hook:{Hook::veto,Hook::seal,Hook::lose_passdoor,Hook::redirect,Hook::extract,Hook::kill}) {
   reset(route,EX_CLOSED,7); hook_target=&target; leave_hook=hook;
   run(route); ++cases;
   assert(!announced() && placements==0);
   assert(actor.in_room==0 && mount.in_room==0);
   if(hook==Hook::veto || hook==Hook::seal || hook==Hook::lose_passdoor) assert(target.in_room==0);
   if(hook==Hook::redirect) assert(target.in_room==2);
   if(hook==Hook::extract) assert(!char_in_list(&target));
  }
  // A displaced rider is dismounted, rather than pulling an unchecked companion through.
  if(route<4) {
   reset(route,EX_CLOSED,2); link_char(&target,&witness,LNK_RIDING); run(route); ++cases;
   assert(target.in_room==1 && witness.in_room==0 && !GET_MOUNT(&target));
  }
 }
 // A mount's own departure veto or lost permission prevents the entire ram.
 for(const Hook hook:{Hook::veto,Hook::seal,Hook::lose_passdoor,Hook::redirect,Hook::extract,Hook::kill}) {
  reset(4,EX_CLOSED,7); hook_target=&mount; leave_hook=hook; run(4); ++cases;
  assert(!announced() && placements==0 && actor.in_room==0 && target.in_room==0);
  if(hook==Hook::veto || hook==Hook::seal || hook==Hook::lose_passdoor) {
   assert(mount.in_room==0 && GET_MOUNT(&actor)==&mount);
  } else assert(!GET_MOUNT(&actor));
 }
 // Arrival hooks are authoritative. No later participant may cross a newly sealed door.
 reset(4,EX_CLOSED,7); hook_target=&actor; enter_hook=Hook::seal; run(4); ++cases;
 assert(actor.in_room==1 && target.in_room==0 && mount.in_room==1 && GET_MOUNT(&actor)==&mount);
 assert(damage_calls==0);
 // Redirecting/removing the charger never leaves a riding link across rooms.
 for(const Hook hook:{Hook::redirect,Hook::extract,Hook::kill}) {
  reset(4,0,7); hook_target=&actor; enter_hook=hook; run(4); ++cases;
  assert(mount.in_room==1 && target.in_room==1 && !GET_RIDER(&mount) && damage_calls==0);
 }
 // Single-target arrival scripts can remove the caster; the caller must stop immediately.
 for(int route=0;route<4;++route) {
  reset(route,0,7); hook_target=&target; enter_hook=Hook::remove_actor; run(route); ++cases;
  assert(!char_in_list(&actor) && target.in_room==1);
 }
 // Victims are knocked off their own mounts; the charger keeps theirs.
 reset(4,EX_CLOSED,7); link_char(&target,&witness,LNK_RIDING); run(4); ++cases;
 assert(actor.in_room==1 && target.in_room==1 && mount.in_room==1 && witness.in_room==0);
 assert(GET_MOUNT(&actor)==&mount && !GET_MOUNT(&target));
 // Three moving bodies cannot crowd into a two-person private room.
 reset(4,0,7); rooms[1].room_flags=ROOM_PRIVATE; run(4); ++cases;
 assert(placements==0 && actor.in_room==0 && target.in_room==0 && mount.in_room==0);
 // Do not accidentally give charge tackle's absolute ocean prohibition.
 reset(4,0,7); rooms[1].sector_type=SECT_OCEAN; run(4); ++cases;
 assert(actor.in_room==1 && target.in_room==1 && mount.in_room==1);
 // A redirected mount remains redirected and is no longer linked to the charger.
 for(const Hook hook:{Hook::redirect,Hook::extract,Hook::kill}) {
  reset(4,0,7); hook_target=&mount; enter_hook=hook; run(4); ++cases;
  assert(actor.in_room==1 && target.in_room==1 && !GET_MOUNT(&actor) && damage_calls==0);
 }
 // CMD_DEATH dispatch runs after the guardian is marked dead; only the victim moves.
 for(unsigned flags : {unsigned(EX_CLOSED),sealed}) {
  reset(1,flags,2); SET_POS(&actor,STAT_DEAD); run(1); ++cases;
  assert(target.in_room==(flags==sealed?0:1));
 }
 // The periodic caller must not reschedule itself after a Squall entry script invalidates its caster.
 for(const Hook hook:{Hook::none,Hook::remove_actor,Hook::redirect_actor}) {
  reset(0,0,7); hook_target=&target; enter_hook=hook;
  fury_data fury{0,3}; event_elemental_fury(&actor,nullptr,nullptr,&fury); ++cases;
  assert(reschedules==(hook==Hook::none?1:0));
 }
 // The indoor post-cast message has no target reference after an arrival hook removes one.
 reset(0,0,7); rooms[0].sector_type=SECT_INSIDE; hook_target=&target; leave_hook=Hook::extract;
 spell_tempest(56,&actor,nullptr,0,&target,nullptr); ++cases;
 assert(char_in_list(&actor) && !char_in_list(&target));
 // A single target's room procedure must not cancel the rest of an area effect.
 for(int route : {1,2}) for(Hook hook : {Hook::veto,Hook::extract,Hook::redirect}) {
  reset(route,EX_CLOSED,2); multiple_targets=true;
  witness.specials.alignment=-1000; witness.specials.affected_by2=AFF2_PASSDOOR;
  hook_target=&witness;
  if(hook==Hook::redirect) enter_hook=hook; else leave_hook=hook;
  run(route); ++cases; assert(target.in_room==1);
 }
 // Interrupted targets still consume Judgement's existing affected-target limit.
 reset(2,EX_CLOSED,2); multiple_targets=true; judgement_limit=1;
 witness.specials.alignment=-1000; witness.specials.affected_by2=AFF2_PASSDOOR;
 hook_target=&witness; leave_hook=Hook::veto; run(2); ++cases;
 assert(target.in_room==0);
 // The dying guardian also continues past an immovable target.
 reset(1,EX_CLOSED,2); SET_POS(&actor,STAT_DEAD); multiple_targets=true;
 witness.specials.affected_by2=AFF2_PASSDOOR; hook_target=&witness; leave_hook=Hook::veto;
 run(1); ++cases; assert(target.in_room==1);
 // A weapon removed by arrival scripts must not be dereferenced after movement.
 for(Hook hook : {Hook::remove_weapon,Hook::disarm}) {
  reset(4,0,7); hook_target=&actor; enter_hook=hook; run(4); ++cases;
  assert(actor.in_room==1 && target.in_room==1 && mount.in_room==1 && damage_calls==0);
 }
 // An approach walk may succeed after its scripts invalidate another charge participant.
 for(Hook hook : {Hook::none,Hook::extract,Hook::redirect,Hook::kill,Hook::remove_actor,
                  Hook::redirect_actor,Hook::remove_weapon,Hook::disarm}) {
  reset(4,0,7); ranged_charge=true; place(&target,1); enter_hook=hook;
  run(4); ++cases; assert(damage_calls==(hook==Hook::none?1:0));
 }
 // Worn lances can be scrapped by DamageOneItem; swapping to a spare must not use one.
 for(bool ram : {false,true}) {
  reset(4,0,7); break_lance=true; obj_data spare{}; spare.type=ITEM_WEAPON; actor.carrying=&spare;
  if(!ram) rooms[0].dir_option[DIR_NORTH]=nullptr;
  run(4); ++cases; assert(!lance_present && damage_calls==1);
 }
 // Walking must finish every leave hook and recheck each mover before either placement pass.
 for(P_char mover : {&actor,&mount}) for(P_char participant : {&actor,&mount})
  for(Hook hook : {Hook::none,Hook::veto,Hook::seal,Hook::lose_passdoor,Hook::redirect,Hook::extract,Hook::kill,Hook::dismount}) {
   reset(4,EX_CLOSED,7); hook_target=participant; leave_hook=hook;
   const bool departed=leave_walking_group(mover,1,DIR_NORTH); ++cases;
   if(hook!=Hook::extract) assert(identity_lookups==0);
   assert(departed==(hook==Hook::none));
   if(departed) {
    assert(actor.in_room==NOWHERE && mount.in_room==NOWHERE);
    assert(char_to_room(mover,1,DIR_NORTH));
    assert(actor.in_room==1 && mount.in_room==1);
   } else {
    assert(placements==0 && (!char_in_list(&actor) || actor.in_room!=NOWHERE) &&
           (!char_in_list(&mount) || mount.in_room!=NOWHERE));
    if(hook==Hook::veto || hook==Hook::seal || hook==Hook::lose_passdoor)
     assert(actor.in_room==0 && mount.in_room==0 && GET_MOUNT(&actor)==&mount);
    if(hook==Hook::dismount)
     assert(actor.in_room==0 && mount.in_room==0 && !GET_MOUNT(&actor) && !GET_RIDER(&mount));
   }
  }
 // An unmounted character cannot walk through a door sealed by their own leave hook either.
 reset(0,0,0); hook_target=&actor; leave_hook=Hook::seal;
 assert(!leave_walking_group(&actor,1,DIR_NORTH) && actor.in_room==0 && placements==0); ++cases;
 printf("protected door movement: %d actual-handler cases passed, including mounted companion execution\n",cases);
}
'''
walking = extract_function('actmove.c', 'int do_simple_move_skipping_procs(')
assert walking.count('leave_walking_group(ch, new_room, exitnumb)') == 2
build = Path(os.environ.get("BIN_ROOT", ROOT / "bin")) / "tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="protected-doors-", dir=build) as directory:
    cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
    cpp.write_text(prelude + "\n".join(functions) + driver)
    subprocess.run(["g++", "-std=c++20", "-g", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", "-fno-pie", "-no-pie", "-ffunction-sections",
                    "-fdata-sections", "-I"+str(ROOT/"src"), str(cpp),
                    str(ROOT/"src/combat/forced_movement.c"), "-Wl,--gc-sections", "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
