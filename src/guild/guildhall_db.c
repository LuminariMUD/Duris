/*
 *  guildhalls_db.c
 *  Duris
 *
 *  Created by Torgal on 1/30/10.
 *
 */

#include "guild/guildhall_db.h"
#include <algorithm>
#include <new>
#include <string>
#include <utility>
#include <vector>
using namespace std;

#include "core/prototypes.h"
#include "core/utility.h"
#include "core/utils.h"
#include "guild/assocs.h"
#include "guild/guildhall.h"
#include "sql/sql.h"
#include "sql/sql_async.h"

extern vector<Guildhall *> guildhalls;
extern P_room world;

int _next_guildhall_id = -1;
int _next_guildhall_room_id = -1;
int _next_guildhall_room_vnum = -1;

/* The one room factory (declared in guildhall_db.h). There used to be two
 * copies of this switch, one per backend, and a room type added to one and not
 * the other would have loaded as a plain generic room on that backend alone. */
GuildhallRoom *make_guildhall_room(int type)
{
	switch (type)
	{
	case GH_ROOM_TYPE_ENTRANCE:
		return new EntranceRoom();
	case GH_ROOM_TYPE_INN:
		return new InnRoom();
	case GH_ROOM_TYPE_HEARTSTONE:
		return new HeartstoneRoom();
	case GH_ROOM_TYPE_PORTAL:
		return new PortalRoom();
	case GH_ROOM_TYPE_WINDOW:
		return new WindowRoom();
	case GH_ROOM_TYPE_HEAL:
		return new HealRoom();
	case GH_ROOM_TYPE_BANK:
		return new BankRoom();
	case GH_ROOM_TYPE_TOWN_PORTAL:
		return new TownPortalRoom();
	case GH_ROOM_TYPE_LIBRARY:
		return new LibraryRoom();
	case GH_ROOM_TYPE_CARGO:
		return new CargoRoom();
	case GH_ROOM_TYPE_FORGE:
		return new WorkshopRoom(GH_ROOM_TEMPLATE_FORGE, GH_FORGE_ANVIL_VNUM);
	case GH_ROOM_TYPE_LOOM:
		return new WorkshopRoom(GH_ROOM_TEMPLATE_LOOM, GH_LOOM_VNUM);
	case GH_ROOM_TYPE_JEWELLER:
		return new WorkshopRoom(GH_ROOM_TEMPLATE_JEWELLER, GH_JEWELLER_BENCH_VNUM);
	case GH_ROOM_TYPE_GUILDSTORE:
		return new WorkshopRoom(GH_ROOM_TEMPLATE_GUILDSTORE, GH_STORE_COUNTER_VNUM);
	default:
		return new GuildhallRoom();
	}
}

/* The ids come from memory: the boot load reads the highest stored ones, and -1
 * means it could not, so no new hall or room is saved over a stored one. */
int next_guildhall_id()
{
	if (_next_guildhall_id < 0)
		return -1;
	return ++_next_guildhall_id;
}

int next_guildhall_room_id()
{
	if (_next_guildhall_room_id < 0)
		return -1;
	return ++_next_guildhall_room_id;
}

// find the next available vnum in the GH rooms block.
// returns -1 if none are available
int next_guildhall_room_vnum()
{
	for (int vnum = GH_START_VNUM; vnum < GH_END_VNUM; vnum++)
	{
		// skip if vnum isn't valid room
		if (real_room(vnum) < 0)
			continue;

		// skip if vnum room is already set as guild room
		if (IS_ROOM(real_room0(vnum), ROOM_GUILD))
			continue;

		SET_BIT(world[real_room0(vnum)].room_flags, ROOM_GUILD);

		return vnum;
	}

	return -1;
}

void load_guildhalls(vector<Guildhall *> &guildhalls)
{
	if (!qry("select (select coalesce(max(id), 0) from guildhalls), "
		 "(select coalesce(max(id), 0) from guildhall_rooms)"))
	{
		logit(LOG_GUILDHALLS, "load_guildhalls(): id query failed");
		return;
	}
	MYSQL_RES *ids = mysql_store_result(DB);
	if (!ids)
	{
		logit(LOG_DEBUG, "%s: mysql_store_result failed", __func__);
		return;
	}
	MYSQL_ROW max_ids = mysql_fetch_row(ids);
	if (max_ids)
	{
		_next_guildhall_id = atoi(max_ids[0]);
		_next_guildhall_room_id = atoi(max_ids[1]);
	}
	mysql_free_result(ids);

	if (!qry("select id, assoc_id, type, outside_vnum, racewar from guildhalls order by id asc"))
	{
		logit(LOG_GUILDHALLS, "load_guildhalls(): query failed");
		return;
	}

	MYSQL_RES *res = mysql_store_result(DB);
	if (!res)
	{
		logit(LOG_DEBUG, "%s: mysql_store_result failed", __func__);
		return;
	}

	MYSQL_ROW row;
	while ((row = mysql_fetch_row(res)))
	{
		int id = atoi(row[0]);
		int assoc_id = atoi(row[1]);
		P_Guild guild = get_guild_from_id(assoc_id);

		if (!guild)
		{
			logit(LOG_GUILDHALLS,
			      "load_guildhalls(): skipping guildhall %d - guild %d not found", id,
			      assoc_id);
			continue;
		}

		Guildhall *gh = new Guildhall();
		gh->id = id;
		gh->assoc_id = assoc_id;
		gh->guild = guild;
		gh->type = atoi(row[2]);
		gh->outside_vnum = atoi(row[3]);
		gh->racewar = atoi(row[4]);

		guildhalls.push_back(gh);
	}

	mysql_free_result(res);
}

