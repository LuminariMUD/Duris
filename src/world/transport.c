/****************************************************************************
 *
 *  File: transport.c                                           Part of Duris
 *  Usage: flying transport routes: service, capture, restore, and commands
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "core/utility.h"
#include "core/utils.h"
#include "world/transport.h"
#include <ctype.h>
#include <list>
#include <algorithm>
#include <chrono>
#include "persistence/persistence_checkpoint.h"
#include "world/map.h"
#include <vector>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <sys/time.h>
#include "guild/assocs.h"
#include "combat/ctf.h"
#include "world/graph.h"
#include "classes/reavers.h"
#include "magic/spells.h"

extern P_char character_list;
extern P_desc descriptor_list;
extern P_index mob_index;
extern P_index obj_index;
extern P_room world;
extern int top_of_world;
extern const char *dirs[];
extern const char *dirs2[];
extern const int rev_dir[];
extern long new_exp_table[];
extern int top_of_zone_table;
extern struct zone_data *zone;
extern struct zone_data *zone_table;
extern P_obj object_list;

#define TRANSPORT_STATE_WAITING 0
#define TRANSPORT_STATE_MOVING 1
#define TRANSPORT_STATE_RETURNING 2

#define TRANSPORT_ID(x) ((x)->only.npc->value[0])
#define TRANSPORT_STATE(x) ((x)->only.npc->value[1])
#define TRANSPORT_ORIGIN(x) (GET_BIRTHPLACE(x))
#define TRANSPORT_ROUTE(x) ((x)->only.npc->value[2])
#define TRANSPORT_STEP(x) ((x)->only.npc->value[3])

#define TRANSPORT_SIGN_VNUM 420

// Discovery bits are permanent identities, independent of catalog order or pad changes.
// Bits 0 (Scorched departure) and 12 (Snow Ogres departure) remain reserved:
// those two services offer their dedicated trips only and cannot be discovered.
struct transport_data
{
	int mob_vnum;
	int origin_vnum;
	int discovery_bit;
	const char *name;
} transports[] = { { 47015, 576577, -1, "&+LThe Isle of &NUndeath&n" },
		   { 47016, 635756, 1, "&+mQuietus Quay&N" },
		   { 47017, 588326, 2, "&+WSto&+Lrm Port&N" },
		   { 47018, 606262, 3, "&+RBloodstone Keep&N" },
		   { 47019, 514072, 4, "&+MMyrabolus&N" },
		   { 47020, 582084, 5, "&+WThe City of &+YTorrhan&N" },
		   { 47021, 543701, 6, "&+yUgta&N" },
		   { 47022, 545407, 7, "&+YVenan'Trut&N" },
		   { 47023, 563522, 8, "&+rFort &+RBoyard&N" },
		   { 47024, 622276, 9, "&+ySarmiz'Duul&N" },
		   { 47025, 519043, 10, "&+WFort &+CKhoralator&N" },
		   { 47026, 543662, 11, "&+YKimordril&N" },
		   { 47027, 619771, -1,
		     "&+GS&+gw&+Ga&+gm&+Gp &+gof &+GChief &+rBlood-&+RE&+ry&+Re&N" },
		   { 47028, 522247, 13, "&+RHel&+rgor &+WOutpost&N" },
		   { 47029, 631413, 14, "&+WClan Shatter Stone&N" },
		   { 47030, 514279, 15, "&+WBone Fort Inn&N" },
		   { 47031, 533479, 16, "&+WWinterhaven&N" },
		   { 47032, 584293, 17, "&+GShady Grove&N" },
		   { 47033, 570024, 18, "&+WTharnadia&N" },
		   { 47034, 529229, 19, "&+cFenaline&n" },
		   { 47035, 546144, 20, "&+WCanderthal Harbor&N" },
		   { 47036, 575328, 21, "&+yNizari&N" },
		   { 47037, 641295, 22, "&+gThe &+GJade &+gEmpire&N" },
		   { 47038, 634060, 23, "&+WDalvik's Dockyard&n" },
		   { 47039, 577835, 24, "&+WV&Na&+Wr&Na&+Wt&Nh&+Wo&Nr&+Wn &+LKeep&N" },
		   { 47040, 616547, 25, "&+rThur'Gurax&N" },
		   { 47041, 557220, 26, "&+GMoonshae &+YIsland&N" },
		   {} };

struct transport_route
{
	int origin_vnum = 0;
	int destination_vnum = 0;
	const char *name = nullptr;
	int cost_in_copper = 0;
	int min_level = 0;
	int discovery_bit = -1; // -1 is a dedicated Extra Destination
	vector<int> path = {};
	int service_vnum = 0;
};

static const transport_route extra_destinations[] = {
	{ 619771,
	  620606,
	  "&+LA Huge &N&+rCavern &+Lon the &N&+rBloodfist &+yMountains&n",
	  50000,
	  51,
	  -1,
	  {},
	  47027 },
	{ 576577, 579365, "&+LA Desolate Island&n", 200000, 51, -1, {}, 47015 },
	{ 588326, 637082, "&+WStorm Port Stronghold&n", 10000, 1, -1, {}, 47017 },
};

// Endpoint metadata exists before file/Redis recovery calls transport_restore().
// Only paths and live service mobs wait for the fully loaded world.
static vector<transport_route> transport_routes = []
{
	vector<transport_route> routes;
	for (const auto &origin : transports)
		if (origin.mob_vnum && origin.discovery_bit >= 0)
			for (const auto &destination : transports)
				if (destination.mob_vnum && destination.discovery_bit >= 0 &&
				    origin.mob_vnum != destination.mob_vnum)
					routes.push_back({ origin.origin_vnum,
							   destination.origin_vnum,
							   destination.name,
							   0,
							   0,
							   destination.discovery_bit,
							   {},
							   origin.mob_vnum });
	for (const auto &extra : extra_destinations)
		routes.push_back(extra);
	routes.push_back({});
	return routes;
}();

bool valid_flying_edge(int from_room, int dir)
{
	return VALID_FLYING_EDGE(from_room, dir);
}

static int transport_service(P_char mob)
{
	if (!mob || !IS_NPC(mob) || GET_RNUM(mob) < 0 || GET_MASTER(mob))
		return -1;
	for (int i = 0; transports[i].mob_vnum; ++i)
		if (mob_index[GET_RNUM(mob)].virtual_number == transports[i].mob_vnum)
			return i;
	return -1;
}

void transport_capture(P_char mob, transport_snapshot *snapshot)
{
	*snapshot = {};
	const int service = transport_service(mob);
	if (service < 0)
		return;
	snapshot->origin = transports[service].origin_vnum;
	snapshot->state = TRANSPORT_STATE(mob);
	snapshot->step = TRANSPORT_STEP(mob);
	const int route = TRANSPORT_ROUTE(mob);
	if (route >= 0 && route < static_cast<int>(std::size(transport_routes)) - 1)
		snapshot->destination = transport_routes[route].destination_vnum;
	P_char rider = GET_RIDER(mob);
	if (rider && !IS_NPC(rider))
		strlcpy(snapshot->rider, GET_NAME(rider), sizeof(snapshot->rider));
}

void transport_restore(P_char mob, const transport_snapshot &snapshot)
{
	const int service = transport_service(mob);
	if (service < 0)
		return;
	TRANSPORT_ROUTE(mob) = -1;
	TRANSPORT_STATE(mob) = TRANSPORT_STATE_WAITING;
	TRANSPORT_STEP(mob) = 0;
	mob->only.npc->transport_recovery_pending = true;
	mob->only.npc->recovered_transport_rider[0] = '\0';
	if (snapshot.origin != transports[service].origin_vnum ||
	    !memchr(snapshot.rider, '\0', sizeof(snapshot.rider)))
		return;
	for (int route = 0; transport_routes[route].origin_vnum; ++route)
		if (transport_routes[route].origin_vnum == snapshot.origin &&
		    transport_routes[route].destination_vnum == snapshot.destination)
		{
			TRANSPORT_ROUTE(mob) = route;
			TRANSPORT_STATE(mob) = snapshot.state;
			TRANSPORT_STEP(mob) = snapshot.step;
			strlcpy(mob->only.npc->recovered_transport_rider, snapshot.rider,
				sizeof(mob->only.npc->recovered_transport_rider));
			break;
		}
}

static void transport_land_at_home(P_char mob, int origin)
{
	// An occupied legacy/duplicate flight is landed with its passenger before
	// retiring the extra dragon. Extraction must never strand a linked rider.
	P_char rider = GET_RIDER(mob);
	if (rider)
	{
		unlink_char(rider, mob, LNK_RIDING);
		rider->specials.z_cord = 0;
		if (rider->in_room != origin)
		{
			char_from_room(rider);
			char_to_room(rider, origin, -1);
		}
	}
	nevent_cancel(nevent_find_next(mob, event_flying_transport_move));
	nevent_cancel(nevent_find_next(mob, event_flying_transport_return));
	if (mob->in_room != origin)
	{
		if (mob->in_room != NOWHERE)
			char_from_room(mob);
		char_to_room(mob, origin, -1);
	}
	mob->specials.z_cord = 0;
	TRANSPORT_STATE(mob) = TRANSPORT_STATE_WAITING;
	TRANSPORT_ROUTE(mob) = -1;
	TRANSPORT_STEP(mob) = 0;
}

void initialize_transport()
{
	static bool paths_initialized = false;
	const auto started = std::chrono::steady_clock::now();
	for (int service = 0; !paths_initialized && transports[service].mob_vnum; ++service)
	{
		const int origin = real_room(transports[service].origin_vnum);
		if (origin < 0)
		{
			logit(LOG_FILE, "Flight service %d has no origin room %d",
			      transports[service].mob_vnum, transports[service].origin_vnum);
			continue;
		}
		// Unit-cost flying edges need one traversal per origin, not one per ticket.
		vector<int> previous(top_of_world + 1, -1);
		vector<int> direction(top_of_world + 1, -1);
		vector<int> pending{ origin };
		bfs_clear_marks();
		BFSMARK(origin);
		for (size_t next = 0; next < pending.size(); ++next)
			for (int dir = 0; dir < NUM_EXITS; ++dir)
				if (valid_flying_edge(pending[next], dir))
				{
					const int room = TOROOM(pending[next], dir);
					BFSMARK(room);
					previous[room] = pending[next];
					direction[room] = dir;
					pending.push_back(room);
				}
		for (auto &route : transport_routes)
		{
			if (route.service_vnum != transports[service].mob_vnum)
				continue;
			const int destination = real_room(route.destination_vnum);
			if (destination < 0 || previous[destination] < 0)
			{
				logit(LOG_FILE, "No flight route from %d to %d", route.origin_vnum,
				      route.destination_vnum);
				continue;
			}
			for (int room = destination; room != origin; room = previous[room])
				route.path.push_back(direction[room]);
			std::reverse(route.path.begin(), route.path.end());
			if (route.discovery_bit >= 0)
				route.cost_in_copper = static_cast<int>(route.path.size()) * 500;
		}
		bfs_clear_marks();
	}
	if (!paths_initialized)
	{
		const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
					     std::chrono::steady_clock::now() - started)
					     .count();
		const auto available = std::count_if(transport_routes.begin(),
						     transport_routes.end(), [](const auto &route)
						     { return !route.path.empty(); });
		logit(LOG_STATUS,
		      "Flight network: %zu services, %zu routes, %ld available; paths prepared in %lld ms.",
		      std::size(transports) - 1, transport_routes.size() - 1,
		      static_cast<long>(available), static_cast<long long>(elapsed));
	}
	paths_initialized = true;

	for (int i = 0; transports[i].mob_vnum; i++)
	{
		const int origin = real_room(transports[i].origin_vnum);
		const int mobile = real_mobile(transports[i].mob_vnum);
		if (origin < 0 || mobile < 0)
			continue;
		mob_index[mobile].func.mob = flying_transport;
		P_obj sign = nullptr;
		for (P_obj object = world[origin].contents; object;)
		{
			P_obj next = object->next_content;
			if (OBJ_VNUM(object) == TRANSPORT_SIGN_VNUM)
			{
				if (!sign)
					sign = object;
				else
				{
					while (object->contains)
					{
						P_obj content = object->contains;
						obj_from_obj(content);
						obj_to_room(content, origin);
					}
					extract_obj(object);
				}
			}
			object = next;
		}
		if (!sign)
			if ((sign = read_object(TRANSPORT_SIGN_VNUM, VIRTUAL)))
				obj_to_room(sign, origin);

		std::vector<P_char> candidates;
		P_char mob = nullptr;
		for (P_char candidate = character_list; candidate; candidate = candidate->next)
			if (transport_service(candidate) == i)
			{
				candidates.push_back(candidate);
				// Reconnect only a recovered, co-located, currently unmounted player.
				if (candidate->only.npc->transport_recovery_pending &&
				    candidate->only.npc->recovered_transport_rider[0])
				{
					P_char rider = find_player_by_name(
						candidate->only.npc->recovered_transport_rider);
					if (rider && rider->in_room == candidate->in_room &&
					    !GET_MOUNT(rider))
						link_char(rider, candidate, LNK_RIDING);
				}
				if (!mob || (GET_RIDER(candidate) && !GET_RIDER(mob)) ||
				    (!GET_RIDER(mob) && !GET_RIDER(candidate) &&
				     TRANSPORT_STATE(candidate) == TRANSPORT_STATE_MOVING))
					mob = candidate;
			}
		if (!mob)
		{
			mob = read_mobile(mobile, REAL);
			if (mob)
				transport_land_at_home(mob, origin);
		}
		if (!mob)
			continue;
		for (P_char duplicate : candidates)
			if (duplicate != mob)
			{
				transport_land_at_home(duplicate, origin);
				// Retain any items that players gave an old duplicate.
				while (duplicate->carrying)
				{
					P_obj object = duplicate->carrying;
					obj_from_char(object);
					obj_to_char(object, mob);
				}
				for (int slot = 0; slot < MAX_WEAR; ++slot)
					if (duplicate->equipment[slot])
						obj_to_char(unequip_char(duplicate, slot), mob);
				extract_char(duplicate);
			}
		GET_HOME(mob) = GET_BIRTHPLACE(mob) = GET_ORIG_BIRTHPLACE(mob) =
			transports[i].origin_vnum;
		SET_BIT(mob->specials.affected_by, AFF_FLY);
		if (mob->only.npc->transport_recovery_pending)
		{
			const int route = TRANSPORT_ROUTE(mob);
			bool valid = route >= 0 &&
				     route < static_cast<int>(std::size(transport_routes)) - 1 &&
				     TRANSPORT_STATE(mob) == TRANSPORT_STATE_MOVING &&
				     TRANSPORT_STEP(mob) >= 0 &&
				     TRANSPORT_STEP(mob) <=
					     static_cast<int>(transport_routes[route].path.size());
			int expected_room = origin;
			for (int step = 0; valid && step < TRANSPORT_STEP(mob); ++step)
			{
				const int dir = transport_routes[route].path[step];
				if (expected_room < 0 || expected_room > top_of_world ||
				    !world[expected_room].dir_option[dir])
					valid = false;
				else
					expected_room = TOROOM(expected_room, dir);
			}
			if (valid && expected_room >= 0 && expected_room <= top_of_world &&
			    expected_room == mob->in_room && !transport_routes[route].path.empty())
			{
				P_char rider = GET_RIDER(mob);
				mob->specials.z_cord = 10;
				if (rider)
					rider->specials.z_cord = 10;
				if (!add_event(rider ? event_flying_transport_move :
						       event_flying_transport_return,
					       PULSE_VIOLENCE, mob, rider, 0, 0, 0, 0))
					transport_land_at_home(mob, origin);
			}
			else
				transport_land_at_home(mob, origin);
			mob->only.npc->transport_recovery_pending = false;
			mob->only.npc->recovered_transport_rider[0] = '\0';
		}
		if (candidates.size() > 1)
			logit(LOG_STATUS, "world singleton: transport=%d removed=%zu",
			      transports[i].mob_vnum, candidates.size() - 1);
	}
}

// Handles list command and shared selection for the flight service
static bool transport_waiting(P_char ch, P_char carrier)
{
	const int service = transport_service(carrier);
	return ch && !IS_NPC(ch) && service >= 0 && IS_ALIVE(carrier) && IS_AWAKE(carrier) &&
	       !IS_IMMOBILE(carrier) && !affected_by_spell(carrier, TAG_CONJURED_PET) &&
	       ch->in_room == carrier->in_room &&
	       carrier->in_room == real_room(transports[service].origin_vnum) &&
	       TRANSPORT_STATE(carrier) == TRANSPORT_STATE_WAITING && !IS_FIGHTING(carrier) &&
	       !IS_RIDING(carrier) && !GET_RIDER(carrier);
}

static vector<int> transport_choices(P_char ch, P_char carrier)
{
	vector<int> choices;
	if (!transport_waiting(ch, carrier))
		return choices;
	const int service_vnum = mob_index[GET_RNUM(carrier)].virtual_number;
	for (int i = 0; transport_routes[i].origin_vnum; ++i)
	{
		const auto &route = transport_routes[i];
		if (route.service_vnum != service_vnum || route.path.empty())
			continue;
		// Flying into Kimordril bypasses its good-side town guards.
		if (route.destination_vnum == 543662 && !IS_RACEWAR_GOOD(ch))
			continue;
		if (route.discovery_bit >= 0)
		{
			if (!(ch->only.pc->learned_flight_stops &
			      (uint64_t{ 1 } << route.discovery_bit)))
				continue;
		}
		else if (!IS_TRUSTED(ch) && GET_LEVEL(ch) < route.min_level)
			continue;
		choices.push_back(i);
	}
	std::sort(choices.begin(), choices.end(),
		  [](int left, int right)
		  {
			  const auto &a = transport_routes[left];
			  const auto &b = transport_routes[right];
			  if (a.path.size() != b.path.size())
				  return a.path.size() < b.path.size();
			  const int a_id = a.discovery_bit >= 0 ? a.discovery_bit :
								  64 + a.destination_vnum;
			  const int b_id = b.discovery_bit >= 0 ? b.discovery_bit :
								  64 + b.destination_vnum;
			  return a_id < b_id;
		  });
	return choices;
}

bool flying_transport_cmd_list(P_char ch, P_char victim, char * /*arg*/)
{
	if (!transport_waiting(ch, victim))
	{
		if (ch)
			send_to_char("This flight service is not ready to depart.\n", ch);
		return true;
	}
	const auto &stop = transports[transport_service(victim)];
	if (stop.discovery_bit >= 0 &&
	    !(ch->only.pc->learned_flight_stops & (uint64_t{ 1 } << stop.discovery_bit)))
	{
		ch->only.pc->learned_flight_stops |= uint64_t{ 1 } << stop.discovery_bit;
		mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS);
		// Set the discovery before gain_exp(): level advancement can capture a save.
		int discoveries = 0;
		for (const auto &known : transports)
			if (known.mob_vnum && known.discovery_bit >= 0 &&
			    (ch->only.pc->learned_flight_stops &
			     (uint64_t{ 1 } << known.discovery_bit)))
				++discoveries;
		send_to_char_f(ch, "&+YYou discover a flight stop: %s&n.\n", stop.name);
		if (GET_LEVEL(ch) > 0 && GET_LEVEL(ch) < MINLVLIMMORTAL)
		{
			const int cap = new_exp_table[GET_LEVEL(ch) + 1] / 3;
			const int reward =
				static_cast<int>(static_cast<int64_t>(cap) * discoveries / 27);
			if (reward > 0)
			{
				const int credited = gain_exp(ch, nullptr, reward, EXP_QUEST);
				if (credited > 0)
					send_to_char_f(ch, "&+CDiscovery EXP: &+G%d&n\n", credited);
			}
		}
	}
	send_to_char("&+WFlight Service&n\nOrdinary flights cost 0.5 platinum per room flown.\n",
		     ch);
	const auto choices = transport_choices(ch, victim);
	for (size_t i = 0; i < choices.size(); ++i)
	{
		const auto &route = transport_routes[choices[i]];
		send_to_char_f(
			ch, "%zu) %s&n - %zu rooms - %s%s\n", i + 1, route.name, route.path.size(),
			coin_stringv(route.cost_in_copper),
			route.discovery_bit < 0 ? " (Extra Destination: one-way, fixed fare)" : "");
	}
	if (choices.empty())
		send_to_char(
			"No destinations available. Discover ordinary stops by visiting their carriers and typing 'list'.\n",
			ch);
	else
		send_to_char("Type 'buy <id>', then 'give ticket <carrier>' to depart.\n", ch);
	return true;
}

