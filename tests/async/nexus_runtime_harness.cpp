#include "core/prototypes.h"
#include "core/defines.h"
#include "core/utils.h"
#include "economy/nexus_stones.h"
#include "flatfile/flatfile_nexus_repository.h"
#include "magic/spells.h"
#include "ships/ship_npc.h"
#include "world/epic_transaction.h"

#include <cassert>
#include <cstring>
#include <filesystem>
#include <iostream>

static index_data mob_templates[512] = {};
static index_data obj_templates[512] = {};
static room_data rooms[2] = {};
P_index mob_index = mob_templates;
P_index obj_index = obj_templates;
P_room world = rooms;
extern const int top_of_world = 1;
P_char character_list = nullptr;
P_obj object_list = nullptr;
P_desc descriptor_list = nullptr;
P_ship cyrics_revenge = nullptr;
bool nexus_to_cyrics_revenge = false;
const char *apply_names[] = { "none", "strength" };

static std::string state_root;
static std::string output_messages;
static int submissions = 0;
static int saves = 0;
static bool refuse_guardian = false;

const char *persistence_mode_flatfile_root()
{
	return state_root.c_str();
}
float get_property(const char *, double fallback)
{
	return fallback;
}
int get_property(const char *, int fallback)
{
	return fallback;
}
int BOUNDED(int lower, int value, int upper)
{
	return std::min(upper, std::max(lower, value));
}
int get_cyrics_revenge_nexus_rvnum(P_ship)
{
	return 3003;
}
std::string strip_ansi(const char *text)
{
	return text;
}
char *str_dup(const char *text)
{
	return strdup(text);
}
void act(const char *text, int, P_char, P_obj, void *, int)
{
	output_messages += text;
}
void send_to_char(const char *text, P_char)
{
	output_messages += text;
}
bool isname(const char *name, const char *target)
{
	return strcmp(name, target) == 0;
}
char *one_argument(const char *argument, char *first)
{
	strcpy(first, argument);
	return const_cast<char *>(argument + strlen(argument));
}
int real_room(const int vnum)
{
	return vnum == 1001 ? 0 : vnum == 3003 ? 1 : -1;
}
int real_mobile(const int vnum)
{
	return vnum;
}
int real_object(const int vnum)
{
	return vnum;
}

P_obj read_object(int rnum, int)
{
	auto obj = new obj_data{};
	obj->R_num = rnum;
	obj->next = object_list;
	object_list = obj;
	return obj;
}
void obj_to_room(P_obj obj, int room)
{
	obj->loc.room = room;
}
void extract_obj(P_obj obj, int)
{
	P_obj *cursor = &object_list;
	while (*cursor != obj)
	{
		assert(*cursor);
		cursor = &(*cursor)->next;
	}
	*cursor = obj->next;
	free(obj->name);
	free(obj->description);
	free(obj->short_description);
	delete obj;
}
P_char read_mobile(int rnum, int)
{
	if (refuse_guardian)
		return nullptr;
	auto mob = new char_data{};
	mob->specials.act = ACT_ISNPC;
	mob->only.npc = new npc_only_data{};
	mob->only.npc->R_num = rnum;
	mob->in_room = -1;
	mob->next = character_list;
	character_list = mob;
	return mob;
}
bool char_to_room(P_char mob, int room, int)
{
	mob->in_room = room;
	mob->next_in_room = world[room].people;
	world[room].people = mob;
	return true;
}
void equip_char(P_char mob, P_obj object, int slot, int)
{
	mob->equipment[slot] = object;
}
affected_type *affect_to_char(P_char mob, affected_type *affect)
{
	auto copy = new affected_type(*affect);
	copy->next = mob->affected;
	mob->affected = copy;
	return copy;
}
void extract_char(P_char mob)
{
	P_char *cursor = &character_list;
	while (*cursor != mob)
	{
		assert(*cursor);
		cursor = &(*cursor)->next;
	}
	*cursor = mob->next;
	if (mob->in_room >= 0)
	{
		cursor = &world[mob->in_room].people;
		while (*cursor != mob)
		{
			assert(*cursor);
			cursor = &(*cursor)->next_in_room;
		}
		*cursor = mob->next_in_room;
	}
	while (mob->affected)
	{
		auto affect = mob->affected;
		mob->affected = affect->next;
		delete affect;
	}
	for (auto obj : mob->equipment)
		if (obj)
			extract_obj(obj, false);
	delete mob->only.npc;
	delete mob;
}
bool do_save_silent(P_char, int)
{
	++saves;
	return true;
}
bool epic_transaction_submit(P_char player, int64_t delta, epic_reason_type, int64_t, uint16_t,
			     critical_source_site, critical_deadline_class,
			     epic_completion_fn completion, const void *context, size_t size)
{
	++submissions;
	player->only.pc->epics += delta;
	if (completion)
		completion(player, true, {}, 0, static_cast<const uint8_t *>(context), size);
	return true;
}

static void establish(const std::filesystem::path &root, int stat = APPLY_NONE)
{
	state_root = root.string();
	std::filesystem::create_directories(root / "metadata");
	std::filesystem::permissions(root, std::filesystem::perms::owner_all);
	std::filesystem::permissions(root / "metadata", std::filesystem::perms::owner_all);
	std::string error;
	assert(flatfile_nexus_establish(state_root,
					{ { 1, "Marduk", 1001, 0, stat, 0, 0, 1 },
					  { 3, "Enlil", 3003, 0, 0, 0, 0, 3 } },
					&error) == flatfile_nexus_result::ok);
}

