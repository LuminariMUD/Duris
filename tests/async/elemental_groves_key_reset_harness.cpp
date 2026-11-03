// Production reset/timer functions are inserted by the Python runner.
#include "key_reset_harness.h"

// PRODUCTION

enum Source
{
	CARRIER,
	FLOOR,
	PEDESTAL
};
struct Gate
{
	int key;
	Source source;
	int holder, home, near, direction, far;
};
const Gate gates[] = {
	{ 3800, CARRIER, 3811, 3900, 3899, 1, 3898 },
	{ 3801, CARRIER, 3812, 3898, 3898, 2, 3897 },
	{ 3802, CARRIER, 3813, 3909, 3910, 1, 3911 },
	{ 3803, CARRIER, 3814, 3910, 3910, 2, 3908 },
	{ 3804, CARRIER, 3815, 3919, 3921, 3, 3922 },
	{ 3805, CARRIER, 3816, 3921, 3921, 0, 3920 },
	{ 3806, CARRIER, 3817, 3925, 3926, 3, 3928 },
	{ 3807, CARRIER, 3818, 3928, 3928, 0, 3927 },
	{ 3808, FLOOR, 0, 3854, 3951, 4, 3952 },
	{ 3809, FLOOR, 0, 3823, 3947, 4, 3953 },
	{ 3810, PEDESTAL, 3818, 3897, 3960, 0, 3961 },
	{ 3811, PEDESTAL, 3818, 3908, 3961, 0, 3962 },
	{ 3812, PEDESTAL, 3818, 3920, 3962, 0, 3963 },
	{ 3813, PEDESTAL, 3818, 3927, 3963, 0, 3964 },
	{ 3814, PEDESTAL, 3818, 3952, 3964, 0, 3965 },
	{ 3815, PEDESTAL, 3819, 3953, 3965, 0, 3966 },
};
// FIXTURE

