#!/usr/bin/env python3
"""Real spell bodies, affect allocation/removal, set provenance and shared support.

World/stat recalculation, output and unrelated spell handlers are fixtures. Full
command/persistence gameplay and cooldown journeys remain in the project plan.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/mm.h"
#include "net/gmcp.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "world/vnum.obj.h"
#include "item/named_set_origin.h"
#include "item/named_set_effects.h"
#include "item/named_sets.h"
#include "item/random_equipment.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "classes/disguise.h"
#include "world/falling.h"
#include "combat/damage.h"
#include <cassert>
#include <cstdlib>
#include <string>
#include <vector>

Skill skills[MAX_AFFECT_TYPES+1];
static index_data indexes[2];
P_index obj_index=indexes;
P_index mob_index=indexes;
zone_data *zone_table=nullptr;
int top_of_zone_table=-1;
static room_data rooms[1];
P_room world=rooms;
P_char character_list=nullptr;
extern const racial_data_type racial_data[LAST_RACE+1]{};
static pc_only_data wearer_pc,companion_pc;
static bool inherent_armor;
static bool track_hit_points;
static mm_ds affect_pool{},link_pool{};
mm_ds *dead_affect_pool=&affect_pool,*dead_link_pool=&link_pool;
link_description link_types[LNK_MAX+1];
static char_data wearer,companion;
static obj_data gear[12];
static int grants;
static int guardian_rejections;
static int output_messages;
static int alias_calls;
static bool high_roll;
static bool innate_eyes;
static int light_updates,room_light_updates;
int number(int low,int high) {return high_roll ? high : low;}
int dice(int count,int sides) {return high_roll ? count*sides : count;}
const Rolls live_rolls={dice,number};
int GET_CLASS(P_char ch,uint cls) {return (ch->player.m_class&cls)!=0;}
int GET_CHAR_SKILL_P(P_char,int) {return 0;}
int NumAttackers(P_char) {return 0;}
float get_property(const char *,double value) {return value;}
int get_property(const char *,int value) {return value;}
bool grouped(P_char,P_char) {return true;}
char *str_dup(const char *text) {return strdup(text);}
void *__malloc(size_t size,const char *,const char *,int) {return calloc(1,size);}
mm_ds *mm_create(const char *,size_t size,size_t,unsigned) {return size==sizeof(affected_type) ? &affect_pool : &link_pool;}
void *_mm_get(mm_ds *pool,const char *,int) {return calloc(1,pool==&affect_pool ? sizeof(affected_type) : sizeof(char_link_data));}
void mm_release(mm_ds *,void *memory) {free(memory);}
void balance_affects(P_char) {}
void gmcp_char_affects(P_char) {}
int char_light(P_char) {++light_updates;return 0;}
int room_light(int,int) {++room_light_updates;return 0;}
void unlink_char_obj_affect(P_char,affected_type *) {assert(false);}
void clear_links(P_char,ush_int) {assert(false);}
void all_affects(P_char ch,int add) {
    // Model native missing-HP preservation; position classification below uses
    // the production calculate_ch_state() body.
    if(track_hit_points) {
        int maximum=1000;
        if(add) for(auto *af=ch->affected;af;af=af->next)
            if(!(af->flags&AFFTYPE_NOAPPLY) && af->location==APPLY_HIT) maximum+=af->modifier;
        GET_HIT(ch)+=maximum-GET_MAX_HIT(ch); GET_MAX_HIT(ch)=maximum;
    }
    ch->specials.affected_by=ch->specials.affected_by2=ch->specials.affected_by3=0;
    ch->specials.affected_by4=ch->specials.affected_by5=0;
    if(!add) return;
    if(inherent_armor) ch->specials.affected_by|=AFF_ARMOR;
    for(auto *af=ch->affected;af;af=af->next) {
        if(af->flags&AFFTYPE_NOAPPLY) continue;
        ch->specials.affected_by|=af->bitvector; ch->specials.affected_by2|=af->bitvector2;
        ch->specials.affected_by3|=af->bitvector3; ch->specials.affected_by4|=af->bitvector4;
        ch->specials.affected_by5|=af->bitvector5;
    }
}
char affect_total(P_char ch,int) {all_affects(ch,FALSE); all_affects(ch,TRUE); return 0;}
bool SanityCheck(P_char ch,const char *) {return IS_ALIVE(ch);}
bool has_innate(P_char,int innate) {return innate_eyes && innate==INNATE_OPHIDIAN_EYES;}
void send_to_char(const char *text,P_char ch) {
    if(named_set_grant::hold_output(ch,text)) return;
    ++output_messages;
    if(strstr(text,"spirits of")) ++grants;
    if(strstr(text,"forefathers")) ++guardian_rejections;
}
int attack_back(P_char,P_char,int) {return 0;}
void act(const char *,int,P_char,P_obj,void *,int) {}
nevent_schedule_result add_event(event_func,int,P_char,P_char,P_obj,int,const void *,int) {return {};}
void disarm_char_nevents(P_char,event_func_type) {}
nevent_handle nevent_handle_from_event(P_nevent event) {return {event,event->sequence};}
nevent_cancel_result nevent_cancel(nevent_handle) {return nevent_cancel_result::canceled;}
int gain_exp(P_char,P_char,int,int) {assert(false);return 0;}
void spell_haste(int,P_char,char *,int,P_char,P_obj) {assert(false);}
void spell_fireshield(int,P_char,char *,int,P_char,P_obj) {assert(false);}
void spell_infernal_fury(int,P_char,char *,int,P_char,P_obj) {assert(false);}
void spell_vitality(int,P_char,char *,int,P_char,P_obj) {}
void spell_bless(int,P_char,char *,int,P_char,P_obj) {}
void unlink_char_affect(P_char,affected_type *);
void internal_unlink_char(P_char,char_link_data *,char_link_data *);
void dispose_link(char_link_data *);
unsigned int char_slice(P_char,unsigned int) {return 0;}
int IS_MORPH(P_char) {return FALSE;}
int GET_PRIME_CLASS(P_char,uint) {return 0;}
int GET_SECONDARY_CLASS(P_char,uint) {return 0;}
void StartRegen(P_char,regen_resource) {}
bool char_falling(P_char) {return false;}
time_info_data age(P_char) {return {};}
void remove_disguise(P_char,bool) {assert(false);}
P_char un_morph(P_char) {assert(false);return nullptr;}
falling_start_result falling_start(P_char) {return falling_start_result::not_applicable;}
static void alias_effect(int,P_char ch,char *,int,P_char,P_obj) {
    ++alias_calls;
    affected_type affect{}; affect.type=SPELL_ANGELIC_COUNTENANCE; affect.duration=12;
    affect_to_char(ch,&affect);
}
''' + extract_function("utility.c", "string strip_ansi(") + extract_function("utility.c", "int BOUNDED(")

for signature in (
        "struct affected_type *get_spell_from_char(", "bool affected_by_spell(",
        "bool affected_by_skill(", "struct affected_type *affect_to_char(", "void affect_remove(",
        "void affect_from_char(", "void affect_join(", "void wear_off_message(", "struct char_link_data *link_char_with_affect(",
        "void linked_affect_to_char(", "void dispose_link(", "void internal_unlink_char(",
        "void unlink_char_affect("):
    # Skip the forward declarations at the top of affects.c.
    if signature in ("void unlink_char_affect(", "void internal_unlink_char(", "void dispose_link("):
        signatures = {
            "void unlink_char_affect(": "void unlink_char_affect(P_char ch, struct affected_type *af)\n{",
            "void internal_unlink_char(": "void internal_unlink_char(P_char ch, struct char_link_data *cld, struct char_link_data *prev)\n{",
            "void dispose_link(": "void dispose_link(struct char_link_data *cld)\n{",
        }
        signature = signatures[signature]
    harness += extract_function("affects.c", signature) + "\n"

import re
affects_source = (ROOT / "src/magic/affects.c").read_text()
harness += re.search(r"^#define AFFECT_UPDATE_SLICES .*", affects_source, re.M).group() + "\n"
harness += extract_function("affects.c", "void affect_update(") + "\n"

magic_source = (ROOT / "src/magic/magic.c").read_text()
harness += re.search(r"^#define MACE_OF_EARTH_VNUM .*", magic_source, re.M).group() + "\n"
for signature in ("static int armor_duration(", "static int armor_armor_class(", "void spell_armor(",
                  "static int strength_duration(", "static int strength_bonus(", "void spell_strength(",
                  "static int endurance_amount(", "void spell_endurance(",
                  "static int vampiric_touch_duration(", "static int vampiric_touch_hitroll(",
                  "void spell_vampiric_touch(", "void spell_miracle(",
                  "static bool has_other_skin_spell(", "bool has_skin_spell(",
                  "static int stone_skin_absorb(", "static int stone_skin_living_stone(",
                  "static int stone_skin_conjurer(", "static int stone_skin_sorcerer(",
                  "static int stone_skin_other(", "static int stone_skin_duration(",
                  "static int stone_skin_layers(", "void spell_stone_skin(",
                  "static int stornogs_spheres_count(", "void spell_stornogs_spheres("):
    harness += extract_function("magic.c", signature) + "\n"
for signature in ("static int song_dragons_duration(", "static int song_dragons_cold_level(",
                  "static int song_dragons_gas_level(", "static int song_dragons_acid_level(",
                  "static int song_dragons_lightning_level(", "static int song_dragons_ward_roll(",
                  "void bard_dragons(int l,"):
    harness += extract_function("bard.c", signature) + "\n"


# Every native body/helper used by the 50-effect expansion pool.
for file, signatures in {
    'classes/ethermancer.c': (
        'static int vapor_armor_duration(',
        'static int vapor_armor_ac(',
        'void spell_vapor_armor(',
        'static int vapor_strike_duration(',
        'static int vapor_strike_hitroll(',
        'void spell_vapor_strike(',
    ),
    'classes/psionics.c': (
        'static int adrenaline_control_duration(',
        'static int adrenaline_control_bonus(',
        'void spell_adrenaline_control(',
        'static int combat_mind_duration(',
        'static int combat_mind_hitroll(',
        'static int combat_mind_damroll(',
        'void spell_combat_mind(',
        'static int displacement_duration(',
        'static int displacement_ac(',
        'void spell_displacement(',
        'static int energy_containment_duration(',
        'static int energy_containment_save(',
        'void spell_energy_containment(',
        'static int enhance_armor_duration(',
        'static int enhance_armor_ac(',
        'void spell_enhance_armor(',
        'static int enhanced_strength_duration(',
        'static int enhanced_strength_bonus(',
        'void spell_enhanced_strength(',
        'static int enhanced_dexterity_duration(',
        'static int enhanced_dexterity_bonus(',
        'void spell_enhanced_dexterity(',
        'static int enhanced_agility_duration(',
        'static int enhanced_agility_bonus(',
        'void spell_enhanced_agility(',
        'static int enhanced_constitution_duration(',
        'static int enhanced_constitution_bonus(',
        'void spell_enhanced_constitution(',
    ),
    'classes/sillusionist.c': (
        'static int phantom_armor_duration(',
        'static int phantom_armor_ac(',
        'void spell_phantom_armor(',
        'static int detect_illusion_duration(',
        'void spell_detect_illusion(',
    ),
    'magic/magic.c': (
        'static int fortitude_duration(',
        'static int fortitude_constitution(',
        'void spell_fortitude(',
        'static int virtue_duration(',
        'void spell_virtue(',
        'static int sense_holiness_duration(',
        'void spell_sense_holiness(',
        'static int lifelust_duration(',
        'static int lifelust_bonus(',
        'void spell_lifelust(',
        'static int pulchritude_duration(',
        'static int pulchritude_charisma(',
        'void spell_pulchritude(',
        'static int serendipity_duration(',
        'static int serendipity_luck(',
        'void spell_serendipity(',
        'static int detect_evil_duration(',
        'void spell_detect_evil(',
        'static int detect_good_duration(',
        'void spell_detect_good(',
        'static void set_protection_duration(',
        'static int protection_from_evil_duration(',
        'void spell_protection_from_evil(',
        'static int protection_from_good_duration(',
        'void spell_protection_from_good(',
        'static int dexterity_duration(',
        'static int dexterity_bonus(',
        'void spell_dexterity(',
        'static int agility_duration(',
        'static int agility_bonus(',
        'void spell_agility(',
        'static int sense_life_duration(',
        'void spell_sense_life(',
        'static int lodestone_vision_duration(',
        'void spell_lodestone_vision(',
        'static int farsee_duration(',
        'void spell_farsee(',
        'int KludgeDuration(',
        'static int battletide_damroll(',
        'static int battletide_hitroll(',
        'static int battletide_duration(',
        'void spell_battletide(',
        'static int mage_flame_duration(',
        'void spell_holy_light(',
        'void spell_mage_flame(',
        'static int globe_of_darkness_duration(',
        'void spell_globe_of_darkness(',
        'static int slow_poison_duration(',
        'void spell_slow_poison(',
        'static int comprehend_languages_duration(',
        'void spell_comprehend_languages(',
        'static int waterbreath_duration(',
        'void spell_waterbreath(',
        'static int protection_spell_duration(',
        'void spell_protection_from_fire(',
        'void spell_protection_from_cold(',
        'void spell_protection_from_animals(',
        'void spell_protection_from_gas(',
        'void spell_protection_from_acid(',
        'void spell_protection_from_lightning(',
        'static int infravision_duration(',
        'void spell_infravision(',
        'static int divine_fury_duration(',
        'static int divine_fury_damroll(',
        'static int divine_fury_hitroll(',
        'void spell_divine_fury(',
        'static int sense_follower_duration(',
        'void spell_sense_follower(',
        'static int warring_zeal_duration(',
        'static int warring_zeal_hitroll(',
        'void spell_warring_zeal(',
    ),
    'magic/smagic.c': (
        'void do_point(',
        'static int animalist_level_bonus(',
        'static int animalist_level(',
        'static int guardian_spirits_renewal(',
        'static int guardian_spirits_duration(',
        'static int guardian_spirits_ac(',
        'void spell_guardian_spirits(',
        'static int bloodhound_duration(',
        'void spell_bloodhound(',
        'static int wolfspeed_duration(',
        'static int wolfspeed_move(',
        'void spell_wolfspeed(',
        'static int hawkvision_duration(',
        'void spell_hawkvision(',
        'static int sense_spirit_duration(',
        'void spell_sense_spirit(',
    ),
}.items():
    for signature in signatures:
        harness += extract_function(file, signature) + "\n"
harness += extract_function("magic.c", "static int prot_from_undead_duration(") + "\n"
harness += extract_function("magic.c", "void spell_prot_from_undead(") + "\n"
harness += extract_function("magic.c", "static int vitality_hit_points(") + "\n"
harness += extract_function("magic.c", "static int vitality_duration(") + "\n"
harness += extract_function("fight.c", "unsigned int calculate_ch_state(") + "\n"
harness += "void update_pos(P_char ch) { ch->specials.position=GET_POS(ch)|calculate_ch_state(ch); }\n"
# Keep unrelated Miracle components stubbed, but execute the complete native
# Vitality body for the wounded ordinary/set transition.
harness += extract_function("magic.c", "void spell_vitality(").replace(
    "void spell_vitality(", "static void cast_native_vitality(", 1) + "\n"

harness += "\n#define SETMSG_NONE 0\n#define SETMSG_PROTECT 1\n#define SETMSG_STRENGTH 2\n"
harness += extract_function("specs.set.c", "static void grant_dragons_to_group(")
harness += extract_function("specs.set.c", "void apply_zone_spell(")
harness += extract_function("fight.c", "bool decrease_skin_counter(")
# Run the production character-dispel traversal with a deterministic self-cast
# save boundary. Object magic, permanent-NPC bits and retaliation are separate.
magic_source = (ROOT / "src/magic/magic.c").read_text()
dispel_start = magic_source.index("// Select active types before removal:")
dispel_end = magic_source.index("\n\t\tsuccess = CheckMobRemoveableSpellBits", dispel_start)
harness += "\nstatic void dispel_active(P_char victim) { P_char ch=victim,orig=nullptr; affected_type *af; int nosave=1,mod=0,success=0;\n"
harness += magic_source[dispel_start:dispel_end]
harness += "\n(void)orig; (void)success; }\n"
harness += "\nstatic int hit_sphere(P_char victim) { P_char ch=&companion; affected_type *af;\n"
harness += extract_function("fight.c", "if (IS_AFFECTED4(victim, AFF4_STORNOGS_SPHERES))")
harness += "\nreturn 99; }\n"
harness += "\nstatic int virtue_accuracy(P_char ch,P_char victim) {int to_hit=1000;\n"
harness += extract_function("fight.c", "if ((IS_EVIL(ch) && !IS_EVIL(victim)) || (IS_GOOD(ch) && !IS_GOOD(victim)))")
harness += "\nreturn to_hit;}\n"
harness += r'''
static void clear_marker(obj_data &item) {
    while(item.ex_description) {
        auto *entry=item.ex_description; item.ex_description=entry->next;
        free(entry->keyword); free(entry->description); free(entry);
    }
}
static void reset() {
    track_hit_points=false;
    for(P_char ch : {&wearer,&companion}) while(ch->affected) affect_remove(ch,ch->affected);
    for(auto &item:gear) {clear_marker(item); item={};}
    wearer={}; companion={};
    wearer.runtime_id=1; companion.runtime_id=2;
    wearer.player.level=56; companion.player.level=56;
    wearer.specials.position=companion.specials.position=STAT_NORMAL|POS_STANDING;
    wearer.only.pc=&wearer_pc; companion.only.pc=&companion_pc;
    wearer.next=&companion; character_list=&wearer;
    wearer.next_in_room=&companion; rooms[0].people=&wearer;
    grants=0; inherent_armor=false; guardian_rejections=0;
}
static void wear(int item,int slot,int zone,bool weapon=false) {
    gear[item].R_num=weapon ? 1 : 0;
    gear[item].loc_p=LOC_WORN; gear[item].loc.wearing=&wearer;
    set_named_set_origin(&gear[item],zone); wearer.equipment[slot]=&gear[item];
}
static int count(P_char ch,int type,bool owned) {
    int result=0;
    for(auto *af=ch->affected;af;af=af->next)
        if(af->type==type && bool(af->flags&AFFTYPE_SET_AFFECT)==owned) ++result;
    return result;
}
static int active_modifier(P_char ch,int type) {
    int result=0;
    for(auto *af=ch->affected;af;af=af->next)
        if(af->type==type && !(af->flags&AFFTYPE_NOAPPLY)) result+=af->modifier;
    return result;
}
// Frozen native grants at invocation levels 30, 50 and 56. These are affect
// modifiers before the character's normal stat caps, not derived character totals.
struct expansion_case {
    int spell;
    decltype(Skill::spell_pointer) callback;
    int location;
    int modifiers[3];
    int durations[3];
    uint64_t bits[5]{};
    int second_location=0;
    int second_modifiers[3]{};
};
static const expansion_case expansion_cases[]={
    {34,spell_protection_from_evil,0,{}, {30,50,56},{AFF_PROTECT_EVIL}},
    {44,spell_sense_life,0,{}, {30,50,56},{AFF_SENSE_LIFE}},
    {53,spell_farsee,0,{}, {60,100,112},{AFF_FARSEE}},
    {73,spell_dexterity,APPLY_DEX,{10,10,10},{30,50,56}},
    {81,spell_protection_from_good,0,{}, {30,50,56},{AFF_PROTECT_GOOD}},
    {85,spell_waterbreath,0,{}, {30,50,56},{AFF_WATERBREATH}},
    {90,spell_detect_evil,0,{}, {30,50,56},{0,AFF2_DETECT_EVIL}},
    {91,spell_detect_good,0,{}, {30,50,56},{0,AFF2_DETECT_GOOD}},
    {96,spell_protection_from_fire,0,{}, {30,50,56},{AFF_PROT_FIRE}},
    {97,spell_protection_from_cold,0,{}, {30,50,56},{0,AFF2_PROT_COLD}},
    {98,spell_protection_from_lightning,0,{}, {30,50,56},{0,AFF2_PROT_LIGHTNING}},
    {104,spell_protection_from_gas,0,{}, {30,50,56},{0,AFF2_PROT_GAS}},
    {105,spell_protection_from_acid,0,{}, {30,50,56},{0,AFF2_PROT_ACID}},
    {106,spell_infravision,0,{}, {30,50,56},{AFF_INFRAVISION}},
    {130,spell_slow_poison,0,{}, {15,25,28},{AFF_SLOW_POISON}},
    {132,spell_comprehend_languages,0,{}, {60,100,112}},
    {157,spell_adrenaline_control,APPLY_STR,{15,15,15},{35,55,61},{},APPLY_CON,{15,15,15}},
    {163,spell_combat_mind,APPLY_HITROLL,{5,8,9},{33,53,59},{},APPLY_DAMROLL,{3,6,7}},
    {169,spell_displacement,APPLY_AC,{-60,-100,-112},{26,46,52}},
    {173,spell_energy_containment,APPLY_SAVING_SPELL,{-3,-6,-7},{22,32,35}},
    {174,spell_enhance_armor,APPLY_AC,{-30,-50,-56},{25,25,25}},
    {175,spell_enhanced_strength,APPLY_STR,{8,13,15},{30,50,56}},
    {176,spell_enhanced_dexterity,APPLY_DEX,{8,13,15},{30,50,56}},
    {177,spell_enhanced_agility,APPLY_AGI,{8,13,15},{30,50,56}},
    {178,spell_enhanced_constitution,APPLY_CON,{7,11,12},{30,50,56}},
    {193,spell_wolfspeed,APPLY_MOVE,{17,27,30},{31,51,57}},
    {204,spell_hawkvision,0,{}, {15,25,28},{0,0,0,AFF4_HAWKVISION}},
    {211,spell_sense_spirit,0,{}, {20,30,33},{AFF_SENSE_LIFE}},
    {279,spell_sense_follower,0,{}, {30,50,56},{0,0,0,AFF4_SENSE_FOLLOWER}},
    {297,spell_mage_flame,0,{30,50,56},{18,28,31},{0,0,0,AFF4_MAGE_FLAME}},
    {302,spell_globe_of_darkness,0,{30,50,56},{8,13,15},{0,0,0,AFF4_GLOBE_OF_DARKNESS}},
    {310,spell_divine_fury,APPLY_HITROLL,{6,10,11},{2,2,2},{},APPLY_DAMROLL,{6,10,11}},
    {316,spell_sense_holiness,0,{}, {25,25,25},{0,0,0,AFF4_SENSE_HOLINESS}},
    {321,spell_lifelust,APPLY_HITROLL,{3,4,4},{15,25,28},{},APPLY_DAMROLL,{3,4,4}},
    {347,spell_pulchritude,APPLY_CHA,{20,30,30},{30,50,56}},
    {348,spell_fortitude,APPLY_CON,{5,5,5},{8,12,12}},
    {352,spell_serendipity,APPLY_LUCK,{12,18,18},{30,50,56}},
    {383,spell_protection_from_animals,0,{}, {30,50,56},{0,0,AFF3_PROT_ANIMAL}},
    {395,spell_battletide,APPLY_DAMROLL,{10,10,10},{10,10,10},{0,0,0,AFF4_BATTLETIDE},APPLY_HITROLL,{10,10,10}},
    {400,spell_phantom_armor,APPLY_AC,{-30,-50,-56},{15,15,15},{AFF_ARMOR}},
    {414,spell_detect_illusion,0,{}, {30,50,56},{AFF_DETECT_INVISIBLE,0,0,AFF4_DETECT_ILLUSION}},
    {452,spell_vapor_armor,APPLY_AC,{-37,-62,-70},{15,25,28},{AFF_ARMOR}},
    {467,spell_vapor_strike,APPLY_HITROLL,{3,3,3},{15,25,28}},
    {515,spell_virtue,0,{30,50,56},{15,25,28}},
    {517,spell_bloodhound,0,{}, {30,50,56}},
    {579,spell_guardian_spirits,APPLY_AC,{-150,-150,-150},{11,21,24}},
    {584,spell_agility,APPLY_AGI,{10,10,10},{30,50,56}},
    {615,spell_holy_light,0,{30,50,56},{18,28,31},{0,0,0,AFF4_MAGE_FLAME}},
    {617,spell_lodestone_vision,0,{}, {5,5,5},{0,0,0,0,AFF5_MINE}},
    {680,spell_warring_zeal,APPLY_HITROLL,{6,10,11},{2,2,2}},
};
static void qualify_expansion_effects() {
    static_assert(std::size(expansion_cases)==50);
    for(const auto &entry:expansion_cases) {
        skills[entry.spell].name="qualification";
        skills[entry.spell].spell_pointer=entry.callback;
    }
    for(const auto &entry:expansion_cases) for(int pieces:{3,5,6,12,40})
        for(int actor_level:{12,56}) for(int kind:{0,1,2}) for(bool endpoint:{false,true}) {
            reset(); high_roll=endpoint;
            wearer.player.level=actor_level;
            wearer.player.m_class=kind?CLASS_SHAMAN:CLASS_WARRIOR;
            wearer.player.spec=kind==2?SPEC_ANIMALIST:0;
            const int sample=pieces==3?0:pieces==5?1:2;
            const int level=sample==0?30:sample==1?50:56;
            apply_zone_spell(&wearer,pieces,"Qualification",10000+entry.spell,&gear[0],entry.spell);
            if(entry.spell==SPELL_GUARDIAN_SPIRITS && !kind) {
                apply_zone_spell(&wearer,pieces,"Qualification",10000+entry.spell,&gear[0],entry.spell);
                assert(!wearer.affected && !grants && !guardian_rejections);
                entry.callback(30,&wearer,nullptr,0,&wearer,nullptr);
                assert(!wearer.affected && guardian_rejections==1); // manual restriction remains
                continue;
            }
            int modifiers[]={entry.modifiers[sample],entry.second_modifiers[sample]};
            int duration=entry.durations[sample];
            if(entry.spell==SPELL_FORTITUDE && actor_level==12) modifiers[0]=3;
            if(entry.spell==SPELL_DETECT_EVIL || entry.spell==SPELL_DETECT_GOOD) duration=actor_level;
            if(entry.spell==SPELL_GUARDIAN_SPIRITS && endpoint) {modifiers[0]=-200;duration+=4;}
            if(entry.spell==SPELL_LODESTONE && endpoint) duration=7;
            if(entry.spell==SPELL_VAPOR_STRIKE && endpoint) modifiers[0]=11;
            if(entry.spell==SPELL_SENSE_SPIRIT && kind) duration=level+5;
            if(entry.spell==SPELL_HAWKVISION && kind==2) duration=(level+20)/2;
            if(entry.spell==SPELL_WOLFSPEED) {
                const int bonus=kind==2?(endpoint?actor_level/2:10):0;
                duration=level+bonus+1;
                modifiers[0]=(level+bonus)/2+(endpoint?4:2);
            }
            const int nodes=entry.second_location?2:1;
            if(count(&wearer,entry.spell,true)!=nodes)
                fprintf(stderr,"missing effect=%d pieces=%d actor=%d class=%d roll=%d: nodes=%d expected=%d\n",
                    entry.spell,pieces,actor_level,kind,endpoint,count(&wearer,entry.spell,true),nodes);
            assert(count(&wearer,entry.spell,true)==nodes);
            for(auto *af=wearer.affected;af;af=af->next) {
                const bool second=entry.second_location && af->location==entry.second_location;
                const bool correct=af->type==entry.spell &&
                    af->location==(second?entry.second_location:entry.location) &&
                    af->modifier==modifiers[second] && af->duration==duration &&
                    af->set_owner==wearer.runtime_id && af->set_spell==entry.spell &&
                    af->set_zone==10000+entry.spell && (af->flags&AFFTYPE_NOSAVE);
                if(!correct) fprintf(stderr,"effect=%d pieces=%d actor=%d class=%d roll=%d: location=%d mod=%d duration=%d, expected mod=%d duration=%d\n",
                    entry.spell,pieces,actor_level,kind,endpoint,af->location,af->modifier,af->duration,modifiers[second],duration);
                assert(correct);
                const uint64_t bits[]={af->bitvector,af->bitvector2,af->bitvector3,af->bitvector4,af->bitvector5};
                for(int bank=0;bank<5;++bank) assert(bits[bank]==(second?0:entry.bits[bank]));
            }
            auto *source=wearer.affected; source->duration=1;
            apply_zone_spell(&wearer,pieces,"Qualification",10000+entry.spell,&gear[0],entry.spell);
            assert(wearer.affected==source && source->duration==1); // no periodic refresh
            entry.callback(30,&wearer,nullptr,0,&wearer,nullptr);
            assert(count(&wearer,entry.spell,false)==nodes);
            for(auto *af=wearer.affected;af;af=af->next)
                if(af->flags&AFFTYPE_SET_AFFECT)
                    assert((af->flags&(AFFTYPE_SET_SUSPENDED|AFFTYPE_NOAPPLY))==(AFFTYPE_SET_SUSPENDED|AFFTYPE_NOAPPLY));
            assert(reconcile_named_set_spell(&wearer,entry.spell));
            assert(count(&wearer,entry.spell,true)==0 && count(&wearer,entry.spell,false)==nodes);
            auto *ordinary=wearer.affected; ordinary->duration=1;
            apply_zone_spell(&wearer,pieces,"Qualification",10000+entry.spell,&gear[0],entry.spell);
            assert(wearer.affected==ordinary && ordinary->duration==1 && count(&wearer,entry.spell,true)==0);
            // The same native nodes also expire through the real affect tick.
            for(auto *af=wearer.affected;af;af=af->next) af->duration=0;
            affect_update(0); assert(!wearer.affected);
            apply_zone_spell(&wearer,pieces,"Qualification",10000+entry.spell,&gear[0],entry.spell);
            dispel_active(&wearer);
            assert(count(&wearer,entry.spell,true)==(entry.spell==SPELL_DIVINE_FURY?nodes:0));
            if(!wearer.affected)
                apply_zone_spell(&wearer,pieces,"Qualification",10000+entry.spell,&gear[0],entry.spell);
            for(auto *af=wearer.affected;af;af=af->next) af->duration=0;
            affect_update(0); assert(!wearer.affected); // set-owned expiry too
        }
    high_roll=false; reset();
    for(int alignment:{-1000,-350,-349,0,349,350,1000})
        for(int target_alignment:{-1000,-350,-349,0,349,350,1000}) {
            reset(); wearer.specials.alignment=alignment; companion.specials.alignment=target_alignment;
            assert(virtue_accuracy(&wearer,&companion)==1000);
            apply_zone_spell(&wearer,3,"Virtue",10515,&gear[0],SPELL_VIRTUE);
            const bool applies=(alignment>=350 && target_alignment<350) ||
                               (alignment<=-350 && target_alignment>-350);
            assert(virtue_accuracy(&wearer,&companion)==(applies?1100:1000));
            reconcile_named_set_spell(&wearer,SPELL_VIRTUE);
            assert(virtue_accuracy(&wearer,&companion)==1000);
        }
    for(int first:{SPELL_HOLY_LIGHT,SPELL_MAGE_FLAME,SPELL_GLOBE_OF_DARKNESS})
        for(int second:{SPELL_HOLY_LIGHT,SPELL_MAGE_FLAME,SPELL_GLOBE_OF_DARKNESS}) {
            if(first==second) continue;
            reset();
            int before=light_updates,room_before=room_light_updates;
            apply_zone_spell(&wearer,3,"First light",10000+first,&gear[0],first);
            auto *original=wearer.affected;
            assert(original && light_updates>before && room_light_updates>room_before);
            original->duration=1; before=light_updates; room_before=room_light_updates;
            int messages=output_messages;
            apply_zone_spell(&wearer,6,"Conflicting light",10000+second,&gear[0],second);
            apply_zone_spell(&wearer,6,"Conflicting light",10000+second,&gear[0],second);
            assert(output_messages==messages);
            assert(wearer.affected==original && !original->next && original->duration==1);
            assert(light_updates==before && room_light_updates==room_before);
            reconcile_named_set_spell(&wearer,first);
            assert(!wearer.affected && light_updates>before && room_light_updates>room_before);
            apply_zone_spell(&wearer,3,"Now available",10000+second,&gear[0],second);
            assert(count(&wearer,second,true)==1);
            reset();
            skills[first].spell_pointer(30,&wearer,nullptr,0,&wearer,nullptr);
            original=wearer.affected;
            messages=output_messages;
            apply_zone_spell(&wearer,6,"Ordinary light retained",10000+second,&gear[0],second);
            apply_zone_spell(&wearer,6,"Ordinary light retained",10000+second,&gear[0],second);
            assert(output_messages==messages);
            assert(wearer.affected==original && !original->next && !(original->flags&AFFTYPE_SET_AFFECT));
            skills[second].spell_pointer(30,&wearer,nullptr,0,&wearer,nullptr);
            assert(output_messages==messages+1); // Manual rejection remains visible.
        }
    for(int spell:{SPELL_PHANTOM_ARMOR,SPELL_VAPOR_ARMOR}) {
        reset(); inherent_armor=true; all_affects(&wearer,TRUE);
        apply_zone_spell(&wearer,3,"Inherent armor",10000+spell,&gear[0],spell);
        assert(!wearer.affected && !grants);
        reset(); spell_armor(40,&wearer,nullptr,0,&wearer,nullptr);
        auto *ordinary=wearer.affected;
        apply_zone_spell(&wearer,3,"Ordinary armor",10000+spell,&gear[0],spell);
        assert(wearer.affected==ordinary && !ordinary->next && ordinary->type==SPELL_ARMOR);
    }
    for(bool innate:{false,true}) {
        reset(); innate_eyes=innate;
        if(!innate) wearer.specials.affected_by|=AFF_INFRAVISION;
        apply_zone_spell(&wearer,3,"Inherent sight",10106,&gear[0],SPELL_INFRAVISION);
        assert(!wearer.affected && !grants);
    }
    innate_eyes=false;
    for(int other:{SPELL_MOLEVISION,SPELL_SNAILSPEED,SPELL_PANTHERSPEED}) {
        reset(); affected_type ordinary{}; ordinary.type=other; ordinary.duration=13;
        auto *existing=affect_to_char(&wearer,&ordinary);
        const int spell=other==SPELL_MOLEVISION?SPELL_HAWKVISION:SPELL_WOLFSPEED;
        apply_zone_spell(&wearer,3,"Shaman exclusion",10000+spell,&gear[0],spell);
        assert(wearer.affected==existing && !existing->next && existing->duration==13);
    }
    reset(); affected_type detection{}; detection.type=SPELL_DETECT_INVISIBLE;
    detection.bitvector=AFF_DETECT_INVISIBLE; detection.duration=13;
    auto *ordinary=affect_to_char(&wearer,&detection);
    apply_zone_spell(&wearer,3,"Illusion",10414,&gear[0],SPELL_DETECT_ILLUSION);
    reconcile_named_set_spell(&wearer,SPELL_DETECT_ILLUSION);
    assert(wearer.affected==ordinary && IS_AFFECTED((&wearer),AFF_DETECT_INVISIBLE));
    assert(!IS_AFFECTED4((&wearer),AFF4_DETECT_ILLUSION));
    reset();
}
static void ordinary_armor(affected_type **saved) {
    spell_armor(40,&wearer,nullptr,0,&wearer,nullptr);
    *saved=get_spell_from_char(&wearer,SPELL_ARMOR);
    assert(*saved && !((*saved)->flags&AFFTYPE_SET_AFFECT));
}
int main() {
    indexes[0].virtual_number=VOBJ_RANDOM_ARMOR; indexes[1].virtual_number=VOBJ_RANDOM_WEAPON;
    link_types[LNK_SONG].name="SONG"; link_types[LNK_SONG].flags=LNKFLG_AFFECT|LNKFLG_ROOM;
    skills[SPELL_ARMOR].name="armor"; skills[SPELL_ARMOR].spell_pointer=spell_armor;
    skills[SPELL_STRENGTH].name="strength"; skills[SPELL_STRENGTH].spell_pointer=spell_strength;
    skills[SPELL_ENDURANCE].name="endurance"; skills[SPELL_ENDURANCE].spell_pointer=spell_endurance;
    skills[SPELL_VAMPIRIC_TOUCH].name="vampiric touch"; skills[SPELL_VAMPIRIC_TOUCH].spell_pointer=spell_vampiric_touch;
    skills[SPELL_STONE_SKIN].name="stone skin"; skills[SPELL_STONE_SKIN].spell_pointer=spell_stone_skin;
    skills[SPELL_STORNOGS_SPHERES].name="spheres"; skills[SPELL_STORNOGS_SPHERES].spell_pointer=spell_stornogs_spheres;
    skills[SONG_DRAGONS].name="song of dragons"; skills[SKILL_EPIC_STRENGTH].name="epic strength";
    {
        reset(); track_hit_points=true;
        affected_type vitality{}; vitality.type=SPELL_VITALITY;
        vitality.location=APPLY_HIT; vitality.modifier=200; vitality.duration=17;
        {
            named_set_grant grant(&wearer,&wearer,824,SPELL_VITALITY);
            affect_to_char(&wearer,&vitality);
        }
        all_affects(&wearer,TRUE);
        // Equal or weaker casts, including from another caster, leave a wounded wearer alone.
        auto *granted=get_spell_from_char(&wearer,SPELL_VITALITY);
        for(int level:{50,40,21,1}) {
            GET_HIT(&wearer)=10; granted->duration=17;
            cast_native_vitality(level,&companion,nullptr,0,&wearer,nullptr);
            assert(GET_HIT(&wearer)==10 && GET_MAX_HIT(&wearer)==1200);
            assert(GET_STAT(&wearer)==STAT_NORMAL && IS_ALIVE(&wearer));
            assert(granted->duration==17 && !(granted->flags&AFFTYPE_SET_SUSPENDED));
            assert(count(&wearer,SPELL_VITALITY,false)==0 && count(&wearer,SPELL_VITALITY,true)==1);
        }
        // A stronger cast still replaces the grant for its duration.
        GET_HIT(&wearer)=50;
        cast_native_vitality(56,&wearer,nullptr,0,&wearer,nullptr);
        assert(GET_HIT(&wearer)==74 && GET_MAX_HIT(&wearer)==1224);
        assert(GET_STAT(&wearer)==STAT_NORMAL && IS_ALIVE(&wearer));
        assert(count(&wearer,SPELL_VITALITY,false)==1 && count(&wearer,SPELL_VITALITY,true)==1);
        assert(granted->flags&AFFTYPE_SET_SUSPENDED);
        // Under a stronger cast, a weak one refreshes that cast instead of the dormant grant.
        cast_native_vitality(21,&companion,nullptr,0,&wearer,nullptr);
        assert(GET_HIT(&wearer)==74 && GET_MAX_HIT(&wearer)==1224);
    }
    {
        // The ordinary cast lands on its target and leaves the target's set grant unchanged.
        reset();
        affected_type undead{}; undead.type=SPELL_PROT_FROM_UNDEAD; undead.duration=17;
        undead.bitvector5=AFF5_PROT_UNDEAD;
        affected_type *granted;
        {
            named_set_grant grant(&wearer,&wearer,412,SPELL_PROT_FROM_UNDEAD);
            granted=affect_to_char(&wearer,&undead);
        }
        spell_prot_from_undead(56,&companion,nullptr,0,&wearer,nullptr);
        assert(granted->duration==17 && (granted->flags&AFFTYPE_SET_SUSPENDED));
        assert(count(&wearer,SPELL_PROT_FROM_UNDEAD,false)==1 && !companion.affected);
    }
    reset();
    affected_type *ordinary=nullptr;
    {
        reset();
        affected_type regeneration{}; regeneration.type=SPELL_REGENERATION;
        regeneration.duration=17; regeneration.bitvector4=AFF4_REGENERATION;
        affected_type *set_regeneration;
        {
            named_set_grant grant(&wearer,&wearer,18,SPELL_REGENERATION);
            set_regeneration=affect_to_char(&wearer,&regeneration);
        }
        affected_type crown{}; crown.type=SPELL_REGENERATION;
        crown.flags=AFFTYPE_ARAMUS_CROWN_REGENERATION;
        crown.duration=11; crown.location=APPLY_HIT_REG; crown.modifier=70;
        auto *crown_regeneration=affect_to_char(&wearer,&crown);
        all_affects(&wearer,TRUE);
        assert(!(set_regeneration->flags&AFFTYPE_SET_SUSPENDED));
        assert(IS_AFFECTED4(&wearer,AFF4_REGENERATION));
        assert(set_regeneration->duration==17 && crown_regeneration->duration==11);
        regeneration.duration=5;
        auto *ordinary_regeneration=affect_to_char(&wearer,&regeneration);
        assert(set_regeneration->flags&AFFTYPE_SET_SUSPENDED);
        affect_remove(&wearer,ordinary_regeneration);
        assert(!(set_regeneration->flags&AFFTYPE_SET_SUSPENDED));
        affect_remove(&wearer,crown_regeneration);
        all_affects(&wearer,TRUE);
        assert(IS_AFFECTED4(&wearer,AFF4_REGENERATION));
    }
    reset();
    ordinary_armor(&ordinary); ordinary->duration=7;
    apply_zone_spell(&wearer,3,"Tharnadia",1325,&gear[0],SPELL_ARMOR);
    assert(!grants && ordinary->duration==7 && !ordinary->set_zone && !ordinary->set_spell && !ordinary->set_owner);
    assert(!reconcile_named_set_spell(&wearer,SPELL_ARMOR) && get_spell_from_char(&wearer,SPELL_ARMOR)==ordinary);
    // Vampire/Angelic Countenance use the same registered handler, with an alias affect ID.
    reset();
    skills[SPELL_VAMPIRE].name="vampire"; skills[SPELL_VAMPIRE].spell_pointer=alias_effect;
    skills[SPELL_ANGELIC_COUNTENANCE].name="angelic countenance"; skills[SPELL_ANGELIC_COUNTENANCE].spell_pointer=alias_effect;
    affected_type angel{}; angel.type=SPELL_ANGELIC_COUNTENANCE; angel.duration=7;
    ordinary=affect_to_char(&wearer,&angel); alias_calls=0;
    apply_zone_spell(&wearer,8,"Barovia",583,&gear[0],SPELL_VAMPIRE);
    assert(!alias_calls && ordinary->duration==7 && !(ordinary->flags&AFFTYPE_SET_AFFECT));
    reset();
    apply_zone_spell(&wearer,8,"Barovia",583,&gear[0],SPELL_VAMPIRE);
    apply_zone_spell(&wearer,8,"Barovia",583,&gear[0],SPELL_VAMPIRE);
    assert(alias_calls==1 && wearer.affected->type==SPELL_ANGELIC_COUNTENANCE && wearer.affected->set_spell==SPELL_VAMPIRE);
    assert(reconcile_named_set_spell(&wearer,SPELL_VAMPIRE) && !wearer.affected);

    // Actual ordinary entries after a set create their own nodes and duration,
    // while the original grant remains dormant with no extra numeric benefit.
    reset(); for(int i=0;i<3;++i) wear(i,i+1,14);
    apply_zone_spell(&wearer,3,"Kobolds",14,&gear[0],SPELL_ARMOR);
    auto *set_armor=get_spell_from_char(&wearer,SPELL_ARMOR); set_armor->duration=8;
    spell_armor(40,&companion,nullptr,0,&wearer,nullptr);
    auto *cast_armor=get_spell_from_char(&wearer,SPELL_ARMOR);
    assert(cast_armor!=set_armor && !(cast_armor->flags&AFFTYPE_SET_AFFECT) && cast_armor->duration==20);
    assert(set_armor->duration==8 && (set_armor->flags&AFFTYPE_SET_SUSPENDED));
    assert(active_modifier(&wearer,SPELL_ARMOR)==cast_armor->modifier && count(&wearer,SPELL_ARMOR,true)==1);
    cast_armor->duration=2;
    spell_armor(56,&companion,nullptr,0,&wearer,nullptr);
    assert(cast_armor->duration==20 && set_armor->duration==8);
    affect_update(0);
    assert(set_armor->duration==7 && cast_armor->duration==19);
    affect_remove(&wearer,cast_armor);
    assert(get_spell_from_char(&wearer,SPELL_ARMOR)==set_armor && set_armor->duration==7 && !(set_armor->flags&AFFTYPE_NOAPPLY));
    assert(grants==1); // no fresh set invocation was needed to resume it

    // Removing the set first preserves the ordinary spell's independent lifetime.
    reset(); for(int i=0;i<3;++i) wear(i,i+1,14);
    apply_zone_spell(&wearer,3,"Kobolds",14,&gear[0],SPELL_ARMOR);
    spell_armor(40,&companion,nullptr,0,&wearer,nullptr);
    cast_armor=get_spell_from_char(&wearer,SPELL_ARMOR);
    for(auto &item:wearer.equipment) item=nullptr;
    assert(reconcile_named_set_spell(&wearer,SPELL_ARMOR));
    assert(get_spell_from_char(&wearer,SPELL_ARMOR)==cast_armor && cast_armor->duration==20);

    // A dormant grant still expires on its original clock, without replacing a cast.
    reset(); apply_zone_spell(&wearer,3,"Kobolds",14,&gear[0],SPELL_ARMOR);
    set_armor=get_spell_from_char(&wearer,SPELL_ARMOR); set_armor->duration=1;
    spell_armor(40,&companion,nullptr,0,&wearer,nullptr);
    cast_armor=get_spell_from_char(&wearer,SPELL_ARMOR);
    affect_update(0); affect_update(0);
    assert(!count(&wearer,SPELL_ARMOR,true) && get_spell_from_char(&wearer,SPELL_ARMOR)==cast_armor && cast_armor->duration==18);

    // Native refusals restore the old grant; inherent armor remains an exclusion.
    reset(); apply_zone_spell(&wearer,3,"Kobolds",14,&gear[0],SPELL_ARMOR);
    set_armor=get_spell_from_char(&wearer,SPELL_ARMOR); set_armor->duration=7;
    inherent_armor=true;
    spell_armor(40,&companion,nullptr,0,&wearer,nullptr);
    assert(get_spell_from_char(&wearer,SPELL_ARMOR)==set_armor && set_armor->duration==7 && !count(&wearer,SPELL_ARMOR,false));

    // Self casts and direct group calls use the same entries, beyond sparser.
    reset(); apply_zone_spell(&wearer,5,"Tharnadia",1325,&gear[0],SPELL_ENDURANCE);
    auto *set_endurance=get_spell_from_char(&wearer,SPELL_ENDURANCE); set_endurance->duration=6;
    spell_endurance(40,&wearer,nullptr,0,&wearer,nullptr);
    auto *cast_endurance=get_spell_from_char(&wearer,SPELL_ENDURANCE);
    assert(cast_endurance!=set_endurance && cast_endurance->duration==9 && set_endurance->duration==6);
    affect_remove(&wearer,cast_endurance);
    assert(get_spell_from_char(&wearer,SPELL_ENDURANCE)==set_endurance && set_endurance->duration==6);
    reset(); apply_zone_spell(&wearer,3,"Kobolds",14,&gear[0],SPELL_ARMOR);
    set_armor=get_spell_from_char(&wearer,SPELL_ARMOR);
    group_list group{}; group.ch=&wearer; wearer.group=&group;
    spell_miracle(56,&wearer,nullptr,0,nullptr,nullptr);
    assert(get_spell_from_char(&wearer,SPELL_ARMOR)!=set_armor && (set_armor->flags&AFFTYPE_SET_SUSPENDED));
    wearer.group=nullptr;

    // Explicit spell-type dispelling still clears the whole type, independently
    // of which source is at the head; no dormant grant is left to break reveal.
    for(bool source_first : {false,true}) {
        reset(); for(int i=0;i<3;++i) wear(i,i+1,14);
        apply_zone_spell(&wearer,3,"Kobolds",14,&gear[0],SPELL_ARMOR);
        set_armor=get_spell_from_char(&wearer,SPELL_ARMOR); set_armor->duration=9;
        spell_armor(40,&companion,nullptr,0,&wearer,nullptr);
        cast_armor=get_spell_from_char(&wearer,SPELL_ARMOR);
        if(!source_first) {wearer.affected=cast_armor; cast_armor->next=set_armor; set_armor->next=nullptr;}
        skills[SPELL_ARMOR].wear_off_char[0]="Your armor fades.";
        int messages=output_messages;
        dispel_active(&wearer);
        assert(output_messages==messages+2); // The buff is gone, so its message and newline print.
        skills[SPELL_ARMOR].wear_off_char[0]=nullptr;
        assert(!get_spell_from_char(&wearer,SPELL_ARMOR) && !count(&wearer,SPELL_ARMOR,true) && !count(&wearer,SPELL_ARMOR,false));
    }
    // Consumable protections spend the active ordinary counter and resume only
    // the original remaining set charges, without a fresh set invocation.
    reset(); apply_zone_spell(&wearer,6,"Earth",238,&gear[0],SPELL_STONE_SKIN);
    auto *set_skin=get_spell_from_char(&wearer,SPELL_STONE_SKIN);
    const int original_charges=set_skin->modifier; set_skin->duration=3;
    spell_stone_skin(40,&companion,nullptr,0,&wearer,nullptr);
    auto *cast_skin=get_spell_from_char(&wearer,SPELL_STONE_SKIN);
    assert(cast_skin!=set_skin && (set_skin->flags&AFFTYPE_SET_SUSPENDED));
    const int cast_charges=cast_skin->modifier;
    assert(decrease_skin_counter(&wearer,SPELL_STONE_SKIN));
    assert(cast_skin->modifier==cast_charges-1 && set_skin->modifier==original_charges);
    cast_skin->modifier=1;
    assert(decrease_skin_counter(&wearer,SPELL_STONE_SKIN));
    assert(get_spell_from_char(&wearer,SPELL_STONE_SKIN)==set_skin && set_skin->modifier==original_charges && set_skin->duration==3 && grants==1);
    reset(); apply_zone_spell(&wearer,8,"Sea Kingdom",315,&gear[0],SPELL_STORNOGS_SPHERES);
    auto *set_spheres=get_spell_from_char(&wearer,SPELL_STORNOGS_SPHERES);
    spell_stornogs_spheres(40,&companion,nullptr,0,&wearer,nullptr);
    auto *cast_spheres=get_spell_from_char(&wearer,SPELL_STORNOGS_SPHERES);
    assert(cast_spheres!=set_spheres && (set_spheres->flags&AFFTYPE_SET_SUSPENDED));
    assert(hit_sphere(&wearer)==DAM_NONEDEAD);
    assert(get_spell_from_char(&wearer,SPELL_STORNOGS_SPHERES)==set_spheres && set_spheres->modifier==1 && IS_AFFECTED4(&wearer,AFF4_STORNOGS_SPHERES));
    assert(hit_sphere(&wearer)==DAM_NONEDEAD && !affected_by_spell(&wearer,SPELL_STORNOGS_SPHERES) && !IS_AFFECTED4(&wearer,AFF4_STORNOGS_SPHERES));

    // A received timed song and an ordinary song keep their separate links and clocks.
    reset(); apply_zone_spell(&wearer,9,"Dragonnia",68,&gear[0],SONG_DRAGONS);
    auto *received_song=get_spell_from_char(&companion,SONG_DRAGONS); received_song->duration=12;
    bard_dragons(56,&companion,&companion,SONG_DRAGONS);
    auto *ordinary_song=get_spell_from_char(&companion,SONG_DRAGONS);
    assert(ordinary_song!=received_song && !(ordinary_song->flags&AFFTYPE_SET_AFFECT) && (received_song->flags&AFFTYPE_SET_SUSPENDED));
    assert(ordinary_song->duration==1 && received_song->duration==12);
    affect_remove(&companion,ordinary_song);
    assert(get_spell_from_char(&companion,SONG_DRAGONS)==received_song && received_song->duration==12 && received_song->set_owner==1);

    // Fresh set nodes carry provenance; ordinary allocation during no grant cannot inherit it.
    reset(); apply_zone_spell(&wearer,3,"Tharnadia",1325,&gear[0],SPELL_ARMOR);
    auto *owned=get_spell_from_char(&wearer,SPELL_ARMOR);
    assert(owned && owned->set_zone==1325 && owned->set_spell==SPELL_ARMOR && owned->set_owner==1);
    assert(owned->flags&AFFTYPE_NOSAVE);
    affected_type cast=*owned; cast.flags=0; cast.duration=11;
    auto *independent=affect_to_char(&wearer,&cast);
    assert(!independent->set_zone && !independent->set_spell && !independent->set_owner);
    assert(reconcile_named_set_spell(&wearer,SPELL_ARMOR));
    assert(get_spell_from_char(&wearer,SPELL_ARMOR)==independent && independent->duration==11);

    // Two real set rows sharing armor retain a single original buff and its duration.
    for(int first : {14,1325}) {
        reset(); for(int i=0;i<3;++i) {wear(i,i+1,14); wear(i+3,i+4,1325);}
        apply_zone_spell(&wearer,3,"Kobolds",14,&gear[0],SPELL_ARMOR);
        owned=get_spell_from_char(&wearer,SPELL_ARMOR);
        owned->duration=9;
        apply_zone_spell(&wearer,3,"Tharnadia",1325,&gear[3],SPELL_ARMOR);
        assert(count(&wearer,SPELL_ARMOR,true)==1 && owned->duration==9);
        for(int slot=1;slot<=6;++slot) if(named_set_origin(wearer.equipment[slot]).zone==first) wearer.equipment[slot]=nullptr;
        assert(!reconcile_named_set_spell(&wearer,SPELL_ARMOR));
        assert(owned->set_zone==(first==14 ? 1325 : 14) && owned->duration==9);
        for(auto &item:wearer.equipment) item=nullptr;
        assert(reconcile_named_set_spell(&wearer,SPELL_ARMOR) && !wearer.affected);
    }
    // Reconciliation uses the same counting exclusions and needs a worn armor driver.
    reset(); apply_zone_spell(&wearer,3,"Kobolds",14,&gear[0],SPELL_ARMOR);
    for(int i=0;i<3;++i) wear(i,i+1,1325,true);
    assert(reconcile_named_set_spell(&wearer,SPELL_ARMOR));
    reset(); apply_zone_spell(&wearer,3,"Kobolds",14,&gear[0],SPELL_ARMOR);
    wear(0,WEAR_BODY,1325); wear(1,WEAR_HEAD,1325); wear(2,WEAR_ATTACH_BELT_2,1325);
    assert(reconcile_named_set_spell(&wearer,SPELL_ARMOR));
    apply_zone_spell(&wearer,3,"Kobolds",14,&gear[0],SPELL_ARMOR);
    wear(3,WEAR_ATTACH_BELT_1,1325);
    assert(!reconcile_named_set_spell(&wearer,SPELL_ARMOR));
    // Provenance does not borrow or overwrite native context payloads.
    reset();
    affected_type contextual{}; contextual.type=SPELL_ENDURANCE;
    contextual.context=reinterpret_cast<void *>(static_cast<intptr_t>(123));
    {
        named_set_grant grant(&wearer,&wearer,1325,SPELL_ENDURANCE);
        owned=affect_to_char(&wearer,&contextual);
        assert(grant.created_affects() && owned->context==contextual.context);
    }
    assert(reconcile_named_set_spell(&wearer,SPELL_ENDURANCE) && !wearer.affected);
    // Different spells remain independent.
    reset();
    apply_zone_spell(&wearer,5,"Tharnadia",1325,&gear[0],SPELL_ENDURANCE);
    apply_zone_spell(&wearer,3,"Towers",93,&gear[0],SPELL_STRENGTH);
    auto *endurance=get_spell_from_char(&wearer,SPELL_ENDURANCE);
    assert(endurance && endurance->modifier==11 && endurance->duration==11);
    assert(reconcile_named_set_spell(&wearer,SPELL_STRENGTH) && get_spell_from_char(&wearer,SPELL_ENDURANCE)==endurance);
    assert(reconcile_named_set_spell(&wearer,SPELL_ENDURANCE) && !wearer.affected);
    // A real multipart grant removes both owned locations and preserves an ordinary instance.
    apply_zone_spell(&wearer,6,"Mansion",35,&gear[0],SPELL_VAMPIRIC_TOUCH);
    assert(count(&wearer,SPELL_VAMPIRIC_TOUCH,true)==2);
    cast=*get_spell_from_char(&wearer,SPELL_VAMPIRIC_TOUCH); cast.flags=0; cast.duration=3;
    independent=affect_to_char(&wearer,&cast);
    assert(reconcile_named_set_spell(&wearer,SPELL_VAMPIRIC_TOUCH));
    assert(!count(&wearer,SPELL_VAMPIRIC_TOUCH,true) && get_spell_from_char(&wearer,SPELL_VAMPIRIC_TOUCH)==independent && independent->duration==3);
    // Epic stat grants must detect their own affect instead of repeating each tick.
    reset();
    apply_zone_spell(&wearer,3,"Zalkapfaan",27,&gear[0],SKILL_EPIC_STRENGTH);
    apply_zone_spell(&wearer,3,"Zalkapfaan",27,&gear[0],SKILL_EPIC_STRENGTH);
    assert(count(&wearer,SKILL_EPIC_STRENGTH,true)==1 && wearer.affected->loc2==SKILL_EPIC_STRENGTH);

    // Existing ordinary group songs are never retagged or given a new duration.
    reset();
    affected_type song{}; song.type=SONG_DRAGONS; song.duration=3;
    auto *old_song=affect_to_char(&companion,&song);
    apply_zone_spell(&wearer,9,"Dragonnia",68,&gear[0],SONG_DRAGONS);
    assert(old_song->duration==3 && !(old_song->flags&AFFTYPE_SET_AFFECT));
    assert(wearer.affected && get_spell_from_char(&wearer,SONG_DRAGONS)->set_owner==1);
    assert(get_spell_from_char(&wearer,SONG_DRAGONS)->duration==56/3);
    assert(!(get_spell_from_char(&wearer,SPELL_PROTECT_FROM_FIRE)->flags&AFFTYPE_SET_AFFECT));
    assert(reconcile_named_set_spell(&wearer,SONG_DRAGONS));
    assert(!get_spell_from_char(&wearer,SONG_DRAGONS) && get_spell_from_char(&wearer,SPELL_PROTECT_FROM_FIRE));
    assert(get_spell_from_char(&companion,SONG_DRAGONS)==old_song);
    // A member whose short ordinary song lapses is not left bare by the wearer's longer grant.
    reset();
    affected_type short_song{}; short_song.type=SONG_DRAGONS; short_song.duration=1;
    auto *lapsing=affect_to_char(&companion,&short_song);
    apply_zone_spell(&wearer,9,"Dragonnia",68,&gear[0],SONG_DRAGONS);
    auto *wearer_song=get_spell_from_char(&wearer,SONG_DRAGONS);
    assert(wearer_song && lapsing->duration==1 && !(lapsing->flags&AFFTYPE_SET_AFFECT));
    // While the ordinary song lasts, the periodic grant leaves it alone.
    apply_zone_spell(&wearer,9,"Dragonnia",68,&gear[0],SONG_DRAGONS);
    assert(get_spell_from_char(&companion,SONG_DRAGONS)==lapsing && lapsing->duration==1);
    affect_remove(&companion,lapsing);
    wearer_song->duration=5;
    apply_zone_spell(&wearer,9,"Dragonnia",68,&gear[0],SONG_DRAGONS);
    auto *regranted=get_spell_from_char(&companion,SONG_DRAGONS);
    assert(regranted && regranted->set_owner==1 && regranted->duration==56/3);
    assert(get_spell_from_char(&wearer,SONG_DRAGONS)==wearer_song && wearer_song->duration==5);
    // A recipient's gear cleanup must not remove another wearer's timed linked song.
    reset(); apply_zone_spell(&wearer,9,"Dragonnia",68,&gear[0],SONG_DRAGONS);
    auto *received=get_spell_from_char(&companion,SONG_DRAGONS);
    assert(received && received->set_owner==1 && received->duration==56/3);
    assert(!reconcile_named_set_spell(&companion,SONG_DRAGONS) && get_spell_from_char(&companion,SONG_DRAGONS)==received);
    reset();
    qualify_expansion_effects();
    {
        // Rejected periodic attempts print nothing, however many procs run.
        const auto silent=[](int spell) {
            const int messages=output_messages;
            for(int proc=0;proc<6;++proc)
                apply_zone_spell(&wearer,3,"Rejected",10000+spell,&gear[0],spell);
            assert(output_messages==messages && !grants && !count(&wearer,spell,true));
        };
        for(int spell:{SPELL_PHANTOM_ARMOR,SPELL_VAPOR_ARMOR}) {
            reset(); spell_armor(40,&wearer,nullptr,0,&wearer,nullptr); silent(spell);
            reset(); inherent_armor=true; all_affects(&wearer,TRUE); silent(spell);
        }
        for(int blocker:{SPELL_PANTHERSPEED,SPELL_MOLEVISION}) {
            reset();
            affected_type other{}; other.type=blocker; other.duration=9;
            affect_to_char(&wearer,&other);
            silent(blocker==SPELL_PANTHERSPEED?SPELL_WOLFSPEED:SPELL_HAWKVISION);
        }
        // A successful attempt keeps the spell's own output and the set's line.
        reset();
        const int messages=output_messages;
        apply_zone_spell(&wearer,3,"Granted",10000+SPELL_FORTITUDE,&gear[0],SPELL_FORTITUDE);
        assert(grants==1 && output_messages==messages+2);
    }
}
'''

build = ROOT / "bin/tests"
# Keep the fixture's IDs and callbacks aligned with the recorded pool and actual
# registration, so a missing/rebound entry cannot silently evade qualification.
assignments = (ROOT / "docs/ongoing-projects/named-zone-set-first-pass-assignments.md").read_text()
pool = assignments.split("## Effect homes after both passes")[1].split("\n## ", 1)[0]
pool_ids = {int(value) for value in re.findall(r"\(#(\d+)\)", pool)}
tested = {int(value): callback for value, callback in re.findall(r"^    \{(\d+),(spell_\w+),", harness, re.M)}
assert set(tested) == pool_ids and len(tested) == 50
defines = dict(re.findall(r"^#define\s+(\w+)\s+(\d+)\s*(?://[^\n]*)?$", (ROOT / "src/magic/spells.h").read_text(), re.M))
registered = {}
for token, callback in re.findall(r'SPELL_CREATE(?:_MSG)?\(\s*"[^"\n]*"\s*,\s*(\w+)\s*,(?:(?!SPELL_CREATE)[\s\S])*?\b(spell_\w+)\s*[,)]', (ROOT / "src/classes/skills.c").read_text()):
    if token in defines and int(defines[token]) in pool_ids:
        registered[int(defines[token])] = callback
assert tested == registered
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="named-set-effects-", dir=build) as directory:
    cpp = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    cpp.write_text(harness)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-pie", "-no-pie",
        "-ffunction-sections", "-fdata-sections", "-Isrc", str(cpp), "src/item/named_set_effects.c",
        "src/item/named_set_origin.c", "src/item/named_sets.c", "src/item/random_equipment_tables.c",
        str(HARNESS_STUBS), "-Wl,--gc-sections", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
print("real named-set ownership plus all 50 expansion handlers, power, classes, alignment, exclusions, expiry and dispel: passed")
