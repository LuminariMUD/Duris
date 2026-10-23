#include "economy/divine_trade_runtime.h"
bool divine_trade_runtime_sale(char_data *, ShipData *, int, int, divine_trade_goods)
{
	return false;
}
#include "core/prototypes.h"
#include "core/defines.h"
#include "core/utils.h"
#include "economy/nexus_stones.h"
#include "economy/boon.h"
#include "flatfile/flatfile_nexus_repository.h"
#include "magic/spells.h"
#include "ships/ship_npc.h"
#include "world/epic_transaction.h"
#include "world/epic.h"
#include "world/epic_bonus.h"
#include "world/difficulty.h"
#include "persistence/persistence_checkpoint.h"

#include <cassert>
#include <cmath>
#include <cstring>
#include <cstdarg>
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
static time_t fixture_time = 1800000000;
static event_func pending_event = nullptr;
static P_obj pending_stone = nullptr;
static int event_delay = 0, capture_awards = 0, boon_completions = 0, task_removals = 0;
static int random_low = 0, random_high = 0;
static affected_type task = {};
static bool has_task = false;
bool nexus_stone_touch(P_obj, P_char);
int fixture_epic_award(P_char, int, int = 1, int = 250);
int sell_cargo(P_char, P_ship, int);
int sell_contra(P_char, P_ship, int);
int errand_notch = 500;
const PortData ports[NUM_PORTS] = { { 1001, "fixture", 0 } };
static int paid_copper = 0, ship_saves = 0;
bool has_epic_task(P_char)
{
	return has_task;
}
float get_epic_bonus(P_char, int)
{
	return 0;
}
double difficulty_multiplier(difficulty_dial)
{
	return 1;
}
void ADD_MONEY(P_char, int copper)
{
	paid_copper += copper;
}
bool has_eq_diplomat(const ShipData *)
{
	return false;
}
void ShipCrew::sail_skill_raise(float) {}
void ShipCrew::rpar_skill_raise(float) {}
void update_crew(P_ship) {}
void update_ship_status(P_ship, P_ship) {}
void queue_ship_save(P_ship, const char *)
{
	++ship_saves;
}
int write_cargo()
{
	return true;
}
int sell_cargo_slot(P_char, P_ship ship, int slot, int, int)
{
	ship->slot[slot].type = SLOT_EMPTY;
	queue_ship_save(ship, "cargo sale");
	return 250;
}
int sell_contra_slot(P_char ch, P_ship ship, int slot, int room, int paid)
{
	return sell_cargo_slot(ch, ship, slot, room, paid);
}
void send_to_char_f(P_char, const char *format, ...)
{
	char buffer[512];
	va_list arguments;
	va_start(arguments, format);
	vsnprintf(buffer, sizeof(buffer), format, arguments);
	va_end(arguments);
	output_messages += buffer;
}

extern "C" time_t time(time_t *out) noexcept
{
	if (out)
		*out = fixture_time;
	return fixture_time;
}

