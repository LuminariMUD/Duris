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
written once from the code of 2026-10-10 and never edited: a change that moves, adds
or drops a single roll changes the output. The random equipment rewrite in
docs/ongoing-projects/plan.md changes only MODULE_SOURCES and the calls into the
module, never the fixtures. A companion fixture records a sentinel roll after each
case to detect terminal draws that leave the current item unchanged. Direct assertions
also cover every suffix total without changing the frozen output.
"""
import os
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function

FIXTURE = ROOT / "tests/fixtures/random_equipment_golden.txt"
RNG_FIXTURE = ROOT / "tests/fixtures/random_equipment_rng_golden.txt"
MODULE_SOURCES = ["src/item/randomeq.c"]
LINKED_SOURCES = [
    "src/core/random.c",
    "src/core/safe_format.c",
    "src/item/random_equipment_config.c",
    "src/world/hardcore_config.c",
]
HELPERS = [
    ("utility.c", "int dice(int num, int size)"),
    ("utility.c", "string strip_ansi(const char *str)"),
    ("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
    ("utility.c", "int BOUNDED(int a, int b, int c)"),
    ("handler.c", "char *FirstWord(char *namelist)"),
    ("handler.c", "bool isname(const char *str, const char *namelist)"),
    ("objconv.c", "void material_restrictions(P_obj obj)"),
    ("salchemist.c", "void set_keywords(P_obj t_obj, const char *newKeys)"),
    ("salchemist.c", "void set_short_description(P_obj t_obj, const char *newShort)"),
    ("salchemist.c", "void set_long_description(P_obj t_obj, const char *newDescription)"),
]


def class_groups():
    """The ALL_MAGES and ALL_ROGUES masks material_restrictions() uses."""
    text = (ROOT / "src/item/objconv.c").read_text()
    return text[text.index("#define ALL_MAGES") : text.index("// Sets anti-class flags")]


def kill_drop_block():
    """The random drop block of die(), as a function of the victim and the killer."""
    die = extract_function("fight.c", "void die(P_char ch, P_char killer)")
    start = die.index("// object code - Normal kills.")
    block = die[start : die.index("update_pos(ch);", start)]
    return "void golden_kill_drop(P_char ch, P_char killer)\n{\nP_obj tempobj = NULL;\n" + block + "}\n"


HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "item/objmisc.h"
#include "item/weapon_actions.h"
#include "magic/spells.h"
#include "world/difficulty.h"
#include "world/vnum.obj.h"

#include <cassert>
#include <climits>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

// ---- The module's interface, as its callers see it today ----
P_obj create_random_eq_new(P_char killer, P_char mob, int item_type, int material_type);
bool check_random_drop(P_char ch, P_char mob, bool piece);
P_obj create_material(int index);
P_obj create_material(P_char ch, P_char mob);
P_obj create_stones(void);
P_obj set_encrust_affect(P_obj obj, int proc);
bool identify_random(P_obj obj);
extern struct random_spells spells_data[61];

// ---- The world ----
// Zone 0 has colour codes in its name, so its items can be named; zone 1 is plain; zone 2
// is a town. Room 2 is a guild room in zone 1.
static zone_data zones[3];
static room_data rooms[4];
static index_data mob_protos[2]; // 0: an ordinary mob, 1: a shopkeeper
struct zone_data *zone_table = zones;
P_room world = rooms;
P_index mob_index = mob_protos;
Skill skills[MAX_SKILLS];
enum { ROOM_COLOURED, ROOM_PLAIN, ROOM_GUILD_HALL, ROOM_TOWN };

static void setup_world()
{
	zones[0].name = const_cast<char *>("&+rThe &+RBurning&n Wastes");
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
item_action_start selected_random_weapon_action(P_obj, P_char, P_char, int, int)
{
	return item_action_start::legacy;
}
char *str_dup(const char *source) { return source ? strdup(source) : nullptr; }
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
	// Every generated name must survive persistence, for direct and kill-drop cases.
	if (obj->R_num == VOBJ_RANDOM_ARMOR || obj->R_num == VOBJ_RANDOM_WEAPON)
		assert(obj->str_mask == (STRUNG_KEYS | STRUNG_DESC1 | STRUNG_DESC2));
	if (obj->str_mask & STRUNG_KEYS)
		free(obj->name);
	if (obj->str_mask & STRUNG_DESC2)
		free(obj->short_description);
	if (obj->str_mask & STRUNG_DESC1)
		free(obj->description);
	delete obj;
}

// What the kill drop puts on the victim.
static std::string given;
void obj_to_char(P_obj obj, P_char ch)
{
	char line[64];
	if (obj->R_num == VOBJ_RANDOM_ARMOR || obj->R_num == VOBJ_RANDOM_WEAPON)
		given += std::string(" eq[") + obj->name + "]";
	else
	{
		snprintf(line, sizeof(line), " obj%d", obj->R_num);
		given += line;
	}
	given += std::string("->") + GET_NAME(ch);
	release(obj);
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
void golden_kill_drop(P_char ch, P_char killer);

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
		// Only the message goes to the owner. Drop rolls and generation use the pet.
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
		golden_kill_drop(&victim.ch, killer);
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
	person mob("goblin warrior", mob_level, 100, false, room);
	P_obj obj = create_random_eq_new(&killer.ch, &mob.ch, slot, material);
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
			person mob("goblin warrior", level, 100, false);
			for (int i = 0; i < 5; i++)
			{
				P_obj obj = create_material(&killer.ch, &mob.ch);
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

int main()
{
	setup_world();
	drop_decision();
	kill_drop();
	generator();
	materials_and_stones();
	suffix_outcomes();
	encrust_and_true_name();
	return 0;
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix="duris-random-equipment-golden-") as directory:
        work = Path(directory)
        harness = work / "harness.cpp"
        helpers = class_groups() + "\n".join(extract_function(name, signature) for name, signature in HELPERS)
        harness.write_text(HARNESS + "\n" + helpers + "\n" + kill_drop_block())
        binary = work / "golden"
        subprocess.run(
            [
                "g++", "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined",
                "-fno-omit-frame-pointer", "-ffunction-sections", "-fdata-sections",
                "-I" + str(ROOT / "src"), str(harness),
                *[str(ROOT / path) for path in MODULE_SOURCES + LINKED_SOURCES],
                "-Wl,--gc-sections", "-o", str(binary),
            ],
            check=True,
        )
        env = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
                   UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
        run = subprocess.run([str(binary)], env=env, capture_output=True, text=True)
        if run.returncode:
            raise SystemExit(f"FAILED: the harness exited {run.returncode}\n{run.stderr}")
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
            raise SystemExit(f"FAILED: {fixture.name}: {len(differing)} of {len(expected_lines)}"
                             f" cases differ; the whole output is in {output}")
        print(f"random equipment golden test passed: {len(run.stdout.splitlines())} cases"
              " and RNG sentinels, plus all 26 suffix totals")


main()
