/* Physical displacement shares world barriers with walking, without its costs or posture rules. */
#include "combat/forced_movement.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "world/map.h"

extern P_room world;
extern const int top_of_world;
extern struct zone_data *zone_table;

extern void act_convert(char *, const char *, P_char, P_char, P_obj, void *, int);

namespace
{
bool can_receive_forced_departure(P_char recipient, P_char attacker)
{
	return recipient->desc && IS_AWAKE(recipient) &&
	       recipient->specials.z_cord == attacker->specials.z_cord &&
	       (IS_NPC(recipient) || !recipient->only.pc || !recipient->only.pc->ignored ||
		recipient->only.pc->ignored != attacker);
}

bool valid_room(int room)
{
	return room >= 0 && room <= top_of_world;
}

struct participant
{
	P_char pointer;
	uint64_t runtime_id;

	P_char present() const
	{
		P_char ch = find_character_by_runtime_id(runtime_id);
		return ch == pointer ? ch : nullptr;
	}

	P_char live() const
	{
		P_char ch = present();
		return IS_ALIVE(ch) ? ch : nullptr;
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
	if (IS_SET(exit->exit_info, EX_SECRET | EX_BLOCKED) ||
	    check_castle_walls(source, exit->to_room) || check_wall(source, direction))
		return forced_block::barrier;
	const forced_block terrain = map_entry_barrier(ch, source, exit->to_room);
	if (terrain != forced_block::none)
		return terrain;
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

bool group_capacity(const std::vector<participant> &people, int destination)
{
	if (!IS_ROOM(destination, ROOM_PRIVATE))
		return true;
	bool limited = false;
	for (const auto &person : people)
	{
		P_char ch = person.live();
		if (!ch)
			return false;
		limited = limited || GET_LEVEL(ch) < 59;
	}
	if (!limited)
		return true;
	int present = 0;
	for (P_char ch = world[destination].people; ch; ch = ch->next_in_room)
	{
		bool participant_present = false;
		for (const auto &person : people)
			participant_present = participant_present || ch == person.live();
		if (!participant_present)
			++present;
	}
	return present + people.size() <= 2;
}
}

std::vector<forced_departure_message> snapshot_forced_departure(P_char ch, P_char victim,
								const char *actor_text,
								const char *target_text,
								const char *room_text, P_obj object)
{
	std::vector<forced_departure_message> messages;
	for (P_char recipient = world[ch->in_room].people; recipient;
	     recipient = recipient->next_in_room)
	{
		if (!can_receive_forced_departure(recipient, ch))
			continue;
		const int type = recipient == ch     ? TO_CHAR :
				 recipient == victim ? TO_VICT :
						       TO_NOTVICT;
		const char *message = recipient == ch	  ? actor_text :
				      recipient == victim ? target_text :
							    room_text;
		if (!message)
			continue;
		char rendered[3 * MAX_STRING_LENGTH];
		act_convert(rendered, message, ch, recipient, object, victim, type);
		messages.emplace_back(recipient->runtime_id, rendered);
	}
	return messages;
}

void deliver_forced_departure(const std::vector<forced_departure_message> &messages, P_char ch,
			      P_char victim, int source, bool paired)
{
	for (const auto &message : messages)
	{
		P_char recipient = find_character_by_runtime_id(message.first);
		if (!recipient || !can_receive_forced_departure(recipient, ch))
			continue;
		const int expected_room =
			recipient == victim || (paired && recipient == ch) ? NOWHERE : source;
		if (recipient->in_room == expected_room)
			send_to_char(message.second.c_str(), recipient);
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
	const bool actor_was_alive = IS_ALIVE(actor);
	// A guardian's CMD_DEATH burst has a dead, still-registered source. A source
	// that was alive must remain alive; every moved character must always be alive.
	auto actor_at_source = [&]()
	{
		P_char ch = kicker.present();
		return ch && ch->in_room == source && (!actor_was_alive || IS_ALIVE(ch));
	};
	if (!actor_at_source() || !at_source(target, source) || !valid_room(source))
		return { forced_move_status::interrupted };
	forced_exit plan{};
	const forced_block blocked = plan_exit(victim, source, direction, plan);
	if (blocked != forced_block::none)
		return { forced_move_status::blocked, blocked };
	char_from_room(victim);
	if (!actor_at_source())
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
	if (entered && moved && moved->in_room == plan.destination && actor_at_source())
		return { forced_move_status::arrived };
	recover(target, source);
	return { forced_move_status::interrupted };
}

// A mounted charge adds its mount to the same validated departure/arrival sequence.
static forced_move_result move_forced_people(P_char first, P_char second, P_char mount,
					     int direction, const std::function<void()> &departure)
{
	if (!first || !second || first == second || mount == first || mount == second)
		return { forced_move_status::interrupted };
	std::vector<participant> people = { { first, first->runtime_id },
					    { second, second->runtime_id } };
	if (mount)
		people.push_back({ mount, mount->runtime_id });
	const int source = first->in_room;
	if (!valid_room(source))
		return { forced_move_status::interrupted };
	std::vector<forced_exit> plans(people.size());
	for (size_t i = 0; i < people.size(); ++i)
	{
		if (!at_source(people[i], source))
			return { forced_move_status::interrupted };
		const forced_block blocked =
			plan_exit(people[i].live(), source, direction, plans[i]);
		if (blocked != forced_block::none)
			return { forced_move_status::blocked, blocked };
	}
	auto riding_together = [&]()
	{
		P_char rider = people[0].live();
		P_char steed = mount ? people[2].live() : nullptr;
		return !mount ||
		       (rider && steed && GET_MOUNT(rider) == steed && GET_RIDER(steed) == rider &&
			!GET_RIDER(rider) && !GET_MOUNT(steed));
	};
	if (!riding_together())
		return { forced_move_status::interrupted };
	// Only tackle has the existing absolute ocean prohibition. Charge's caller checks entry.
	if (!mount && IS_OCEAN_ROOM(plans[0].destination))
		return { forced_move_status::blocked, forced_block::barrier };
	if (!group_capacity(people, plans[0].destination))
		return { forced_move_status::blocked, forced_block::private_room };

	bool suspended_riding = false;
	auto suspend_riding = [&]()
	{
		if (!mount)
			return;
		// A participant may have died without being extracted yet. Detach that link too.
		P_char rider = find_character_by_runtime_id(people[0].runtime_id);
		P_char steed = find_character_by_runtime_id(people[2].runtime_id);
		if (rider == people[0].pointer && steed == people[2].pointer &&
		    GET_MOUNT(rider) == steed && GET_RIDER(steed) == rider)
		{
			// char_to_room otherwise pulls companions in without their own exit checks.
			unlink_char(rider, steed, LNK_RIDING);
			suspended_riding = true;
		}
	};
	auto restore_riding = [&]()
	{
		P_char rider = people[0].live();
		P_char steed = mount ? people[2].live() : nullptr;
		if (suspended_riding && rider && steed && rider->in_room != NOWHERE &&
		    rider->in_room == steed->in_room && !GET_MOUNT(rider) && !GET_RIDER(steed))
			link_char(rider, steed, LNK_RIDING);
	};
	auto fail = [&](forced_move_result result)
	{
		suspend_riding();
		for (const auto &person : people)
			recover(person, source);
		restore_riding();
		for (const auto &person : people)
			if (!at_source(person, source))
				return forced_move_result{ forced_move_status::interrupted };
		return result;
	};
	for (size_t i = 0; i < people.size(); ++i)
	{
		forced_move_result checked = recheck(people[i], plans[i], false);
		if (checked.status != forced_move_status::arrived)
			return fail(checked);
		char_from_room(people[i].live());
		checked = recheck(people[i], plans[i], true);
		if (checked.status != forced_move_status::arrived)
			return fail(checked);
	}
	for (size_t i = 0; i < people.size(); ++i)
	{
		const forced_move_result checked = recheck(people[i], plans[i], true);
		if (checked.status != forced_move_status::arrived)
			return fail(checked);
	}
	if (!riding_together())
		return fail({ forced_move_status::interrupted });
	if (!group_capacity(people, plans[0].destination))
		return fail({ forced_move_status::blocked, forced_block::private_room });
	if (mount)
		separate_riders(people[1].live());
	else
		for (const auto &person : people)
			separate_riders(person.live());
	departure();
	bool arrived = true;
	for (size_t i = 0; i < people.size(); ++i)
	{
		// All three have left and passed their own checks. char_to_room brings the
		// mount in before the rider's arrival hook, preserving mounted script behavior.
		if (mount && i == 2)
		{
			P_char steed = people[i].live();
			if (steed && steed->in_room == plans[i].destination)
				continue;
		}
		// Earlier arrival procedures may remove another participant or seal the exit.
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
	for (size_t i = 0; i < people.size(); ++i)
	{
		P_char moved = people[i].live();
		if (!moved || moved->in_room != plans[i].destination)
			arrived = false;
	}
	if (mount)
	{
		P_char rider = people[0].live();
		P_char steed = people[2].live();
		if (!rider || !steed || rider->in_room != steed->in_room)
			suspend_riding();
		if (!riding_together())
			arrived = false;
	}
	return { arrived ? forced_move_status::arrived : forced_move_status::interrupted };
}

forced_move_result move_forced_pair(P_char first, P_char second, int direction,
				    const std::function<void()> &departure)
{
	return move_forced_people(first, second, nullptr, direction, departure);
}

forced_move_result move_forced_mounted(P_char rider, P_char victim, int direction,
				       const std::function<void()> &departure)
{
	P_char mount = rider ? GET_MOUNT(rider) : nullptr;
	if (!mount)
		return { forced_move_status::interrupted };
	return move_forced_people(rider, victim, mount, direction, departure);
}
