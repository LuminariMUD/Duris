#!/usr/bin/env python3
"""Real grant guards, affect scheduler, snapshot wire and offline/pet timer restore.

Timed spell consequences, stat totals, output and prototype reads are fixtures;
native spell behavior has separate effect-ownership and conjurer runtime tests.
"""
import os
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function, source

prelude = r'''
#include "world/new_events.c"
#include "net/gmcp.h"
#include "item/named_set_effects.h"
#include "item/named_set_origin.h"
#include "item/named_sets.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_codec.h"
#include "player/pet_restore_runtime.h"
#include <cassert>
#include <unordered_set>
int pulse;
bool after_events_call;
P_char character_list;
P_obj object_list;
Skill skills[MAX_AFFECT_TYPES+1];
P_index obj_index=nullptr, mob_index=nullptr;
static room_data room;
P_room world=&room;
const int top_of_world=0;
extern const named_set_definition named_sets[]={{1,{{3,SPELL_STONE_SKIN},{0,0},{0,0}}}};
extern const size_t named_set_count=1;
bool named_set_effect_supported(int) { return true; }
named_set_identity named_set_origin(const obj_data *) { return {}; }
static mm_ds affect_pool{}, event_pool{};
mm_ds *dead_affect_pool=&affect_pool;
mm_ds *mm_create(const char *,size_t size,size_t,unsigned) { return size==sizeof(affected_type)?&affect_pool:&event_pool; }
void *_mm_get(mm_ds *pool,const char *,int) {
    ++pool->objs_used;
    return calloc(1,pool==&affect_pool?sizeof(affected_type):sizeof(nevent_data));
}
void mm_release(mm_ds *pool,void *memory) { --pool->objs_used; free(memory); }
void *__malloc(size_t size,const char *,const char *,int) { return malloc(size); }
void __free(void *memory,const char *,int) { free(memory); }
bool nevent_periodic_begin(P_nevent) { return false; }
void nevent_periodic_complete(P_nevent) {}
void nevent_periodic_watchdog() {}
bool nevent_periodic_event_is_valid(P_nevent) { return true; }
long nevent_periodic_integrity_errors(bool) { return 0; }
const char *event_name_registry_lookup(const void *) { return nullptr; }
void release_mob_mem(P_char,P_char,P_obj,void *) {}
#define LABEL(name) void name(P_char,P_char,P_obj,void *) {}
LABEL(event_hit_regen) LABEL(event_move_regen) LABEL(event_ward_regen)
LABEL(event_spellcast) LABEL(event_memorize) LABEL(event_balance_affects)
LABEL(event_item_action_active) LABEL(event_mob_mundane) LABEL(event_reset_zone)
LABEL(event_autosave) LABEL(event_wait)
LABEL(event_web_spray)
#undef LABEL
char_link_data *link_char(P_char,P_char,ush_int) { assert(false); return nullptr; }
void remove_link(P_char,char_link_data *) { assert(false); }
int GET_CLASS(P_char ch,uint cls) { return (ch->player.m_class&cls)!=0; }
int GET_CHAR_SKILL_P(P_char,int) { return 0; }
int get_property(const char *,int fallback) { return fallback; }
void balance_affects(P_char) {}
void all_affects(P_char,int) {}
int char_light(P_char) { return 0; }
int room_light(int,int) { return 0; }
void unlink_char_affect(P_char,affected_type *) { assert(false); }
void unlink_char_obj_affect(P_char,affected_type *) { assert(false); }
void wear_off_message(P_char,affected_type *) {}
void gmcp_char_affects(P_char) {}
void send_to_char(const char *,P_char) {}
void act(const char *,int,P_char,P_obj,void *,int) {}
char *str_dup(const char *text) { return strdup(text); }
void str_free(const char *text) { free(const_cast<char *>(text)); }
bool training_dummy_capture_target_allowed(P_char) { return true; }
void affect_to_char_with_messages(P_char,affected_type *,const char *,const char *) { assert(false); }
bool grouped(P_char,P_char) { return false; }
int IS_MORPH(P_char) { return FALSE; }
P_char un_morph(P_char) { assert(false); return nullptr; }
void bard_dragons(int,P_char,P_char,int) { assert(false); }
void apply_awareness(P_char,int) {}
void spell_haste(int,P_char,char *,int,P_char,P_obj) { assert(false); }
void spell_fireshield(int,P_char,char *,int,P_char,P_obj) { assert(false); }
void spell_infernal_fury(int,P_char,char *,int,P_char,P_obj) { assert(false); }
bool has_skin_spell(P_char ch) { return affected_by_spell(ch,SPELL_STONE_SKIN); }
static int casts;
static void record_cast(int,P_char,char *,int,P_char,P_obj) { ++casts; }
void spell_stone_skin(int,P_char ch,char *,int,P_char,P_obj) {
    ++casts;
    affected_type skin{}; skin.type=SPELL_STONE_SKIN; skin.duration=50;
    affect_to_char(ch,&skin);
}
void spell_ironwood(int,P_char ch,char *,int,P_char,P_obj) {
    ++casts; affected_type skin{}; skin.type=SPELL_IRONWOOD; skin.duration=50; affect_to_char(ch,&skin);
}
enum {SETMSG_NONE,SETMSG_PROTECT,SETMSG_STRENGTH};
'''