void do_flights(P_char ch, char * /*argument*/, int /*cmd*/)
{
	if (!ch || IS_NPC(ch))
		return;
	int position = ch->in_room;
	if (position >= 0 && position <= top_of_world && !IS_MAP_ROOM(position))
		position = real_room(maproom_of_zone(world[position].zone));
	struct known_stop
	{
		int service;
		int distance;
	};
	vector<known_stop> known;
	for (int i = 0; transports[i].mob_vnum; ++i)
	{
		const auto &stop = transports[i];
		if (stop.discovery_bit < 0 ||
		    !(ch->only.pc->learned_flight_stops & (uint64_t{ 1 } << stop.discovery_bit)))
			continue;
		int distance = -1;
		const int destination = real_room(stop.origin_vnum);
		int dx = 0, dy = 0;
		if (position >= 0 && position <= top_of_world && destination >= 0 &&
		    calculate_map_coords(position, destination, dx, dy))
		{
			const auto &map = zone_table[world[position].zone];
			dx = std::abs(dx);
			dy = std::abs(dy);
			distance = std::min(dx, map.mapx - dx) + std::min(dy, map.mapy - dy);
		}
		known.push_back({ i, distance });
	}
	std::sort(known.begin(), known.end(),
		  [](const auto &a, const auto &b)
		  {
			  if (a.distance != b.distance)
				  return a.distance >= 0 &&
					 (b.distance < 0 || a.distance < b.distance);
			  return transports[a.service].discovery_bit <
				 transports[b.service].discovery_bit;
		  });
	send_to_char("&+WYour learned flight stops&n\n", ch);
	if (known.empty())
		send_to_char(
			"None yet. Visit an ordinary flight carrier and type 'list' to discover its stop.\n",
			ch);
	for (const auto &stop : known)
		if (stop.distance >= 0)
			send_to_char_f(ch, "%s&n - approximately %d map rooms away\n",
				       transports[stop.service].name, stop.distance);
		else
			send_to_char_f(ch, "%s&n - distance unavailable\n",
				       transports[stop.service].name);
	if (!known.empty())
		send_to_char(
			"Map estimates are not ticket quotes. Use 'list' at a carrier for routes and fares.\n",
			ch);
}