static int guardian_count(int id)
{
	int count = 0;
	for (auto mob = character_list; mob; mob = mob->next)
		if (guardian_stone_id(mob) == id)
			++count;
	return count;
}
static int stone_count(int id)
{
	int count = 0;
	for (auto obj = object_list; obj; obj = obj->next)
		if (OBJ_VNUM(obj) == 394 && STONE_ID(obj) == id)
			++count;
	return count;
}

int main(int argc, char **argv)
{
	assert(argc == 2);
	const std::filesystem::path root(argv[1]);
	for (int i = 0; i < 512; ++i)
	{
		mob_templates[i].virtual_number = i;
		obj_templates[i].virtual_number = i;
	}
	world[0].number = 1001;
	world[1].number = 3003;
	char_data staff = {};
	staff.player.name = const_cast<char *>("Fixture");
	establish(root / "lifecycle");
	assert(load_nexus_stones());
	assert(get_nexus_guardian(1) && GET_VNUM(get_nexus_guardian(1)) == 74);
	assert(get_nexus_guardian(3) && GET_VNUM(get_nexus_guardian(3)) == 74);
	for (int repeat = 0; repeat < 3; ++repeat)
	{
		P_char other = get_nexus_guardian(3);
		reload_nexus_stone(&staff, 1);
		assert(get_nexus_guardian(3) == other);
		assert(stone_count(1) == 1 && guardian_count(1) == 1);
		reset_nexus_stones(&staff);
		assert(stone_count(1) == 1 && stone_count(3) == 1);
		assert(guardian_count(1) == 1 && guardian_count(3) == 1);
	}
	for (int align : { -3, -2, -1, 0, 1, 2, 3 })
	{
		assert(update_nexus_stone_align(1, align));
		reload_nexus_stone(&staff, 1);
		assert(stone_count(1) == 1 && STONE_ALIGN(get_nexus_stone(1)) == align);
		const int expected = align == -3 ? 66 : align == 3 ? 65 : align == 0 ? 74 : 0;
		assert(guardian_count(1) == (expected ? 1 : 0));
		if (expected)
			assert(GET_VNUM(get_nexus_guardian(1)) == expected);
	}
	for (int repeat = 0; repeat < 2; ++repeat)
	{
		expire_nexus_stone(1);
		assert(STONE_ALIGN(get_nexus_stone(1)) == 0 && guardian_count(1) == 1);
		assert(GET_VNUM(get_nexus_guardian(1)) == 74 && guardian_count(3) == 1);
		NexusStoneInfo info = {};
		assert(nexus_stone_info(1, &info) && info.align == 0 && info.last_touched_at == 0);
	}
	while (character_list)
		extract_char(character_list);
	while (object_list)
		extract_obj(object_list, false);
	refuse_guardian = true;
	output_messages.clear();
	reset_nexus_stones(&staff);
	assert(output_messages.find("reset is incomplete") != std::string::npos);
	assert(stone_count(1) == 0 && stone_count(3) == 0);
	output_messages.clear();
	reload_nexus_stone(&staff, 1);
	assert(output_messages.find("reload failed") != std::string::npos);
	assert(stone_count(1) == 0);
	refuse_guardian = false;

	char_data player = {};
	pc_only_data pc = {};
	player.only.pc = &pc;
	player.in_room = -1;
	for (int stat : { APPLY_NONE, -1, 255, APPLY_STR })
	{
		establish(root / ("sage-" + std::to_string(stat)), stat);
		auto sage = read_mobile(MOB_GOOD_SAGE, REAL);
		sage->player.name = const_cast<char *>("sage");
		affected_type tag = {};
		tag.type = TAG_GUARD_NEXUS_STONE;
		tag.modifier = 1;
		affect_to_char(sage, &tag);
		player.base_stats.Str = 50;
		pc.epics = 10;
		submissions = saves = 0;
		output_messages.clear();
		char argument[] = "sage";
		assert(nexus_sage_ask(sage, &player, argument));
		assert(submissions == 0 && pc.epics == 10 && player.base_stats.Str == 50);
		assert(output_messages.find(stat == APPLY_STR ?
						    "considerable strength" :
						    "no stat training") != std::string::npos);
		output_messages.clear();
		assert(nexus_sage_train(sage, &player, argument));
		if (stat == APPLY_STR)
		{
			assert(submissions == 1 && pc.epics == 9 && player.base_stats.Str == 53 &&
			       saves == 1);
			assert(output_messages.find("strength increasing") != std::string::npos);
			player.base_stats.Str = 100;
			assert(nexus_sage_ask(sage, &player, argument));
			assert(nexus_sage_train(sage, &player, argument));
			assert(submissions == 1 && pc.epics == 9 && player.base_stats.Str == 100);
			player.base_stats.Str = 50;
			pc.epics = 0;
			assert(nexus_sage_train(sage, &player, argument));
			assert(submissions == 1 && pc.epics == 0 && player.base_stats.Str == 50);
		}
		else
		{
			assert(submissions == 0 && pc.epics == 10 && player.base_stats.Str == 50 &&
			       saves == 0);
			assert(output_messages.find("no stat training") != std::string::npos);
			assert(output_messages.find("epic offering") == std::string::npos);
		}
		extract_char(sage);
	}
	std::cout << "Nexus actual sage handlers and neutral/partial/faction lifecycle passed\n";
}
