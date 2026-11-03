// Production reset/timer functions are inserted by the Python runner.
#include "key_reset_harness.h"

// PRODUCTION

struct Gate
{
	int key, mob, home, near, direction, far, slot;
};
const Gate gates[] = {
	{ 2405, 2406, 2427, 2414, 5, 2415, 18 }, { 2418, 2415, 2439, 2427, 4, 2428, 0 },
	{ 2422, 2418, 2452, 2446, 3, 2448, 0 },	 { 2425, 2419, 2456, 2460, 4, 2461, 18 },
	{ 2436, 2433, 2481, 2471, 0, 2479, 0 },	 { 2437, 2420, 2477, 2480, 0, 2488, 4 },
	{ 2438, 2428, 2493, 2480, 2, 2498, 18 }
};
// FIXTURE

P_char carrier(const Gate &gate)
{
	for (auto &mob : characters)
		if (mob->npc && mob->rnum == real_mobile(gate.mob))
			return mob.get();
	return nullptr;
}
P_obj key_on(P_char mob, int key)
{
	for (auto item : mob->equipment)
		if (item && OBJ_VNUM(item) == key)
			return item;
	for (auto item = mob->carrying; item; item = item->next_content)
		if (OBJ_VNUM(item) == key)
			return item;
	return nullptr;
}
room_direction_data *door(int room, int direction)
{
	return world[real_room(room)].dir_option[direction];
}
void check_pair(const Gate &gate, bool locked)
{
	for (auto exit :
	     { door(gate.near, gate.direction), door(gate.far, rev_dir[gate.direction]) })
	{
		assert(IS_SET(exit->exit_info, EX_ISDOOR) && IS_SET(exit->exit_info, EX_CLOSED));
		assert(IS_SET(exit->exit_info, EX_PICKPROOF));
		assert(!!IS_SET(exit->exit_info, EX_LOCKED) == locked);
		assert(!!IS_SET(exit->exit_info, EX_SECRET) == (locked && gate.key == 2436));
	}
}
void held_sequence(const Gate &gate)
{
	// A live off-carrier copy suppresses E/G on the newly spawned carrier.
	auto held = read_object_for_creation(real_object(gate.key), REAL);
	reset_zone(1, 0);
	auto mob = carrier(gate);
	assert(mob && !key_on(mob, gate.key));
	assert(obj_index[real_object(gate.key)].number == 1);
	const bool initially_unlocked =
		!IS_SET(door(gate.near, gate.direction)->exit_info, EX_LOCKED);
	// Model successful consumption; actual commands/dirty saves run in the socket journey.
	extract_obj(held);
	const int prior_births = births;
	const auto prior_objects = objects.size();
	std::vector<P_obj> prior_object_ids;
	for (const auto &item : objects)
		prior_object_ids.push_back(item.get());
	for (int repeat = 0; repeat < 3; ++repeat)
	{
		reset_zone(1, 0);
		assert(carrier(gate) == mob && !key_on(mob, gate.key));
		assert(obj_index[real_object(gate.key)].number == 0);
		assert(births == prior_births && objects.size() == prior_objects);
		for (size_t i = 0; i < objects.size(); ++i)
			assert(objects[i].get() == prior_object_ids[i]);
		check_pair(gate, false);
	}
	assert(initially_unlocked);
	extract_char(mob);
	reset_zone(1, 0);
	assert(key_on(carrier(gate), gate.key));
	check_pair(gate, true);
}
void controls()
{
	reset_zone(1, 2);
	for (const auto &gate : gates)
	{
		assert(key_on(carrier(gate), gate.key));
		check_pair(gate, true);
	}
	assert(OBJ_VNUM(carrier(gates[5])->equipment[4]) == 2437);
	assert(OBJ_VNUM(carrier(gates[5])->equipment[HOLD]) != 2437);
	const auto count = objects.size();
	const auto born = births;
	reset_zone(1, 0);
	assert(objects.size() == count && births == born);
	for (const auto &gate : gates)
		check_pair(gate, true);
	for (const auto &gate : gates)
	{
		const auto case_count = objects.size();
		const auto case_births = births;
		auto mob = carrier(gate);
		auto item = key_on(mob, gate.key);
		detach(item); // held/corpse/container copies all remain live but off the carrier
		reset_zone(1, 0);
		check_pair(gate, false);
		assert(objects.size() == case_count && births == case_births);
		obj_to_char(item, mob);
		reset_zone(1, 0);
		check_pair(gate, true); // inventory counts as well as its authored equipment slot
		char_to_room(mob, real_room(5760), -2);
		reset_zone(1, 0);
		check_pair(gate, false);
		char_to_room(mob, real_room(gate.home), -2);
		reset_zone(1, 0);
		check_pair(gate, true);
		extract_char(mob);
		fail_object = gate.key;
		reset_zone(1, 0);
		check_pair(gate, false);
		assert(carrier(gate) && !key_on(carrier(gate), gate.key));
		fail_object = -1;
		extract_char(carrier(gate));
		reset_zone(1, 0);
		check_pair(gate, true);
	}
}
P_char player(int room)
{
	auto ch = std::make_unique<Character>();
	ch->npc = false;
	ch->next = character_list;
	character_list = ch.get();
	characters.push_back(std::move(ch));
	char_to_room(character_list, real_room(room), -2);
	return character_list;
}
void occupancy()
{
	reset_zone(1, 0);
	auto pc = player(2415);
	Descriptor descriptor{ 0, pc, nullptr };
	descriptor_list = &descriptor;
	int zone = 1;
	zone_table[zone].age = zone_table[zone].lifespan;
	const int born = births;
	event_reset_zone(nullptr, nullptr, nullptr, &zone);
	assert(zone_table[zone].age == 6 && births == born && reschedules == 1);
	for (const auto &gate : gates)
		check_pair(gate, true);
	descriptor_list = nullptr; // linkdead body still in the zone
	event_reset_zone(nullptr, nullptr, nullptr, &zone);
	assert(zone_table[zone].age == 0 && births == born && reschedules == 2);
	for (const auto &gate : gates)
		check_pair(gate, false);
	assert(!IS_SET(door(2401, 0)->exit_info, EX_LOCKED));
	assert(!IS_SET(door(2402, 2)->exit_info, EX_LOCKED));
	descriptor_list = &descriptor;
	reset_zone(1, 0); // staff zreset ok bypasses the timer admission
	for (const auto &gate : gates)
		check_pair(gate, false);
	char_to_room(pc, real_room(5760), -2);
	zone_table[zone].age = zone_table[zone].lifespan;
	event_reset_zone(nullptr, nullptr, nullptr, &zone);
	assert(zone_table[zone].age == 0);
	for (const auto &gate : gates)
		check_pair(gate, true);
	assert(IS_SET(door(2402, 2)->exit_info, EX_LOCKED));
	// A morphed player's visible body is an NPC; the original PC is in limbo.
	char_to_room(pc, real_room(2415), -2);
	pc->npc = pc->morph = true;
	descriptor_list = nullptr;
	zone_table[zone].age = zone_table[zone].lifespan;
	event_reset_zone(nullptr, nullptr, nullptr, &zone);
	for (const auto &gate : gates)
		check_pair(gate, false);
	assert(!IS_SET(door(2402, 2)->exit_info, EX_LOCKED));
	pc->npc = pc->morph = false;
	char_from_room(pc); // NOWHERE does not count as castle occupancy
	reset_zone(1, 0);
	for (const auto &gate : gates)
		check_pair(gate, true);
	descriptor_list = nullptr;
}
void boundaries()
{
	// Scope uses zone number, not its array index.
	zone_table[1].number = 25;
	auto held = read_object_for_creation(real_object(gates[0].key), REAL);
	reset_zone(1, 0);
	check_pair(gates[0], true);
	zone_table[1].number = 24;
	reset_zone(1, 0);
	check_pair(gates[0], false);
	assert(IS_SET(door(2401, 0)->exit_info, EX_LOCKED));
	assert(!IS_SET(door(2403, 0)->exit_info, EX_LOCKED)); // unrelated closed-only door
	extract_obj(held);
	// An unexpected reverse exit must not be silently changed.
	auto reverse = door(gates[0].far, rev_dir[gates[0].direction]);
	const int target = reverse->to_room;
	reverse->to_room = real_room(5760);
	reset_zone(1, 0);
	assert(IS_SET(door(gates[0].near, gates[0].direction)->exit_info, EX_LOCKED));
	assert(IS_SET(reverse->exit_info, EX_LOCKED));
	reverse->to_room = target;
	reset_zone(1, 0);
	check_pair(gates[0], false);
	// The unrelated consumable bookcase key neither supplies a door nor gets replaced.
	auto bookcase_key = read_object_for_creation(real_object(2434), REAL);
	obj_to_char(bookcase_key, carrier(gates[0]));
	const auto count = objects.size();
	reset_zone(1, 0);
	check_pair(gates[0], false);
	assert(key_on(carrier(gates[0]), 2434) == bookcase_key && objects.size() == count);
}
int main(int argc, char **argv)
{
	assert(argc == 2);
	zone_table[1].number = 24;
	load_fixture();
	const std::string scenario = argv[1];
	if (scenario == "controls")
		controls();
	else if (scenario == "occupancy")
		occupancy();
	else if (scenario == "boundaries")
		boundaries();
	else
	{
		const int key = std::atoi(argv[1]);
		bool found = false;
		for (const auto &gate : gates)
			if (gate.key == key)
			{
				held_sequence(gate);
				found = true;
			}
		assert(found);
	}
}