functions = ''.join(extract_function('affects.c', signature) for signature in (
    'void event_short_affect(', 'struct affected_type *affect_to_char(',
    'void affect_remove(', 'void affect_from_char(', 'bool affected_by_spell(',
    'struct affected_type *get_spell_from_char(', 'bool affected_by_skill('))
functions += extract_function('specs.set.c', 'static void grant_dragons_to_group(')
functions += extract_function('specs.set.c', 'void apply_zone_spell(')
magic = source('magic.c').read_text()
start = magic.index('// Select active types before removal:')
end = magic.index('\n\t\tsuccess = CheckMobRemoveableSpellBits', start)
functions += extract_function('magic.c', 'P_char dispel_character_affect(')
functions += '\nstatic void dispel_active(P_char victim) { P_char ch=victim; affected_type *af; int nosave=1,mod=0,success=0;\n'
functions += magic[start:end] + '\n(void)success; }\n'
capture = source('player_snapshot_capture.c').read_text()
functions += capture[capture.index('struct capture_budget'):capture.index('template <typename T> bool add_status_integer')]
functions += extract_function('player_snapshot_capture.c', 'player_snapshot_capture_result capture_affects(')
restore = extract_function('player_load_materialize.c', 'for (auto affect_entry = result.snapshot.affects.rbegin();')
functions += '\nstatic void restore_player(P_char ch,const player_snapshot &snapshot) {\n' + restore.replace('result.snapshot.affects', 'snapshot.affects') + '\n}\n'
offline = extract_function('nanny.c', 'for (afp1 = ch->affected; afp1; afp1 = afp2)')
reset_timers = extract_function('nanny.c', 'for (affected_type *timer = ch->affected, *next; timer; timer = next)')
functions += '\nstatic void offline_player(P_char ch,long rest) { affected_type *afp1,*afp2; P_nevent evp; long time_gone=0;\n' + offline + reset_timers + '\n}\n'