#define VNUM_OBJ_FLIGHT_PATH_TICKET 47008

// Handles buy command for flying_transport proc
bool flying_transport_cmd_buy(P_char ch, P_char victim, char *arg)
{
	if (!transport_waiting(ch, victim))
	{
		if (ch)
			send_to_char("This flight service is not ready to depart.\n", ch);
		return true;
	}
	char number[MAX_INPUT_LENGTH];
	one_argument(arg, number);
	char *end = nullptr;
	const long choice = strtol(number, &end, 10);
	const auto choices = transport_choices(ch, victim);
	if (!number[0] || !end || *end || choice < 1 ||
	    static_cast<size_t>(choice) > choices.size())
	{
		send_to_char("Invalid choice. Use 'list' to see available flights.\n", ch);
		return true;
	}
	const auto &route = transport_routes[choices[choice - 1]];
	if (GET_MONEY(ch) < route.cost_in_copper)
	{
		send_to_char("You don't have enough money!\n", ch);
		return true;
	}
	P_obj ticket = read_object(VNUM_OBJ_FLIGHT_PATH_TICKET, VIRTUAL);
	if (!ticket)
	{
		send_to_char("Unable to create a flight ticket. Please report this with 'bug'.\n",
			     ch);
		return true;
	}
	if (SUB_MONEY(ch, route.cost_in_copper, 0) < 0)
	{
		extract_obj(ticket, TRUE);
		send_to_char("Unable to pay for the flight. Please try again.\n", ch);
		return true;
	}
	ticket->value[6] = route.service_vnum;
	ticket->value[7] = route.destination_vnum;
	obj_to_char(ticket, ch);
	send_to_char("Here is your ticket! Give it to this carrier to depart.\n", ch);
	return true;
}

