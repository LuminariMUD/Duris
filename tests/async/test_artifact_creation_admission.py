#!/usr/bin/env python3
"""Actual constructor/clone/extraction with the artifact service and writer captures."""
from pathlib import Path
import subprocess
import re
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function

HARNESS = r"""
#include "guild/artifact.c"
#include "world/object_template.h"
#include "cmd/interp.h"
#include "redis/redis_floor_runtime.h"
#include "world/world_recovery_pipeline.h"
#include "world/world_recovery_codec.h"
#include "item/encumbrance_policy.h"
#include "player/player_snapshot.h"
#include <cassert>
#include <cstdlib>
#include <iostream>
index_data indexes[4] = {};
index_data mob_indexes[1] = {};
P_index mob_index=mob_indexes;
P_char character_list=nullptr;
int real_room(int vnum) { return vnum==2300 ? 0 : -1; }
room_data rooms[1] = {};
const char *equipment_types[CUR_MAX_WEAR+1] = {};
P_room world=rooms;
extern const int top_of_world=0;
P_index obj_index = indexes;
P_obj object_list = nullptr;
mm_ds pool = {};
mm_ds *dead_obj_pool = &pool;
const int top_of_objt = 3;
static unsigned long long next_uid=10000;
static size_t procedures=0, floors=0;
static std::vector<persistence_job_write_fn> writes;
static std::vector<std::vector<flatfile_artifact_record>> captures;
static bool booting=false;
bool sql_async_booting() { return booting; }
static bool fail_invalidation=false;
bool redis_invalidate_artifact_cache() {
 if(fail_invalidation) { fail_invalidation=false; throw std::bad_alloc(); }
 return true;
}
const char *persistence_mode_flatfile_root() { return "fixture"; }
flatfile_artifact_result flatfile_artifact_snapshot_apply(const std::string &,
 const std::vector<flatfile_artifact_record> &records,std::string *) {
 captures.push_back(records); return flatfile_artifact_result::ok;
}
player_save_submit_result persistence_writer_submit(persistence_job_kind kind,uint64_t,size_t,
 persistence_job_write_fn write) {
 assert(kind==persistence_job_kind::artifact); writes.push_back(std::move(write));
 return player_save_submit_result::accepted;
}
void drain() {
 for(auto &write:writes) assert(write().outcome==player_save_apply_outcome::applied);
 writes.clear(); assert(!artifact_save_pulse(false)); captures.clear();
}
unsigned long long persistence_next_item_uid() { return next_uid++; }
void *_mm_get(mm_ds *source,const char *,int) { ++source->objs_used; return calloc(1,sizeof(obj_data)); }
void mm_release(mm_ds *source,void *object) { assert(source->objs_used); --source->objs_used; free(object); }
char *str_dup(const char *text) { return strdup(text); }
void *__malloc(size_t size,const char *,const char *,int) { return calloc(1,size); }
void __free(void *memory,const char *,int) { free(memory); }
int strn_cmp(const char *left,const char *right,unsigned int size) { return strncasecmp(left,right,size); }
int number(int from,int) { return from; }
int real_object(const int vnum) { return vnum>=900 && vnum<=903 ? vnum-900 : -1; }
int periodic(P_obj,P_char,int,char *) { ++procedures; return 0; }
int item_switch(P_obj,P_char,int,char *) { return 0; }
void event_object_proc(P_char,P_char,P_obj,void *) {}
void event_random_exit(P_char,P_char,P_obj,void *) {}
nevent_schedule_result add_event(event_func,int,P_char,P_char,P_obj,int,const void *,int) { return {}; }
int proclibObj_add(P_obj,char *,char *) { return 0; }
int FillMasterSpellBook(P_obj) { return 0; }
void convertObj(P_obj) {}
void world_recovery_capture_forget_object(P_obj) {}
void item_actions_source_leaving(P_obj) {}
void ferry_forget_object(P_obj) {}
void redis_remove_floor_drop(unsigned long) { ++floors; }
void disarm_obj_nevents(P_obj,event_func_type) {}
void remove_linked_object(P_obj) {}
void free_obj(P_obj object) { mm_release(dead_obj_pool,object); }
void unlink_content(P_obj object,P_obj *head) {
 for(;*head && *head!=object;head=&(*head)->next_content) {}
 if(*head==object) *head=object->next_content;
 object->next_content=nullptr; object->loc_p=LOC_NOWHERE; object->loc.room=NOWHERE;
}
void obj_from_room(P_obj object) { unlink_content(object,&rooms[0].contents); }
void obj_from_char(P_obj object) { auto *owner=object->loc.carrying; unlink_content(object,&owner->carrying); }
void obj_from_obj(P_obj object) { auto *parent=object->loc.inside; unlink_content(object,&parent->contains); }
P_obj unequip_char(P_char mob,int slot,bool) {
 auto *object=mob->equipment[slot]; mob->equipment[slot]=nullptr;
 object->loc_p=LOC_NOWHERE; object->loc.room=NOWHERE; return object;
}
void obj_to_room(P_obj object,int room) {
 object->loc_p=LOC_ROOM; object->loc.room=room;
 object->next_content=rooms[room].contents; rooms[room].contents=object; artifact_object_placed(object);
}
void obj_to_char(P_obj object,P_char mob) {
 object->loc_p=LOC_CARRIED; object->loc.carrying=mob;
 object->next_content=mob->carrying; mob->carrying=object; artifact_object_placed(object);
}
void obj_to_obj(P_obj object,P_obj parent) {
 object->loc_p=LOC_INSIDE; object->loc.inside=parent;
 object->next_content=parent->contains; parent->contains=object; artifact_object_placed(object);
}
void equip_char(P_char mob,P_obj object,int slot,int) {
 mob->equipment[slot]=object; object->loc_p=LOC_WORN; object->loc.wearing=mob; artifact_object_placed(object);
}
P_obj get_obj_num(int number) {
 for(P_obj object=object_list;object;object=object->next) if(object->R_num==number) return object;
 return nullptr;
}
P_obj get_obj_in_list_num(int number,P_obj list) {
 for(;list;list=list->next_content) if(list->R_num==number) return list;
 return nullptr;
}
int itemvalue(P_obj) { return 1; }
bool item_load_check(P_obj,int,int) { return true; }
void enhance_on_npc_item_reset_skipped(P_char,P_obj) {}
int shop_keeper(P_char,P_char,int,char *) { return 0; }
object_template parse_object_template(int index) {
 object_template prototype; prototype.R_num=index; prototype.extra_flags=(index==1 || index==3) ? 0 : ITEM_ARTIFACT;
 prototype.type=index==3 ? ITEM_CONTAINER : 0; prototype.wear_flags=ITEM_TAKE;
 return prototype;
}
void balance_affects(P_char) {}
// PLAYER_ATTACHMENT
// CONSTRUCTORS
// EXTRACTION
// CLONE
// NEST_CHECK
// RESET
// RESTORE_WRAPPER
int main() {
 indexes[0].virtual_number=900; indexes[1].virtual_number=901; indexes[2].virtual_number=902; indexes[3].virtual_number=903; rooms[0].number=2300;
 indexes[0].func.obj=periodic;
 artifact_cache_loaded=true;
 const std::vector<artifact_population_template> prototypes={{900,ITEM_ARTIFACT},{901,0},{902,ITEM_ARTIFACT}};
 const auto stage=[&](bool complete) {
  booting=true; const bool result=artifacts_stage_population({},prototypes,complete); booting=false; return result;
 };
 fail_invalidation=true;
 assert(stage(true) && fail_invalidation); // canonical staging does not need the report cache
 fail_invalidation=false; artifact_save_pulse(true); drain();
 obj_data invalid={}; invalid.R_num=-1; invalid.extra_flags=ITEM_ARTIFACT; invalid.obj_uid=123;
 assert(!artifact_begin_creation(&invalid) && errno==ENODATA && !clone_obj(&invalid));
 artifact_object_extracted(&invalid,true); assert(!artifact_is_canonical(&invalid));
 artifact_binds[900]={42,777}; artifact_rows.at(900).timer=888;
 fail_invalidation=true;
 auto *probe=read_object_for_creation(900,VIRTUAL); assert(probe && fail_invalidation);
 extract_obj(probe,FALSE); assert(fail_invalidation && !artifact_rows.at(900).creation_pending && !pool.objs_used);
 fail_invalidation=false; procedures=0;
 auto *first=read_object_for_creation(900,VIRTUAL);
 assert(first && procedures==1 && pool.objs_used==1 && indexes[0].number==1);
 assert(artifact_rows.at(900).creation_pending && writes.empty());
 assert(!read_object_for_creation(900,VIRTUAL) && errno==EEXIST && procedures==1);
 assert(pool.objs_used==1 && indexes[0].number==1 && object_list==first);
 fail_invalidation=true;
 extract_obj(first,FALSE); assert(fail_invalidation); fail_invalidation=false;
 assert(artifact_rows.at(900).identity_state==artifact_identity_state::absent &&
  !artifact_rows.at(900).canonical_item_uid && artifact_rows.at(900).timer==888 &&
  artifact_binds.at(900).owner_pid==42 && artifact_binds.at(900).timer==777 && writes.empty());
 assert(!object_list && !pool.objs_used && !indexes[0].number);
 artifact_rows.at(900).canonical_item_uid=123;
 artifact_rows.at(900).identity_state=artifact_identity_state::retired;
 first=read_object_for_creation(900,VIRTUAL); assert(first); extract_obj(first,FALSE);
 assert(artifact_rows.at(900).identity_state==artifact_identity_state::retired &&
  artifact_rows.at(900).canonical_item_uid==123 && writes.empty());
 first=read_object_for_creation(900,VIRTUAL); assert(first);
 first->loc_p=LOC_ROOM; first->loc.room=0; artifact_object_placed(first);
 assert(artifact_is_canonical(first) && !artifact_rows.at(900).creation_pending &&
  artifact_rows.at(900).live_object==first && artifact_binds.at(900).owner_pid==0);
 artifact_save_pulse(true); drain();
 artifact_rows.at(900).timer=9999; artifact_binds[900]={55,666};
 auto *temporary=read_object(900,VIRTUAL); assert(temporary);
 assert(!remove_owned_artifact_sql(temporary) && writes.empty());
 const auto before=floors; temporary->obj_uid=first->obj_uid;
 extract_obj(temporary,TRUE);
 assert(floors==before && artifact_is_canonical(first) && artifact_rows.at(900).timer==9999 &&
  artifact_binds.at(900).owner_pid==55 && writes.empty());
 // Effective flags on an ordinary prototype use the same claim before placement.
 auto *converted=read_object(901,VIRTUAL); assert(converted); converted->extra_flags=ITEM_ARTIFACT;
 assert(artifact_begin_creation(converted));
 converted->loc_p=LOC_ROOM; converted->loc.room=0; artifact_object_placed(converted);
 auto *extra_converted=read_object(901,VIRTUAL); assert(extra_converted); extra_converted->extra_flags=ITEM_ARTIFACT;
 assert(!artifact_begin_creation(extra_converted) && errno==EEXIST);
 extract_obj(extra_converted,FALSE); extract_obj(converted,TRUE); drain();
 assert(!clone_obj(first));
 auto *container=read_object(903,VIRTUAL); auto *nested_copy=read_object(903,VIRTUAL);
 auto *blocked=read_object(900,VIRTUAL); auto *sibling=read_object(901,VIRTUAL);
 assert(container && nested_copy && blocked && sibling);
 obj_to_obj(blocked,container); obj_to_obj(sibling,container);
 clone_container_obj(nested_copy,container);
 assert(nested_copy->contains && !IS_ARTIFACT(nested_copy->contains) && !nested_copy->contains->next_content);
 extract_obj(container,FALSE); extract_obj(nested_copy,FALSE);
 assert(artifact_is_canonical(first) && artifact_rows.at(900).timer==9999 && artifact_binds.at(900).owner_pid==55);
 auto *ordinary=read_object(901,VIRTUAL); assert(ordinary);
 ordinary->extra_flags=ITEM_ARTIFACT; assert(!clone_obj(ordinary)); ordinary->extra_flags=0;
 auto *copy=clone_obj(ordinary); assert(copy && !IS_ARTIFACT(copy));
 extract_obj(copy,FALSE); extract_obj(ordinary,FALSE); extract_obj(first,FALSE);
 assert(artifact_rows.at(900).identity_state==artifact_identity_state::present &&
  !artifact_rows.at(900).live_object && !read_object_for_creation(900,VIRTUAL) && errno==EEXIST);
 assert(stage(false));
 assert(!read_object_for_creation(902,VIRTUAL) && errno==ENODATA);
 assert(stage(true)); artifact_save_pulse(true); drain();
 auto *second=read_object_for_creation(902,VIRTUAL); assert(second);
 second->loc_p=LOC_ROOM; second->loc.room=0; artifact_object_placed(second);
 artifact_save_pulse(true); drain(); extract_obj(second,TRUE);
 assert(artifact_rows.at(902).identity_state==artifact_identity_state::retired &&
  !artifact_rows.at(902).live_object);
 auto *replacement=read_object_for_creation(902,VIRTUAL); assert(replacement);
 replacement->loc_p=LOC_ROOM; replacement->loc.room=0; artifact_object_placed(replacement);
 artifact_save_pulse(true); drain(); // old retirement ACKs cannot release the replacement
 assert(artifact_rows.at(902).canonical_item_uid==replacement->obj_uid && artifact_is_canonical(replacement));
 assert(!read_object_for_creation(902,VIRTUAL) && errno==EEXIST);
 extract_obj(replacement,FALSE);
 assert(!object_list && !pool.objs_used);
 reset_matrix(prototypes);
 artifact_rows.at(902).timer=1234; artifact_binds[902]={77,88};
 const auto prior_uid=artifact_rows.at(902).canonical_item_uid;
 const auto prior_state=artifact_rows.at(902).identity_state;
 {
  artifact_restore_scope restoring; assert(restoring);
  auto *staged=read_object_for_creation(902,VIRTUAL); assert(staged);
  staged->loc_p=LOC_ROOM; staged->loc.room=0; artifact_object_placed(staged);
  artifact_update_sql(902,true,ARTIFACT_ON_PC,55,9999,ARTIFACT_MAJOR);
  artifact_bind_store(902,55,66); assert(artifact_binds_reset(-1));
  artifact_save_pulse(true); assert(writes.empty());
  extract_obj(staged,FALSE);
 } // a later world-step failure restores the complete pre-recovery authority
 assert(artifact_rows.at(902).canonical_item_uid==prior_uid && artifact_rows.at(902).identity_state==prior_state &&
  artifact_rows.at(902).timer==1234 && artifact_binds.at(902).owner_pid==77 && artifact_binds.at(902).timer==88 && writes.empty());
 P_obj committed=nullptr;
 {
  artifact_restore_scope restoring; assert(restoring);
  artifact_restore_scope nested; assert(!nested && errno==EBUSY);
  committed=read_object_for_creation(902,VIRTUAL); assert(committed);
  committed->loc_p=LOC_ROOM; committed->loc.room=0; artifact_object_placed(committed);
  artifact_update_sql(902,true,ARTIFACT_ON_PC,55,9999,ARTIFACT_MAJOR);
  artifact_bind_store(902,55,66); artifact_save_pulse(true); assert(writes.empty());
  restoring.commit();
 }
 assert(artifact_is_canonical(committed) && artifact_rows.at(902).timer==9999 && artifact_binds.at(902).owner_pid==55);
 artifact_save_pulse(true); assert(!writes.empty()); drain();
 extract_obj(committed,FALSE); assert(!object_list && !pool.objs_used);
 assert(stage(true)); artifact_save_pulse(true); drain();
 artifact_rows.at(902).timer=4321; artifact_binds[902]={77,99};
 const auto wrapper_uid=artifact_rows.at(902).canonical_item_uid;
 const auto wrapper_state=artifact_rows.at(902).identity_state;
 fail_materialization=true;
 assert(!world_recovery_restore_with_floor(nullptr,0,300,0,nullptr,nullptr,0,nullptr));
 assert(!materializing && !object_list && writes.empty() && artifact_rows.at(902).canonical_item_uid==wrapper_uid &&
  artifact_rows.at(902).identity_state==wrapper_state && artifact_rows.at(902).timer==4321 && artifact_binds.at(902).owner_pid==77);
 fail_materialization=false;
 world_recovery_header header={};
 assert(world_recovery_restore_with_floor(nullptr,0,300,0,nullptr,nullptr,0,&header));
 assert(!materializing && last_materialized && artifact_is_canonical(last_materialized) &&
  artifact_rows.at(902).timer==9876 && artifact_binds.at(902).owner_pid==88 && header.sequence==123);
 artifact_save_pulse(true); drain(); extract_obj(last_materialized,FALSE); assert(!object_list && !pool.objs_used);
 // Legacy reconstruction keeps the canonical UID and registers one live body.
 auto &legacy=artifact_rows.at(900);
 legacy={true,ARTIFACT_ONGROUND,2300,7777,ARTIFACT_MAJOR};
 legacy.identity_state=artifact_identity_state::present; legacy.canonical_item_uid=80001;
 artifact_binds[900]={55,666};
 addOnGroundArtis_sql(); addOnGroundArtis_sql();
 assert(object_list && !object_list->next && object_list->obj_uid==80001 && legacy.live_object==object_list);
 assert(legacy.timer==7777 && artifact_binds.at(900).owner_pid==55);
 extract_obj(object_list,TRUE); assert(legacy.identity_state==artifact_identity_state::retired);
 artifact_save_pulse(true); drain();
 char_data holder={}; npc_only_data npc={}; holder.only.npc=&npc;
 holder.specials.act=ACT_ISNPC; npc.R_num=0; mob_indexes[0].virtual_number=2000; character_list=&holder;
 legacy={true,ARTIFACT_ON_NPC,2000,7777,ARTIFACT_MAJOR};
 legacy.identity_state=artifact_identity_state::present; legacy.canonical_item_uid=80002;
 addOnMobArtis_sql(); addOnMobArtis_sql();
 assert(holder.carrying && !holder.carrying->next_content && holder.carrying->obj_uid==80002 && legacy.live_object==holder.carrying);
 extract_obj(holder.carrying,FALSE); assert(!legacy.live_object && legacy.identity_state==artifact_identity_state::present);
 // Player/recovery hydration assigns a saved UID before the normal placement hook.
 auto *hydrated=read_object(900,VIRTUAL); hydrated->obj_uid=80002;
 player_item_snapshot saved={}; saved.equipment_slot=0;
 attach_loaded_inventory(&holder,{hydrated},{0},{saved});
 assert(legacy.live_object==hydrated);
 player_load_items_discard(&holder);
 assert(!legacy.live_object && legacy.identity_state==artifact_identity_state::present && !object_list);
 hydrated=read_object(900,VIRTUAL); hydrated->obj_uid=80002;
 attach_loaded_inventory(&holder,{hydrated},{0},{saved});
 assert(legacy.live_object==hydrated && !legacy.creation_pending && legacy.timer==7777);
 auto *duplicate=read_object(900,VIRTUAL); duplicate->obj_uid=80002; obj_to_char(duplicate,&holder);
 assert(legacy.live_object==hydrated); extract_obj(duplicate,TRUE);
 assert(legacy.identity_state==artifact_identity_state::present);
 artifact_binds.erase(900); // a legacy canonical row need not have a soul row
 extract_obj(hydrated,TRUE); assert(legacy.identity_state==artifact_identity_state::retired && !legacy.live_object);
 artifact_save_pulse(true); drain(); character_list=nullptr;
 assert(!object_list && !pool.objs_used);
 std::cout<<"actual artifact constructor/clone/extraction admission: PASS\n";
}
"""
source=HARNESS.replace("// PLAYER_ATTACHMENT", "\n".join(extract_function("player_load_items.c", sig) for sig in ("void attach_loaded_inventory(", "void clear_item_uids(", "void player_load_items_discard(")))
source=source.replace("// CONSTRUCTORS","\n".join(extract_function("db.c",sig) for sig in (
 "static P_obj instantiate_object_template_impl(","P_obj instantiate_object_template(const object_template &prototype)",
 "P_obj read_object_for_creation(","P_obj read_object(int nr, int type)")))
