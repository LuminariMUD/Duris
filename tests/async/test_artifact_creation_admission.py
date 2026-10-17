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
#include "player/player_load_items.h"
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <iostream>
index_data indexes[4] = {};
index_data mob_indexes[1] = {};
P_index mob_index=mob_indexes;
P_char character_list=nullptr;
int real_room(int vnum) { return vnum==2300 ? 0 : -1; }
room_data rooms[2] = {};
const char *equipment_types[CUR_MAX_WEAR+1] = {};
P_room world=rooms;
extern const int top_of_world=1;
P_index obj_index = indexes;
P_obj object_list = nullptr;
mm_ds pool = {};
mm_ds *dead_obj_pool = &pool;
const int top_of_objt = 3;
static unsigned long long next_uid=10000;
static size_t procedures=0, floors=0;
static uint64_t expected_procedure_uid=0;
static bool drop_swap_artifact_flag=false, renew_swap_source=false;
static int swap_placement_fault=0;
static size_t removed_wear_links=0;
static std::vector<uint64_t> removed_floor_uids;
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
void str_free(const char *text) { free(const_cast<char *>(text)); }
void *__malloc(size_t size,const char *,const char *,int) { return calloc(1,size); }
void __free(void *memory,const char *,int) { free(memory); }
int strn_cmp(const char *left,const char *right,unsigned int size) { return strncasecmp(left,right,size); }
int number(int from,int) { return from; }
int real_object(const int vnum) { return vnum>=900 && vnum<=903 ? vnum-900 : -1; }
int periodic(P_obj object,P_char,int,char *) {
 if(expected_procedure_uid) assert(object->obj_uid==expected_procedure_uid && IS_ARTIFACT(object) && !artifact_is_canonical(object));
 if(OBJ_VNUM(object)==902 && drop_swap_artifact_flag) object->extra_flags&=~ITEM_ARTIFACT;
 if(OBJ_VNUM(object)==902 && renew_swap_source) artifact_rows.at(900).timer+=60;
 ++procedures; return 0;
}
int item_switch(P_obj,P_char,int,char *) { return 0; }
void event_object_proc(P_char,P_char,P_obj,void *) {}
void event_random_exit(P_char,P_char,P_obj,void *) {}
nevent_schedule_result add_event(event_func,int,P_char,P_char,P_obj,int,const void *,int) { return {}; }
int proclibObj_add(P_obj,char *,char *) { return 0; }
int FillMasterSpellBook(P_obj) { return 0; }
void convertObj(P_obj) {}
void world_recovery_capture_forget_object(P_obj) {}
static std::map<P_obj,unsigned> pending_actions;
void item_actions_source_leaving(P_obj object) { pending_actions.erase(object); }
void ferry_forget_object(P_obj) {}
void redis_remove_floor_drop(unsigned long uid) { ++floors; removed_floor_uids.push_back(uid); }
void disarm_obj_nevents(P_obj,event_func_type) {}
void remove_linked_object(P_obj) {}
void free_obj(P_obj object) { mm_release(dead_obj_pool,object); }
void unlink_content(P_obj object,P_obj *head) {
 for(;*head && *head!=object;head=&(*head)->next_content) {}
 if(*head==object) *head=object->next_content;
 object->next_content=nullptr; object->loc_p=LOC_NOWHERE; object->loc.room=NOWHERE;
}
void obj_from_room(P_obj object) { unlink_content(object,&rooms[object->loc.room].contents); }
void obj_from_char(P_obj object) { auto *owner=object->loc.carrying; unlink_content(object,&owner->carrying); }
void obj_from_obj(P_obj object) { auto *parent=object->loc.inside; unlink_content(object,&parent->contains); }
void all_affects(P_char,int) {}
static void mark_char_or_owner_dirty(P_char) {}
int char_light(P_char) { return 0; }
int room_light(int,int) { return 0; }
// ACTUAL_UNEQUIP
void place_tree(P_obj object) {
 for(P_obj child=object->contains;child;child=child->next_content) place_tree(child);
 artifact_object_placed(object);
}
// Exercise the void placement contract: refusal, an alternate destination, or destruction.
static bool intercept_swap_placement(P_obj object) {
 if(object->R_num!=2 || !swap_placement_fault) return false;
 const int fault=swap_placement_fault;
 if(fault==2) { swap_placement_fault=0; obj_to_room(object,1); swap_placement_fault=fault; }
 else if(fault==3) extract_obj(object,TRUE);
 return true;
}
void obj_to_room(P_obj object,int room) {
 if(intercept_swap_placement(object)) return;
 object->loc_p=LOC_ROOM; object->loc.room=room;
 object->next_content=rooms[room].contents; rooms[room].contents=object; place_tree(object);
}
void obj_to_char(P_obj object,P_char mob) {
 if(intercept_swap_placement(object)) return;
 object->loc_p=LOC_CARRIED; object->loc.carrying=mob;
 object->next_content=mob->carrying; mob->carrying=object; artifact_object_placed(object);
}
void obj_to_obj(P_obj object,P_obj parent) {
 if(intercept_swap_placement(object)) return;
 object->loc_p=LOC_INSIDE; object->loc.inside=parent;
 object->next_content=parent->contains; parent->contains=object;
 P_obj root=parent; while(OBJ_INSIDE(root)) root=root->loc.inside;
 if(!OBJ_NOWHERE(root)) place_tree(object);
}
void equip_char(P_char mob,P_obj object,int slot,int) {
 if(intercept_swap_placement(object)) return;
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
float get_property(const char *,double fallback) { return fallback; }
int get_property(const char *,int fallback) { return fallback; }
int real_room0(const int) { return 0; }
int itemvalue(P_obj) { return 1; }
bool item_load_check(P_obj,int,int) { return true; }
void enhance_on_npc_item_reset_skipped(P_char,P_obj) {}
int shop_keeper(P_char,P_char,int,char *) { return 0; }
object_template parse_object_template(int index) {
 object_template prototype; prototype.R_num=index; prototype.extra_flags=(index==1 || index==3) ? 0 : ITEM_ARTIFACT;
 prototype.type=index==3 ? ITEM_CONTAINER : 0; prototype.wear_flags=ITEM_TAKE;
 return prototype;
}
static std::string command_output;
void send_to_char(const char *text,P_char) { command_output+=text; }
void send_to_char_f(P_char,const char *format,...) {
 char text[MAX_STRING_LENGTH]; va_list args; va_start(args,format); std::vsnprintf(text,sizeof(text),format,args); va_end(args); command_output+=text;
}
char *one_argument(const char *input,char *word) {
 while(*input && isspace(static_cast<unsigned char>(*input))) ++input;
 while(*input && !isspace(static_cast<unsigned char>(*input))) *word++=*input++;
 *word=0; while(*input && isspace(static_cast<unsigned char>(*input))) ++input;
 return const_cast<char *>(input);
}
bool is_abbrev(const char *word,const char *full) { return *word && !strncasecmp(word,full,strlen(word)); }
const object_template *find_object_template(int vnum) {
 static bool ready=false; static object_template templates[4];
 if(!ready) { for(int index=0;index<4;++index) templates[index]=parse_object_template(index); ready=true; }
 const int index=real_object(vnum); return index<0 ? nullptr : &templates[index];
}
static size_t offline_released=0, offline_saves=0, corpse_saves=0, expiry_retries=0;
static bool owner_online=false, owner_loading=false, offline_save_allowed=true;
static std::vector<std::function<void(P_char)>> offline_callbacks;
char *get_player_name_from_pid(int pid) { return pid==77 ? const_cast<char *>("Offline") : nullptr; }
bool is_pid_online(int,bool) { return owner_online; }
bool player_load_pipeline_pid_pending(int) { return owner_loading; }
bool player_load_offline(const char *,bool,std::function<void(P_char)> done) { offline_callbacks.push_back(std::move(done)); return true; }
bool player_load_offline_for(P_char staff,const char *,bool,std::function<void(P_char,P_char)> done) {
 offline_callbacks.push_back([staff,done=std::move(done)](P_char owner) { done(staff,owner); }); return true;
}
static bool inspect_swap_snapshot=false;
int writeCharacter(P_char owner,int,int) {
 ++offline_saves;
 if(inspect_swap_snapshot) assert(!artifact_on_owner(owner,900) && artifact_on_owner(owner,902));
 return offline_save_allowed ? 1 : 0;
}
void clear_links(P_char,P_obj,int flag) { assert(flag==LNKFLG_BREAK_REMOVE); ++removed_wear_links; }
void writeCorpse(P_obj) { ++corpse_saves; }
void do_shout(P_char,char *,int) {}
void free_char(P_char owner) {
 assert(!owner->carrying); for(auto *object:owner->equipment) assert(!object); ++offline_released;
}
void nevent_periodic_continue_after(unsigned long long) {}
void nevent_periodic_retry_after(unsigned long long,const char *) { ++expiry_retries; }
void balance_affects(P_char) {}
// PLAYER_ATTACHMENT
// CONSTRUCTORS
// EXTRACTION
// RECOVERY_TREE
// CLONE
// NEST_CHECK
// RESET
// RESTORE_WRAPPER
// RECOVERY_CASES
// MAINTENANCE_CASES
// SWAP_CASES
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
 extract_obj(probe,FALSE); assert(fail_invalidation && artifact_rows.at(900).pending==artifact_pending::none && !pool.objs_used);
 fail_invalidation=false; procedures=0;
 auto *first=read_object_for_creation(900,VIRTUAL);
 assert(first && procedures==1 && pool.objs_used==1 && indexes[0].number==1);
 assert(artifact_rows.at(900).pending==artifact_pending::creation && writes.empty());
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
 assert(artifact_is_canonical(first) && artifact_rows.at(900).pending==artifact_pending::none &&
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
 recovery_cases(prototypes);
 offline_expiry_cases();
 maintenance_inspection_cases();
 swap_admission_cases();
 // Legacy reconstruction keeps the canonical UID and registers one live body.
 auto &legacy=artifact_rows[900];
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
 assert(legacy.live_object==hydrated && legacy.pending==artifact_pending::none && legacy.timer==7777);
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
source=HARNESS.replace("// PLAYER_ATTACHMENT", "\n".join(extract_function("player_load_items.c", sig) for sig in ("void attach_loaded_inventory(", "void clear_item_uids(", "void player_load_items_discard(", "unsigned int player_load_items_qualify(")))
source=source.replace("// CONSTRUCTORS","\n".join(extract_function("db.c",sig) for sig in (
 "static P_obj instantiate_object_template_impl(","P_obj instantiate_object_template(const object_template &prototype)",
 "P_obj read_object_for_creation(","P_obj read_object_for_recovery(","P_obj read_object(int nr, int type)")))
source=source.replace("// ACTUAL_UNEQUIP",extract_function("handler.c","P_obj unequip_char("))
source=source.replace("// EXTRACTION",extract_function("handler.c","void extract_obj(P_obj obj, int gone_for_good)")+"\n"+extract_function("handler.c","P_obj find_live_object(P_obj expected, uint64_t uid)"))
source=source.replace("// RECOVERY_TREE",extract_function("world_recovery_pipeline.c","P_obj find_object_uid(")+"\n"+extract_function("world_recovery_pipeline.c","struct planned_object")+";\n"+
 extract_function("world_recovery_pipeline.c","void replace_object_text(")+"\n"+
 extract_function("world_recovery_pipeline.c","P_obj materialize_object("))

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
 assert(!indexes[0].number && artifact_rows.at(51005).pending==artifact_pending::none && artifact_rows.at(51005).canonical_item_uid==previous_uid);
 extract_obj(wrong_parent,FALSE);
 reset_com missing={'P',false,0,3,3,100};
 for(int attempt=0;attempt<3;++attempt) reset_command(missing,nullptr,2,2);
 assert(!object_list && artifact_rows.at(51005).pending==artifact_pending::none &&
  artifact_rows.at(51005).identity_state==previous_state && artifact_rows.at(51005).canonical_item_uid==previous_uid && writes.empty());
 for(char kind: {'G','E'}) {
  reset_com absent={kind,false,0,3,12,100};
  for(int attempt=0;attempt<3;++attempt) reset_command(absent,nullptr,2,2);
  assert(!object_list && artifact_rows.at(51005).pending==artifact_pending::none &&
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
bool add_object_record(recovery_plan *,const unsigned char *,size_t,artifact_payload_domain,uint64_t) { return false; }
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
recovery_cases=r"""
void recovery_cases(const std::vector<artifact_population_template> &prototypes) {
 assert(!object_list && !pool.objs_used); artifact_rows.clear(); artifact_binds.clear();
 artifact_payload_projection saved={}; saved.domain=artifact_payload_domain::copyover_ground;
 saved.owner_reference=2300; saved.owner_context=44; saved.row_id=1;
 saved.item_uid=4242; saved.payload_root_item_uid=4242; saved.vnum=900;
 saved.extra_flags=ITEM_ARTIFACT; saved.extra_flags_present=true; saved.quantity=1;
 saved.payload_owner={item_owner_type::room,2300,0}; saved.custody_examined=true;
 auto &prior=artifact_rows[900]; prior.canonical_item_uid=4242;
 prior.identity_state=artifact_identity_state::present; prior.timer=4567;
 prior.locType=ARTIFACT_ONGROUND; prior.location=2300; prior.owned=true;
 artifact_binds[900]={77,88};
 const auto stage_saved=[&](const std::vector<artifact_payload_projection> &items,bool complete) {
  booting=true; const bool result=artifacts_stage_population(items,prototypes,complete); booting=false;
  assert(result); artifact_save_pulse(true); drain();
 };
 stage_saved({saved},false); // known qualified UID survives unrelated incomplete sources
 assert(artifact_rows.at(900).canonical_payloads.size()==1);
 const auto uid_cursor=next_uid;
 for(int variant=0;variant<11;++variant) {
  auto wrong=saved;
  switch(variant) {
  case 0: wrong.domain=artifact_payload_domain::player; break;
  case 1: ++wrong.owner_context; break;
  case 2: ++wrong.owner_reference; break;
  case 3: ++wrong.payload_root_item_uid; break;
  case 4: ++wrong.parent_item_uid; break;
  case 5: wrong.extra_flags |= ITEM_GLOW; break;
  case 6: ++wrong.item_uid; break;
  case 7: wrong.role=artifact_payload_role::history; break;
  case 8: wrong.source_quarantined=true; break;
  case 9: wrong.owner_context=0; break;
  case 10: wrong.extra_flags=0; break;
  }
  const auto count=procedures;
  assert(!read_object_for_recovery(wrong) && errno==ENODATA);
  assert(procedures==count && !pool.objs_used && !object_list && next_uid==uid_cursor && writes.empty());
 }
 expected_procedure_uid=4242;
 auto *first=read_object_for_recovery(saved); assert(first && first->obj_uid==4242 && next_uid==uid_cursor);
 expected_procedure_uid=0;
 assert(artifact_rows.at(900).pending==artifact_pending::recovery && !artifact_is_canonical(first));
 const auto count=procedures;
 assert(!read_object_for_recovery(saved) && errno==EEXIST && procedures==count);
 assert(!read_object_for_creation(900,VIRTUAL) && errno==EEXIST);
 extract_obj(first,FALSE);
 assert(!object_list && !pool.objs_used && artifact_rows.at(900).timer==4567 &&
  artifact_binds.at(900).owner_pid==77 && artifact_binds.at(900).timer==88 && writes.empty());
 first=read_object_for_recovery(saved); assert(first); obj_to_room(first,0);
 assert(artifact_is_canonical(first) && artifact_rows.at(900).timer==4567 &&
  artifact_rows.at(900).owned && artifact_binds.at(900).owner_pid==77 && writes.empty());
 auto *copy=read_object(900,VIRTUAL); assert(copy); copy->obj_uid=4242;
 const auto floor_count=floors; extract_obj(copy,TRUE);
 assert(floors==floor_count && artifact_is_canonical(first) && artifact_rows.at(900).timer==4567);
 extract_obj(first,FALSE);
 assert(!artifact_rows.at(900).live_object && artifact_rows.at(900).canonical_item_uid==4242);
 auto &row=artifact_rows.at(900); row.identity_state=artifact_identity_state::retired;
 assert(!read_object_for_recovery(saved) && errno==ENODATA); row.identity_state=artifact_identity_state::present;
 // Real location tracking must preserve an unowned recovered timer, including zero.
 for(time_t timer:{time_t{0},time_t{4567}}) {
  artifact_rows.at(900).owned=false; artifact_rows.at(900).timer=timer;
  { artifact_restore_scope group; assert(group);
    first=read_object_for_recovery(saved); assert(first); obj_to_room(first,0);
    artifact_update_location_sql(first);
    assert(artifact_rows.at(900).timer==timer && artifact_binds.at(900).owner_pid==77);
    extract_obj(first,FALSE);
    artifact_update_sql(900,false,ARTIFACT_ONGROUND,2300,timer,ARTIFACT_MAJOR);
    assert(artifact_rows.at(900).timer==timer);
  }
  assert(writes.empty());
 }
 artifact_rows.at(900).owned=true; artifact_rows.at(900).timer=4567;
 // All three pinned sources require their own exact qualified locator.
 for(auto domain:{artifact_payload_domain::redis_generation,artifact_payload_domain::redis_floor,
                  artifact_payload_domain::copyover_ground}) {
  saved.domain=domain; stage_saved({saved},true);
  first=read_object_for_recovery(saved); assert(first); obj_to_room(first,0); extract_obj(first,FALSE);
  assert(artifact_rows.at(900).timer==4567 && artifact_binds.at(900).owner_pid==77);
 }
 // A saved artifact flag on an ordinary prototype is checked before its procedure too.
 auto converted=saved; converted.row_id=2; converted.vnum=901; converted.item_uid=5151;
 converted.payload_root_item_uid=5151;
 stage_saved({saved,converted},true); indexes[1].func.obj=periodic;
 first=read_object_for_recovery(converted); assert(first && IS_ARTIFACT(first));
 assert(!read_object_for_recovery(converted) && errno==EEXIST); extract_obj(first,FALSE);
 converted.extra_flags=0; converted.item_uid=6161; first=read_object_for_recovery(converted); assert(first && !IS_ARTIFACT(first));
 obj_to_room(first,0); extract_obj(first,FALSE); indexes[1].func.obj=nullptr;
 // The actual recovery tree body carries pinned provenance and commits descendants
 // only when its ordinary ancestor is placed. A refused child releases the root.
 auto parent=saved; parent.row_id=1; parent.vnum=901; parent.item_uid=70000;
 parent.payload_root_item_uid=70000; parent.extra_flags=0;
 saved.row_id=2; saved.parent_row_id=1; saved.parent_item_uid=70000; saved.payload_root_item_uid=70000;
 stage_saved({parent,saved},true);
 planned_object plan; plan.room_rnum=0; plan.room_vnum=2300;
 plan.source_domain=saved.domain; plan.source_context=saved.owner_context;
 world_recovery_item_snapshot outer={},inner={};
 outer.item_uid=70000; outer.root_item_uid=70000; outer.vnum=901; outer.type=ITEM_CONTAINER;
 inner.item_uid=4242; inner.root_item_uid=70000; inner.parent_item_uid=70000; inner.vnum=900;
 inner.extra_flags=ITEM_ARTIFACT; plan.items={outer,inner};
 ++plan.source_context; assert(!materialize_object(plan) && !object_list && !pool.objs_used);
 assert(artifact_rows.at(900).timer==4567 && artifact_binds.at(900).owner_pid==77 && writes.empty());
 --plan.source_context;
 { artifact_restore_scope transaction; assert(transaction);
   auto *tree=materialize_object(plan); assert(tree && tree->contains && artifact_is_canonical(tree->contains));
   assert(artifact_rows.at(900).timer==4567 && artifact_binds.at(900).owner_pid==77);
   extract_obj(tree,FALSE); // a later group step failed; all captures remain deferred
 }
 assert(!object_list && !pool.objs_used && !artifact_rows.at(900).live_object && writes.empty());
 auto *tree=materialize_object(plan); assert(tree && artifact_is_canonical(tree->contains));
 plan.existing_root=tree; const auto prior_procedures=procedures;
 artifact_rows.at(900).live_object=nullptr; // a legacy materializer already placed this exact UID
 assert(materialize_object(plan)==tree && artifact_is_canonical(tree->contains) && procedures==prior_procedures);
 ++plan.source_context; assert(!materialize_object(plan) && artifact_is_canonical(tree->contains));
 --plan.source_context;
 extract_obj(tree,FALSE); assert(!object_list && !pool.objs_used && writes.empty());
 // A captured corpse wrapper can contain a distinct logical custody root.
 parent.payload_owner=saved.payload_owner={item_owner_type::corpse,77,12};
 parent.custody_examined=parent.custody_found=parent.custody_required=parent.custody_owner_revision_found=true;
 saved.custody_examined=saved.custody_found=saved.custody_required=saved.custody_owner_revision_found=true;
 parent.custody={70000,70000,0,parent.payload_owner,1,1,901,item_custody_state::active};
 saved.custody={4242,4242,0,saved.payload_owner,1,1,900,item_custody_state::active};
 stage_saved({parent,saved},true); plan.existing_root=nullptr; plan.items[0].type=ITEM_CORPSE;
 tree=materialize_object(plan); assert(tree && tree->contains && artifact_is_canonical(tree->contains));
 assert(artifact_rows.at(900).timer==4567 && artifact_binds.at(900).owner_pid==77);
 extract_obj(tree,FALSE); assert(!object_list && !pool.objs_used && writes.empty());
 // A mutable player cut may legitimately move after the pinned boot source.
 auto player=saved; player.domain=artifact_payload_domain::player;
 player.owner_reference=77; player.owner_context=0; player.row_id=100;
 player.parent_row_id=0; player.parent_item_uid=0; player.payload_root_item_uid=4242;
 player.payload_owner={item_owner_type::player,77,0};
 player.custody_examined=player.custody_found=player.custody_owner_revision_found=true;
 player.custody={4242,4242,0,player.payload_owner,3,7,900,item_custody_state::active};
 stage_saved({player},true); item_ownership_runtime_reset();
 assert(!artifact_player_source_error(player));
 auto zero_revision=player; zero_revision.custody.owner_revision=0;
 assert(!artifact_player_source_error(zero_revision));
 const auto before_player_procedures=procedures;
 for(int kind=0;kind<12;++kind) {
  auto bad=player;
  switch(kind) {
   case 0: bad.custody_found=false; break;
   case 1: bad.custody.owner.id=88; break;
   case 2: bad.custody.state=item_custody_state::absent; break;
   case 3: bad.custody.vnum=901; break;
   case 4: bad.custody.item_revision=0; break;
   case 5: bad.custody_owner_revision_found=false; break;
   case 6: bad.parent_item_uid=10; break;
   case 7: bad.payload_root_item_uid=10; break;
   case 8: bad.parent_missing=true; break;
   case 9: bad.parent_owner_disagrees=true; break;
   case 10: bad.extra_flags=0; break;
   case 11: ++bad.item_uid; bad.payload_root_item_uid=bad.item_uid; bad.custody.item_uid=bad.item_uid; bad.custody.root_item_uid=bad.item_uid; break;
  }
  assert(artifact_player_source_error(bad));
  assert(!read_object_for_recovery(bad));
  assert(procedures==before_player_procedures && !object_list && !pool.objs_used);
 }
 auto current=player.custody; current.owner.id=88;
 assert(item_ownership_runtime_hydrate(current));
 assert(artifact_player_source_error(player)==ESTALE && !read_object_for_recovery(player));
 item_ownership_runtime_reset(); current=player.custody; ++current.item_revision;
 assert(item_ownership_runtime_hydrate(current));
 assert(artifact_player_source_error(player)==ESTALE);
 item_ownership_runtime_reset(); current=player.custody; ++current.owner_revision;
 assert(item_ownership_runtime_hydrate(current));
 assert(!artifact_player_source_error(player)); // unrelated owner-fence advance
 expected_procedure_uid=4242;
 first=read_object_for_recovery(player); assert(first && first->obj_uid==4242);
 assert(artifact_player_source_error(player)==EEXIST && !read_object_for_recovery(player));
 extract_obj(first,FALSE); // cancelled before placement: release only the tentative pointer
 assert(!artifact_rows.at(900).live_object && artifact_rows.at(900).canonical_item_uid==4242);
 first=read_object_for_recovery(player); assert(first); obj_to_room(first,0);
 assert(artifact_is_canonical(first) && artifact_rows.at(900).timer==4567 && artifact_binds.at(900).owner_pid==77);
 extract_obj(first,FALSE); expected_procedure_uid=0;
 assert(!artifact_rows.at(900).live_object && writes.empty());
 artifact_rows.at(900).identity_state=artifact_identity_state::retired;
 assert(artifact_player_source_error(player)==ENODATA && !read_object_for_recovery(player));
 artifact_rows.at(900).identity_state=artifact_identity_state::present;
 // A canonical UID cannot become ordinary by changing its payload vnum.
 auto foreign_vnum=player; foreign_vnum.vnum=901; foreign_vnum.extra_flags=0;
 assert(artifact_player_source_error(foreign_vnum));
 assert(!read_object_for_recovery(foreign_vnum) && !object_list && !pool.objs_used);
 foreign_vnum.domain=artifact_payload_domain::copyover_ground; foreign_vnum.owner_context=44;
 assert(!read_object_for_recovery(foreign_vnum) && !object_list && !pool.objs_used);
 auto ordinary=player; ordinary.extra_flags=0; ordinary.item_uid=99999;
 assert(!artifact_player_source_error(ordinary));
 first=read_object_for_recovery(ordinary); assert(first && !IS_ARTIFACT(first)); extract_obj(first,FALSE);
 player_load_result foreign_only={}; foreign_only.pid=77; foreign_only.outcome=player_load_outcome::applied;
 player_load_source_item raw={}; raw.row_id=100; raw.item_uid=raw.root_item_uid=4242; raw.bytes=50;
 raw.vnum=900; raw.quantity=1; raw.extra_flags=ITEM_ARTIFACT; raw.extra_flags_present=true;
 raw.custody_found=raw.custody_owner_revision_found=true; raw.custody=player.custody; raw.custody.owner.id=88;
 foreign_only.item_sources={raw};
 assert(!player_load_items_qualify(&foreign_only) && foreign_only.snapshot.items.empty() &&
  foreign_only.snapshot.retained_items.rows.size()==1 && foreign_only.snapshot.retained_items.rows[0].source_row_id==100);
 raw.vnum=901; raw.extra_flags=0; foreign_only.item_sources={raw}; foreign_only.snapshot.retained_items={};
 assert(!player_load_items_qualify(&foreign_only) && foreign_only.snapshot.retained_items.rows.size()==1);
 raw.item_uid=raw.root_item_uid=99999; raw.vnum=901; raw.extra_flags=0; raw.custody.item_uid=raw.custody.root_item_uid=99999; raw.custody.vnum=901;
 foreign_only.item_sources={raw}; foreign_only.snapshot.retained_items={};
 assert(!player_load_items_qualify(&foreign_only) && foreign_only.snapshot.retained_items.rows.empty());
 item_ownership_runtime_reset();
 std::cout<<"mutable player source/custody qualification, live reservation and cancellation: PASS\n";
 std::cout<<"source-qualified recovery factory and actual nested tree: PASS\n";
}
"""
recovery_cases += r"""
void offline_expiry_cases() {
 assert(!object_list && !pool.objs_used && writes.empty());
 artifact_rows.clear(); artifact_binds.clear(); item_ownership_runtime_reset();
 artifact_population_complete=true; artifact_cache_loaded=true;
 char_data owner={}; pc_only_data pc={}; owner.only.pc=&pc; pc.pid=77;
 owner.player.name=const_cast<char *>("Offline"); owner.player.level=51; owner.specials.act=PLR_MORTAL; owner.in_room=NOWHERE;
 auto &missing=artifact_rows[900]; missing.canonical_item_uid=70000;
 missing.identity_state=artifact_identity_state::present; missing.type=ARTIFACT_MAJOR; missing.owned=true;
 missing.locType=ARTIFACT_ON_PC; missing.location=77; missing.timer=1;
 artifact_binds[900]={77,88};
 auto before=offline_saves;
 poof_loaded_owner(900,77,&owner);
 assert(artifact_rows.at(900).owned && artifact_rows.at(900).timer==1 &&
        artifact_rows.at(900).canonical_item_uid==70000 && artifact_rows.at(900).identity_state==artifact_identity_state::present &&
        artifact_binds.at(900).owner_pid==77 && offline_saves==before && writes.empty());
 const auto make_nested=[&]() {
  assert(!object_list && !pool.objs_used && writes.empty());
  artifact_rows.clear(); artifact_binds.clear();
  auto &absent=artifact_rows[900]; absent.type=ARTIFACT_MAJOR; absent.identity_state=artifact_identity_state::absent;
  absent.population_reason=artifact_population_reason::complete; absent.removed=true;
  auto *object=read_object_for_creation(900,VIRTUAL); assert(object);
  auto *bag=read_object_for_creation(903,VIRTUAL); assert(bag); bag->value[0]=1000;
  obj_to_obj(object,bag); obj_to_char(bag,&owner); artifact_object_placed(object);
  auto &row=artifact_rows.at(900); row.owned=true; row.removed=false; row.locType=ARTIFACT_ON_PC;
  row.location=77; row.timer=1; artifact_binds[900]={77,88}; assert(artifact_expired(row));
  return object;
 };
 // Trusted holders are exempt even when legacy tracking still names another PID.
 for(int location=0;location<3;++location) {
  auto *held=make_nested(); auto *bag=held->loc.inside;
  if(location<2) {
   obj_from_obj(held); extract_obj(bag,FALSE); bag=nullptr;
   if(location==0) obj_to_char(held,&owner); else equip_char(&owner,held,0,TRUE);
  }
  auto &tracked=artifact_rows.at(900); tracked.location=88;
  artifact_save_pulse(true); drain();
  const auto count=pool.objs_used; const auto uid=held->obj_uid;
  owner.player.level=FORGER; owner.specials.act=0;
  updateArtis=false; event_artifact_check_poof_sql(nullptr,nullptr,nullptr,nullptr); updateArtis=true;
  event_artifact_check_poof_sql(nullptr,nullptr,nullptr,nullptr);
  assert(tracked.identity_state==artifact_identity_state::present && tracked.live_object==held &&
         tracked.canonical_item_uid==uid && tracked.timer==1 && pool.objs_used==count && writes.empty());
  owner.player.level=51; owner.specials.act=PLR_MORTAL;
  updateArtis=false; event_artifact_check_poof_sql(nullptr,nullptr,nullptr,nullptr); updateArtis=true;
  event_artifact_check_poof_sql(nullptr,nullptr,nullptr,nullptr);
  assert(tracked.identity_state==artifact_identity_state::retired && !tracked.live_object);
  if(bag) extract_obj(bag,FALSE);
  artifact_save_pulse(true); drain(); assert(!object_list && !pool.objs_used);
 }
 auto *object=make_nested(); const uint64_t saved_uid=object->obj_uid;
 assert(artifact_on_owner(&owner,900)==object);
 auto *alias=read_object(0,REAL); assert(alias); alias->obj_uid=saved_uid; obj_to_char(alias,&owner);
 const auto before_alias=pool.objs_used;
 poof_artifact(alias); assert(pool.objs_used==before_alias && artifact_rows.at(900).live_object==object && artifact_is_canonical(object));
 alias->obj_uid=0; extract_obj(alias,FALSE);
 artifact_rows.at(900).timer=time(nullptr)+1000; before=offline_saves;
 poof_loaded_owner(900,77,&owner); // a feed renewed the timer while the read was in flight
 assert(!object_list && !pool.objs_used && offline_saves==before &&
        artifact_rows.at(900).identity_state==artifact_identity_state::present &&
        artifact_rows.at(900).canonical_item_uid==saved_uid && artifact_binds.at(900).owner_pid==77);
 artifact_save_pulse(true); drain();
 object=make_nested(); const uint64_t retired_uid=object->obj_uid;
 poof_loaded_owner(900,77,&owner);
 assert(!object_list && !pool.objs_used && artifact_rows.at(900).identity_state==artifact_identity_state::retired &&
        artifact_rows.at(900).canonical_item_uid==retired_uid && !artifact_rows.at(900).owned &&
        !artifact_binds.at(900).owner_pid && offline_saves>before);
 artifact_save_pulse(true); drain();
 // A refused snapshot queue must not leak an unlisted temporary owner.
 object=make_nested(); const auto before_release=offline_released;
 offline_save_allowed=false; poof_loaded_owner(900,77,&owner); offline_save_allowed=true;
 assert(!object_list && !pool.objs_used && offline_released==before_release+1 &&
        artifact_rows.at(900).identity_state==artifact_identity_state::retired &&
        "temporary offline owner leaked after snapshot queue failure");
 artifact_save_pulse(true); drain();
 // A missing owner cannot clear its UID or starve a healthy later page.
 artifact_rows.clear(); artifact_binds.clear();
 auto &lost=artifact_rows[900]; lost.type=ARTIFACT_MAJOR; lost.identity_state=artifact_identity_state::present;
 lost.canonical_item_uid=80000; lost.owned=true; lost.locType=ARTIFACT_ON_PC; lost.location=99; lost.timer=1;
 auto &available=artifact_rows[902]; available.type=ARTIFACT_MAJOR; available.identity_state=artifact_identity_state::absent;
 available.population_reason=artifact_population_reason::complete; available.removed=true;
 auto *healthy=read_object_for_creation(902,VIRTUAL); assert(healthy); obj_to_room(healthy,0);
 artifact_rows.at(902).owned=true; artifact_rows.at(902).removed=false; artifact_rows.at(902).timer=1;
 updateArtis=false; event_artifact_check_poof_sql(nullptr,nullptr,nullptr,nullptr); updateArtis=true;
 const auto retries=expiry_retries;
 event_artifact_check_poof_sql(nullptr,nullptr,nullptr,nullptr);
 assert(expiry_retries==retries+1 && artifact_rows.at(900).canonical_item_uid==80000 && artifact_rows.at(900).owned);
 event_artifact_check_poof_sql(nullptr,nullptr,nullptr,nullptr);
 assert(!object_list && !pool.objs_used && artifact_rows.at(902).identity_state==artifact_identity_state::retired &&
        artifact_rows.at(900).identity_state==artifact_identity_state::present && artifact_rows.at(900).owned);
 artifact_save_pulse(true); drain();
 // A queued read stays singular; a failed result retains the canonical UID.
 artifact_rows.clear(); artifact_binds.clear();
 auto &offline=artifact_rows[900]; offline.type=ARTIFACT_MAJOR; offline.identity_state=artifact_identity_state::present;
 offline.canonical_item_uid=81000; offline.owned=true; offline.locType=ARTIFACT_ON_PC; offline.location=77; offline.timer=1;
 updateArtis=false; event_artifact_check_poof_sql(nullptr,nullptr,nullptr,nullptr); updateArtis=true;
 event_artifact_check_poof_sql(nullptr,nullptr,nullptr,nullptr);
 assert(offline_callbacks.size()==1);
 owner_loading=true;
 event_artifact_check_poof_sql(nullptr,nullptr,nullptr,nullptr); // wrap cursor
 event_artifact_check_poof_sql(nullptr,nullptr,nullptr,nullptr);
 assert(offline_callbacks.size()==1);
 offline_callbacks.front()(nullptr); offline_callbacks.clear(); owner_loading=false;
 assert(artifact_rows.at(900).owned && artifact_rows.at(900).canonical_item_uid==81000 && writes.empty());
 // Qualified absence may clear obsolete timer tracking, preserving configured availability.
 artifact_rows.clear(); artifact_binds.clear();
 auto &absent=artifact_rows[900]; absent.type=ARTIFACT_MAJOR; absent.identity_state=artifact_identity_state::absent;
 absent.population_reason=artifact_population_reason::complete; absent.owned=true; absent.timer=1;
 updateArtis=false; event_artifact_check_poof_sql(nullptr,nullptr,nullptr,nullptr); updateArtis=true;
 event_artifact_check_poof_sql(nullptr,nullptr,nullptr,nullptr);
 assert(!artifact_rows.at(900).owned && !artifact_rows.at(900).canonical_item_uid && artifact_rows.at(900).identity_state==artifact_identity_state::absent);
 artifact_save_pulse(true); drain();
 auto *fresh=read_object_for_creation(900,VIRTUAL); assert(fresh); obj_to_room(fresh,0); extract_obj(fresh,FALSE);
 artifact_save_pulse(true); drain();
 assert(!object_list && !pool.objs_used && offline_callbacks.empty());
 std::cout<<"offline canonical target, timer renewal, nested retirement and independent expiry pages: PASS\n";
}
"""
source=source.replace("// RECOVERY_CASES",recovery_cases)
source=source.replace("// MAINTENANCE_CASES", r"""
void maintenance_inspection_cases() {
 assert(!object_list && !pool.objs_used && writes.empty());
 artifact_rows.clear(); artifact_binds.clear();
 auto &row=artifact_rows[900]; row.canonical_item_uid=70000; row.identity_state=artifact_identity_state::present;
 row.type=ARTIFACT_MAJOR; row.owned=true; row.locType=ARTIFACT_ON_PC; row.location=77; row.timer=time(nullptr)+3600;
 artifact_binds[900]={77,88};
 char_data staff={}; pc_only_data pc={}; staff.only.pc=&pc; staff.player.level=OVERLORD;
 const auto cursor=next_uid; const auto effects=procedures;
 char invalid[]="set 900 not-a-number"; arti_timer_sql(&staff,invalid);
 assert(next_uid==cursor && procedures==effects && !object_list && !pool.objs_used &&
        "timer argument inspection constructed a gameplay object");
 char valid[]="set 900 1"; const auto before=time(nullptr); arti_timer_sql(&staff,valid);
 assert(row.timer>=before+60 && row.timer<=time(nullptr)+60 && row.canonical_item_uid==70000 &&
        artifact_binds.at(900).owner_pid==77 && artifact_binds.at(900).timer==88);
 assert(next_uid==cursor && procedures==effects && !object_list && !pool.objs_used);
 artifact_save_pulse(true); drain();
 const auto before_wrapped_vnum=row.timer;
 char wrapped_vnum[]="set 4294968196 10"; arti_timer_sql(&staff,wrapped_vnum);
 assert(row.timer==before_wrapped_vnum && writes.empty() && "overflowing vnum updated a different record");
 row.timer=time(nullptr)+3600;
 char enormous[]="add 900 2147483647"; arti_timer_sql(&staff,enormous);
 assert(row.timer<=time(nullptr)+ARTIFACT_BLOOD_DAYS*SECS_PER_REAL_DAY && row.timer>time(nullptr));
 artifact_save_pulse(true); drain();
 row.timer=INT64_MAX;
 char subtract[]="subtract 900 9223372036854775807"; const auto subtract_start=time(nullptr); arti_timer_sql(&staff,subtract);
 assert(row.timer>=subtract_start+60 && row.timer<=time(nullptr)+60);
 artifact_save_pulse(true); drain();
 row.timer=INT64_MIN;
 char cancel_extreme[]="add 900 153722867280912931"; const auto cancel_start=time(nullptr);
 arti_timer_sql(&staff,cancel_extreme);
 assert(row.timer>=cancel_start+60 && row.timer<=time(nullptr)+60 && "extreme addition saturated before accounting for its negative epoch");
 artifact_save_pulse(true); drain();
 row.timer=INT64_MIN;
 char repair[]="set +900 +2"; const auto repair_start=time(nullptr); arti_timer_sql(&staff,repair);
 assert(row.timer>=repair_start+120 && row.timer<=time(nullptr)+120);
 artifact_save_pulse(true); drain();
 const auto unchanged=row.timer;
 char overflow[]="set 900 9223372036854775808"; arti_timer_sql(&staff,overflow);
 char negative[]="add 900 -9223372036854775808"; arti_timer_sql(&staff,negative);
 char ordinary[]="set 901 1"; arti_timer_sql(&staff,ordinary);
 char missing[]="set 999 1"; arti_timer_sql(&staff,missing);
 assert(row.timer==unchanged && writes.empty() && next_uid==cursor && procedures==effects && !pool.objs_used);
 char invalid_poof[]="4294968196"; arti_poof_sql(&staff,invalid_poof);
 char swap_wrapped_source[]="4294968196 902"; arti_swap_sql(&staff,swap_wrapped_source);
 char swap_wrapped_target[]="900 4294968198"; arti_swap_sql(&staff,swap_wrapped_target);
 assert(offline_callbacks.empty() && next_uid==cursor && procedures==effects && !pool.objs_used && writes.empty());
 char swap_invalid[]="900 0"; arti_swap_sql(&staff,swap_invalid);
 assert(next_uid==cursor && procedures==effects && !pool.objs_used && writes.empty());
 // A poof request pins the UID before the asynchronous source read.
 row.locType=ARTIFACT_ON_PC; row.location=77; row.removed=false;
 char requested[]="900"; arti_poof_sql(&staff,requested); assert(offline_callbacks.size()==1);
 row.canonical_item_uid=70001;
 char_data owner={}; pc_only_data owner_pc={}; owner.only.pc=&owner_pc; owner_pc.pid=77;
 owner.player.name=const_cast<char *>("Offline"); owner.player.level=51; owner.specials.act=PLR_MORTAL; owner.in_room=NOWHERE;
 artifact_payload_projection restored={}; restored.domain=artifact_payload_domain::player;
 restored.row_id=1; restored.item_uid=restored.payload_root_item_uid=70001; restored.owner_reference=77;
 restored.payload_owner={item_owner_type::player,77,0}; restored.vnum=900;
 restored.extra_flags=ITEM_ARTIFACT; restored.extra_flags_present=true; restored.quantity=1;
 restored.custody_examined=restored.custody_found=restored.custody_owner_revision_found=true;
 restored.custody={70001,70001,0,restored.payload_owner,1,1,900,item_custody_state::active};
 auto *replacement=read_object_for_recovery(restored); assert(replacement); obj_to_char(replacement,&owner);
 const auto restored_effects=procedures;
 offline_callbacks.front()(&owner); offline_callbacks.clear();
 assert(row.canonical_item_uid==70001 && row.identity_state==artifact_identity_state::present && row.timer==unchanged &&
        artifact_binds.at(900).owner_pid==77 && artifact_binds.at(900).timer==88 && writes.empty() &&
        procedures==restored_effects && !object_list && !pool.objs_used);
 // The live pointer is authoritative even when a same-vnum legacy alias is first.
 replacement=read_object_for_recovery(restored); assert(replacement); obj_to_char(replacement,&owner);
 auto *alias=read_object(0,REAL); assert(alias); alias->obj_uid=70002; obj_to_char(alias,&owner);
 const auto poof_cursor=next_uid; const auto poof_effects=procedures;
 char live_poof[]="900"; arti_poof_sql(&staff,live_poof);
 assert(row.canonical_item_uid==70001 && row.identity_state==artifact_identity_state::retired &&
        owner.carrying==alias && pool.objs_used==1 && next_uid==poof_cursor && procedures==poof_effects);
 alias->obj_uid=0; extract_obj(alias,FALSE); artifact_save_pulse(true); drain();
 row.identity_state=artifact_identity_state::present; row.canonical_item_uid=70001;
 row.owned=true; row.removed=false; row.timer=unchanged;
 // Effective saved artifact flags may promote an ordinary prototype.
 auto &promoted=artifact_rows[901]; promoted.canonical_item_uid=71000;
 promoted.identity_state=artifact_identity_state::present; promoted.owned=true;
 promoted.type=ARTIFACT_MAJOR; promoted.locType=ARTIFACT_ON_PC; promoted.location=77; promoted.timer=unchanged;
 char promoted_timer[]="set 901 1"; const auto promoted_start=time(nullptr); arti_timer_sql(&staff,promoted_timer);
 assert(promoted.timer>=promoted_start+60 && promoted.timer<=time(nullptr)+60 && promoted.canonical_item_uid==71000 &&
        next_uid==poof_cursor && procedures==poof_effects && !pool.objs_used);
 artifact_save_pulse(true); drain();
 row.identity_state=artifact_identity_state::unresolved; row.canonical_item_uid=0;
 char unverified[]="set 900 10"; arti_timer_sql(&staff,unverified);
 assert(row.timer==unchanged && writes.empty());
 row.identity_state=artifact_identity_state::absent; row.canonical_item_uid=0; row.owned=false;
 row.removed=false;
 char invalid_clear[]="4294968196"; arti_clear_sql(&staff,invalid_clear);
 assert(!row.removed && writes.empty());
 char clear[]="  +900  "; const auto clear_cursor=next_uid; const auto clear_effects=procedures;
 arti_clear_sql(&staff,clear);
 assert(row.identity_state==artifact_identity_state::absent && row.removed && !row.canonical_item_uid &&
        next_uid==clear_cursor && procedures==clear_effects && !pool.objs_used);
 artifact_save_pulse(true); drain();
 std::cout<<"cached maintenance inspection and bounded canonical timer editing: PASS\n";
}
""")
source=source.replace("// SWAP_CASES", r"""
void swap_admission_cases() {
 assert(!object_list && !pool.objs_used && writes.empty());
 artifact_rows.clear(); artifact_binds.clear();
 for(int vnum : {900,902}) {
  auto &row=artifact_rows[vnum]; row.identity_state=artifact_identity_state::absent;
  row.population_reason=artifact_population_reason::complete; row.type=ARTIFACT_MAJOR; row.removed=true;
 }
 auto *source=read_object_for_creation(900,VIRTUAL); assert(source); obj_to_room(source,0);
 auto *occupied=read_object_for_creation(902,VIRTUAL); assert(occupied); obj_to_room(occupied,0);
 auto &row=artifact_rows.at(900); row.owned=true; row.removed=false; row.locType=ARTIFACT_ONGROUND;
 row.location=2300; row.timer=time(nullptr)+3600; artifact_binds[900]={77,88};
 const auto source_uid=source->obj_uid; const auto occupied_uid=occupied->obj_uid;
 const auto source_timer=row.timer;
 artifact_save_pulse(true); drain();
 indexes[2].func.obj=periodic;
 char_data staff={}; pc_only_data pc={}; staff.only.pc=&pc; staff.player.level=OVERLORD;
 const auto effects=procedures; const auto population=pool.objs_used;
 char blocked[]="900 902"; arti_swap_sql(&staff,blocked);
 assert(procedures==effects && pool.objs_used==population &&
        "swap constructed or removed an already-present replacement");
 assert(artifact_rows.at(900).canonical_item_uid==source_uid && artifact_rows.at(900).live_object==source &&
        artifact_rows.at(900).timer==source_timer && artifact_binds.at(900).owner_pid==77 &&
        artifact_rows.at(902).canonical_item_uid==occupied_uid && artifact_rows.at(902).live_object==occupied && writes.empty());
 // A first same-vnum alias cannot choose the source or clear the survivor.
 extract_obj(occupied,TRUE); artifact_save_pulse(true); drain();
 const auto refused_uid=next_uid; const auto refused_effects=procedures;
 obj_from_room(source);
 char unlocated[]="900 902"; arti_swap_sql(&staff,unlocated);
 assert(next_uid==refused_uid && procedures==refused_effects && artifact_is_canonical(source) && writes.empty());
 obj_to_room(source,0);
 row.owned=false;
 char stopped[]="900 902"; arti_swap_sql(&staff,stopped);
 assert(next_uid==refused_uid && procedures==refused_effects && !artifact_rows.at(902).live_object && writes.empty());
 row.owned=true;
 const auto previous_target=artifact_rows.at(902);
 artifact_rows.at(902).identity_state=artifact_identity_state::unresolved; artifact_rows.at(902).canonical_item_uid=0;
 char unverified[]="900 902"; arti_swap_sql(&staff,unverified);
 assert(procedures==refused_effects && pool.objs_used==1 && artifact_is_canonical(source) && writes.empty());
 artifact_rows.at(902)=previous_target;
 // Unregistered legacy target bodies must also block replacement creation.
 for(const auto target_state : {artifact_identity_state::absent, artifact_identity_state::retired}) {
  auto &target_row=artifact_rows.at(902); target_row.identity_state=target_state;
  target_row.canonical_item_uid=target_state==artifact_identity_state::absent ? 0 : occupied_uid;
  auto *legacy_target=read_object(902,VIRTUAL); assert(legacy_target && !artifact_is_canonical(legacy_target));
  const auto uid_cursor=next_uid; const auto creation_effects=procedures; const auto live_count=pool.objs_used;
  char duplicate_target[]="900 902"; arti_swap_sql(&staff,duplicate_target);
  assert(next_uid==uid_cursor && procedures==creation_effects && pool.objs_used==live_count &&
         artifact_rows.at(900).live_object==source && artifact_rows.at(900).canonical_item_uid==source_uid &&
         artifact_rows.at(900).timer==source_timer && !target_row.live_object && writes.empty());
  extract_obj(legacy_target,FALSE);
 }
 artifact_rows.at(902)=previous_target;
 drop_swap_artifact_flag=true;
 char lost_flag[]="900 902"; arti_swap_sql(&staff,lost_flag); drop_swap_artifact_flag=false;
 assert(pool.objs_used==1 && artifact_is_canonical(source) &&
        artifact_rows.at(902).canonical_item_uid==occupied_uid &&
        artifact_rows.at(902).identity_state==artifact_identity_state::retired &&
        artifact_rows.at(902).pending==artifact_pending::none && writes.empty());
 auto *alias=read_object(0,REAL); assert(alias); alias->obj_uid=99900; obj_to_room(alias,0);
 char allowed[]="900 902"; renew_swap_source=true; arti_swap_sql(&staff,allowed); renew_swap_source=false;
 auto &target=artifact_rows.at(902); auto *replacement=target.live_object;
 assert(replacement && artifact_is_canonical(replacement) && replacement->obj_uid!=occupied_uid &&
        target.timer==source_timer+60 && target.owned && OBJ_ROOM(replacement) && replacement->loc.room==0);
 assert(artifact_rows.at(900).canonical_item_uid==source_uid && artifact_rows.at(900).identity_state==artifact_identity_state::retired &&
        !artifact_binds.at(900).owner_pid && pool.objs_used==2 && OBJ_ROOM(alias) && alias->obj_uid==99900);
 alias->obj_uid=0; extract_obj(alias,FALSE); extract_obj(replacement,TRUE); artifact_save_pulse(true); drain();
 // Existing carried, worn, nested, NPC and corpse locations still use the same finisher.
 char_data owner={}; pc_only_data owner_pc={}; npc_only_data npc={};
 owner.only.pc=&owner_pc; owner_pc.pid=77; owner.player.name=const_cast<char *>("Offline");
 owner.player.level=51; owner.specials.act=PLR_MORTAL; owner.in_room=NOWHERE;
 for(int location=0; location<5; ++location) {
  P_obj parent=nullptr;
  if(location==3) { owner.only.npc=&npc; owner.specials.act=ACT_ISNPC; }
  else { owner.only.pc=&owner_pc; owner.specials.act=PLR_MORTAL; }
  source=read_object_for_creation(900,VIRTUAL); assert(source);
  if(location==0 || location==3) obj_to_char(source,&owner);
  else if(location==1) equip_char(&owner,source,0,TRUE);
  else {
   parent=read_object_for_creation(903,VIRTUAL); assert(parent);
   if(location==4) { parent->type=ITEM_CORPSE; parent->value[CORPSE_FLAGS]=PC_CORPSE; obj_to_room(parent,0); }
   else obj_to_char(parent,&owner);
   obj_to_obj(source,parent);
  }
  auto &from=artifact_rows.at(900); from.owned=true; from.removed=false; from.timer=source_timer;
  from.locType=location==4 ? ARTIFACT_ONCORPSE : location==3 ? ARTIFACT_ON_NPC : ARTIFACT_ON_PC;
  from.location=77;
  P_obj child=nullptr;
  if(location==2) {
   source->type=ITEM_CONTAINER; source->value[0]=1000;
   child=read_object_for_creation(901,VIRTUAL); assert(child); child->value[0]=123; obj_to_obj(child,source);
  }
  artifact_binds[900]={77,88}; artifact_save_pulse(true); drain();
  const auto original_uid=source->obj_uid; const auto original_population=pool.objs_used;
  if(location==1) {
   pending_actions[source]=3; // active and passive actions referencing the worn source
   assert(unequip_char(&owner,0,FALSE)==source && !pending_actions.contains(source));
   equip_char(&owner,source,0,TRUE); pending_actions[source]=3;
  }
  for(int fault : {1,2,3}) {
   const auto before_target_uid=artifact_rows.at(902).canonical_item_uid;
   const auto before_links=removed_wear_links; const auto before_floor=removed_floor_uids.size();
   const auto before_saves=offline_saves; const auto before_corpses=corpse_saves;
   swap_placement_fault=fault;
   char refused[]="900 902"; arti_swap_sql(&staff,refused);
   swap_placement_fault=0;
   if(location==1) assert(pending_actions.contains(source) && pending_actions.at(source)==3);
   assert(!rooms[1].contents && "failed redirection left a live object on the alternate floor");
   assert(artifact_rows.at(900).live_object==source && artifact_rows.at(900).canonical_item_uid==original_uid &&
          artifact_rows.at(900).identity_state==artifact_identity_state::present && artifact_is_canonical(source) &&
          artifact_rows.at(900).timer==source_timer && artifact_binds.at(900).owner_pid==77 && artifact_binds.at(900).timer==88 &&
          "failed placement retired or changed the original artifact");
   if(location==0 || location==3) assert(OBJ_CARRIED(source) && source->loc.carrying==&owner);
   else if(location==1) assert(owner.equipment[0]==source && OBJ_WORN(source) && source->loc.wearing==&owner);
   else assert(OBJ_INSIDE(source) && source->loc.inside==parent);
   if(child) assert(source->contains==child && child->value[0]==123 && child->loc.inside==source);
   assert(artifact_rows.at(902).canonical_item_uid==before_target_uid && !artifact_rows.at(902).live_object &&
          artifact_rows.at(902).pending==artifact_pending::none && pool.objs_used==original_population &&
          removed_wear_links==before_links && offline_saves==before_saves && corpse_saves==before_corpses && writes.empty());
   assert(artifact_save_pulse(false)==0);
   for(size_t index=before_floor; index<removed_floor_uids.size(); ++index) assert(removed_floor_uids[index]!=original_uid);
  }
  char swap[]="900 902"; arti_swap_sql(&staff,swap);
  assert(!pending_actions.contains(source)); // committed replacement cancels old-source actions
  replacement=artifact_rows.at(902).live_object;
  assert(replacement && artifact_is_canonical(replacement) && artifact_rows.at(902).timer==source_timer);
  if(location==0 || location==3) assert(OBJ_CARRIED(replacement) && replacement->loc.carrying==&owner);
  else if(location==1) assert(owner.equipment[0]==replacement && OBJ_WORN(replacement));
  else assert(OBJ_INSIDE(replacement) && replacement->loc.inside==parent);
  extract_obj(replacement,TRUE); if(parent) extract_obj(parent,FALSE);
  artifact_save_pulse(true); drain(); assert(!object_list && !pool.objs_used);
 }
 owner.only.pc=&owner_pc; owner.specials.act=PLR_MORTAL;
 // A delayed request cannot substitute a later physical UID of the same artifact.
 auto &offline=artifact_rows.at(900); offline.canonical_item_uid=80000;
 offline.identity_state=artifact_identity_state::present; offline.owned=true; offline.removed=false;
 offline.locType=ARTIFACT_ON_PC; offline.location=77; offline.timer=source_timer;
 artifact_binds[900]={77,88};
 const auto request_uid=next_uid; const auto request_effects=procedures;
 char requested[]="900 902"; arti_swap_sql(&staff,requested);
 assert(offline_callbacks.size()==1 && next_uid==request_uid && procedures==request_effects && !pool.objs_used);
 offline.canonical_item_uid=80001;
 artifact_payload_projection restored={}; restored.domain=artifact_payload_domain::player;
 restored.row_id=1; restored.item_uid=restored.payload_root_item_uid=80001; restored.owner_reference=77;
 restored.payload_owner={item_owner_type::player,77,0}; restored.vnum=900;
 restored.extra_flags=ITEM_ARTIFACT; restored.extra_flags_present=true; restored.quantity=1;
 restored.custody_examined=restored.custody_found=restored.custody_owner_revision_found=true;
 restored.custody={80001,80001,0,restored.payload_owner,1,1,900,item_custody_state::active};
 source=read_object_for_recovery(restored); assert(source); obj_to_char(source,&owner);
 const auto restored_effects=procedures;
 offline_callbacks.front()(&owner); offline_callbacks.clear();
 assert(offline.canonical_item_uid==80001 && offline.identity_state==artifact_identity_state::present && offline.timer==source_timer &&
        artifact_binds.at(900).owner_pid==77 && procedures==restored_effects && !object_list && !pool.objs_used && writes.empty());
 // Staging rollback must precede discarding a temporary graph, so no saved live pointer dangles.
 char failed_placement[]="900 902"; arti_swap_sql(&staff,failed_placement); assert(offline_callbacks.size()==1);
 source=read_object_for_recovery(restored); assert(source); obj_to_char(source,&owner);
 swap_placement_fault=2; offline_callbacks.front()(&owner); swap_placement_fault=0; offline_callbacks.clear();
 assert(artifact_rows.at(900).canonical_item_uid==80001 && !artifact_rows.at(900).live_object &&
        artifact_rows.at(900).identity_state==artifact_identity_state::present && artifact_rows.at(900).timer==source_timer &&
        artifact_binds.at(900).owner_pid==77 && !object_list && !pool.objs_used && writes.empty());
 // Refused snapshots restore source identity before discarding the temporary graph.
 inspect_swap_snapshot=true;
 for(int refused_location=0;refused_location<3;++refused_location) {
  char retry[]="900 902"; arti_swap_sql(&staff,retry); assert(offline_callbacks.size()==1);
  source=read_object_for_recovery(restored); assert(source);
  if(refused_location==0) obj_to_char(source,&owner);
  else if(refused_location==1) equip_char(&owner,source,0,TRUE);
  else {
   auto *bag=read_object_for_creation(903,VIRTUAL); assert(bag); bag->value[0]=1000;
   obj_to_char(bag,&owner); obj_to_obj(source,bag);
  }
  const auto releases=offline_released;
  const auto links_before=removed_wear_links;
  const auto target_before_refusal=artifact_rows.at(902);
  command_output.clear();
  offline_save_allowed=false; offline_callbacks.front()(&owner); offline_save_allowed=true; offline_callbacks.clear();
  assert(offline_released==releases+1 && !object_list && !pool.objs_used &&
         artifact_rows.at(900).canonical_item_uid==80001 && artifact_rows.at(900).identity_state==artifact_identity_state::present &&
         !artifact_rows.at(900).live_object && artifact_rows.at(900).timer==source_timer &&
         artifact_binds.at(900).owner_pid==77 && artifact_binds.at(900).timer==88 &&
         artifact_rows.at(902).canonical_item_uid==target_before_refusal.canonical_item_uid &&
         artifact_rows.at(902).identity_state==target_before_refusal.identity_state &&
         !artifact_rows.at(902).live_object && writes.empty() && !artifact_save_pulse(false) && removed_wear_links==links_before);
  assert(command_output.find("original retained")!=std::string::npos && command_output.find("swapped with")==std::string::npos);
 }
 // The unchanged durable source remains admissible when snapshot capture recovers.
 char admitted_retry[]="900 902"; arti_swap_sql(&staff,admitted_retry); assert(offline_callbacks.size()==1);
 source=read_object_for_recovery(restored); assert(source); obj_to_char(source,&owner);
 offline_callbacks.front()(&owner); offline_callbacks.clear(); inspect_swap_snapshot=false;
 assert(!object_list && !pool.objs_used && artifact_rows.at(900).identity_state==artifact_identity_state::retired &&
        artifact_rows.at(902).identity_state==artifact_identity_state::present && artifact_rows.at(902).timer==source_timer);
 artifact_save_pulse(true); drain();
 // A saved artifact on an ordinary prototype is eligible through its actual UID/flags.
 artifact_rows.clear(); artifact_binds.clear();
 auto &empty_target=artifact_rows[902]; empty_target.identity_state=artifact_identity_state::absent;
 empty_target.population_reason=artifact_population_reason::complete; empty_target.type=ARTIFACT_MAJOR; empty_target.removed=true;
 auto &promoted=artifact_rows[901]; promoted.canonical_item_uid=81000;
 promoted.identity_state=artifact_identity_state::present; promoted.owned=true;
 promoted.type=ARTIFACT_MAJOR; promoted.locType=ARTIFACT_ON_PC; promoted.location=77; promoted.timer=source_timer;
 auto saved_promoted=restored; saved_promoted.vnum=901;
 saved_promoted.item_uid=saved_promoted.payload_root_item_uid=81000;
 saved_promoted.custody={81000,81000,0,saved_promoted.payload_owner,1,1,901,item_custody_state::active};
 source=read_object_for_recovery(saved_promoted); assert(source); obj_to_char(source,&owner);
 char promoted_swap[]="901 902"; arti_swap_sql(&staff,promoted_swap);
 replacement=artifact_rows.at(902).live_object;
 assert(replacement && artifact_is_canonical(replacement) && artifact_rows.at(902).timer==source_timer &&
        artifact_rows.at(901).canonical_item_uid==81000 && artifact_rows.at(901).identity_state==artifact_identity_state::retired);
 extract_obj(replacement,TRUE); artifact_save_pulse(true); drain();
 assert(!object_list && !pool.objs_used && offline_callbacks.empty());
 std::cout<<"canonical swap admission and UID-pinned callbacks: PASS\n";
}
""")
with tempfile.TemporaryDirectory(prefix="artifact-creation-",dir=output) as directory:
 cpp=Path(directory)/"creation.cpp"; binary=Path(directory)/"creation"; cpp.write_text(source)
 subprocess.run(["g++","-std=c++20","-Wall","-Wextra","-Werror","-D__NO_MYSQL__",
  "-Isrc","-Isrc/no_mysql","-ffunction-sections","-fdata-sections","-fsanitize=address,undefined",
  "-fno-sanitize-recover=all","-fno-omit-frame-pointer",str(cpp),"src/guild/artifact_population.c",
  "src/item/item_transfer_command.c","src/item/item_ownership_runtime.c","src/core/safe_format.c","src/player/player_load_topology.c",str(HARNESS_STUBS),"-Wl,--gc-sections","-lcrypto","-pthread",
  "-o",str(binary)],cwd=ROOT,check=True)
 subprocess.run([str(binary)],cwd=ROOT,check=True,timeout=30)