void load_guildhall_rooms(Guildhall *guildhall)
{
	if (!guildhall)
	{
		logit(LOG_GUILDHALLS, "read_guildhall_rooms(): invalid guildhall!");
		return;
	}

	if (guildhall->id <= 0)
	{
		logit(LOG_GUILDHALLS, "read_guildhall_rooms(): invalid id (%d)", guildhall->id);
		return;
	}

	if (!qry("select id, vnum, guildhall_id, name, type, value0, value1, value2, value3, value4, value5, value6, value7, exit0, exit1, exit2, exit3, exit4, exit5, exit6, exit7, exit8, exit9 from "
		 "guildhall_rooms where guildhall_id = %d order by vnum",
		 guildhall->id))
	{
		logit(LOG_GUILDHALLS, "read_guildhall_rooms(): query failed");
		return;
	}

	MYSQL_RES *res = mysql_store_result(DB);
	if (!res)
	{
		logit(LOG_DEBUG, "%s: mysql_store_result failed", __func__);
		return;
	}

	MYSQL_ROW row;
	while ((row = mysql_fetch_row(res)))
	{
		GuildhallRoom *room = make_guildhall_room(atoi(row[4]));

		if (!room)
		{
			logit(LOG_GUILDHALLS,
			      "load_guildhall_rooms(): couldn't allocate new guildhallroom!");
			mysql_free_result(res);
			return;
		}

		room->id = atoi(row[0]);
		room->vnum = atoi(row[1]);
		room->assoc_id = guildhall->assoc_id;
		room->guild = guildhall->get_assoc();
		room->name = string(row[3]);
		room->type = atoi(row[4]);

		for (int i = 0; i < GH_ROOM_NUM_VALUES; i++)
		{
			room->value[i] = atoi(row[5 + i]);
		}

		for (int i = 0; i < NUM_EXITS; i++)
		{
			room->exits[i] = atoi(row[5 + GH_ROOM_NUM_VALUES + i]);
		}

		guildhall->add_room(room);
	}

	mysql_free_result(res);
}

bool save_guildhall(Guildhall *gh)
{
	if (!gh)
	{
		logit(LOG_GUILDHALLS, "save_guildhall(): invalid gh!");
		return FALSE;
	}

	if (gh->outside_vnum < 0)
	{
		logit(LOG_GUILDHALLS, "save_guildhall(): invalid outside_vnum! (%d)",
		      gh->outside_vnum);
		return FALSE;
	}

	if (gh->id <= 0)
	{
		logit(LOG_GUILDHALLS, "save_guildhall(): invalid id! (%d)", gh->id);
		return FALSE;
	}

	sql_queue(
		"replace into guildhalls (id, assoc_id, type, outside_vnum, racewar) values (%d, %d, %d, %d, %d)",
		gh->id, gh->guild->get_id(), gh->type, gh->outside_vnum, gh->racewar);
	return TRUE;
}

bool save_guildhall_room(GuildhallRoom *room)
{
	if (!room)
	{
		logit(LOG_GUILDHALLS, "save_guildhall_room(): invalid gh!");
		return FALSE;
	}

	if (room->vnum < 0)
	{
		logit(LOG_GUILDHALLS, "save_guildhall_room(): invalid vnum! (%d)", room->vnum);
		return FALSE;
	}

	if (room->id <= 0)
	{
		logit(LOG_GUILDHALLS, "save_guildhall_room(): invalid id! (%d)", room->id);
		return FALSE;
	}

	sql_queue(
		"replace into guildhall_rooms (id, vnum, guildhall_id, name, type, value0, value1, value2, value3, value4, value5, value6, value7, exit0, exit1, exit2, exit3, exit4, exit5, exit6, "
		"exit7, exit8, exit9) values (%d, %d, %d, '%s', %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d)",
		room->id, room->vnum, room->guildhall->id, escape_str(room->name.c_str()).c_str(),
		room->type, room->value[0], room->value[1], room->value[2], room->value[3],
		room->value[4], room->value[5], room->value[6], room->value[7], room->exits[0],
		room->exits[1], room->exits[2], room->exits[3], room->exits[4], room->exits[5],
		room->exits[6], room->exits[7], room->exits[8], room->exits[9]);
	return TRUE;
}

bool delete_guildhall(Guildhall *gh)
{
	if (!gh)
	{
		logit(LOG_GUILDHALLS, "delete_guildhall(): invalid gh!");
		return FALSE;
	}

	if (gh->id <= 0)
	{
		logit(LOG_GUILDHALLS, "delete_guildhall(): invalid id! (%d)", gh->id);
		return FALSE;
	}

	sql_queue("delete from guildhalls where id = %d", gh->id);
	return TRUE;
}

bool delete_guildhall_room(GuildhallRoom *room)
{
	if (!room)
	{
		logit(LOG_GUILDHALLS, "delete_guildhall_room(): invalid room!");
		return FALSE;
	}

	if (room->id <= 0)
	{
		logit(LOG_GUILDHALLS, "delete_guildhall_room(): invalid id! (%d)", room->id);
		return FALSE;
	}

	sql_queue("delete from guildhall_rooms where id = %d", room->id);
	return TRUE;
}