source=source.replace("// EXTRACTION",extract_function("handler.c","void extract_obj(P_obj obj, int gone_for_good)"))
source=source.replace("// CLONE",extract_function("actwiz.c","struct obj_data *clone_obj(P_obj obj)")+"\n"+extract_function("actwiz.c","void clone_container_obj(P_obj to, P_obj obj)"))
reset=extract_function("db.c","void reset_zone(int zone, int force_item_repop)")
parts=[]
for letter in "OPGE":
 start=reset.index("case '"+letter+"':")
 after=start+len("case 'X':")
 following=re.search(r"(?m)^\s*(?:case |default:)", reset[after:])
 assert following
 parts.append(reset[start:after+following.start()])
reset_harness=r"""
int reset_command(reset_com &command,P_char mob,int respawn,int force_item_repop) {
 int last_cmd=1,ival=0,zone=0; P_obj obj=nullptr,obj_to=nullptr;
 #define ZCMD command
 switch(command.command) {
 // RESET_CASES
 }
 #undef ZCMD
 return last_cmd;
}
void reset_matrix(const std::vector<artifact_population_template> &original) {
 auto prototypes=original; prototypes[0].vnum=51005; indexes[0].virtual_number=51005;
 for(int respawn=0;respawn<=2;++respawn) for(int force=0;force<=2;++force)
 for(char kind: {'O','P','G','E'}) for(int artifact=0;artifact<2;++artifact) {
  booting=true; assert(artifacts_stage_population({},prototypes,true)); booting=false;
  artifact_save_pulse(true); drain();
  char_data mob={}; npc_only_data npc={}; mob.only.npc=&npc; mob.specials.act=ACT_ISNPC; mob.in_room=0;
  if(kind=='P') { auto *bag=read_object_for_creation(903,VIRTUAL); assert(bag); obj_to_room(bag,0); }
  reset_com command={kind,false,artifact ? 0 : 1,3,kind=='P' ? 3 : kind=='E' ? 12 : 0,100};
  for(int attempt=0;attempt<4;++attempt) {
   const auto before=indexes[artifact ? 0 : 1].number;
   const auto completed=reset_command(command,&mob,respawn,force);
   if(artifact && before) assert(!completed);
  }
  const int expected=artifact ? ((respawn==2 || (respawn==1 && force==2)) ? 1 : 0) : (force ? 4 : 3);
  if(indexes[artifact ? 0 : 1].number!=expected || command.command!=kind)
   std::cerr<<"reset "<<kind<<" respawn="<<respawn<<" force="<<force<<" artifact="<<artifact<<" actual="<<indexes[artifact ? 0 : 1].number<<" expected="<<expected<<" command="<<command.command<<'\n';
  assert(indexes[artifact ? 0 : 1].number==expected && command.command==kind);
  if(artifact && expected) assert(artifact_rows.at(51005).identity_state==artifact_identity_state::present);
  while(object_list) extract_obj(object_list,TRUE);
  artifact_save_pulse(true); drain();
  assert(!pool.objs_used && !rooms[0].contents);
 }
 booting=true; assert(artifacts_stage_population({},prototypes,true)); booting=false;
 artifact_save_pulse(true); drain();
 const auto previous_state=artifact_rows.at(51005).identity_state;
 const auto previous_uid=artifact_rows.at(51005).canonical_item_uid;
 auto *wrong_parent=read_object_for_creation(901,VIRTUAL); assert(wrong_parent); obj_to_room(wrong_parent,0);
 reset_com refused={'P',false,0,3,1,100};
 for(int attempt=0;attempt<3;++attempt) reset_command(refused,nullptr,2,2);
 assert(!indexes[0].number && !artifact_rows.at(51005).creation_pending && artifact_rows.at(51005).canonical_item_uid==previous_uid);
 extract_obj(wrong_parent,FALSE);
 reset_com missing={'P',false,0,3,3,100};
 for(int attempt=0;attempt<3;++attempt) reset_command(missing,nullptr,2,2);
 assert(!object_list && !artifact_rows.at(51005).creation_pending &&
  artifact_rows.at(51005).identity_state==previous_state && artifact_rows.at(51005).canonical_item_uid==previous_uid && writes.empty());
 for(char kind: {'G','E'}) {
  reset_com absent={kind,false,0,3,12,100};
  for(int attempt=0;attempt<3;++attempt) reset_command(absent,nullptr,2,2);
  assert(!object_list && !artifact_rows.at(51005).creation_pending &&
   artifact_rows.at(51005).canonical_item_uid==previous_uid && writes.empty());
 }
 indexes[0].virtual_number=900;
}
""".replace("// RESET_CASES","\n".join(parts))
source=source.replace("// NEST_CHECK",extract_function("handler.c","bool obj_can_nest("))
source=source.replace("// RESET",reset_harness)
restore_support=r"""
// Keep the actual restore coordinator; world planning/materialization I/O is
// controlled here, while its callback uses the real artifact/constructor code.
struct recovery_plan {
 std::vector<world_recovery_authority_item> authority_items;
 std::vector<int> mobs,objects;
 world_recovery_header header={};
};
bool fail_materialization=false,materializing=false;
P_obj last_materialized=nullptr;
bool build_recovery_plan(const unsigned char *,size_t,int,uint64_t,recovery_plan *plan) { plan->header.sequence=123; return true; }
bool floor_record_repeats(const recovery_plan &,const std::vector<unsigned char> &) { return false; }
bool add_object_record(recovery_plan *,const unsigned char *,size_t) { return false; }
bool leave_out_owned_trees(recovery_plan *) { return true; }
bool world_recovery_decode_record(world_recovery_record_type,const unsigned char *,size_t,std::vector<unsigned char> *) { return false; }
bool sql_persistence_reconcile_world_recovery_items(const world_recovery_authority_item *,size_t,item_ownership_runtime_entry *,size_t) { return true; }
void redis_floor_runtime_set_materializing(bool active) { materializing=active; }
bool materialize_plan(const recovery_plan &,const std::vector<item_ownership_runtime_entry> &) {
 last_materialized=read_object_for_creation(902,VIRTUAL); assert(last_materialized);
 last_materialized->loc_p=LOC_ROOM; last_materialized->loc.room=0; artifact_object_placed(last_materialized);
 artifact_update_sql(902,true,ARTIFACT_ON_PC,88,9876,ARTIFACT_MAJOR); artifact_bind_store(902,88,123);
 artifact_save_pulse(true); assert(writes.empty());
 if(fail_materialization) { extract_obj(last_materialized,FALSE); last_materialized=nullptr; return false; }
 return true;
}
"""
source=source.replace("// RESTORE_WRAPPER",restore_support+extract_function("world_recovery_pipeline.c","bool world_recovery_restore_with_floor("))


output=ROOT/"bin/tests"; output.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix="artifact-creation-",dir=output) as directory:
 cpp=Path(directory)/"creation.cpp"; binary=Path(directory)/"creation"; cpp.write_text(source)
 subprocess.run(["g++","-std=c++20","-Wall","-Wextra","-Werror","-D__NO_MYSQL__",
  "-Isrc","-Isrc/no_mysql","-ffunction-sections","-fdata-sections","-fsanitize=address,undefined",
  "-fno-sanitize-recover=all","-fno-omit-frame-pointer",str(cpp),"src/guild/artifact_population.c",
  "src/item/item_transfer_command.c",str(HARNESS_STUBS),"-Wl,--gc-sections","-lcrypto","-pthread",
  "-o",str(binary)],cwd=ROOT,check=True)
 subprocess.run([str(binary)],cwd=ROOT,check=True,timeout=30)
