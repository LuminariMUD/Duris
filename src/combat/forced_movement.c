/* Physical displacement shares world barriers with walking, without its costs or posture rules. */
#include "combat/forced_movement.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "world/map.h"

extern P_room world;
extern const int top_of_world;
extern struct zone_data *zone_table;

namespace
{
bool valid_room(int room)
{
	return room >= 0 && room <= top_of_world;
}

struct participant
{
	P_char pointer;
	uint64_t runtime_id;

	P_char live() const
	{
		P_char ch = find_character_by_runtime_id(runtime_id);
		return ch == pointer && IS_ALIVE(ch) ? ch : nullptr;
	}
};

struct forced_exit
{
	int source;
	int destination;
	int direction;
	struct room_direction_data *exit;
};

forced_block plan_exit(P_char ch, int source, int direction, forced_exit &plan)
{
	if (!ch || !IS_ALIVE(ch) || !valid_room(source) || direction < 0 || direction >= NUM_EXITS)
		return forced_block::invalid_room;
	const auto exit = world[source].dir_option[direction];
	if (!exit)
		return forced_block::barrier;
	if (!valid_room(exit->to_room))
		return forced_block::invalid_room;
	if (exit->to_room == source)
		return forced_block::barrier;
	const forced_block terrain = map_entry_barrier(ch, source, exit->to_room);
	if (terrain != forced_block::none)
		return terrain;
	if (IS_SET(exit->exit_info, EX_SECRET | EX_BLOCKED) ||
	    check_castle_walls(source, exit->to_room) || check_wall(source, direction))
		return forced_block::barrier;
	const bool passdoor =
		IS_AFFECTED2(ch, AFF2_PASSDOOR) &&
		(!IS_SET(exit->exit_info, EX_LOCKED) || !IS_SET(exit->exit_info, EX_PICKPROOF));
	if (IS_SET(exit->exit_info, EX_CLOSED) && !IS_TRUSTED(ch) && !passdoor)
		return forced_block::door;
	if (IS_ROOM(exit->to_room, ROOM_PRIVATE) && GET_LEVEL(ch) < 59)
	{
		int present = 0;
		for (P_char person = world[exit->to_room].people; person;
		     person = person->next_in_room)
			++present;
		if (present > 1)
			return forced_block::private_room;
	}
	plan = { source, exit->to_room, direction, exit };
	return forced_block::none;
}

forced_move_result recheck(const participant &person, const forced_exit &plan, bool detached)
{
	P_char ch = person.live();
	if (!ch || (detached ? ch->in_room != NOWHERE ||
				       ch->specials.was_in_room != world[plan.source].number :
			       ch->in_room != plan.source))
		return { forced_move_status::interrupted };
	forced_exit current{};
	const forced_block blocked = plan_exit(ch, plan.source, plan.direction, current);
	if (blocked != forced_block::none)
		return { forced_move_status::blocked, blocked };
	if (current.exit != plan.exit || current.destination != plan.destination)
		return { forced_move_status::blocked, forced_block::barrier };
	return { forced_move_status::arrived };
}

void recover(const participant &person, int source)
{
	P_char ch = person.live();
	if (!ch || ch->in_room != NOWHERE)
		return;
	const int destination = valid_room(source) ? source : 0;
	if (!char_to_room(ch, destination, -2))
		logit(LOG_DEBUG, "Forced movement could not restore character %llu to room %d.",
		      static_cast<unsigned long long>(person.runtime_id), destination);
}

void separate_riders(P_char ch)
{
	if (P_char mount = get_linked_char(ch, LNK_RIDING))
	{
		unlink_char(ch, mount, LNK_RIDING);
		send_to_char("The impact parts you and your mount in a flurry of flailing limbs!\n",
			     ch);
		send_to_char("The impact parts you and your rider in a flurry of flailing limbs!\n",
			     mount);
	}
	if (P_char rider = get_linking_char(ch, LNK_RIDING))
	{
		unlink_char(rider, ch, LNK_RIDING);
		send_to_char("The impact parts you and your mount in a flurry of flailing limbs!\n",
			     rider);
		send_to_char("The impact parts you and your rider in a flurry of flailing limbs!\n",
			     ch);
	}
}

bool at_source(const participant &person, int source)
{
	P_char ch = person.live();
	return ch && ch->in_room == source;
}

bool pair_capacity(const participant &first, const participant &second, int destination)
{
	if (!IS_ROOM(destination, ROOM_PRIVATE))
		return true;
	P_char first_ch = first.live();
	P_char second_ch = second.live();
	if (!first_ch || !second_ch)
		return false;
	if (GET_LEVEL(first_ch) >= 59 && GET_LEVEL(second_ch) >= 59)
		return true;
	int present = 0;
	for (P_char ch = world[destination].people; ch; ch = ch->next_in_room)
		if (ch != first_ch && ch != second_ch)
			++present;
	return present == 0;
}
}