int live(int key)
{
	return obj_index[real_object(key)].number;
}
P_char carrier(const Gate &gate)
{
	for (auto &mob : characters)
		if (mob->npc && mob->rnum == real_mobile(gate.holder))
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
P_obj pedestal(const Gate &gate)
{
	return get_obj_in_list_num(real_object(gate.holder), world[real_room(gate.home)].contents);
}
// The key at its authored source, or nullptr.
P_obj stocked(const Gate &gate)
{
	switch (gate.source)
	{
	case CARRIER:
		return carrier(gate) ? key_on(carrier(gate), gate.key) : nullptr;
	case FLOOR:
		return get_obj_in_list_num(real_object(gate.key),
					   world[real_room(gate.home)].contents);
	case PEDESTAL:
		return pedestal(gate) ? get_obj_in_list_num(real_object(gate.key),
							    pedestal(gate)->contains) :
					nullptr;
	}
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
		assert(!!IS_SET(exit->exit_info, EX_LOCKED) == locked);
		assert(!IS_SET(exit->exit_info, EX_SECRET));
	}
}
void check_all(bool locked)
{
	for (const auto &gate : gates)
		check_pair(gate, locked);
}
// A copy held elsewhere suppresses its reload; consuming it must neither leave
// the gate locked without a key nor create a second copy.
void carrier_sequence(const Gate &gate)
{
	auto held = read_object_for_creation(real_object(gate.key), REAL);
	reset_zone(1, 0);
	auto mob = carrier(gate);
	assert(mob && !key_on(mob, gate.key) && live(gate.key) == 1);
	check_pair(gate, false);
	extract_obj(held); // unlocking breaks the key (value[1] = 100)
	const int prior_births = births;
	const auto prior_objects = objects.size();
	for (int repeat = 0; repeat < 3; ++repeat)
	{
		reset_zone(1, 0);
		assert(carrier(gate) == mob && !key_on(mob, gate.key) && live(gate.key) == 0);
		assert(births == prior_births && objects.size() == prior_objects);
		check_pair(gate, false);
	}
	extract_char(mob);
	reset_zone(1, 0);
	assert(key_on(carrier(gate), gate.key) && live(gate.key) == 1);
	check_pair(gate, true);
}
// Loose and pedestal keys reload through their own source on the next reset.
void item_sequence(const Gate &gate)
{
	reset_zone(1, 2);
	auto source = stocked(gate);
	assert(source && live(gate.key) == 1);
	check_pair(gate, true);
	detach(source); // picked up and held elsewhere
	reset_zone(1, 0);
	assert(!stocked(gate) && live(gate.key) == 1);
	check_pair(gate, false);
	extract_obj(source); // broken in the lock
	reset_zone(1, 0);
	assert(stocked(gate) && live(gate.key) == 1);
	check_pair(gate, true);
	const auto count = objects.size();
	reset_zone(1, 0);
	assert(objects.size() == count && live(gate.key) == 1);
	check_pair(gate, true);
}
void controls()
{
	reset_zone(1, 2);
	for (const auto &gate : gates)
		assert(stocked(gate) && live(gate.key) == 1);
	check_all(true);
	const auto count = objects.size();
	const auto born = births;
	reset_zone(1, 0);
	assert(objects.size() == count && births == born);
	check_all(true);
	// Each plaque restocks into its own pedestal, not the newest pedestal.
	for (const auto &gate : gates)
		if (gate.source == PEDESTAL)
			extract_obj(stocked(gate));
	reset_zone(1, 0);
	for (const auto &gate : gates)
		assert(stocked(gate) && live(gate.key) == 1);
	check_all(true);
	// A destroyed pedestal reloads with its plaque through the zone rows...
	const auto &stone = gates[10];
	extract_obj(pedestal(stone));
	reset_zone(1, 0);
	assert(stocked(stone) && live(stone.key) == 1);
	check_all(true);
	// ...and one that cannot reload leaves its gate passable, not keyless.
	extract_obj(pedestal(stone));
	fail_object = stone.holder;
	reset_zone(1, 0);
	assert(!pedestal(stone) && live(stone.key) == 0);
	check_pair(stone, false);
	check_pair(gates[11], true);
	fail_object = -1;
	reset_zone(1, 0);
	assert(stocked(stone));
	check_pair(stone, true);
	// A fixed reload failure leaves the gate passable rather than keyless.
	const auto &cloudy = gates[8];
	extract_obj(stocked(cloudy));
	fail_object = cloudy.key;
	reset_zone(1, 0);
	assert(!stocked(cloudy));
	check_pair(cloudy, false);
	fail_object = -1;
	reset_zone(1, 0);
	check_pair(cloudy, true);
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
	reset_zone(1, 2);
	auto pc = player(3961);
	Descriptor descriptor{ 0, pc, nullptr };
	descriptor_list = &descriptor;
	int zone = 1;
	zone_table[zone].age = zone_table[zone].lifespan;
	const int born = births;
	event_reset_zone(nullptr, nullptr, nullptr, &zone);
	assert(births == born && reschedules == 1); // a connected player blocks the reset
	check_all(true);
	descriptor_list = nullptr; // linkdead body still in the zone
	event_reset_zone(nullptr, nullptr, nullptr, &zone);
	assert(zone_table[zone].age == 0 && reschedules == 2);
	check_all(false);
	descriptor_list = &descriptor;
	reset_zone(1, 0); // staff zreset bypasses the timer admission
	check_all(false);
	char_to_room(pc, real_room(5760), -2);
	reset_zone(1, 0);
	check_all(true);
	// A morphed player's visible body is an NPC; the original PC is in limbo.
	char_to_room(pc, real_room(3961), -2);
	pc->npc = pc->morph = true;
	reset_zone(1, 0);
	check_all(false);
	pc->npc = pc->morph = false;
	char_from_room(pc); // NOWHERE does not count as occupancy
	reset_zone(1, 0);
	check_all(true);
	descriptor_list = nullptr;
}
void boundaries()
{
	reset_zone(1, 2);
	// Scope uses zone number, not its array index.
	auto held = stocked(gates[0]);
	detach(held);
	zone_table[1].number = 39;
	reset_zone(1, 0);
	check_pair(gates[0], true);
	zone_table[1].number = 38;
	reset_zone(1, 0);
	// Gravel opens 3899 east; the far side takes slate, and both sides open.
	check_pair(gates[0], false);
	check_pair(gates[1], true);
	obj_to_char(held, carrier(gates[0]));
	reset_zone(1, 0);
	check_pair(gates[0], true);
	// An unexpected reverse exit must not be silently changed.
	auto plaque = stocked(gates[12]);
	detach(plaque);
	auto reverse = door(gates[12].far, rev_dir[gates[12].direction]);
	const int target = reverse->to_room;
	reverse->to_room = real_room(5760);
	reset_zone(1, 0);
	assert(IS_SET(door(gates[12].near, gates[12].direction)->exit_info, EX_LOCKED));
	assert(IS_SET(reverse->exit_info, EX_LOCKED));
	reverse->to_room = target;
	reset_zone(1, 0);
	check_pair(gates[12], false);
	extract_obj(plaque);
	// The keyless elemental door (key -2) is never opened by this rule.
	reset_zone(1, 0);
	assert(IS_SET(door(3966, 0)->exit_info, EX_LOCKED));
	assert(IS_SET(door(3967, 2)->exit_info, EX_LOCKED));
	check_all(true);
}
int main(int argc, char **argv)
{
	assert(argc == 2);
	zone_table[1].number = 38;
	zone_table[1].lifespan = zone_table[1].lifespan_min = zone_table[1].lifespan_max = 5;
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
				if (gate.source == CARRIER)
					carrier_sequence(gate);
				else
					item_sequence(gate);
				found = true;
			}
		assert(found);
	}
}
