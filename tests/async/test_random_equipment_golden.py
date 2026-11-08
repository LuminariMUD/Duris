#!/usr/bin/env python3
"""Random equipment, roll for roll: every drop decision, item, material and stone.

The harness compiles the module's own source files whole, links the real RNG
(src/core/random.c), safe_format.c and both config modules at their compiled-in
defaults, and takes the few helpers it calls from elsewhere (dice, strip_ansi,
FirstWord, isname, material_restrictions, GET_CLASS, BOUNDED and the string setters)
from their real source. Only
the world is stubbed: three zones, four rooms, the two blank objects, materials and
stones by vnum and the difficulty dials. It runs under ASan
and UBSan.

Each case seeds the RNG from its own name, so a failure names one case and adding a
case moves no other. The output must equal tests/fixtures/random_equipment_golden.txt,
written from the code of 2026-10-10. Issue #812 intentionally updates only the four
pet-kill cases to use owner rewards; all other cases remain frozen across module
refactors. A companion fixture records a sentinel roll after each
case to detect terminal draws that leave the current item unchanged. Direct assertions
also cover every suffix total, blank template identity and rejected kill contexts
without changing the frozen output.
"""
import os
import json
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

FIXTURE = ROOT / "tests/fixtures/random_equipment_golden.txt"
RNG_FIXTURE = ROOT / "tests/fixtures/random_equipment_rng_golden.txt"
MODULE_SOURCES = [
    "src/item/random_equipment.c",
    "src/item/random_equipment_drop.c",
    "src/item/random_equipment_tables.c",
]
LINKED_SOURCES = [
    "src/core/random.c",
    "src/item/named_set_origin.c",
    "src/core/safe_format.c",
    "src/item/random_equipment_config.c",
    "src/world/hardcore_config.c",
]
HELPERS = [
    ("utility.c", "int dice(int num, int size)"),
    ("utility.c", "string strip_ansi(const char *str)"),
    ("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
    ("utility.c", "int BOUNDED(int a, int b, int c)"),
    ("new_skills.c", "int CanDoFightMove("),
    ("handler.c", "char *FirstWord(char *namelist)"),
    ("handler.c", "bool isname(const char *str, const char *namelist)"),
    ("handler.c", "void set_obj_extra2_flags("),
    ("objconv.c", "void material_restrictions(P_obj obj)"),
    ("salchemist.c", "void set_keywords(P_obj t_obj, const char *newKeys)"),
    ("salchemist.c", "void set_short_description(P_obj t_obj, const char *newShort)"),
    ("salchemist.c", "void set_long_description(P_obj t_obj, const char *newDescription)"),
]


def class_groups():
    """The ALL_MAGES and ALL_ROGUES masks material_restrictions() uses."""
    text = (ROOT / "src/item/objconv.c").read_text()
    return text[text.index("#define ALL_MAGES") : text.index("// Sets anti-class flags")]


HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "net/gmcp.h"
#include "net/comm.h"
#include "item/objmisc.h"
#include "item/random_equipment.h"
#include "item/named_set_origin.h"
#include "item/weapon_actions.h"
#include "magic/spells.h"
#include "world/difficulty.h"
#include "world/vnum.obj.h"
#include "combat/training_dummy.h"

#include <cassert>
#include <climits>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

// ---- The world ----
void gmcp_item_changed(P_obj) {}
// Zone 0 has colour codes in its name, so its items can be named; zone 1 is plain; zone 2
// is a town. Room 2 is a guild room in zone 1.
static zone_data zones[3];
static room_data rooms[4];
static index_data mob_protos[2]; // 0: an ordinary mob, 1: a shopkeeper
struct zone_data *zone_table = zones;
P_room world = rooms;
int top_of_zone_table = 2;
P_index mob_index = mob_protos;
static index_data item_protos[VOBJ_RANDOM_WEAPON + 1];
P_index obj_index = item_protos;
Skill skills[MAX_SKILLS];
enum { ROOM_COLOURED, ROOM_PLAIN, ROOM_GUILD_HALL, ROOM_TOWN };

// Birthplaces are virtual room numbers, not indexes. Zero is unset here.
int real_room(const int vnum)
{
    for (int i = 0; i < 4; ++i)
        if (rooms[i].number == vnum) return i;
    return -1;
}

static void setup_world()
{
	for (int i = 0; i < 4; ++i) rooms[i].number = 80000 + i;
	item_protos[VOBJ_RANDOM_ARMOR].virtual_number = VOBJ_RANDOM_ARMOR;
	item_protos[VOBJ_RANDOM_WEAPON].virtual_number = VOBJ_RANDOM_WEAPON;
	zones[0].name = const_cast<char *>("&+rThe &+RBurning&n Wastes");
	zones[0].number = 740;
	zones[1].number = 1325;
	zones[2].number = 204;
	zones[0].difficulty = 5;
	zones[1].name = const_cast<char *>("Quiet Hills");
	zones[1].difficulty = 1;
	zones[2].name = const_cast<char *>("Market Town");
	zones[2].difficulty = 1;
	zones[2].hometown = 1;
	rooms[ROOM_COLOURED].zone = 0;
	rooms[ROOM_PLAIN].zone = 1;
	rooms[ROOM_GUILD_HALL].zone = 1;
	rooms[ROOM_GUILD_HALL].room_flags = ROOM_GUILD;
	rooms[ROOM_TOWN].zone = 2;
	mob_protos[1].func.mob = shop_keeper;
}

static double loot_drops_dial = 1.0, loot_quality_dial = 1.0;
double difficulty_multiplier(difficulty_dial dial)
{
	return dial == DIFFICULTY_LOOT_DROPS ? loot_drops_dial :
	       dial == DIFFICULTY_LOOT_QUALITY ? loot_quality_dial : 1.0;
}

int shop_keeper(P_char, P_char, int, char *) { return 0; }
bool training_dummy_is(P_char) {return false;}
bool training_dummy_target_allowed(P_char,P_char) {return true;}
void training_dummy_retarget_nonpet(P_char,P_char) {assert(false);}
bool ac_can_see(P_char,P_char,bool) {return true;}
bool AdjacentInRoom(P_char,P_char) {return true;}
P_char get_linking_char(P_char,ush_int) {return nullptr;}
int GET_CHAR_SKILL_P(P_char,int) {return 0;}
void debug(const char *,...) {assert(false);}
item_action_start selected_random_weapon_action(P_obj, P_char, P_char, int, int)
{
	return item_action_start::legacy;
}
char *str_dup(const char *source) { return source ? strdup(source) : nullptr; }
void *__malloc(size_t size, const char *, const char *, int) { return calloc(1, size); }
void __free(void *p, const char *, int) { free(p); }

// Every message the module sends, in order, for the current case.
static std::string sent;
void send_to_char(const char *text, P_char ch)
{
	sent += " msg(" + std::string(GET_NAME(ch)) + "): " + text;
	while (!sent.empty() && (sent.back() == '\n' || sent.back() == '\r'))
		sent.pop_back();
}

// The two blanks (as areas/obj/heavens.obj defines them), materials and stones.
static bool blanks_missing = false;
P_obj read_object(int nr, int type)
{
	if (type != VIRTUAL)
		return nullptr;
	const bool blank = nr == VOBJ_RANDOM_ARMOR || nr == VOBJ_RANDOM_WEAPON;
	const bool material = nr >= 400000 && nr <= 400209;
	const bool stone = nr >= ENCRUST_VNUM_BEGIN && nr <= ENCRUST_VNUM_END;
	if ((blank && blanks_missing) || (!blank && !material && !stone))
		return nullptr;
	P_obj obj = new obj_data{};
	obj->R_num = nr; // The harness reads the vnum back from here.
	// Prototype strings are borrowed until a real setter installs an owned replacement.
	obj->name = const_cast<char *>(nr == VOBJ_RANDOM_WEAPON ? "object enchant" : "object random");
	obj->short_description = const_cast<char *>("a blank");
	obj->description = const_cast<char *>("A blank lies here.");
	if (blank)
	{
		obj->type = ITEM_TRASH;
		obj->material = 15;
		obj->craftsmanship = 7;
		obj->extra_flags = 8256;
	}
	return obj;
}
static void release(P_obj obj)
{
	if (!obj)
		return;
	if (obj->str_mask & STRUNG_KEYS)
		free(obj->name);
	if (obj->str_mask & STRUNG_DESC2)
		free(obj->short_description);
	if (obj->str_mask & STRUNG_DESC1)
		free(obj->description);
	while (obj->ex_description) {
		auto *description = obj->ex_description;
		obj->ex_description = description->next;
		free(description->keyword);
		free(description->description);
		free(description);
	}
	delete obj;
}

// What the kill drop puts on the victim.
static std::string given;
static bool capture_rewards = false;
static int equipment_count, material_count, stone_count;
static std::string reward_state;
static void capture_reward(P_obj obj);
bool obj_to_char(P_obj obj, P_char ch)
{
	if (capture_rewards)
	{
		assert(std::string(GET_NAME(ch)) == "victim");
		capture_reward(obj);
	}
	char line[64];
	if (obj->R_num == VOBJ_RANDOM_ARMOR || obj->R_num == VOBJ_RANDOM_WEAPON)
	{
		assert((obj->str_mask & ~STRUNG_EDESC) == (STRUNG_KEYS | STRUNG_DESC1 | STRUNG_DESC2));
		assert(obj->R_num == (obj->wear_flags & ITEM_WIELD ? VOBJ_RANDOM_WEAPON : VOBJ_RANDOM_ARMOR));
		given += std::string(" eq[") + obj->name + "]";
	}
	else
	{
		snprintf(line, sizeof(line), " obj%d", obj->R_num);
		given += line;
	}
	given += std::string("->") + GET_NAME(ch);
	release(obj);
	return false;
}

// ---- Characters ----
static P_char pet_owner = nullptr, owned_pet = nullptr;
P_char get_linked_char(P_char ch, ush_int type)
{
	return type == LNK_PET && ch == owned_pet ? pet_owner : nullptr;
}

struct person {
	char_data ch{};
	pc_only_data pc{};
	npc_only_data npc{};
	person(const char *name, int level, int luck, bool is_pc, int room = ROOM_COLOURED)
	{
		ch.player.name = const_cast<char *>(name);
		ch.player.level = level;
		ch.player.racewar = RACEWAR_GOOD;
		ch.curr_stats.Luk = luck;
		ch.in_room = room;
		ch.points.curr_exp = 1000;
		SET_POS(&ch, STAT_NORMAL + POS_STANDING);
		if (is_pc)
			ch.only.pc = &pc;
		else
		{
			ch.only.npc = &npc;
			SET_BIT(ch.specials.act, ACT_ISNPC);
		}
	}
};

// ---- Output ----
static uint64_t seed_of(const std::string &name)
{
	uint64_t hash = 1469598103934665603ULL; // FNV-1a
	for (unsigned char c : name)
		hash = (hash ^ c) * 1099511628211ULL;
	return hash ? hash : 1;
}
static std::string current;
static void start_case(const std::string &name)
{
	current = name + " |";
	sent.clear();
	given.clear();
	randomize(seed_of(name));
}
static void put(const char *format, ...) __attribute__((format(printf, 1, 2)));
static void put(const char *format, ...)
{
	char buffer[4096];
	va_list args;
	va_start(args, format);
	vsnprintf(buffer, sizeof(buffer), format, args);
	va_end(args);
	current += buffer;
}
static void finish_case()
{
	std::printf("%s%s\n", current.c_str(), sent.c_str());
	// Keep the original item fixture intact; record the next global RNG draw separately.
	std::fprintf(stderr, "%.*s | %d\n", (int)current.find(" |"), current.c_str(), number(0, INT_MAX));
}
static void put_obj(P_obj o)
{
	if (!o)
	{
		put(" NULL");
		return;
	}
	// Generated descriptions must be owned so persistence saves them.
	assert((o->str_mask & ~STRUNG_EDESC) == (STRUNG_KEYS | STRUNG_DESC1 | STRUNG_DESC2));
	assert(o->R_num == (o->wear_flags & ITEM_WIELD ? VOBJ_RANDOM_WEAPON : VOBJ_RANDOM_ARMOR));
	put(" %s | %s | %s | type=%d wear=%u extra=%u", o->name, o->short_description,
	    o->description, o->type, o->wear_flags, o->extra_flags);
	// Flag fields that are almost always zero are shown only when they are not.
	const struct { const char *name; unsigned long value; } sparse[] = {
		{ "extra2", o->extra2_flags }, { "anti", o->anti_flags },
		{ "anti2", o->anti2_flags },   { "bits1", o->bitvector },
		{ "bits2", o->bitvector2 },    { "bits3", o->bitvector3 },
		{ "bits4", o->bitvector4 },    { "bits5", o->bitvector5 },
	};
	for (const auto &field : sparse)
		if (field.value)
			put(" %s=%lu", field.name, field.value);
	put(" material=%d craft=%d weight=%d values=%d,%d,%d,%d,%d,%d,%d,%d", o->material,
	    o->craftsmanship, o->weight, o->value[0], o->value[1], o->value[2], o->value[3],
	    o->value[4], o->value[5], o->value[6], o->value[7]);
	put(" affects=");
	for (int i = 0; i < MAX_OBJ_AFFECT; i++)
		put("%s%d:%d", i ? "," : "", o->affected[i].location, o->affected[i].modifier);
}

// Full generated state for paired direct/pet kills, without changing golden output.
static void capture_reward(P_obj obj)
{
	const auto saved = current;
	current.clear();
	if (obj->R_num == VOBJ_RANDOM_ARMOR || obj->R_num == VOBJ_RANDOM_WEAPON)
	{
		++equipment_count;
		put_obj(obj);
		put(" origin=%d", named_set_origin(obj).zone);
	}
	else
	{
		if (obj->R_num >= 400000 && obj->R_num <= 400209)
			++material_count;
		else
			++stone_count;
		put(" vnum=%d", obj->R_num);
	}
	reward_state += current;
	current = saved;
}

static void owner_reward_contract()
{
	person owner("Owner",32,160,true,ROOM_GUILD_HALL);
	person pet("Pet",1,60,false,ROOM_COLOURED);
	person victim("victim",34,100,false,ROOM_COLOURED);
	// Preserve #813's victim-home difficulty bonus on both reward routes,
	// including when the pet later fights outside the victim's home zone.
	GET_BIRTHPLACE(&victim.ch)=80000+ROOM_COLOURED;
	pet_owner=&owner.ch; owned_pet=&pet.ch;

	// The RNG sentinel proves both the result and the path/draw count agree.
	auto decision = [&](bool by_pet, bool piece, uint64_t seed) {
		const int room=owner.ch.in_room;
		if (!by_pet) owner.ch.in_room=pet.ch.in_room;
		randomize(seed);
		const bool won=check_random_drop(by_pet ? &pet.ch : &owner.ch,&victim.ch,piece);
		const int next=number(0,INT_MAX);
		owner.ch.in_room=room;
		return std::make_pair(won,next);
	};
	for (int level : {14,15,25,26,32})
	for (int mob_level : {level-10,level-11,34,35,36,37,38,39,40,41})
	for (int luck : {60,160})
	for (bool hardcore : {false,true})
	for (bool neutral : {false,true})
	{
		owner.ch.player.level=level; owner.ch.curr_stats.Luk=luck;
		owner.ch.specials.act2=hardcore ? PLR2_HARDCORE_CHAR : 0;
		owner.ch.player.racewar=neutral ? RACEWAR_NEUTRAL : RACEWAR_GOOD;
		pet.ch.player.racewar=neutral ? RACEWAR_GOOD : RACEWAR_NEUTRAL;
		victim.ch.player.level=mob_level;
		for (int pet_level : {1,62})
		for (bool piece : {false,true})
		for (uint64_t seed=1;seed<=64;++seed)
		{
			pet.ch.player.level=pet_level;
			pet.ch.curr_stats.Luk=220-luck;
			pet.ch.specials.act2=PLR2_HARDCORE_CHAR; // NPC flag cannot grant a bonus.
			assert(decision(false,piece,seed)==decision(true,piece,seed));
			if (level-mob_level>10) assert(!decision(true,piece,seed).first);
		}
	}
	owner.ch.player.level=32; victim.ch.player.level=34;
	owner.ch.player.racewar=RACEWAR_GOOD;
	for (bool piece : {false,true})
	{
		bool luck_changes=false, hardcore_changes=false;
		for (uint64_t seed=1;seed<=512;++seed)
		{
			owner.ch.curr_stats.Luk=60; owner.ch.specials.act2=0;
			const bool ordinary=decision(true,piece,seed).first;
			owner.ch.curr_stats.Luk=160;
			luck_changes |= ordinary!=decision(true,piece,seed).first;
			const bool lucky=decision(true,piece,seed).first;
			owner.ch.specials.act2=PLR2_HARDCORE_CHAR;
			hardcore_changes |= lucky!=decision(true,piece,seed).first;
		}
		assert(luck_changes && hardcore_changes);
	}
	// Neutral early wins bypass all scaling; fallthrough still uses ordinary draws.
	owner.ch.player.racewar=RACEWAR_NEUTRAL;
	loot_drops_dial=0;
	bool early=false, fallthrough=false;
	for (uint64_t seed=1;seed<=64;++seed)
	{
		randomize(seed);
		const bool early_win=number(0,9)==0;
		const int next=number(0,INT_MAX);
		for (bool piece : {false,true})
		{
			const auto direct=decision(false,piece,seed), linked=decision(true,piece,seed);
			assert(direct==linked && linked.first==early_win);
			if (early_win) { assert(linked.second==next); early=true; }
			else fallthrough=true;
		}
	}
	assert(early && fallthrough); loot_drops_dial=1;

	owner.ch.player.racewar=RACEWAR_GOOD;
	owner.ch.specials.act2=PLR2_HARDCORE_CHAR;
	owner.ch.player.level=56; owner.ch.curr_stats.Luk=160;
	victim.ch.player.level=62;
	owner.ch.player.m_class=CLASS_ALCHEMIST;
	int outcomes=0; bool saw_stone=false, saw_named=false, saw_owner=false, saw_alchemist=false;
	capture_rewards=true;
	auto kill = [&](bool by_pet, uint64_t seed) {
		const int room=owner.ch.in_room;
		if (!by_pet) owner.ch.in_room=pet.ch.in_room;
		owner.pc.spell_bind_used=100;
		sent.clear(); given.clear(); reward_state.clear();
		equipment_count=material_count=stone_count=0;
		randomize(seed);
		random_equipment_kill_drop(by_pet ? &pet.ch : &owner.ch,&victim.ch);
		assert(equipment_count+material_count+stone_count<=2);
		const std::string salvage="It appears you were able to salvage";
		const auto first=sent.find(salvage);
		assert(first==std::string::npos || sent.find(salvage,first+1)==std::string::npos);
		assert(sent.find("msg(Pet)")==std::string::npos);
		outcomes |= 1 << ((equipment_count ? 1 : 0) | (material_count ? 2 : 0));
		saw_stone |= stone_count>0;
		saw_named |= reward_state.find("origin=740")!=std::string::npos;
		saw_owner |= reward_state.find(" Owner")!=std::string::npos;
		saw_alchemist |= owner.pc.spell_bind_used<100;
		const auto result=reward_state+sent+std::to_string(owner.pc.spell_bind_used)+
			" rng="+std::to_string(number(0,INT_MAX));
		owner.ch.in_room=room;
		return result;
	};
	for (int luck : {60,100,160})
	{
		owner.ch.curr_stats.Luk=luck;
		for (uint64_t seed=1;seed<=2048;++seed)
			assert(kill(false,seed)==kill(true,seed));
	}
	assert(outcomes==15 && saw_stone && saw_named && saw_owner && saw_alchemist);

	// Remote owner room never changes town/guild eligibility or named-zone generation.
	for (int owner_room : {ROOM_COLOURED,ROOM_PLAIN,ROOM_GUILD_HALL,ROOM_TOWN})
	for (int kill_room : {ROOM_COLOURED,ROOM_PLAIN,ROOM_GUILD_HALL,ROOM_TOWN})
	for (int mob_level : {25,26,62})
	{
		owner.ch.in_room=owner_room; pet.ch.in_room=kill_room;
		owner.ch.player.level=32; victim.ch.player.level=mob_level;
		for (uint64_t seed=1;seed<=64;++seed)
			assert(kill(false,seed)==kill(true,seed));
	}
	// The owner need not be alive/grouped/present; only the actual killer must be alive.
	owner.ch.in_room=ROOM_PLAIN; pet.ch.in_room=ROOM_COLOURED;
	owner.ch.player.level=32; victim.ch.player.level=34;
	for (uint64_t seed=1;seed<=64;++seed)
	{
		SET_POS(&owner.ch,STAT_NORMAL+POS_STANDING);
		const auto alive=kill(true,seed);
		SET_POS(&owner.ch,STAT_DEAD+POS_STANDING);
		assert(alive==kill(true,seed));
	}
	// Existing rejection gates must consume no rolls and create no rewards/messages.
	SET_POS(&owner.ch,STAT_NORMAL+POS_STANDING);
	for (int context=0;context<5;++context)
	{
		pet_owner=context==0 ? nullptr : &owner.ch;
		if (context==1) SET_BIT(owner.ch.specials.act,ACT_ISNPC);
		if (context==2) SET_POS(&pet.ch,STAT_DEAD+POS_STANDING);
		victim.ch.points.curr_exp=context==3 ? 0 : 1000;
		victim.npc.R_num=context==4 ? 1 : 0;
		randomize(1234); const int next=number(0,INT_MAX);
		const auto result=kill(true,1234);
		assert(reward_state.empty() && sent.empty());
		assert(result=="100 rng="+std::to_string(next));
		REMOVE_BIT(owner.ch.specials.act,ACT_ISNPC);
		SET_POS(&pet.ch,STAT_NORMAL+POS_STANDING);
	}
	capture_rewards=false;
	pet_owner=owned_pet=nullptr;
}

// ---- Drop decision ----
enum drop_condition { PLAIN, ELITE, NEUTRAL, HARDCORE, TOWN, GUILD, NO_EXP, SHOPKEEPER, DIAL };
static const char *condition_names[] = { "plain", "elite", "neutral", "hardcore", "town",
					 "guild", "no-exp", "shopkeeper", "dial1.5" };

static void drop_case(int killer_level, int mob_level, int luck, drop_condition condition,
		      bool piece)
{
	char name[128];
	snprintf(name, sizeof(name), "drop k%02d m%02d luck%d %s %s", killer_level, mob_level,
		 luck, condition_names[condition], piece ? "equipment" : "material");
	start_case(name);
	person killer("Finder", killer_level, luck, true,
		      condition == TOWN ? ROOM_TOWN : condition == GUILD ? ROOM_GUILD_HALL : ROOM_PLAIN);
	person mob("goblin warrior", mob_level, 100, false);
	if (condition == ELITE)
		SET_BIT(mob.ch.specials.act, ACT_ELITE);
	if (condition == NEUTRAL)
		killer.ch.player.racewar = RACEWAR_NEUTRAL;
	if (condition == HARDCORE)
		SET_BIT(killer.ch.specials.act2, PLR2_HARDCORE_CHAR);
	if (condition == NO_EXP)
		mob.ch.points.curr_exp = 0;
	if (condition == SHOPKEEPER)
		mob.npc.R_num = 1;
	loot_drops_dial = condition == DIAL ? 1.5 : 1.0;
	put(" ");
	for (int i = 0; i < 50; i++)
		put("%d", check_random_drop(&killer.ch, &mob.ch, piece) ? 1 : 0);
	loot_drops_dial = 1.0;
	finish_case();
}

static void drop_decision()
{
	const int killer_levels[] = { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 20, 30, 45, 62 };
	const int mob_levels[] = { 1, 5, 9, 13, 17, 25, 35, 50, 62 };
	for (int k : killer_levels)
		for (int m : mob_levels)
		{
			for (int luck : { 60, 100, 160 })
				drop_case(k, m, luck, PLAIN, true);
			drop_case(k, m, 100, PLAIN, false);
		}
	const int pairs[][2] = { { 10, 12 }, { 30, 30 }, { 50, 45 } };
	for (int condition = ELITE; condition <= DIAL; condition++)
		for (const auto &pair : pairs)
			for (bool piece : { true, false })
				drop_case(pair[0], pair[1], 100, (drop_condition)condition, piece);
}

// ---- Kill drop ----
static void kill_case(bool by_pet, int killer_level, int mob_level, int luck)
{
	char name[128];
	snprintf(name, sizeof(name), "kill %s k%02d m%02d luck%d", by_pet ? "pet" : "player",
		 killer_level, mob_level, luck);
	start_case(name);
	person owner("Owner", killer_level, luck, true, ROOM_PLAIN);
	person pet("wolf companion", killer_level, luck, false, ROOM_PLAIN);
	if (by_pet)
	{
		// #812: rewards use this owner, while the kill still takes place outside the guild.
		owner.ch.player.level = 62;
		owner.ch.curr_stats.Luk = 60;
		owner.ch.in_room = ROOM_GUILD_HALL;
	}
	P_char killer = by_pet ? &pet.ch : &owner.ch;
	pet_owner = &owner.ch;
	owned_pet = &pet.ch;
	for (int i = 0; i < 40; i++)
	{
		person victim("victim", mob_level, 100, false, ROOM_PLAIN);
		random_equipment_kill_drop(killer, &victim.ch);
		put(" %d:%s%s;", i, given.empty() ? " -" : given.c_str(), sent.c_str());
		given.clear();
		sent.clear();
	}
	pet_owner = owned_pet = nullptr;
	finish_case();
}

static void kill_drop()
{
	for (bool by_pet : { false, true })
	{
		kill_case(by_pet, 1, 12, 160);
		kill_case(by_pet, 30, 30, 100);
		kill_case(by_pet, 50, 45, 160);
		kill_case(by_pet, 1, 62, 160); // Both rolls always win.
	}
}

// Rejected kill contexts must produce neither drops/messages nor RNG draws.
static void rejected_kills()
{
	for (int context = 0; context < 4; context++)
	{
		// Ordinary NPC killer, player victim, dead player killer, dead pet killer.
		person killer("Finder", 1, 160, context != 0 && context != 3, ROOM_PLAIN);
		person victim("victim", 62, 100, context == 1, ROOM_PLAIN);
		person owner("Owner", 1, 160, true, ROOM_PLAIN);
		if (context == 3)
		{
			owned_pet = &killer.ch;
			pet_owner = &owner.ch;
		}
		if (context >= 2)
			SET_POS(&killer.ch, STAT_DEAD + POS_STANDING);
		randomize(1234);
		const int next_roll = number(0, INT_MAX);
		randomize(1234);
		given.clear();
		sent.clear();
		random_equipment_kill_drop(&killer.ch, &victim.ch);
		assert(given.empty() && sent.empty());
		assert(number(0, INT_MAX) == next_roll);
		pet_owner = owned_pet = nullptr;
	}
}

// ---- Generator ----
enum killer_kind { PC, NPC, SHOP, NEWBIE };
static const char *killer_names[] = { "pc", "npc", "shopkeeper", "newbie" };

static void gen_case(const char *group, int killer_level, int mob_level, int luck, int room,
		     killer_kind kind, int slot, int material)
{
	char name[160];
	snprintf(name, sizeof(name), "gen %s k%02d m%02d luck%d %s %s slot%d material%d", group,
		 killer_level, mob_level, luck, room == ROOM_COLOURED ? "coloured" : "plain",
		 killer_names[kind], slot, material);
	start_case(name);
	person killer(kind == PC || kind == NEWBIE ? "Finder" : "orc shaman", killer_level, luck,
		      kind == PC || kind == NEWBIE, room);
	if (kind == SHOP)
		killer.npc.R_num = 1;
	if (kind == NEWBIE)
		SET_BIT(killer.ch.specials.act2, PLR2_NEWBIE);
	P_obj obj = create_random_eq(&killer.ch, killer_level, mob_level, slot, material);
	put_obj(obj);
	release(obj);
	finish_case();
}

static void generator()
{
	for (int slot = 0; slot < MAX_SLOT; slot++)
		gen_case("slot", 56, 62, 160, ROOM_COLOURED, PC, slot, -1);
	for (int slot = 0; slot < MAX_SLOT; slot++)
		gen_case("slot", 50, 50, 100, ROOM_PLAIN, PC, slot, -1);
	for (int k : { 1, 11, 25, 40, 56, 62 })
		for (int m : { 1, 20, 46, 62 })
		{
			for (int luck : { 60, 100, 160 })
				gen_case("random", k, m, luck, ROOM_COLOURED, PC, -1, -1);
			gen_case("random", k, m, 100, ROOM_PLAIN, PC, -1, -1);
			gen_case("random", k, m, 100, ROOM_COLOURED, NPC, -1, -1);
		}
	for (int i = 0; i < 4; i++)
	{
		gen_case("shop", 56, 62, 160 + i, ROOM_COLOURED, SHOP, -1, -1);
		gen_case("newbie", 56, 62, 160 + i, ROOM_COLOURED, NEWBIE, -1, -1);
	}
	for (int material = 0; material < MAXMATERIAL; material++)
		gen_case("material", 40, 40, 100, ROOM_COLOURED, PC, -1, material);
	gen_case("bounds", 40, 40, 100, ROOM_COLOURED, PC, 500, -1);
	gen_case("bounds", 40, 40, 100, ROOM_COLOURED, PC, -7, -1);
	gen_case("bounds", 40, 40, 100, ROOM_COLOURED, PC, -1, 99);
	gen_case("bounds", 40, 40, 100, ROOM_COLOURED, PC, -1, -7);
	loot_quality_dial = 1.5;
	for (int k : { 10, 30, 50 })
		for (int m : { 20, 62 })
			gen_case("quality1.5", k, m, 100, ROOM_COLOURED, PC, -1, -1);
	loot_quality_dial = 1.0;
	blanks_missing = true;
	gen_case("missing-blank", 40, 40, 100, ROOM_COLOURED, PC, -1, -1);
	blanks_missing = false;
}

// ---- Materials and stones ----
static void materials_and_stones()
{
	for (int level = 1; level <= 62; level++)
		for (bool alchemist : { false, true })
		{
			char name[64];
			snprintf(name, sizeof(name), "material level%02d %s", level,
				 alchemist ? "alchemist" : "other");
			start_case(name);
			person killer("Finder", level, 100, true);
			if (alchemist)
				killer.ch.player.m_class = CLASS_ALCHEMIST;
			for (int i = 0; i < 5; i++)
			{
				P_obj obj = create_material(&killer.ch, level, level);
				put(" %d", obj ? obj->R_num : 0);
				release(obj);
			}
			put(" bind=%ld", killer.pc.spell_bind_used);
			finish_case();
		}
	for (int index = 0; index <= MAXMATERIAL; index++)
	{
		start_case("material index" + std::to_string(index));
		for (int i = 0; i < 5; i++)
		{
			P_obj obj = create_material(index);
			put(" %d", obj ? obj->R_num : 0);
			release(obj);
		}
		finish_case();
	}
	start_case("stones");
	for (int i = 0; i < 30; i++)
	{
		P_obj obj = create_stones();
		put(" %d", obj ? obj->R_num : 0);
		release(obj);
	}
	finish_case();
}

// ---- Every suffix total, including the rare 5/6/7 and no-affect 28/29/30 ----
static void suffix_outcomes()
{
	const struct {
		uint64_t seed;
		unsigned long bits1, bits2, bits3, bits5;
	} cases[] = {
		{ 20476, AFF_DETECT_INVISIBLE, 0, 0, 0 },
		{ 1167, 0, AFF2_ULTRAVISION, 0, 0 },
		{ 3, 0, AFF2_FIRESHIELD, 0, 0 },
		{ 67, AFF_SLOW_POISON, 0, 0, 0 },
		{ 39, AFF_WATERBREATH, 0, 0, 0 },
		{ 7, AFF_INFRAVISION, 0, 0, 0 },
		{ 60, AFF_PROTECT_GOOD, 0, 0, 0 },
		{ 42, AFF_PROTECT_EVIL, 0, 0, 0 },
		{ 30, 0, AFF2_PROT_COLD, 0, 0 },
		{ 4, AFF_LEVITATE, 0, 0, 0 },
		{ 8, 0, AFF2_DETECT_EVIL, 0, 0 },
		{ 1, 0, AFF2_DETECT_GOOD, 0, 0 },
		{ 10, 0, AFF2_DETECT_MAGIC, 0, 0 },
		{ 14, AFF_PROT_FIRE, 0, 0, 0 },
		{ 12, 0, 0, 0, AFF5_PROT_UNDEAD },
		{ 6, 0, AFF2_PROT_ACID, 0, 0 },
		{ 15, AFF_SENSE_LIFE, 0, 0, 0 },
		{ 25, AFF_MINOR_GLOBE, 0, 0, 0 },
		{ 31, AFF_FARSEE, 0, 0, 0 },
		{ 99, 0, 0, AFF3_COLDSHIELD, 0 },
		{ 5, 0, AFF2_SOULSHIELD, 0, 0 },
		{ 18, AFF_BARKSKIN, 0, 0, 0 },
		{ 359, AFF_HASTE, 0, 0, 0 },
		{ 215, 0, 0, 0, 0 },
		{ 909, 0, 0, 0, 0 },
		{ 10194, 0, 0, 0, 0 },
	};
	for (int i = 0; i < (int)ARRAY_SIZE(cases); i++)
	{
		const auto &expected = cases[i];
		randomize(expected.seed);
		assert(dice(5, 6) == i + 5);
		const int next_roll = number(1, 1000000);
		randomize(expected.seed);
		obj_data obj{};
		assert(setsuffix_obj_new(&obj) == &obj);
		assert(obj.bitvector == expected.bits1);
		assert(obj.bitvector2 == expected.bits2);
		assert(obj.bitvector3 == expected.bits3);
		assert(obj.bitvector4 == 0);
		assert(obj.bitvector5 == expected.bits5);
		assert(number(1, 1000000) == next_roll);
	}
}

// ---- Encrust and true name ----
static void encrust_and_true_name()
{
	const int spells[] = { 0, SPELL_ACID_BLAST, SPELL_FIREBALL, SPELL_MAGIC_MISSILE,
			       SPELL_CHILL_TOUCH, SPELL_NEGATIVE_CONCUSSION_BLAST,
			       SPELL_SHOCKING_GRASP, SPELL_FLAMESTRIKE, SPELL_BLINDNESS,
			       SPELL_ENERGY_DRAIN, SPELL_HEAL };
	for (int spell : spells)
	{
		start_case("encrust spell" + std::to_string(spell));
		obj_data obj{};
		set_encrust_affect(&obj, spell);
		put(" bits=%lu,%lu,%lu,%lu,%lu", obj.bitvector, obj.bitvector2, obj.bitvector3,
		    obj.bitvector4, obj.bitvector5);
		finish_case();
	}
	const char *shorts[] = { "a &+Lfine &nsteel &+Llong sword&n",
				 "a &+Lfine sword of &+Rfire&n crafted by Kvark" };
	for (int i = -1; i < (int)ARRAY_SIZE(spells_data); i++)
		for (const char *short_description : shorts)
		{
			const int spell = i < 0 ? 0 : spells_data[i].spell;
			start_case("true-name entry" + std::to_string(i) + " spell" + std::to_string(spell) +
			      (short_description == shorts[0] ? " plain" : " already-named"));
			obj_data obj{};
			obj.value[5] = spell;
			obj.short_description = str_dup(short_description);
			obj.str_mask = STRUNG_DESC2;
			const bool changed = identify_random(&obj);
			put(" %s %s", changed ? "renamed" : "unchanged", obj.short_description);
			free(obj.short_description);
			finish_case();
		}
}

// A valid spell outside the random-weapon table must leave the name alone.
// This assertion adds no fixture output; ASan also checks the table boundary.
static void foreign_spell_name()
{
	P_obj obj = read_object(VOBJ_RANDOM_WEAPON, VIRTUAL);
	obj->value[5] = SPELL_BLINDNESS;
	assert(!identify_random(obj));
	assert(!strcmp(obj->short_description, "a blank"));
	release(obj);
}


static void origin_generation_contract()
{
    person finder("Finder", 56, 160, true);
    char *saved_title=zones[0].name;
    const int saved_number=zones[0].number;
    for(int zone : {13, 44, 204, 808, 811, 814, 990, 1350, 300}) {
        zones[0].number=zone;
        for(const char *title : {"&+WCeothia&n", "&+gNeverwind Valley&n", "&+gNeverwinter Woods&n"}) {
            zones[0].name=const_cast<char *>(title);
            randomize(7);
            P_obj object=create_random_eq(&finder.ch,56,62,0,-1);
            assert(object && named_set_origin(object).zone==zone);
            assert(object->ex_description && (object->str_mask & STRUNG_EDESC));
            release(object);
        }
    }
    zones[0].number=saved_number;
    zones[0].name=const_cast<char *>("Plain Title");
    randomize(7);
    P_obj plain=create_random_eq(&finder.ch,56,62,0,-1);
    assert(plain && !plain->ex_description && !named_set_origin(plain).zone);
    release(plain);
    zones[0].name=saved_title;
}
static void restored_zone_titles_contract()
{
    const struct {int zone; const char *title; const char *visible;} titles[]={
        RESTORED_ZONE_TITLES
    };
    person finder("Finder",56,160,true);
    char *saved_title=zones[0].name;
    const int saved_number=zones[0].number;
    for(const auto &entry:titles) {
        assert(strip_ansi(entry.title)==entry.visible);
        zones[0].number=entry.zone;
        zones[0].name=const_cast<char *>(entry.title);
        randomize(7);
        P_obj named=create_random_eq(&finder.ch,56,62,0,-1);
        assert(named && named_set_origin(named).zone==entry.zone);
        assert(strstr(named->short_description,entry.title));
        release(named);
        // The same authored title still requires the normal successful roll.
        person unlucky("Finder",56,60,true);
        randomize(7);
        P_obj failed=create_random_eq(&unlucky.ch,56,62,0,-1);
        assert(failed && !named_set_origin(failed).zone && !failed->ex_description);
        release(failed);
        // Fixed materials keep the ordinary non-zone-name path.
        randomize(7);
        P_obj fixed=create_random_eq(&finder.ch,56,62,0,0);
        assert(fixed && !named_set_origin(fixed).zone && !fixed->ex_description);
        release(fixed);
    }
    zones[0].number=saved_number; zones[0].name=saved_title;
}
static void zone_flag_admission_contract()
{
    person fighter("Fighter",20,100,true), victim("Mob",20,100,false);
    const auto saved_zone_flags=zones[0].flags;
    const auto saved_room_flags=rooms[ROOM_COLOURED].room_flags;
    zones[0].flags=0; rooms[ROOM_COLOURED].room_flags=0;
    assert(CanDoFightMove(&fighter.ch,&victim.ch));
    bool saw_drop=false;
    for(uint64_t seed=1;seed<=64;++seed) {
        zones[0].flags=0;
        randomize(seed); const bool ordinary=check_random_drop(&fighter.ch,&victim.ch,false);
        const auto ordinary_next=number(0,INT_MAX);
        zones[0].flags=ZONE_SAFE;
        assert(CanDoFightMove(&fighter.ch,&victim.ch));
        randomize(seed); assert(check_random_drop(&fighter.ch,&victim.ch,false)==ordinary);
        assert(number(0,INT_MAX)==ordinary_next);
        saw_drop|=ordinary;
    }
    assert(saw_drop);
    rooms[ROOM_COLOURED].room_flags=ROOM_SAFE;
    assert(!CanDoFightMove(&fighter.ch,&victim.ch));
    zones[0].flags=saved_zone_flags; rooms[ROOM_COLOURED].room_flags=saved_room_flags;
}
// Exercise the real drop decision against independently specified multipliers,
// including rounding, unchanged material RNG, and the neutral early win.
static void home_zone_drop_contract()
{
    person fighter("Finder",40,100,true,ROOM_PLAIN), victim("Mob",40,100,false,ROOM_PLAIN);
    GET_BIRTHPLACE(&victim.ch)=80000 + ROOM_COLOURED;
    const int saved_difficulty=zones[0].difficulty;
    const struct { int difficulty; float multiplier; } cases[] = {
        {0,1.0f}, {1,1.0f}, {2,1.1f}, {3,1.141421356f},
        {5,1.2f}, {10,1.3f}, {11,1.3f}
    };
    int improved=0;
    for (const auto &entry : cases) {
        zones[0].difficulty=entry.difficulty;
        for (bool piece : {false,true})
        for (bool hardcore : {false,true})
        for (bool neutral : {false,true})
        for (double dial : {1.0,1.5}) {
            fighter.ch.specials.act2=hardcore ? PLR2_HARDCORE_CHAR : 0;
            fighter.ch.player.racewar=neutral ? RACEWAR_NEUTRAL : RACEWAR_GOOD;
            loot_drops_dial=dial;
            for (uint64_t seed=1;seed<=256;++seed) {
                randomize(seed);
                bool expected=neutral && !number(0,9);
                if (!expected) {
                    float chance=50.0f + number(-5,5);
                    if (hardcore) chance*=1.5f;
                    chance*=piece ? 0.15 : 0.08;
                    const float baseline=chance * static_cast<float>(dial);
                    if (piece) chance*=entry.multiplier;
                    chance*=static_cast<float>(dial);
                    const int roll=number(1,100);
                    expected=static_cast<int>(chance+.5)>=roll;
                    if (expected && static_cast<int>(baseline+.5)<roll) ++improved;
                }
                const int next=number(0,INT_MAX);
                randomize(seed);
                assert(check_random_drop(&fighter.ch,&victim.ch,piece)==expected);
                assert(number(0,INT_MAX)==next);
            }
        }
    }
    assert(improved>0);
    fighter.ch.specials.act2=0;
    fighter.ch.player.racewar=RACEWAR_GOOD;
    loot_drops_dial=1.0;
    // Home difficulty 1 and absent home both stay unboosted even when the kill
    // happens in a difficulty-10 zone; birthplace must never be a room index.
    zones[0].difficulty=10;
    fighter.ch.in_room=victim.ch.in_room=ROOM_COLOURED;
    for (uint64_t seed=1;seed<=256;++seed) {
        GET_BIRTHPLACE(&victim.ch)=80000 + ROOM_PLAIN;
        randomize(seed); const bool baseline=check_random_drop(&fighter.ch,&victim.ch,true);
        const int next=number(0,INT_MAX);
        for (int missing : {0,99999}) {
            GET_BIRTHPLACE(&victim.ch)=missing;
            randomize(seed); assert(check_random_drop(&fighter.ch,&victim.ch,true)==baseline);
            assert(number(0,INT_MAX)==next);
        }
    }
    // A difficulty bonus must not bypass the level-gap refusal.
    GET_BIRTHPLACE(&victim.ch)=80000 + ROOM_COLOURED;
    victim.ch.player.level=29;
    for (uint64_t seed=1;seed<=64;++seed) {
        randomize(seed); const int next=number(0,INT_MAX);
        randomize(seed); assert(!check_random_drop(&fighter.ch,&victim.ch,true));
        assert(number(0,INT_MAX)==next);
    }
    zones[0].difficulty=saved_difficulty;
}

int main()
{
	setup_world();
	owner_reward_contract();
	drop_decision();
	kill_drop();
	rejected_kills();
	generator();
	materials_and_stones();
	suffix_outcomes();
	encrust_and_true_name();
	foreign_spell_name();
	origin_generation_contract();
	restored_zone_titles_contract();
	zone_flag_admission_contract();
	home_zone_drop_contract();
	return 0;
}
'''


def main():
    output_root = ROOT / "bin/tests/random-equipment"
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="golden-", dir=output_root) as directory:
        work = Path(directory)
        harness = work / "harness.cpp"
        helpers = class_groups() + "\n".join(extract_function(name, signature) for name, signature in HELPERS)
        titles=[]
        for zone, area, visible in (
            (87,"gibber","Lair of the Gibberling King"),
            (370,"vrzawild","Crystalspyre Mountains"),
            (676,"thri","Taliccicopiid"),
            (824,"suntmpl","The Temple of the Sun"),
            (16,"truk","Truktakyagyo"),
            (57,"minizones","Mini Zones"),
            (206,"elftomb","Barrow of the Quiosho"),
            (292,"newbie","Ailvio, Duris Newbie Outpost"),
            (340,"basin_wa","The Basin Wastes"),
            (413,"highway","Southern Coastal Highway"),
            (532,"shortc","The Orcish Slave Camp"),
            (678,"shortb","The Undead Fog"),
            (690,"tentro2","The Mountain Village of Tentro"),
            (755,"teka2","The Dark Stone Tower of the Northern Realms"),
            (777,"hall","The Hall of the Ancients"),
            (806,"yuan_ti2","Village of the Damned"),
            (807,"clwcvrn","The Clawed Caverns"),
            (821,"outpost","The Human Outpost"),
            (822,"lylr","Lylr-Meop"),
            (903,"rtun","Tunnels of Payang"),
            (914,"wutvr","Wutvr, Duris Newbie Outpost"),
            (930,"dungeon","Treasure Caves"),
            (935,"wemic","Wellvolen"),
            (986,"ruins","Village of Refugees"),
            (1320,"githyanki_fortress","The Githyanki Fortress"),
        ):
            lines=(ROOT / "areas/zon" / (area + ".zon")).read_text().splitlines()
            assert lines[0]==f"#{zone}" and lines[1].endswith("~")
            titles.append(f"{{{zone},{json.dumps(lines[1][:-1])},{json.dumps(visible)}}},")
        harness.write_text(HARNESS.replace("RESTORED_ZONE_TITLES", "\n".join(titles)) + "\n" + helpers)
        binary = work / "golden"
        subprocess.run(
            [
                "g++", "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined",
                "-fno-omit-frame-pointer", "-ffunction-sections", "-fdata-sections",
                "-I" + str(ROOT / "src"), str(harness),
                *[str(ROOT / path) for path in MODULE_SOURCES + LINKED_SOURCES], str(HARNESS_STUBS),
                "-Wl,--gc-sections", "-o", str(binary),
            ],
            check=True,
        )
        env = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
                   UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
        run = subprocess.run([str(binary)], env=env, capture_output=True, text=True)
        if run.returncode:
            raise SystemExit(f"FAILED: the harness exited {run.returncode}\n{run.stderr}")
        failures = []
        for fixture, actual in ((FIXTURE, run.stdout), (RNG_FIXTURE, run.stderr)):
            expected = fixture.read_text()
            if actual == expected:
                continue
            output = work.parent / (fixture.stem + ".actual.txt")
            output.write_text(actual)
            actual_lines, expected_lines = actual.splitlines(), expected.splitlines()
            differing = [i for i in range(max(len(actual_lines), len(expected_lines)))
                         if i >= len(actual_lines) or i >= len(expected_lines)
                         or actual_lines[i] != expected_lines[i]]
            for i in differing[:3]:
                print("expected:", expected_lines[i] if i < len(expected_lines) else "(none)")
                print("actual:  ", actual_lines[i] if i < len(actual_lines) else "(none)")
            failures.append(f"FAILED: {fixture.name}: {len(differing)} of {len(expected_lines)}"
                            f" cases differ; the whole output is in {output}")
        if failures:
            raise SystemExit("\n".join(failures))
        print(f"random equipment golden test passed: {len(run.stdout.splitlines())} cases"
              " and RNG sentinels, plus owner/pet rewards, suffix totals, template identity,"
              " rejected kills and home-zone drop scaling")


main()