// Handles give command for flying_transport proc
bool flying_transport_cmd_give(P_char ch, P_char victim, char *arg)
{
	if (!ch || IS_NPC(ch))
		return false;
	char objectarg[MAX_INPUT_LENGTH], targetarg[MAX_INPUT_LENGTH];
	arg = one_argument(arg, objectarg);
	one_argument(arg, targetarg);
	if (!objectarg[0] || !targetarg[0] || get_char_room_vis(ch, targetarg) != victim)
		return false;
	P_obj ticket = get_obj_in_list_vis(ch, objectarg, ch->carrying);
	if (!ticket || OBJ_VNUM(ticket) != VNUM_OBJ_FLIGHT_PATH_TICKET)
		return false;
	if (!transport_waiting(ch, victim))
	{
		send_to_char("This flight service is not ready to depart.\n", ch);
		return true;
	}
	int route_index = -1;
	for (int choice : transport_choices(ch, victim))
	{
		const auto &route = transport_routes[choice];
		if (route.service_vnum == ticket->value[6] &&
		    route.destination_vnum == ticket->value[7])
		{
			route_index = choice;
			break;
		}
	}
	if (route_index < 0)
	{
		send_to_char("That ticket is not valid for a flight you can take from here.\n", ch);
		return true;
	}
	if (IS_FIGHTING(ch))
	{
		send_to_char("You're a bit busy fighting to be flying!\n", ch);
		return true;
	}
	if (IS_RIDING(ch))
	{
		send_to_char("You're already riding something!\n", ch);
		return true;
	}
	if (!add_event(event_flying_transport_move, PULSE_VIOLENCE, victim, ch, 0, 0, 0, 0))
	{
		send_to_char(
			"The carrier cannot depart right now. Keep your ticket and try again.\n",
			ch);
		return true;
	}
	// The route is resolved and access checked before extraction frees the ticket.
	extract_obj(ticket, TRUE);
	TRANSPORT_ROUTE(victim) = route_index;
	TRANSPORT_STEP(victim) = 0;
#if defined(CTF_MUD) && (CTF_MUD == 1)
	if (ctf_carrying_flag(ch) == CTF_PRIMARY)
	{
		send_to_char("You can't carry that with you.\r\n", ch);
		drop_ctf_flag(ch);
	}
#endif
	act("You climb up and ride $n.", FALSE, victim, 0, ch, TO_VICT);
	act("$N climbs up and rides $n.", FALSE, victim, 0, ch, TO_NOTVICT);
	link_char(ch, victim, LNK_RIDING);
	ch->specials.z_cord = 10;
	victim->specials.z_cord = 10;
	TRANSPORT_STATE(victim) = TRANSPORT_STATE_MOVING;
	act("With a mighty leap, $n launches $mself into the air.", FALSE, victim, 0, ch, TO_ROOM);
	return true;
}

