#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "combat/damage.h"
#include "combat/trap.h"
#include "world/vnum.obj.h"
#include "cmd/interp.h"
#include "net/comm.h"
#include "world/specs.prototypes.h"
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <vector>
#include <string>

room_data rooms[2] = {};
P_room world = rooms;
int top_of_world = 1;
index_data indexes[4] = {};
P_index obj_index = indexes, mob_index = indexes;
P_char character_list;
P_obj object_list;
P_desc descriptor_list;
Skill skills[MAX_SKILLS];
extern const int rev_dir[] = { 2, 3, 0, 1, 5, 4 };
static uint64_t next_id = 1;
static int created, discarded, attacks, poison_level, last_damage, last_flags, last_caster_level;
static int fail_creation = -1, fail_placement = -1, placement_calls;
static int lifecycle;
static bool resistant, freedom, save_result;
static std::deque<bool> saves;
static std::vector<int> save_mods;
static P_char actor;
static P_char pet;
static P_obj trap;
static bool remove_first_placement;
static std::vector<uint64_t> damaged;
static P_char last_attacked;
static int waits, last_wait;
void CharWait(P_char, int duration)
{
	++waits;
	last_wait = duration;
}
P_obj get_obj_in_list_vis(P_char, const char *, P_obj list, bool)
{
	return list;
}
int fill_word(char *)
{
	return false;
}
int generic_find(const char *, int, P_char, P_char *found_char, P_obj *found_object)
{
	*found_char = nullptr;
	*found_object = trap;
	return FIND_OBJ_INV;
}

P_char find_character_by_runtime_id(uint64_t id)
{
	for (P_char ch = character_list; ch; ch = ch->next)
		if (ch->runtime_id == id)
			return ch;
	return nullptr;
}
P_obj find_live_object(P_obj expected, uint64_t uid)
{
	for (P_obj object = object_list; object; object = object->next)
		if (object == expected && object->obj_uid == uid)
			return object;
	return nullptr;
}
static P_char character(bool npc = false)
{
	auto *ch = new char_data{};
	if (npc)
	{
		ch->specials.act = ACT_ISNPC;
		ch->only.npc = new npc_only_data{};
	}
	else
		ch->only.pc = new pc_only_data{};
	ch->runtime_id = next_id++;
	ch->in_room = NOWHERE;
	ch->player.level = 25;
	ch->player.race = RACE_HUMAN;
	ch->specials.position = STAT_NORMAL + POS_STANDING;
	ch->points.hit = ch->points.max_hit = 1000;
	ch->curr_stats.Pow = 60;
	ch->next = character_list;
	character_list = ch;
	return ch;
}
bool char_to_room(P_char ch, int room, int)
{
	if (placement_calls++ == fail_placement)
	{
		extract_char(ch);
		return false;
	}
	ch->in_room = room;
	ch->next_in_room = rooms[room].people;
	rooms[room].people = ch;
	if (remove_first_placement && placement_calls == 2 && ch->next_in_room != actor)
	{
		extract_char(ch->next_in_room);
	}
	return true;
}
void extract_char(P_char ch)
{
	for (auto **link = &character_list; *link; link = &(*link)->next)
		if (*link == ch)
		{
			*link = ch->next;
			break;
		}
	if (ch->in_room >= 0)
		for (auto **link = &rooms[ch->in_room].people; *link; link = &(*link)->next_in_room)
			if (*link == ch)
			{
				*link = ch->next_in_room;
				break;
			}
	while (ch->affected)
	{
		auto *af = ch->affected;
		ch->affected = af->next;
		delete af;
	}
	if (IS_NPC(ch))
	{
		++discarded;
		delete ch->only.npc;
	}
	else
		delete ch->only.pc;
	delete ch;
}
P_char read_mobile(int vnum, int, bool)
{
	if (created == fail_creation)
		return nullptr;
	++created;
	auto *ch = character(true);
	ch->only.npc->R_num = vnum == 14 ? 0 : vnum == 200 ? 1 : vnum == 32861 ? 2 : 3;
	return ch;
}
P_char read_mobile(int vnum, int mode)
{
	return read_mobile(vnum, mode, true);
}
void MobStartFight(P_char, P_char victim)
{
	++attacks;
	last_attacked = victim;
}
P_char get_linked_char(P_char ch, ush_int)
{
	return ch == pet ? actor : nullptr;
}
int NumAttackers(P_char)
{
	return 0;
}
bool is_aggr_to(P_char, P_char)
{
	return true;
}
bool AdjacentInRoom(P_char, P_char)
{
	return true;
}
bool fear_check(P_char, bool)
{
	return true;
}
void do_flee(P_char, char *, int)
{
	std::abort();
}
void remember(P_char, P_char, bool) {}
void remember(P_char, P_char) {}
void stop_fighting(P_char ch)
{
	GET_OPPONENT(ch) = nullptr;
}
bool resists_spell(P_char, P_char)
{
	return resistant;
}
bool NewSaves(P_char, int, int mod)
{
	save_mods.push_back(mod);
	if (saves.empty())
		return save_result;
	bool result = saves.front();
	saves.pop_front();
	return result;
}
bool saves_spell(P_char, int)
{
	return save_result;
}
int get_default_save_mod(P_char, P_char, int, int)
{
	return 0;
}
int number(int low, int)
{
	return low;
}
int dice(int, int)
{
	return 10;
}
int get_property(const char *, int fallback)
{
	return fallback;
}
bool check_freedom_of_movement(P_char)
{
	return freedom;
}
bool is_linked_to(P_char, P_char, ush_int)
{
	return false;
}
bool ac_can_see(P_char, P_char, bool)
{
	return true;
}
void StopMercifulAttackers(P_char) {}
void appear(P_char, bool) {}
void balance_affects(P_char) {}
void wear_off_message(P_char, affected_type *) {}
P_char un_morph(P_char)
{
	std::abort();
}
int real_object(int)
{
	return -1;
}
void Decay(P_obj)
{
	std::abort();
}
void send_to_room(const char *, int) {}
void spell_teleport(int, P_char, char *, int, P_char, P_obj) {}
bool damage(P_char, P_char, double, int)
{
	return true;
}