const char *persistence_mode_flatfile_root()
{
	return state_root.c_str();
}
static float cargo_bonus = .110f;
float get_property(const char *name, double fallback)
{
	if (!strcmp(name, "nexusStones.touchTimerSecs"))
		return 300;
	if (!strcmp(name, "nexusStones.turnTimerSecs"))
		return 3600;
	if (!strcmp(name, "nexusStones.expireDays"))
		return 12;
	if (!strcmp(name, "nexusStones.epicsMin"))
		return 15;
	if (!strcmp(name, "nexusStones.epicsMax"))
		return 25;
	if (!strcmp(name, "nexusStones.bonus.cargo"))
		return cargo_bonus;
	if (!strcmp(name, "nexusStones.bonus.epics"))
		return .110;
	return fallback;
}
int get_property(const char *name, int fallback)
{
	return get_property(name, static_cast<double>(fallback));
}
int BOUNDED(int lower, int value, int upper)
{
	return std::min(upper, std::max(lower, value));
}
char *coin_stringv(int, int)
{
	static char coins[] = "coins";
	return coins;
}
int number(int low, int high)
{
	random_low = low;
	random_high = high;
	return low;
}
affected_type *get_epic_task(P_char)
{
	return has_task ? &task : nullptr;
}
void affect_remove(P_char, affected_type *value)
{
	assert(value == &task);
	has_task = false;
	++task_removals;
}
bool gain_epic(P_char player, int type, int stone_id, int amount)
{
	assert(type == EPIC_NEXUS_STONE && (stone_id == 1 || stone_id == 3));
	amount = fixture_epic_award(player, type, stone_id, amount);
	if (!amount)
		return false;
	++capture_awards;
	player->only.pc->epics += amount;
	return true;
}
void check_boon_completion(P_char, P_char, double id, int kind)
{
	assert(kind == BOPT_NEXUS && (id == 1 || id == 3));
	++boon_completions;
}
void mark_player_dirty_components(int, player_component_mask_t) {}
nevent_schedule_result add_event(event_func callback, int delay, P_char, P_char, P_obj obj, int,
				 const void *, int)
{
	pending_event = callback;
	pending_stone = obj;
	event_delay = delay;
	return { nevent_schedule_status::scheduled, { nullptr, 1 } };
}
static void finish_touch_cooldown()
{
	assert(event_delay == 300 * WAIT_SEC && pending_event == event_nexus_stone_hum);
	fixture_time += 300;
	pending_event(nullptr, nullptr, pending_stone, nullptr);
	pending_event = nullptr;
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
		// Change durable state independently of the in-memory reward cache.
		std::string error;
		const auto updated = flatfile_nexus_update_state(state_root, 1, align, 0, &error);
		assert(updated == flatfile_nexus_result::ok ||
		       updated == flatfile_nexus_result::unchanged);
		reload_nexus_stone(&staff, 1);
		NexusStoneInfo cached;
		assert(nexus_stone_info(1, &cached) && cached.align == align);
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
	establish(root / "capture");
	nexus_to_cyrics_revenge = true;
	cyrics_revenge = reinterpret_cast<P_ship>(&staff);
	assert(load_nexus_stones());
	player.player.level = 51;
	player.player.racewar = RACEWAR_GOOD;
	player.in_room = 0;
	pc.epics = 1000;
	P_obj stone = get_nexus_stone(1);
	auto attempt_touch = [&](P_obj target)
	{
		// Arrange a healed, eligible mortal before each independent command attempt.
		player.points.hit = 1000;
		player.specials.position = POS_STANDING + STAT_NORMAL;
		return nexus_stone_touch(target, &player);
	};
	assert(!attempt_touch(stone)); // living guardian
	extract_char(get_nexus_guardian(1));
	player.player.level = 50;
	assert(!attempt_touch(stone));
	player.player.level = 51;
	player.player.racewar = 0;
	assert(!attempt_touch(stone));
	player.player.racewar = RACEWAR_GOOD;
	const time_t started = fixture_time;
	assert(attempt_touch(stone) && STONE_ALIGN(stone) == 1);
	assert(!attempt_touch(stone));
	fixture_time += 299;
	assert(!attempt_touch(stone));
	fixture_time -= 299;
	finish_touch_cooldown();
	assert(attempt_touch(stone) && STONE_ALIGN(stone) == 2);
	assert(capture_awards == 0 && boon_completions == 0);
	assert(check_nexus_bonus(&player, 250, NEXUS_BONUS_EPICS) == 250);
	finish_touch_cooldown();
	assert(!attempt_touch(stone)); // full turn still on cooldown
	fixture_time = started + 3599;
	assert(!attempt_touch(stone));
	fixture_time = started + 3600;
	has_task = true;
	task.modifier = SPILL_BLOOD + 1;
	assert(attempt_touch(stone) && STONE_ALIGN(stone) == 3);
	assert(capture_awards == 1 && boon_completions == 1 && task_removals == 1);
	assert(random_low == 15 && random_high == 50 && pc.epics == 1016);
	assert(check_nexus_bonus(&player, 250, NEXUS_BONUS_EPICS) == 277);
	assert(std::abs(check_nexus_bonus_precise(&player, 250, NEXUS_BONUS_EPICS) - 277.5) <
	       0.0001);
	assert(std::abs(check_nexus_bonus_precise(&player, 100.5, NEXUS_BONUS_EPICS) - 111.555) <
	       0.0001);
	assert(check_nexus_bonus(&player, 1, NEXUS_BONUS_EPICS) == 2);
	assert(STONE_ALIGN(get_random_enemy_nexus(&player)) == 0);
	player.player.racewar = RACEWAR_EVIL;
	assert(check_nexus_bonus(&player, 250, NEXUS_BONUS_EPICS) == 250);
	assert(check_nexus_bonus_precise(&player, 100.5, NEXUS_BONUS_EPICS) == 100.5);
	player.in_room = 1;
	stone = get_nexus_stone(3);
	extract_char(get_nexus_guardian(3));
	for (int touch = 1; touch <= 3; ++touch)
	{
		assert(attempt_touch(stone) && STONE_ALIGN(stone) == -touch);
		finish_touch_cooldown();
	}
	assert(capture_awards == 2 && boon_completions == 2);
	assert(random_low == 30 && random_high == 50 && pc.epics == 1046);
	assert(check_nexus_bonus(&player, 250, NEXUS_BONUS_CARGO) == 277);
	cargo_bonus = .100f;
	int preview = 0;
	assert(!check_nexus_bonus_preview(&player, 1952257860, NEXUS_BONUS_CARGO, &preview));
	assert(check_nexus_bonus_preview(&player, 1952257859, NEXUS_BONUS_CARGO, &preview) &&
	       preview == INT_MAX);
	assert(check_nexus_bonus(&player, 1952257859, NEXUS_BONUS_CARGO) == preview);
	assert(check_nexus_bonus(&player, 1952257860, NEXUS_BONUS_CARGO) == 1952257860);
	cargo_bonus = .110f;

	assert(check_nexus_bonus(&player, 1, NEXUS_BONUS_CARGO) == 11);
	assert(STONE_ID(get_random_enemy_nexus(&player)) == 1);
	player.player.racewar = RACEWAR_GOOD;
	assert(check_nexus_bonus(&player, 250, NEXUS_BONUS_CARGO) == 250);
	assert(STONE_ID(get_random_enemy_nexus(&player)) == 3);
	player.in_room = 0;
	player.specials.position = POS_STANDING + STAT_NORMAL;
	ShipData trader = {};
	trader.location = 0;
	for (int align : { -3, -2, -1, 0, 1, 2, 3 })
	{
		assert(update_nexus_stone_align(1, align));
		assert(update_nexus_stone_align(3, align));
		for (int side : { RACEWAR_GOOD, RACEWAR_EVIL })
		{
			player.player.racewar = side;
			const bool owned = (align == 3 && side == RACEWAR_GOOD) ||
					   (align == -3 && side == RACEWAR_EVIL);
			const int expected = owned ? 277 : 250;
			assert(fixture_epic_award(&player, EPIC_PVP) == expected);
			assert(fixture_epic_award(&player, EPIC_NEXUS_STONE) == expected);
			assert(epic_calculate_pvp_award(&player, 250) == expected);
			assert(fixture_epic_award(&player, EPIC_BOTTLE) == 250);
			for (bool contraband : { false, true })
			{
				trader.slot[0].type = contraband ? SLOT_CONTRABAND : SLOT_CARGO;
				paid_copper = ship_saves = 0;
				assert(contraband ? sell_contra(&player, &trader, 0) :
						    sell_cargo(&player, &trader, 0));
				assert(paid_copper == expected && ship_saves == 1);
				assert(trader.slot[0].type == SLOT_EMPTY);
			}
		}
	}
	while (character_list)
		extract_char(character_list);
	while (object_list)
		extract_obj(object_list, false);
	std::cout
		<< "Nexus real sage, guardian, capture/cooldown, task/boon dispatch and faction bonus paths passed\n";
}