int flying_transport(P_char ch, P_char victim, int cmd, char *arg)
{
	if (cmd == CMD_SET_PERIODIC)
	{
		return TRUE;
	}

	if (!IS_ALIVE(ch))
	{
		return FALSE;
	}

	// A ticket given to a busy carrier must remain with its owner, rather than
	// falling through to the ordinary give command and entering the mob's inventory.
	if (cmd == CMD_GIVE && victim && flying_transport_cmd_give(victim, ch, arg))
		return TRUE;

	if (TRANSPORT_STATE(ch) == TRANSPORT_STATE_WAITING)
	{
		if (!victim)
		{
			return FALSE;
		}

		switch (cmd)
		{
		case CMD_LIST:
			return flying_transport_cmd_list(victim, ch, arg);
		case CMD_BUY:
			return flying_transport_cmd_buy(victim, ch, arg);
		default:
			break;
		}
	}
	else if (TRANSPORT_STATE(ch) == TRANSPORT_STATE_MOVING)
	{
		if (!victim || victim != get_linking_char(ch, LNK_RIDING))
		{
			return FALSE;
		}

		if (IS_TRUSTED(victim))
		{
			return FALSE;
		}

		if (cmd == CMD_LOOK || cmd == CMD_SCORE || cmd == CMD_INVENTORY ||
		    cmd == CMD_ATTRIBUTES || cmd == CMD_NEWS || cmd == CMD_PETITION ||
		    cmd == CMD_TOGGLE || cmd == CMD_FLIGHTS)
		{
			return FALSE;
		}

		act("You can't do that, you're holding on for dear life!", FALSE, ch, 0, victim,
		    TO_VICT);
		return TRUE;
	}

	return FALSE;
}