affected_type *affect_to_char(P_char ch, affected_type *af)
{
	auto *copy = new affected_type(*af);
	copy->next = ch->affected;
	ch->affected = copy;
	ch->specials.affected_by |= af->bitvector;
	ch->specials.affected_by2 |= af->bitvector2;
	return copy;
}
bool affected_by_spell(P_char ch, int type)
{
	for (auto *af = ch->affected; af; af = af->next)
		if (af->type == type)
			return true;
	return false;
}
void affect_from_char(P_char ch, int type)
{
	for (auto **link = &ch->affected; *link;)
	{
		auto *af = *link;
		if (af->type == type)
		{
			*link = af->next;
			delete af;
		}
		else
			link = &af->next;
	}
}
void add_tag_to_char(P_char, int, int, int, int)
{
	std::abort();
}
affected_type *get_spell_from_char(P_char ch, int type, void *, int)
{
	for (auto *af = ch->affected; af; af = af->next)
		if (af->type == type)
			return af;
	return nullptr;
}
static void poison_family(int level, P_char, char *, int, P_char, P_obj)
{
	poison_level = level;
}
int spell_damage(P_char caster, P_char victim, double amount, int, uint flags, damage_messages *,
		 int *)
{
	last_damage = amount;
	last_flags = flags;
	last_caster_level = GET_LEVEL(caster);
	assert(caster != victim && IS_SET(caster->runtime_flags, CHAR_RFLAG_TRAP_CASTER));
	damaged.push_back(victim->runtime_id);
	if (lifecycle == 1)
	{
		extract_char(victim);
		lifecycle = 0;
	}
	else if (lifecycle == 2)
	{
		extract_char(caster);
		lifecycle = 0;
	}
	else if (lifecycle == 3)
	{
		object_list = trap->next;
		delete trap;
		trap = nullptr;
		lifecycle = 0;
	}
	return 0;
}