forced_block map_entry_barrier(P_char ch, int source, int destination)
{
	if (!ch || !valid_room(source) || !valid_room(destination) || IS_TRUSTED(ch) ||
	    !IS_MAP_ROOM(source) || !IS_MAP_ROOM(destination))
		return forced_block::none;
	if (world[destination].sector_type == SECT_MOUNTAIN)
		return forced_block::mountain;
	if (world[destination].sector_type == SECT_UNDRWLD_MOUNTAIN)
		return forced_block::cavern_wall;
	return forced_block::none;
}

forced_move_result move_forced(P_char actor, P_char victim, int direction,
			       const std::function<void()> &departure)
{
	if (!actor || !victim)
		return { forced_move_status::interrupted };
	const participant kicker{ actor, actor->runtime_id };
	const participant target{ victim, victim->runtime_id };
	const int source = victim->in_room;
	if (!at_source(kicker, source) || !at_source(target, source) || !valid_room(source))
		return { forced_move_status::interrupted };
	forced_exit plan{};
	const forced_block blocked = plan_exit(victim, source, direction, plan);
	if (blocked != forced_block::none)
		return { forced_move_status::blocked, blocked };
	char_from_room(victim);
	if (!at_source(kicker, source))
	{
		recover(kicker, source);
		recover(target, source);
		return { forced_move_status::interrupted };
	}
	forced_move_result checked = recheck(target, plan, true);
	if (checked.status != forced_move_status::arrived)
	{
		recover(target, source);
		if (!at_source(target, source))
			return { forced_move_status::interrupted };
		return checked;
	}
	separate_riders(target.live());
	departure();
	const bool entered = char_to_room(target.live(), plan.destination, direction);
	P_char moved = target.live();
	if (entered && moved && moved->in_room == plan.destination)
		return { forced_move_status::arrived };
	recover(target, source);
	return { forced_move_status::interrupted };
}

forced_move_result move_forced_pair(P_char first, P_char second, int direction,
				    const std::function<void()> &departure)
{
	if (!first || !second || first == second)
		return { forced_move_status::interrupted };
	const participant people[] = { { first, first->runtime_id },
				       { second, second->runtime_id } };
	const int source = first->in_room;
	if (!valid_room(source) || !at_source(people[0], source) || !at_source(people[1], source))
		return { forced_move_status::interrupted };
	forced_exit plans[2]{};
	for (int i = 0; i < 2; ++i)
	{
		const forced_block blocked =
			plan_exit(people[i].live(), source, direction, plans[i]);
		if (blocked != forced_block::none)
			return { forced_move_status::blocked, blocked };
	}
	// Tackle retains its existing ocean restriction.
	if (IS_OCEAN_ROOM(plans[0].destination))
		return { forced_move_status::blocked, forced_block::barrier };
	if (!pair_capacity(people[0], people[1], plans[0].destination))
		return { forced_move_status::blocked, forced_block::private_room };
	auto fail = [&](forced_move_result result)
	{
		for (const auto &person : people)
			recover(person, source);
		if (!at_source(people[0], source) || !at_source(people[1], source))
			return forced_move_result{ forced_move_status::interrupted };
		return result;
	};
	for (int i = 0; i < 2; ++i)
	{
		forced_move_result checked = recheck(people[i], plans[i], false);
		if (checked.status != forced_move_status::arrived)
			return fail(checked);
		char_from_room(people[i].live());
		checked = recheck(people[i], plans[i], true);
		if (checked.status != forced_move_status::arrived)
			return fail(checked);
	}
	for (int i = 0; i < 2; ++i)
	{
		const forced_move_result checked = recheck(people[i], plans[i], true);
		if (checked.status != forced_move_status::arrived)
			return fail(checked);
	}
	if (!pair_capacity(people[0], people[1], plans[0].destination))
		return fail({ forced_move_status::blocked, forced_block::private_room });
	for (const auto &person : people)
		separate_riders(person.live());
	departure();
	bool arrived = true;
	for (int i = 0; i < 2; ++i)
	{
		// The first arrival procedure may have moved or removed the other participant.
		if (recheck(people[i], plans[i], true).status != forced_move_status::arrived)
		{
			recover(people[i], source);
			arrived = false;
			continue;
		}
		const bool entered =
			char_to_room(people[i].live(), plans[i].destination, direction);
		P_char moved = people[i].live();
		if (!entered || !moved || moved->in_room != plans[i].destination)
		{
			recover(people[i], source);
			arrived = false;
		}
	}
	for (int i = 0; i < 2; ++i)
	{
		P_char moved = people[i].live();
		if (!moved || moved->in_room != plans[i].destination)
			arrived = false;
	}
	return { arrived ? forced_move_status::arrived : forced_move_status::interrupted };
}