int do_simple_move_skipping_procs(P_char ch, int exitnumb, unsigned int flags);

void event_flying_transport_move(P_char ch, P_char victim, P_obj /*obj*/, void * /*data*/)
{
	char buff[MAX_STRING_LENGTH];

	if (!ch || !victim)
		return;

	if (TRANSPORT_STATE(ch) != TRANSPORT_STATE_MOVING || ch->in_room != victim->in_room)
		return;

	const int service = transport_service(ch);
	if (service < 0)
		return;
	const int route = TRANSPORT_ROUTE(ch);
	if (route < 0 || route >= static_cast<int>(transport_routes.size()) - 1 ||
	    transport_routes[route].service_vnum != transports[service].mob_vnum ||
	    TRANSPORT_STEP(ch) < 0 ||
	    TRANSPORT_STEP(ch) > static_cast<int>(transport_routes[route].path.size()))
	{
		transport_land_at_home(ch, real_room(transports[service].origin_vnum));
		return;
	}

	int dir = BFS_ERROR;

	int path_size = transport_routes[TRANSPORT_ROUTE(ch)].path.size();

	if (path_size < 1)
	{
		dir = BFS_NO_PATH;
	}
	else if (TRANSPORT_STEP(ch) == path_size)
	{
		dir = BFS_ALREADY_THERE;
	}
	else
	{
		dir = transport_routes[TRANSPORT_ROUTE(ch)].path[TRANSPORT_STEP(ch)++];
	}

	//  dir = (int) find_first_step(ch->in_room, real_room0(TRANSPORT_DESTINATION(ch)), BFS_CAN_FLY, 0, WAGON_TYPE_FLYING, &dist);

	if (dir == BFS_ERROR || dir == BFS_NO_PATH)
	{
		act("$n looks confused for a moment, lands, and you dismount hastily.", FALSE, ch,
		    0, victim, TO_VICT);
		act("$n looks confused for a moment, lands, and $N dismounts hastily.", FALSE, ch,
		    0, victim, TO_NOTVICT);

		logit(LOG_DEBUG,
		      "BFS_ERROR or BFS_NO_PATH in event_flying_transport_move() transport.c with %s as rider and %s as transport.",
		      GET_NAME(victim), GET_NAME(ch));

		transport_land_at_home(ch, real_room(transports[service].origin_vnum));
		return;
	}
	else if (dir == BFS_ALREADY_THERE)
	{
		act("$n lands.", FALSE, ch, 0, victim, TO_ROOM);

		ch->specials.z_cord = 0;
		victim->specials.z_cord = 0;
		do_dismount(victim, 0, CMD_DISMOUNT);

		act("$n launches $mself into the air.", FALSE, ch, 0, victim, TO_ROOM);

		if (!add_event(event_flying_transport_return, (int)(PULSE_VIOLENCE / 2), ch,
			       nullptr, 0, 0, 0, 0))
			transport_land_at_home(ch, real_room(transports[service].origin_vnum));
		return;
	}

	int was_in = ch->in_room;

	if (was_in < 0 || was_in > top_of_world || dir < 0 || dir >= NUM_EXITS ||
	    !world[was_in].dir_option[dir] || TOROOM(was_in, dir) < 0 ||
	    TOROOM(was_in, dir) > top_of_world)
	{
		act("$n looks confused for a moment, lands, and you dismount hastily.", FALSE, ch,
		    0, victim, TO_VICT);
		act("$n looks confused for a moment, lands, and $N dismounts hastily.", FALSE, ch,
		    0, victim, TO_NOTVICT);

		logit(LOG_DEBUG,
		      "dir option error in event_flying_transport_move() transport.c with %s as rider and %s as transport.",
		      GET_NAME(victim), GET_NAME(ch));

		transport_land_at_home(ch, real_room(transports[service].origin_vnum));
		return;
	}

	int dest_room = TOROOM(was_in, dir);

	snprintf(buff, MAX_STRING_LENGTH, "Far above, $n flies %s.", dirs[dir]);
	act(buff, FALSE, ch, 0, victim, TO_NOTVICT | ACT_IGNORE_ZCOORD);

	snprintf(buff, MAX_STRING_LENGTH, "$n flies %s.", dirs[dir]);
	act(buff, FALSE, ch, 0, victim, TO_VICT);

	char_from_room(ch);
	ch->specials.was_in_room = was_in;
	char_to_room(ch, dest_room, dir);

	snprintf(buff, MAX_STRING_LENGTH, "Far above, $n flies in from the %s.",
		 dirs2[rev_dir[dir]]);
	act(buff, FALSE, ch, 0, victim, TO_NOTVICT | ACT_IGNORE_ZCOORD);

	if (!add_event(event_flying_transport_move, (int)(PULSE_VIOLENCE / 5), ch, victim, 0, 0, 0,
		       0))
		transport_land_at_home(ch, real_room(transports[service].origin_vnum));
}