// NATIVE_SPELLS

static void reset(int type, int level = 60, int vnum = 1458)
{
	while (character_list)
		extract_char(character_list);
	while (object_list)
	{
		P_obj object = object_list;
		object_list = object->next;
		delete object;
	}
	trap = new obj_data{};
	trap->obj_uid = 1;
	trap->trap_dam = type;
	trap->trap_level = level;
	trap->trap_charge = 2;
	trap->trap_eff = 2;
	object_list = trap;
	trap->loc_p = LOC_ROOM;
	trap->loc.room = 0;
	rooms[0].contents = trap;
	indexes[0].virtual_number = vnum;
	indexes[1].virtual_number = 200;
	indexes[2].virtual_number = 32861;
	indexes[3].virtual_number = 32871;
	actor = character();
	char_to_room(actor, 0, -2);
	pet = nullptr;
	remove_first_placement = false;
	damaged.clear();
	last_attacked = nullptr;
	created = discarded = attacks = poison_level = last_damage = last_flags =
		last_caster_level = placement_calls = 0;
	fail_creation = fail_placement = -1;
	resistant = freedom = save_result = false;
	saves.clear();
	save_mods.clear();
	lifecycle = 0;
}

int main()
{
	for (int poison = FIRST_POISON; poison <= LAST_POISON; ++poison)
		skills[poison].spell_pointer = poison_family;
	for (int level : { 0, 1, 16, 19, 20, 25, 60, 80, 100, 200 })
	{
		reset(15, level);
		trapdamage(actor, trap);
		int effective = level ? std::min(level, 100) : 25;
		assert(actor->affected &&
		       actor->affected->duration ==
			       int(std::clamp(effective / 5, 4, 16) * WAIT_SEC * .75));
		assert(save_mods == std::vector<int>{ 0 } && created == 1 && discarded == 1 &&
		       trap->trap_charge == 1);
		auto *original = actor->affected;
		trapdamage(actor, trap);
		assert(actor->affected == original && trap->trap_charge == 0);
		reset(16, level);
		trapdamage(actor, trap);
		assert(actor->affected &&
		       actor->affected->duration == std::clamp(effective / 20, 1, 4) * WAIT_SEC);
		assert(discarded == 1);
	}
	reset(16);
	saves = { true, false };
	trapdamage(actor, trap);
	assert(actor->affected && actor->affected->duration == WAIT_SEC * 3 / 2);
	reset(16);
	saves = { true, true };
	trapdamage(actor, trap);
	assert(!actor->affected && trap->trap_charge == 1);
	for (int type : { 15, 16 })
	{
		reset(type);
		resistant = true;
		trapdamage(actor, trap);
		assert(!actor->affected && trap->trap_charge == 1);
		reset(type);
		save_result = true;
		trapdamage(actor, trap);
		assert(!actor->affected);
	}
	reset(15);
	freedom = true;
	trapdamage(actor, trap);
	assert(!actor->affected);
	reset(15);
	actor->specials.affected_by2 = AFF2_MAJOR_PARALYSIS;
	trapdamage(actor, trap);
	assert(!actor->affected);
	reset(16);
	actor->player.race = RACE_CONSTRUCT;
	actor->player.level = 60;
	trapdamage(actor, trap);
	assert(!actor->affected);
	reset(12);
	actor->player.race = RACE_CONSTRUCT;
	trapdamage(actor, trap);
	assert(!actor->affected && !last_damage);
	reset(12);
	actor->specials.apply_saving_throw[SAVING_SPELL] = 10;
	trapdamage(actor, trap);
	assert(actor->affected);
	for (int level : { 16, 100 })
	{
		reset(9, level);
		affected_type removable = {};
		removable.type = SPELL_ARMOR;
		affect_to_char(actor, &removable);
		affected_type protected_spell = {};
		protected_spell.type = SPELL_HASTE;
		protected_spell.flags = AFFTYPE_NODISPEL;
		affect_to_char(actor, &protected_spell);
		trapdamage(actor, trap);
		assert(!affected_by_spell(actor, SPELL_ARMOR) &&
		       affected_by_spell(actor, SPELL_HASTE));
		assert(!save_mods.empty() && created == discarded);
	}
	for (bool saved : { false, true })
	{
		reset(13);
		save_result = saved;
		trapdamage(actor, trap);
		assert(last_damage == (saved ? 100 : 200) && (last_flags & RAWDAM_NOKILL));
		assert(last_caster_level == 60 && created == discarded);
	}
	reset(14, 0);
	trapdamage(actor, trap);
	assert(poison_level == 25);
	reset(14);
	resistant = true;
	trapdamage(actor, trap);
	assert(!poison_level && trap->trap_charge == 1);
	reset(13);
	P_char other = character();
	char_to_room(other, 0, -2);
	P_char staff = character();
	staff->player.level = MAXLVLMORTAL + 1;
	char_to_room(staff, 0, -2);
	P_char ordinary = character(true);
	char_to_room(ordinary, 0, -2);
	pet = character(true);
	char_to_room(pet, 0, -2);
	trap->trap_eff |= 4;
	trapdamage(actor, trap);
	assert(damaged.size() == 3 && trap->trap_charge == 1 && created == 1 && discarded == 1);
	for (auto *target : { actor, other, pet })
		assert(std::find(damaged.begin(), damaged.end(), target->runtime_id) !=
		       damaged.end());
	for (int failure : { 0, 1 })
	{
		reset(13);
		if (failure)
			fail_placement = 0;
		else
			fail_creation = 0;
		trapdamage(actor, trap);
		assert(trap->trap_charge == 2 && !last_damage && created == discarded);
	}
	for (int mode : { 1, 2, 3 })
	{
		reset(13);
		lifecycle = mode;
		trapdamage(actor, trap);
		assert(created == discarded);
	}
	reset(13);
	trap->trap_eff |= 1024;
	trapdamage(actor, trap);
	assert(trap->trap_charge == 2);
	trap->trap_charge = 0;
	trapdamage(actor, trap);
	assert(trap->trap_charge == 0);
	reset(13, -1);
	trapdamage(actor, trap);
	assert(trap->trap_charge == 2 && !created);
	for (int type : { -1, 17, 32767, 10, 11 })
	{
		reset(type);
		trapdamage(actor, trap);
		assert(trap->trap_charge == 2 && !created);
	}
	reset(11, 50, 32820);
	trapdamage(actor, trap);
	assert(created == 3 && attacks == 3 && trap->trap_charge == 1);
	trapdamage(actor, trap);
	assert(created == 6 && attacks == 6 && trap->trap_charge == 0);
	trap->trap_charge = 1;
	trapdamage(actor, trap);
	assert(created == 6 && trap->trap_charge == 1);
	for (int failure = 0; failure < 3; ++failure)
	{
		reset(11, 50, 32820);
		fail_creation = failure;
		trapdamage(actor, trap);
		assert(created == discarded && trap->trap_charge == 2 && !attacks);
		reset(11, 50, 32820);
		fail_placement = failure;
		trapdamage(actor, trap);
		assert(created == discarded && trap->trap_charge == 2 && !attacks);
	}
	reset(11, 50, 32820);
	remove_first_placement = true;
	trapdamage(actor, trap);
	assert(created == discarded && trap->trap_charge == 2 && !attacks);
	for (const auto &profile : { std::array<int, 5>{ 41361, 10, 200, 1, 1 },
				     { 42290, 10, 200, 1, 1 },
				     { 32820, 11, 32861, 3, 6 },
				     { 32870, 11, 32861, 3, 6 },
				     { 32835, 11, 32861, 1, 6 },
				     { 32846, 11, 32871, 1, 1 },
				     { 41927, 11, 200, 1, 1 } })
	{
		reset(profile[1], 50, profile[0]);
		trap->trap_eff |= 4;
		auto *bystander = character();
		char_to_room(bystander, 0, -2);
		trapdamage(actor, trap);
		assert(created == profile[3] && trap->trap_charge == 1);
		assert(attacks == (profile[1] == 11 ? profile[3] : 0));
		int count = 0;
		for (auto *mob = character_list; mob; mob = mob->next)
			if (IS_NPC(mob))
			{
				++count;
				assert(GET_VNUM(mob) == profile[2]);
			}
		assert(count == profile[3]);
	}
	reset(10, 50, 42290);
	trapdamage(actor, trap);
	assert(created == 1 && attacks == 0 && trap->trap_charge == 1);
	assert(character_list->only.npc->trap_gate_target_runtime_id == actor->runtime_id);
	mobact_memoryHandle(character_list);
	assert(attacks == 1 && last_attacked == actor);
	reset(10, 50, 42290);
	pet = character(true);
	char_to_room(pet, 0, -2);
	trapdamage(pet, trap);
	assert(attacks == 0 &&
	       character_list->only.npc->trap_gate_target_runtime_id == pet->runtime_id);
	mobact_memoryHandle(character_list);
	assert(attacks == 1 && last_attacked == pet);

	// Unlimited glyphs fire once per attempt; a later blocking trap remains visible.
	reset(13);
	trap->trap_eff = 1 | 8 | 1024 | 2048;
	auto *second = new obj_data(*trap);
	second->obj_uid = 2;
	second->trap_eff = 1 | 8;
	trap->next = trap->next_content = second;
	std::vector<std::pair<P_obj, uint64_t>> sprung;
	assert(!checkmovetrap(actor, 0, &sprung) && sprung.size() == 1 && trap->trap_charge == 2);
	assert(checkmovetrap(actor, 0, &sprung) && damaged.size() == 2 && second->trap_charge == 1);
	for (bool saved : { false, true })
	{
		reset(15);
		trap->trap_eff = 1 | 8 | 2048;
		save_result = saved;
		sprung.clear();
		assert(checkmovetrap(actor, 0, &sprung) == !saved);
		assert(sprung.size() == 1 && trap->trap_charge == 1);
	}
	reset(13);
	actor->player.level = MAXLVLMORTAL + 1;
	assert(!checkgetput(actor, trap) && trap->trap_charge == 2 && !created);
	// Builder rejection is atomic, including a previously unconfigured effect mask.
	reset(0);
	trap->trap_eff = 0;
	auto builder_set = [](const char *text)
	{
		std::string command = text;
		do_trapset(actor, command.data(), 0);
	};
	for (const char *bad :
	     { "item damage gate", "item damage summon", "item move sideways", "item level -1",
	       "item charge nonsense", "item charge 101", "item nonsense north" })
	{
		builder_set(bad);
		assert(!trap->trap_eff && trap->trap_dam == 0 && trap->trap_charge == 2 &&
		       trap->trap_level == 60);
	}
	builder_set("item damage dispel");
	assert(trap->trap_dam == 9);
	builder_set("item move east");
	assert(trap->trap_eff == 17);
	builder_set("item glyph");
	assert(trap->trap_eff == (17 | 2048));
	builder_set("item multi");
	assert(trap->trap_eff == (17 | 2048 | 1024));
	builder_set("item charge 0");
	assert(trap->trap_charge == 0);
	reset(0, 0, 32831);
	trap->trap_eff = trap->trap_charge = 0;
	char chest_name[] = "chest";
	assert(!pesky_imp_chest(trap, actor, CMD_OPEN, chest_name));
	assert(created == 3 && attacks == 3 && trap->value[3] == 1);
	pesky_imp_chest(trap, actor, CMD_OPEN, chest_name);
	assert(created == 3 && attacks == 3);
	waits = last_wait = 0;
	trap_tower1_para(trap, actor, CMD_UP, nullptr);
	assert(waits == 1 && last_wait == 5 * PULSE_VIOLENCE);
	actor->player.level = MAXLVLMORTAL + 1;
	trap_tower1_para(trap, actor, CMD_UP, nullptr);
	assert(waits == 1);
	while (character_list)
		extract_char(character_list);
	delete trap;
	trap = nullptr;
}