driver = r'''
static void advance(int ticks) { while(ticks--) { ne_events(); nevent_advance_tick(); } }
static void clear(P_char ch) { while(ch->affected) affect_remove(ch,ch->affected); disarm_char_nevents(ch,nullptr); }
int main() {
    nevent_bind_game_thread(); ne_dead_event_pool=&event_pool;
    pc_only_data pc{},other_pc{};
    char_data ch{},other{}; ch.only.pc=&pc; other.only.pc=&other_pc;
    ch.runtime_id=1; other.runtime_id=2;
    ch.player.level=other.player.level=MAXLVLMORTAL+1; // staff must observe set cooldowns
    ch.points.max_vitality=other.points.max_vitality=100;
    SET_POS(&ch,STAT_NORMAL+POS_STANDING); SET_POS(&other,STAT_NORMAL+POS_STANDING);
    character_list=&ch; ch.next=&other;
    assert(IS_TRUSTED((&ch)));
    affected_type transient{};
    transient.type=TAG_SKILL_TIMER; transient.modifier=TAG_PHYS_SKILL_NOTCH;
    transient.flags=AFFTYPE_STORE|AFFTYPE_SHORT; transient.duration=300*WAIT_SEC;
    affect_to_char(&ch,&transient); offline_player(&ch,0);
    assert(!ch.affected); // Ordinary login-reset timers still reset.
    for(int spell:named_set_cooldown_spells) {
        skills[spell].spell_pointer=record_cast;
        obj_data first{},replacement{};
        casts=0;
        apply_zone_spell(&ch,3,"One",1,&first,spell);
        assert(casts==1);
        const int full=(spell==SPELL_CONJURE_ELEMENTAL?300:60)*WAIT_SEC;
        assert(named_set_cooldown_remaining(&ch,spell)==full);
        auto *timer=ch.affected;
        while(timer && timer->type!=TAG_SKILL_TIMER) timer=timer->next;
        assert(timer && timer->modifier==spell && (timer->flags&AFFTYPE_OFFLINE));
        assert(!(timer->flags&(AFFTYPE_SET_AFFECT|AFFTYPE_NOSAVE)));
        reconcile_named_set_spell(&ch,spell); // remove gear support, keep cooldown
        assert(named_set_cooldown_remaining(&ch,spell)==full);
        affected_type ordinary{}; ordinary.type=SPELL_ARMOR; ordinary.duration=9;
        affect_to_char(&ch,&ordinary);
        dispel_active(&ch);
        assert(!affected_by_spell(&ch,SPELL_ARMOR));
        assert(named_set_cooldown_remaining(&ch,spell)==full);
        for(int zone:{1,2,3}) apply_zone_spell(&ch,6,"Swapped",zone,&replacement,spell);
        assert(casts==1 && replacement.timer[0]==0);
        apply_zone_spell(&other,3,"Transferred",1,&first,spell);
        assert(casts==1); // Original item timer is still a transfer floor.
        obj_data fresh{};
        apply_zone_spell(&other,3,"Separate wearer",2,&fresh,spell);
        assert(casts==2);
        clear(&other);
        advance(17);
        const int remaining=full-17;
        assert(named_set_cooldown_remaining(&ch,spell)==remaining);

        player_snapshot snapshot{}; capture_budget budget;
        assert(capture_affects(&ch,snapshot,budget)==player_snapshot_capture_result::ok);
        assert(snapshot.affects.size()==1 && snapshot.affects[0].duration==remaining);
        snapshot.schema_version=PLAYER_SNAPSHOT_SCHEMA_VERSION; snapshot.pid=42; snapshot.revision=1;
        snapshot.components=PLAYER_COMPONENT_AFFECTS; snapshot.encoded_size_bound=PLAYER_SNAPSHOT_MAX_BYTES;
        std::vector<uint8_t> wire;
        assert(player_snapshot_encode(snapshot,&wire)==player_snapshot_codec_result::ok);
        player_snapshot reloaded;
        assert(player_snapshot_decode(wire.data(),wire.size(),&reloaded)==player_snapshot_codec_result::ok);
        clear(&ch); restore_player(&ch,reloaded);
        assert(named_set_cooldown_remaining(&ch,spell)==remaining);
        offline_player(&ch,2);
        assert(named_set_cooldown_remaining(&ch,spell)==remaining-2*WAIT_SEC);
        apply_zone_spell(&ch,3,"After reload",9,&replacement,spell); assert(casts==2);
        advance(remaining-2*WAIT_SEC+1);
        assert(!named_set_cooldown_remaining(&ch,spell));
        apply_zone_spell(&ch,3,"Expired",9,&replacement,spell); assert(casts==3);
        clear(&ch); restore_player(&ch,reloaded); offline_player(&ch,1000);
        assert(!ch.affected && !named_set_cooldown_remaining(&ch,spell));
    }
    // Native casts remain independent, even while a set timer is active.
    start_named_set_cooldown(&ch,SPELL_STONE_SKIN,60*WAIT_SEC);
    spell_stone_skin(56,&ch,nullptr,0,&ch,nullptr);
    assert(!(ch.affected->flags&AFFTYPE_SET_AFFECT)); clear(&ch);
    ch.points.vitality=ch.points.max_vitality;
    obj_data item{};
    apply_zone_spell(&ch,3,"Full vitality",1,&item,SPELL_INVIGORATE);
    assert(!ch.affected && !item.timer[0]);

    // Both ordinary and summoned pet wearers retain wall-clock deadlines.
    for(bool summoned:{false,true}) {
        npc_only_data npc{},restored_npc{};
        char_data pet{},restored{}; pet.only.npc=&npc; restored.only.npc=&restored_npc;
        pet.specials.act=restored.specials.act=ACT_ISNPC;
        SET_POS(&pet,STAT_NORMAL+POS_STANDING); SET_POS(&restored,STAT_NORMAL+POS_STANDING);
        if(summoned) {
            npc.summon_kind=static_cast<uint32_t>(summoned_pet_kind::conjured_fire_elemental);
            pet.player.name=const_cast<char *>("elemental");
            pet.player.short_descr=const_cast<char *>("an elemental");
            pet.player.long_descr=const_cast<char *>("An elemental waits here.\n");
            pet.player.level=30; pet.points.base_hit=100;
        }
        for(int spell:named_set_cooldown_spells) start_named_set_cooldown(&pet,spell,61);
        std::string encoded; assert(summoned_pet_capture(&pet,&encoded) && !encoded.empty());
        pet_restore_state state; assert(pet_restore_state_decode(encoded,&state) && state.version==3);
        // v2 keeps exactly its original three deadline positions and defaults Ironwood to zero.
        auto legacy=state; legacy.version=2; legacy.named_set_cooldowns[3]=0;
        std::string legacy_wire; assert(pet_restore_state_encode(legacy,&legacy_wire));
        pet_restore_state legacy_read; assert(pet_restore_state_decode(legacy_wire,&legacy_read));
        assert(legacy_read.version==2 && legacy_read.named_set_cooldowns[3]==0);
        for(size_t i=0;i<3;++i) assert(legacy_read.named_set_cooldowns[i]==state.named_set_cooldowns[i]);
        assert(summoned_pet_apply(&restored,state));
        for(int spell:named_set_cooldown_spells) {
            const int remaining=named_set_cooldown_remaining(&restored,spell);
            assert(remaining>=57 && remaining<=64); // Rounded up to whole seconds in pet payload.
        }
        clear(&restored);
        state.named_set_cooldowns.fill(time(nullptr)-1);
        assert(summoned_pet_apply(&restored,state) && !restored.affected);
        if(summoned) {
            free(restored.player.name); free(restored.player.short_descr); free(restored.player.long_descr);
        }
        clear(&pet);
    }
    assert(affect_pool.objs_used==0 && event_pool.objs_used==0 && ne_event_counter==0);
    puts("PASS named cooldowns: swaps, transfers, staff, scheduler expiry, player wire/offline and pet deadlines");
}
'''

out = ROOT / 'bin/tests'
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='named-set-cooldowns-', dir=out) as temporary:
    cpp, binary = Path(temporary) / 'test.cpp', Path(temporary) / 'test'
    cpp.write_text(prelude + functions + driver)
    subprocess.run(['g++', '-std=c++20', '-O1', '-g', '-ffunction-sections', '-fdata-sections',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-pie', '-no-pie', '-pthread',
                    '-Isrc', '-I/usr/include/mysql', str(cpp), 'src/item/named_set_effects.c',
                    'src/player/player_snapshot_codec.c', 'src/player/pet_restore_state.c',
                    'src/player/pet_restore_runtime.c', 'src/persistence/latency_trace.c',
                    str(HARNESS_STUBS), '-Wl,--gc-sections', '-lbsd', '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], env=dict(os.environ, DURIS_NEVENT_BUDGET_USEC='0',
                                         DURIS_NEVENT_MAX_CALLBACKS='0'), check=True, timeout=30)