void event_flying_transport_return(P_char ch, P_char /*victim*/, P_obj /*obj*/, void * /*data*/)
{
	char buff[MAX_STRING_LENGTH];

	if (!ch)
		return;

	if (TRANSPORT_STATE(ch) != TRANSPORT_STATE_MOVING)
		return;

	const int service = transport_service(ch);
	if (service < 0)
		return;
	const int route = TRANSPORT_ROUTE(ch);
	if (route < 0 || route >= static_cast<int>(transport_routes.size()) - 1 ||
	    transport_routes[route].service_vnum != transports[service].mob_vnum ||
	    TRANSPORT_STEP(ch) < 0 ||
	    TRANSPORT_STEP(ch) > static_cast<int>(transport_routes[route].path.size()))
	{
		transport_land_at_home(ch, real_room(transports[service].origin_vnum));
		return;
	}

	int dir = BFS_ERROR;

	int path_size = transport_routes[TRANSPORT_ROUTE(ch)].path.size();

	if (path_size < 1)
	{
		dir = BFS_NO_PATH;
	}
	else if (TRANSPORT_STEP(ch) == 0)
	{
		dir = BFS_ALREADY_THERE;
	}
	else
	{
		dir = rev_dir[transport_routes[TRANSPORT_ROUTE(ch)].path[--TRANSPORT_STEP(ch)]];
	}

	//  dir = (int) find_first_step(ch->in_room, real_room0(TRANSPORT_DESTINATION(ch)), BFS_CAN_FLY, 0, WAGON_TYPE_FLYING, &dist);

	if (dir == BFS_ERROR || dir == BFS_NO_PATH || dir == BFS_ALREADY_THERE)
	{
		if (dir == BFS_ERROR || dir == BFS_NO_PATH)
		{
			logit(LOG_DEBUG, "Invalid return flight path for %s.", GET_NAME(ch));
		}

		act("$n lands.", FALSE, ch, 0, nullptr, TO_ROOM);
		transport_land_at_home(ch, real_room(transports[service].origin_vnum));
		return;
	}

	int was_in = ch->in_room;
	if (was_in < 0 || was_in > top_of_world || dir < 0 || dir >= NUM_EXITS ||
	    !world[was_in].dir_option[dir] || TOROOM(was_in, dir) < 0 ||
	    TOROOM(was_in, dir) > top_of_world)
	{
		transport_land_at_home(ch, real_room(transports[service].origin_vnum));
		return;
	}
	int dest_room = TOROOM(was_in, dir);

	snprintf(buff, MAX_STRING_LENGTH, "Far above, $n flies %s.", dirs[dir]);
	act(buff, FALSE, ch, 0, 0, TO_ROOM | ACT_IGNORE_ZCOORD);

	char_from_room(ch);
	ch->specials.was_in_room = was_in;
	char_to_room(ch, dest_room, dir);

	snprintf(buff, MAX_STRING_LENGTH, "Far above, $n flies in from the %s.",
		 dirs2[rev_dir[dir]]);
	act(buff, FALSE, ch, 0, 0, TO_ROOM | ACT_IGNORE_ZCOORD);

	if (!add_event(event_flying_transport_return, (int)(PULSE_VIOLENCE / 8), ch, nullptr, 0, 0,
		       0, 0))
		transport_land_at_home(ch, real_room(transports[service].origin_vnum));
}
