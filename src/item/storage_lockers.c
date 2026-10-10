/****************************************************************************
 *
 *  File: storage_lockers.c                                     Part of Duris
 *  Usage: storage lockers: chests, snapshots, access, and commands
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Zusuk                                      Date: 2026-09-23
 *
 ****************************************************************************/

#include "account/password_async.h"
#include <string>
//
// C Implementation: storage_lockers
//
// Description:
//
//
// Author: Gary Dezern <gdezern@comcast.net>, (C) 2004
//
// Copyright: See COPYING file that comes with this distribution
//
//

#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "core/utility.h"
#include "core/utils.h"
#include "item/storage_lockers.h"
#include "item/locker_identify.h"
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <algorithm>
#include <cerrno>
#include <mysql/mysqld_error.h>
#include <set>
#include <vector>
#include <sys/types.h>
#include <sys/wait.h>
#include "guild/assocs.h"
#include "combat/ctf.h"
#include "world/graph.h"
#include "combat/justice.h"
#include "core/mm.h"
#include "item/objmisc.h"
#include "account/password_hash.h"
#include "ships/ships.h"
#include "specs/specs.winterhaven.h"
#include "magic/spells.h"
#include "sql/sql.h"
#include "sql/sql_player.h"
#include "sql/sql_async.h"
#include "world/vnum.room.h"
#include "persistence/locker_async.h"
#include "persistence/persistence_mode.h"
#include "flatfile/flatfile_corpse_ownership.h"
#include "flatfile/flatfile_locker_repository.h"
#include "player/player_load_items.h"
#include "item/item_movement_transaction.h"

extern P_index obj_index;
extern P_index mob_index;
extern P_obj object_list;
extern P_room world;
extern const int top_of_world;
extern struct mm_ds *dead_mob_pool;
extern struct mm_ds *dead_pconly_pool;
extern P_char character_list;
extern struct zone_data *zone_table;

extern P_nevent get_scheduled(P_char ch, event_func func);
void event_memorize(P_char, P_char, P_obj, void *);
int is_wearing_necroplasm(P_char);
static int save_locker_char(P_char chInLocker, int bTerminal);
static void free_locker(int roomNum);
static bool check_for_artisInRoom(P_char ch, int rroom);
static void event_deferredTerminalSave(P_char chLocker, P_char ch, P_obj obj, void *data);

static long locker_elapsed_ms(const struct timespec *start, const struct timespec *end)
{
	long seconds = (long)(end->tv_sec - start->tv_sec);
	long nanoseconds = (long)(end->tv_nsec - start->tv_nsec);

	return (seconds * 1000L) + (nanoseconds / 1000000L);
}

#define LOCKERS_START 65201
#define LOCKERS_MAX 99
// for mini_mode
// #define LOCKERS_START           1285
// #define LOCKERS_MAX             2

#define LOCKERS_SECT_TYPE SECT_INSIDE
#define LOCKERS_ROOMFLAGS                                                            \
	(ROOM_NO_MOB | ROOM_NO_TRACK | ROOM_INDOORS | ROOM_SILENT | ROOM_NO_RECALL | \
	 ROOM_NO_MAGIC | ROOM_NO_TELEPORT | ROOM_LOCKER | ROOM_SAFE | ROOM_NO_HEAL | \
	 ROOM_NO_SUMMON | ROOM_NO_PSI | ROOM_NO_GATE | ROOM_BLOCKS_SIGHT)

#define LOCKERS_DOORSIGN "The door has a sign with the current occupant's name on it: "

inline StorageLocker *GetChestList(int real_room)
{
	void *raw_pointer = NULL;

	if ((world[real_room].ex_description) && (world[real_room].ex_description->next) &&
	    (world[real_room].ex_description->next->keyword))
	{
		if (sscanf(world[real_room].ex_description->next->keyword, "%p", &raw_pointer) != 1)
			raw_pointer = NULL;
	}
	return static_cast<StorageLocker *>(raw_pointer);
}

/* Called from locker_async.c after a non-terminal public snapshot is sealed:
 * put items back into chests/floor so the room is usable again while the
 * worker applies SQL. */
extern "C" void locker_async_restore_snapshot_view(P_char chUser)
{
	StorageLocker *pLocker;

	if (!chUser || chUser->in_room == NOWHERE || !IS_ROOM(chUser->in_room, ROOM_LOCKER))
		return;
	pLocker = GetChestList(chUser->in_room);
	if (!pLocker || chUser != pLocker->GetLockerUser())
		return;
	pLocker->PFileToLocker();
}

/* Optional UI refresh after async non-terminal success (items already restored). */
extern "C" void locker_async_request_resort(P_char chLocker, P_char chUser)
{
	if (!chLocker || !chUser)
		return;
	if (!get_scheduled(chLocker, StorageLocker::event_resortLocker))
		add_event(StorageLocker::event_resortLocker, 1, chLocker, chUser, NULL, 0, NULL, 0);
}

/* Move room/chests onto locker char before snapshot (re-entrant for rebuild gens). */
extern "C" int locker_async_prepare_snapshot(P_char chUser)
{
	StorageLocker *pLocker;

	if (!chUser || chUser->in_room == NOWHERE || !IS_ROOM(chUser->in_room, ROOM_LOCKER))
		return 0;
	pLocker = GetChestList(chUser->in_room);
	if (!pLocker || chUser != pLocker->GetLockerUser())
		return 0;
	return pLocker->LockerToPFile() ? 1 : 0;
}

static std::vector<P_obj> locker_snapshot_char_carrying(P_char ch)
{
	std::vector<P_obj> objs;

	if (!ch)
		return objs;

	for (P_obj obj = ch->carrying; obj; obj = obj->next_content)
		objs.push_back(obj);

	return objs;
}

static std::vector<P_obj> locker_snapshot_room_contents(int room)
{
	std::vector<P_obj> objs;

	if (room < 0 || room > top_of_world)
		return objs;

	for (P_obj obj = world[room].contents; obj; obj = obj->next_content)
		objs.push_back(obj);

	return objs;
}

static int locker_count_carried_objects(P_char ch)
{
	int count = 0;

	for (P_obj obj = ch ? ch->carrying : NULL; obj; obj = obj->next_content)
		++count;

	return count;
}

static int locker_count_room_objects(int room)
{
	int count = 0;

	if (room < 0 || room > top_of_world)
		return 0;

	for (P_obj obj = world[room].contents; obj; obj = obj->next_content)
		++count;

	return count;
}

static const char *locker_room_name(int room)
{
	if (room < 0 || room > top_of_world || !world[room].name)
		return "<invalid-room>";

	return world[room].name;
}

static void locker_log_save_failure(StorageLocker *pLocker, P_char ch, P_char chLocker,
				    const char *phase, const char *detail)
{
	const int locker_room = pLocker ? pLocker->GetRealRoom() : NOWHERE;
	char msg[MAX_STRING_LENGTH];
	snprintf(
		msg, sizeof(msg),
		"Locker save failed (%s): user=%s user_room=%d locker_char=%s locker_char_room=%d locker_id=%d locker_room=%d(%s) locker_items=%d room_items=%d carried=%d was_in_room=%d detail=%s",
		phase, ch ? GET_NAME(ch) : "<null>", ch ? ch->in_room : NOWHERE,
		chLocker ? GET_NAME(chLocker) : "<null>", chLocker ? chLocker->in_room : NOWHERE,
		pLocker ? pLocker->GetLockerId() : -1, locker_room, locker_room_name(locker_room),
		pLocker ? pLocker->m_itemCount : -1, locker_count_room_objects(locker_room),
		locker_count_carried_objects(chLocker),
		(ch && ch->specials.was_in_room != NOWHERE) ? ch->specials.was_in_room : -1,
		detail ? detail : "<none>");
	logit(LOG_OBJ, "%s", msg);
	logit(LOG_FILE, "%s", msg);
}

bool locker_eq_type_fits_for_storage(::byte eqType, P_obj obj)
{
	if (!obj || obj->type != eqType)
		return false;

	// Containers and corpses are handled by the unsorted chest rejection
	// and remain on the locker room floor.  For type-specific chests, a
	// matching type is sufficient - the save/load path preserves nested
	// contents for containers of the correct type.
	return true;
}

static int locker_exit_room(P_char ch, int fallback_room)
{
	if (ch && (ch->in_room != NOWHERE) && world[ch->in_room].dir_option[0] &&
	    (world[ch->in_room].dir_option[0]->to_room != NOWHERE))
		return world[ch->in_room].dir_option[0]->to_room;

	if (ch && (ch->specials.was_in_room != NOWHERE))
	{
		int was_in = real_room(ch->specials.was_in_room);
		if (was_in != NOWHERE)
			return was_in;
	}

	if (ch && GET_HOME(ch))
	{
		int home = real_room(GET_HOME(ch));
		if (home != NOWHERE)
			return home;
	}

	if (ch && GET_BIRTHPLACE(ch))
	{
		int birth = real_room(GET_BIRTHPLACE(ch));
		if (birth != NOWHERE)
			return birth;
	}

	if (ch)
	{
		logit(LOG_DEBUG,
		      "locker_exit_room: fallback to locker room for %s in_room=%d fallback_room=%d was_in=%d home=%d birth=%d",
		      GET_NAME(ch), ch->in_room, fallback_room, ch->specials.was_in_room,
		      GET_HOME(ch), GET_BIRTHPLACE(ch));
	}

	return fallback_room;
}

static bool esc_locker_name_matches_player(const char *esc_locker_name, P_char ch)
{
	char name[MAX_INPUT_LENGTH];

	if (!esc_locker_name || !ch)
		return false;

	int name_len = snprintf(name, sizeof(name), "%s", esc_locker_name);
	if (name_len < 0 || (size_t)name_len >= sizeof(name))
		return false;
	if (strrchr(name, '.'))
		*(strrchr(name, '.')) = '\0';

	if (strstr(name, "account.") == name)
	{
		const char *player_acct = get_account_name_safe(ch);
		char locker_acct[MAX_INPUT_LENGTH];
		char *src = name + 8;
		char *dot = strchr(src, '.');
		if (dot)
		{
			int len = dot - src;
			if (len <= 0)
				len = 0;
			if (len > MAX_INPUT_LENGTH)
				len = MAX_INPUT_LENGTH - 1;
			memcpy(locker_acct, src, len);
			locker_acct[len] = '\0';
			int locker_racewar = atoi(dot + 1);
			return (player_acct && !str_cmp(locker_acct, player_acct) &&
				locker_racewar == GET_RACEWAR(ch));
		}
		return false;
	}

	return !str_cmp(name, GET_NAME(ch));
}

static void locker_eject_to_exit(P_char ch, int room)
{
	if (!ch)
		return;

	int exit_room = locker_exit_room(ch, room);
	logit(LOG_OBJ, "Locker eject: user=%s from_room=%d(%s) exit_room=%d(%s) was_in_room=%d",
	      GET_NAME(ch), ch->in_room,
	      (ch->in_room >= 0 && ch->in_room <= top_of_world && world[ch->in_room].name) ?
		      world[ch->in_room].name :
		      "<invalid-room>",
	      exit_room, locker_room_name(exit_room),
	      (ch->specials.was_in_room != NOWHERE) ? ch->specials.was_in_room : -1);

	char_from_room(ch);
	char_to_room(ch, exit_room, 0);
}

static bool locker_handle_leave(P_char ch, StorageLocker *pLocker, int room, int troom)
{
	P_char tmpChar = NULL;
	P_char nextChar = NULL;

	if (!ch || !pLocker || (ch != pLocker->GetLockerUser()))
		return true;
	if (item_movement_transaction_player_busy(ch))
	{
		send_to_char(
			"Your last item movement is still being secured. Please wait before leaving.\r\n",
			ch);
		return false;
	}

	/* Move items from room/chests to the locker character for saving. */
	P_char chLocker = pLocker->GetLockerChar();
	if (!chLocker)
	{
		logit(LOG_OBJ, "Locker leave: no locker char for %s; refusing departure",
		      GET_NAME(ch));
		persistence_alert(AVATAR, "locker", "leave_prepare", "none", "none",
				  "terminal_not_durable", "leave_vetoed=1");
		send_to_char(
			"&+RYour locker could not be prepared for saving, so you remain inside. Staff have been notified.&n\r\n",
			ch);
		return false;
	}
	else if (!pLocker->LockerToPFile())
	{
		/* The snapshot is not coherent, so neither a terminal save nor
		 * free_locker() is safe. Keep the player, locker character, chests,
		 * and room live for a later retry. */
		locker_log_save_failure(
			pLocker, ch, chLocker, "leave-locker-to-pfile",
			"LockerToPFile failed during leave; departure vetoed with live state retained");
		persistence_alert(AVATAR, "locker", "leave_prepare", "none", "none",
				  "terminal_not_durable", "leave_vetoed=1");
		send_to_char(
			"&+RYour locker could not be saved, so you remain inside. Staff have been notified.&n\r\n",
			ch);
		return false;
	}
	else
	{
		/* Items are now on the locker character.  Schedule async terminal
		 * save so the player leaves without waiting for SQL serialization.
		 * Re-entry is blocked via locker_async_name_busy + locker char presence
		 * until the worker completes and extracts the locker char. */
		if (!locker_async_mark_dirty(chLocker, ch, 1, "leave-terminal"))
		{
			/* the async writer is full: ask it again shortly */
			if (!get_scheduled(chLocker, event_deferredTerminalSave))
				add_event(event_deferredTerminalSave, 1, chLocker, ch, NULL, 0,
					  NULL, 0);
			logit(LOG_DEBUG,
			      "Locker leave: deferred terminal save (async unavailable) for %s locker_char=%s",
			      GET_NAME(ch), GET_NAME(chLocker));
		}
		else
		{
			logit(LOG_DEBUG,
			      "Locker leave: async terminal save marked for %s locker_char=%s locker_id=%d room=%d(%s)",
			      GET_NAME(ch), GET_NAME(chLocker), pLocker->GetLockerId(), room,
			      locker_room_name(room));
		}
	}

	/* Persistence preparation succeeded. It is now safe to eject every other
	 * occupant before the room is released. */
	tmpChar = world[ch->in_room].people;
	while (tmpChar)
	{
		nextChar = tmpChar->next_in_room;
		if (tmpChar != ch)
		{
			send_to_char(
				"You feel yourself being (ungracefully) ejected from the locker.\r\n",
				tmpChar);
			char_from_room(tmpChar);
			char_to_room(tmpChar, locker_exit_room(ch, room), 0);
		}
		tmpChar = nextChar;
	}

	/* throw any corpses out as well */
	P_obj next_obj;

	for (P_obj tmp_obj = world[ch->in_room].contents; tmp_obj; tmp_obj = next_obj)
	{
		next_obj = tmp_obj->next_content;
		if (tmp_obj->type == ITEM_CORPSE)
		{
			char buf[MAX_STRING_LENGTH];

			snprintf(buf, MAX_STRING_LENGTH, "%s&n flies out in front of you!\r\n",
				 tmp_obj->short_description);
			send_to_char(buf, ch);
			obj_from_room(tmp_obj);
			obj_to_room(tmp_obj, locker_exit_room(ch, room));
		}
	}
	send_to_char(
		"As you leave, you see the &+YSLSC&n member applying magic locks to the door...\r\n",
		ch);

	troom = locker_exit_room(ch, room);
	if (IS_TOWN_RAIDED(ch))
	{
		if (world[ch->in_room].dir_option[0])
			world[ch->in_room].dir_option[0]->to_room = troom;
		else
			logit(LOG_WIZ, "locker_exit_room missing while saving %s in room %d",
			      GET_NAME(ch), ch->in_room);
	}

	free_locker(room);
	return true;
}

static int locker_handle_save_hook(P_char ch, int troom)
{
	int exit_room = locker_exit_room(ch, troom);
	ch->specials.was_in_room = (exit_room != NOWHERE) ? world[exit_room].number :
							    world[troom].number;

	// Return artifacts to the player's inventory BEFORE the player save so
	// they are included in the saved record.  This was originally in the
	// post-save hook (-81), which meant a crash between saves could lose
	// or desynchronize the artifact.
	if (ch->in_room != NOWHERE && ch->in_room >= 0 && ch->in_room <= top_of_world)
	{
		if (check_for_artisInRoom(ch, ch->in_room))
		{
			StorageLocker *pLocker = GetChestList(ch->in_room);
			logit(LOG_OBJ,
			      "Locker pre-save returned artifact(s) for %s (room=%d(%s) locker_id=%d locker_room=%d(%s))",
			      GET_NAME(ch), ch->in_room, locker_room_name(ch->in_room),
			      pLocker ? pLocker->GetLockerId() : -1,
			      pLocker ? pLocker->GetRealRoom() : NOWHERE,
			      pLocker ? locker_room_name(pLocker->GetRealRoom()) :
					"<invalid-room>");
			send_to_char(
				"&+YNOTICE:&n An artifact was returned to your hands before locker save.\\r\\n",
				ch);
		}
	}

	return troom;
}

static void locker_handle_postsave(P_char ch, StorageLocker *pLocker, int room)
{
	if (!ch || !pLocker || (ch != pLocker->GetLockerUser()))
		return;

	/* if so, save the locker too */
	if (!save_locker_char(ch, FALSE))
	{
		/* wasn't able to save the locker char.  This is bad, but can happen
		   if the locker char was purged by a god, or idle rented.  the only way
		   to deal with it is to eject the player from the locker */
		locker_log_save_failure(
			pLocker, ch, pLocker->GetLockerChar(), "postsave-eject",
			"locker save returned false; ejecting occupant from locker");
		locker_eject_to_exit(ch, room);
	}
	else
	{
		/* anti-idle code.  only let people idle in their own locker */
		bool idle_is_owner =
			esc_locker_name_matches_player(GET_NAME(pLocker->GetLockerChar()), ch);

		if (!idle_is_owner && (ch->specials.timer > 3))
		{
			logit(LOG_OBJ,
			      "Locker anti-idle eject: user=%s locker_char=%s locker_id=%d room=%d(%s) timer=%d",
			      GET_NAME(ch), GET_NAME(pLocker->GetLockerChar()),
			      pLocker->GetLockerId(), pLocker->GetRealRoom(),
			      locker_room_name(pLocker->GetRealRoom()), ch->specials.timer);
			send_to_char("You can only sit idle in your own locker...  GET OUT!\r\n",
				     ch);
			locker_eject_to_exit(ch, room);
		}
	}
}

static StorageLocker *locker_current(P_char ch)
{
	if (!ch)
		return NULL;

	return GetChestList(ch->in_room);
}

static StorageLocker *locker_current_or_error(P_char ch, const char *message)
{
	StorageLocker *pLocker = locker_current(ch);

	if (!pLocker && ch && message)
		send_to_char(message, ch);

	return pLocker;
}

static bool locker_is_guild_member(StorageLocker *pLocker, P_char ch)
{
	if (!pLocker || !ch)
		return false;

	P_char locker_char = pLocker->GetLockerChar();
	if (!locker_char || !GET_NAME(locker_char))
		return false;

	// Guild lockers are named "guild.<id>.locker"
	if (strncmp(GET_NAME(locker_char), "guild.", 6) != 0)
		return false;

	int guild_id = atoi(GET_NAME(locker_char) + 6);
	if (guild_id <= 0)
		return false;

	// Check if the player is a member of this guild
	if (!GET_ASSOC(ch))
		return false;

	return GET_ASSOC(ch)->get_id() == static_cast<unsigned int>(guild_id);
}

static bool locker_require_owner(StorageLocker *pLocker, P_char ch, const char *message)
{
	if (!pLocker || !ch)
		return false;

	bool is_staff = (GET_LEVEL(ch) >= OVERLORD) || god_check(ch->player.name);
	P_char locker_char = pLocker->GetLockerChar();
	bool is_owner = locker_char && esc_locker_name_matches_player(GET_NAME(locker_char), ch);
	bool is_guild_member = locker_is_guild_member(pLocker, ch);
	if (is_staff || is_owner || is_guild_member)
		return true;

	if (message)
		send_to_char(message, ch);

	return false;
}

static P_char locker_char_or_error(StorageLocker *pLocker, P_char ch, const char *message)
{
	if (!pLocker)
		return NULL;

	P_char chLocker = pLocker->GetLockerChar();
	if (!chLocker && ch && message)
		send_to_char(message, ch);

	return chLocker;
}

const unsigned LockerChest::m_chestVnum = 173;

StorageLocker::StorageLocker(int rroom, P_char chLocker, P_char chUser)
	: m_itemCount(0)
	, m_pChestList(NULL)
	, m_realRoom(rroom)
	, m_chLocker(chLocker)
	, m_chUser(chUser)
	, m_bIValue(false)
	, m_currentChestId(0)
	, m_lockerId(0)
	, m_publicChestId(0)
{
	if (!world[rroom].ex_description)
	{
		CREATE(world[rroom].ex_description, extra_descr_data, 1, MEM_TAG_EXDESCD);
		CREATE(world[rroom].ex_description->next, extra_descr_data, 1, MEM_TAG_EXDESCD)
	}
	char buf[500];

	strcpy(buf, GET_NAME(chLocker));
	world[rroom].ex_description->keyword = str_dup(buf);
	world[rroom].ex_description->description = NULL;
	snprintf(buf, 500, "%p", (void *)this);
	world[rroom].ex_description->next->keyword = str_dup(buf);
	world[rroom].ex_description->next->description = NULL;
	world[rroom].ex_description->next->next = NULL;
};

StorageLocker::~StorageLocker(void)
{
	NukeLockerChests();

	// NukeLockerChests preserves private chest wrappers; delete them now
	// since the StorageLocker is being destroyed.
	LockerChest *p = m_pChestList;
	while (p)
	{
		LockerChest *next = p->m_pNextInChain;
		delete p;
		p = next;
	}
	m_pChestList = NULL;

	if ((world[m_realRoom].ex_description) && (world[m_realRoom].ex_description->keyword))
	{
		str_free(world[m_realRoom].ex_description->keyword);
		world[m_realRoom].ex_description->keyword = NULL;
	}
	if ((world[m_realRoom].ex_description) && (world[m_realRoom].ex_description->next) &&
	    (world[m_realRoom].ex_description->next->keyword))
	{
		str_free(world[m_realRoom].ex_description->next->keyword);
		world[m_realRoom].ex_description->next->keyword = NULL;
	}

	//  free_char(m_chLocker);
}

void StorageLocker::NukeLockerChests(void)
{
	LockerChest *p;
	LockerChest *privateChests = NULL;
	LockerChest *lastPrivate = NULL;

	// separate private chests from the list - don't delete them
	while (m_pChestList)
	{
		p = m_pChestList;
		m_pChestList = p->m_pNextInChain;
		p->m_pNextInChain = NULL;

		if (p->IsPrivateChest())
		{
			if (!privateChests)
				privateChests = p;
			else
				lastPrivate->m_pNextInChain = p;
			lastPrivate = p;
		}
		else
		{
			delete p;
		}
	}

	// restore private chests to the list
	m_pChestList = privateChests;
}

bool StorageLocker::PutInProperChest(P_obj obj)
{
	// assumes 'obj' is located in nowhere
	LockerChest *p = m_pChestList;

	while (p)
	{
		if (p->ItemFits(obj))
		{
			obj_to_obj(obj, p->GetChestObj());
			return true;
		}
		p = p->m_pNextInChain;
	}
	return false;
};

LockerChest *StorageLocker::AddLockerChest(LockerChest *p)
{
	if (p)
	{
		// update:  need to add it to the END of the list!
		if (!m_pChestList)
			m_pChestList = p;
		else
		{
			LockerChest *next = m_pChestList;

			while (next->m_pNextInChain)
				next = next->m_pNextInChain;
			next->m_pNextInChain = p;
		}
	}
	return p;
}

LockerChest *StorageLocker::FindChestForObject(P_obj obj)
{
	if (!obj)
		return NULL;

	for (LockerChest *p = m_pChestList; p; p = p->m_pNextInChain)
	{
		if (p->GetChestObj() == obj)
			return p;
	}

	return NULL;
}

PrivateChest *StorageLocker::FindPrivateChest(const char *name)
{
	for (LockerChest *p = m_pChestList; p; p = p->m_pNextInChain)
		if (p->IsPrivateChest() &&
		    !strcasecmp(static_cast<PrivateChest *>(p)->GetName(), name))
			return static_cast<PrivateChest *>(p);
	return NULL;
}

std::vector<PrivateChest *> StorageLocker::GetPrivateChests(void)
{
	std::vector<PrivateChest *> chests;
	for (LockerChest *p = m_pChestList; p; p = p->m_pNextInChain)
		if (p->IsPrivateChest())
			chests.push_back(static_cast<PrivateChest *>(p));
	return chests;
}

void StorageLocker::RemovePrivateChest(PrivateChest *chest)
{
	for (LockerChest **link = &m_pChestList; *link; link = &(*link)->m_pNextInChain)
		if (*link == chest)
		{
			*link = chest->m_pNextInChain;
			delete chest;
			return;
		}
}

#define LOCKER_HELP_NONE 0
#define LOCKER_HELP_SHORT BIT_1
#define LOCKER_HELP_LONG BIT_2
#define LOCKER_HELP_ALL_SHORT BIT_3
#define LOCKER_HELP_ALL_LONG BIT_4
bool StorageLocker::MakeChests(P_char ch, char *args)
{
	bool bRet = true;
	bool bIsCustomChest = false;
	int helpMode = LOCKER_HELP_NONE;
	char GBuf1[MAX_STRING_LENGTH];
	char GBuf2[MAX_STRING_LENGTH], *tmp;

	GBuf1[0] = GBuf2[0] = '\0';

	// Change held to hold (every instance but first).
	while ((tmp = strstr(args, " held")))
	{
		tmp[2] = 'o';
	}
	if (!strncmp(args, "held ", 5))
	{
		args[1] = 'o';
	}

	args = one_argument(args, GBuf1);
	while (*args == ' ')
	{
		args++;
	}
	if (('\0' == GBuf1[0]) || !str_cmp(GBuf1, "help") || !str_cmp(GBuf1, "?"))
	{
		args = one_argument(args, GBuf1);
		if (!str_cmp(GBuf1, "all"))
		{
			args = one_argument(args, GBuf1);
			if (!str_cmp(GBuf1, "long"))
			{
				helpMode = LOCKER_HELP_ALL_LONG;
			}
			else
			{
				helpMode = LOCKER_HELP_ALL_SHORT;
			}
			GBuf1[0] = '\0';
			args = GBuf1;
		}
		else if (!str_cmp(GBuf1, "long"))
		{
			helpMode = LOCKER_HELP_LONG;
			args = one_argument(args, GBuf1);
			if (GBuf1[0] == '\0' || !str_cmp(GBuf1, "all"))
			{
				helpMode = LOCKER_HELP_ALL_LONG;
				GBuf1[0] = '\0';
				args = GBuf1;
			}
		}
		else
		{
			if (!str_cmp(GBuf1, "short"))
			{
				args = one_argument(args, GBuf1);
				if (GBuf1[0] == '\0' || !str_cmp(GBuf1, "all"))
				{
					helpMode = LOCKER_HELP_ALL_SHORT;
					GBuf1[0] = '\0';
					args = GBuf1;
				}
				else
				{
					helpMode = LOCKER_HELP_SHORT;
				}
			}
			else if (GBuf1[0] == '\0')
			{
				helpMode = LOCKER_HELP_ALL_SHORT;
			}
			// equip sort ? {type}*
			else
			{
				helpMode = LOCKER_HELP_LONG;
			}
		}
	}
	else
	{
		if (!str_cmp("none", GBuf1))
			strcpy(GBuf1, "unsorted");

		// check for 'custom' chest type next...
		if (!str_cmp("custom", GBuf1))
		{
			// deal with it...
			bIsCustomChest = true;
			args = one_argument(args, GBuf1);
			if (('\0' == GBuf1[0]))
				helpMode = LOCKER_HELP_ALL_SHORT;
		}
		// eq sort custom might set help mode... and don't want to nuke existing chests on help mode
		if (helpMode == LOCKER_HELP_NONE)
			NukeLockerChests();
	}
	if (helpMode != LOCKER_HELP_NONE)
	{
		bRet = false;
		strcpy(GBuf2,
		       "Usage:  \r\n"
		       "  For help:              equip sort {help|?} [short|long] [all|type1] [type2] [type3] ...\r\n"
		       "  To Remove all sorting: equip sort none\r\n"
		       "  Multiple chests:       equip sort type1 [type2] [type3] ...\r\n"
		       "  A custom sort chest:   equip sort custom type1 type2 [type3] ...\r\n"
		       "\r\nValid types are:");
		// Long mode -> newline, short mode = 3 spaces (2 replaced with ".\n" if no valid args in reg short mode).
		strcat(GBuf2, (helpMode == LOCKER_HELP_LONG || helpMode == LOCKER_HELP_ALL_LONG) ?
				      "\r\n" :
				      "   ");
	}

	// hold and attach are special case chests.. being that damn near every item in the
	// game is holdable, and quite a few are attachable, force them to always be created
	// last...  Do this by setting a couple bools for them...
	bool bMakeHoldable = false;
	bool bMakeAttachable = false;

	const char *chestKeyword;
	const char *chestDesc;

#define IF_ISLOCKERTYPE(keyword, desc, action)                                                     \
	chestKeyword = (keyword);                                                                  \
	chestDesc = (desc);                                                                        \
	if (helpMode == LOCKER_HELP_ALL_LONG)                                                      \
	{                                                                                          \
		bFound = true;                                                                     \
		checked_snprintf(GBuf2 + strlen(GBuf2), MAX_STRING_LENGTH - strlen(GBuf2),         \
				 "&+C%15s&n   &+w(items %s)\r\n", keyword, desc);                  \
	}                                                                                          \
	else if (helpMode == LOCKER_HELP_ALL_SHORT)                                                \
	{                                                                                          \
		bFound = true;                                                                     \
		checked_snprintf(GBuf2 + strlen(GBuf2), MAX_STRING_LENGTH - strlen(GBuf2),         \
				 "&+C%s&n, ", keyword);                                            \
	}                                                                                          \
	else if (!str_cmp(keyword, GBuf1))                                                         \
	{                                                                                          \
		if (isname(keyword, args))                                                         \
			bFound = true;                                                             \
		else if (helpMode == LOCKER_HELP_LONG)                                             \
		{                                                                                  \
			bFound = true;                                                             \
			checked_snprintf(GBuf2 + strlen(GBuf2), MAX_STRING_LENGTH - strlen(GBuf2), \
					 "&+C%15s&n   &+w(items %s)\r\n", keyword, desc);          \
		}                                                                                  \
		else if (helpMode == LOCKER_HELP_SHORT)                                            \
		{                                                                                  \
			bFound = true;                                                             \
			checked_snprintf(GBuf2 + strlen(GBuf2), MAX_STRING_LENGTH - strlen(GBuf2), \
					 "&+C%s&n, ", keyword);                                    \
		}                                                                                  \
		else                                                                               \
			action;                                                                    \
	}

	if (helpMode != LOCKER_HELP_NONE || ('\0' != GBuf1[0]))
	{
		bool bFound;
		LockerChest *p;
		do
		{
			bFound = FALSE;
			p = NULL;

			// parse 'GBuf1'
			IF_ISLOCKERTYPE("hold", "that you can hold", bFound = bMakeHoldable = true);
			IF_ISLOCKERTYPE("attach", "attached to belt",
					bFound = bMakeAttachable = true);
			IF_ISLOCKERTYPE("ivalue", "in chest sorted by item value",
					bFound = m_bIValue = true);

			IF_ISLOCKERTYPE("horns", "worn on body",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_HORN, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("nose", "worn on nose",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_NOSE, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("tail", "worn on tail",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_TAIL, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("horse", "worn on a horses body",
					p = AddLockerChest(new EqSlotChest(
						ITEM_HORSE_BODY, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("spider", "worn on a spider body",
					p = AddLockerChest(new EqSlotChest(
						ITEM_SPIDER_BODY, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("back", "worn on back",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_BACK, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("badge", "worn as a badge",
					p = AddLockerChest(new EqSlotChest(
						ITEM_GUILD_INSIGNIA, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("quiver", "worn as a quiver",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_QUIVER, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("ear", "worn on or in ear",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_EARRING, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("face", "worn on face",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_FACE, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("eyes", "worn on or over eyes",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_EYES, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("wield", "used as a weapon or wielded",
					p = AddLockerChest(new EqSlotChest(ITEM_WIELD, chestKeyword,
									   chestDesc)));
			IF_ISLOCKERTYPE("wrist", "worn around wrist",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_WRIST, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("waist", "worn about waist",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_WAIST, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("about", "worn about body",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_ABOUT, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("shield", "worn as a shield",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_SHIELD, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("arms", "worn on arms",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_ARMS, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("hands", "worn on hands",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_HANDS, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("feet", "worn on feet",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_FEET, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("legs", "worn on legs",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_LEGS, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("head", "worn on head",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_HEAD, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("body", "worn on body",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_BODY, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("neck", "worn around neck",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_NECK, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("finger", "worn on finger",
					p = AddLockerChest(new EqSlotChest(
						ITEM_WEAR_FINGER, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("warrior", "usable by a warrior",
					p = AddLockerChest(new EqWearChest(
						CLASS_WARRIOR, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("ranger", "usable by a ranger",
					p = AddLockerChest(new EqWearChest(
						CLASS_RANGER, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("psionicist", "usable by a psionicist",
					p = AddLockerChest(new EqWearChest(
						CLASS_PSIONICIST, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("paladin", "usable by a paladin",
					p = AddLockerChest(new EqWearChest(
						CLASS_PALADIN, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("antipaladin", "usable by an antipaladin",
					p = AddLockerChest(new EqWearChest(
						CLASS_ANTIPALADIN, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("cleric", "usable by a cleric",
					p = AddLockerChest(new EqWearChest(
						CLASS_CLERIC, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("monk", "usable by a monk",
					p = AddLockerChest(new EqWearChest(CLASS_MONK, chestKeyword,
									   chestDesc)));
			IF_ISLOCKERTYPE("druid", "usable by a druid",
					p = AddLockerChest(new EqWearChest(
						CLASS_DRUID, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("shaman", "usable by a shaman",
					p = AddLockerChest(new EqWearChest(
						CLASS_SHAMAN, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("sorcerer", "usable by a sorcerer",
					p = AddLockerChest(new EqWearChest(
						CLASS_SORCERER, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("necromancer", "usable by a necromancer",
					p = AddLockerChest(new EqWearChest(
						CLASS_NECROMANCER, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("conjurer", "usable by a conjurer",
					p = AddLockerChest(new EqWearChest(
						CLASS_CONJURER, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("rogue", "usable by a rogue",
					p = AddLockerChest(new EqWearChest(
						CLASS_ROGUE, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("summoner", "usable by a summoner",
					p = AddLockerChest(new EqWearChest(
						CLASS_SUMMONER, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("assassin", "usable by an assassin",
					p = AddLockerChest(new EqWearChest(
						CLASS_ASSASSIN, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("mercenary", "usable by a mercenary",
					p = AddLockerChest(new EqWearChest(
						CLASS_MERCENARY, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("bard", "usable by a bard",
					p = AddLockerChest(new EqWearChest(CLASS_BARD, chestKeyword,
									   chestDesc)));
			IF_ISLOCKERTYPE("thief", "usable by a thief",
					p = AddLockerChest(new EqWearChest(
						CLASS_THIEF, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("alchemist", "usable by an alchemist",
					p = AddLockerChest(new EqWearChest(
						CLASS_ALCHEMIST, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("berserker", "usable by a berserker",
					p = AddLockerChest(new EqWearChest(
						CLASS_BERSERKER, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("reaver", "usable by a reaver",
					p = AddLockerChest(new EqWearChest(
						CLASS_REAVER, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("illusionist", "usable by an illusionist",
					p = AddLockerChest(new EqWearChest(
						CLASS_ILLUSIONIST, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("dreadlord", "usable by a dreadlord",
					p = AddLockerChest(new EqWearChest(
						CLASS_DREADLORD, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("ethermancer", "usable by an ethermancer",
					p = AddLockerChest(new EqWearChest(
						CLASS_ETHERMANCER, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("blighter", "usable by a blighter",
					p = AddLockerChest(new EqWearChest(
						CLASS_BLIGHTER, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("totems", "used as totems",
					p = AddLockerChest(new EqTypeChest(ITEM_TOTEM, chestKeyword,
									   chestDesc)));
			IF_ISLOCKERTYPE("instruments", "playable as bard instruments",
					p = AddLockerChest(new EqTypeChest(
						ITEM_INSTRUMENT, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("potions", "quaffable or used as potions",
					p = AddLockerChest(new EqTypeChest(
						ITEM_POTION, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("spellbooks", "used as spellbooks",
					p = AddLockerChest(new EqTypeChest(
						ITEM_SPELLBOOK, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("scrolls", "used as scrolls",
					p = AddLockerChest(new EqTypeChest(
						ITEM_SCROLL, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("containers", "that are also containers",
					p = AddLockerChest(new EqTypeChest(
						ITEM_CONTAINER, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("hitpoints", "that affect hitpoints",
					p = AddLockerChest(new EqApplyChest(APPLY_HIT, chestKeyword,
									    chestDesc)));
			IF_ISLOCKERTYPE("mana", "that affect mana",
					p = AddLockerChest(new EqApplyChest(
						APPLY_MANA, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("moves", "that affect moves",
					p = AddLockerChest(new EqApplyChest(
						APPLY_MOVE, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("hitroll", "that affect hitroll",
					p = AddLockerChest(new EqApplyChest(
						APPLY_HITROLL, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("damroll", "that affect damroll",
					p = AddLockerChest(new EqApplyChest(
						APPLY_DAMROLL, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("save_para", "that affect save_para",
					p = AddLockerChest(new EqApplyChest(
						APPLY_SAVING_PARA, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("save_rod", "that affect save_rod",
					p = AddLockerChest(new EqApplyChest(
						APPLY_SAVING_ROD, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("save_fear", "that affect save_fear",
					p = AddLockerChest(new EqApplyChest(
						APPLY_SAVING_FEAR, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("save_breath", "that affect save_breath",
					p = AddLockerChest(new EqApplyChest(
						APPLY_SAVING_BREATH, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("save_spell", "that affect save_spell",
					p = AddLockerChest(new EqApplyChest(
						APPLY_SAVING_SPELL, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("str", "that affect strength",
					p = AddLockerChest(new EqApplyChest(APPLY_STR, chestKeyword,
									    chestDesc)));
			IF_ISLOCKERTYPE("dex", "that affect dexterity",
					p = AddLockerChest(new EqApplyChest(APPLY_DEX, chestKeyword,
									    chestDesc)));
			IF_ISLOCKERTYPE("int", "that affect intelligence",
					p = AddLockerChest(new EqApplyChest(APPLY_INT, chestKeyword,
									    chestDesc)));
			IF_ISLOCKERTYPE("wis", "that affect wisdom",
					p = AddLockerChest(new EqApplyChest(APPLY_WIS, chestKeyword,
									    chestDesc)));
			IF_ISLOCKERTYPE("con", "that affect constitution",
					p = AddLockerChest(new EqApplyChest(APPLY_CON, chestKeyword,
									    chestDesc)));
			IF_ISLOCKERTYPE("agi", "that affect agility",
					p = AddLockerChest(new EqApplyChest(APPLY_AGI, chestKeyword,
									    chestDesc)));
			IF_ISLOCKERTYPE("pow", "that affect power",
					p = AddLockerChest(new EqApplyChest(APPLY_POW, chestKeyword,
									    chestDesc)));
			IF_ISLOCKERTYPE("cha", "that affect charisma",
					p = AddLockerChest(new EqApplyChest(APPLY_CHA, chestKeyword,
									    chestDesc)));
			IF_ISLOCKERTYPE("luck", "that affect luck",
					p = AddLockerChest(new EqApplyChest(
						APPLY_LUCK, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("karma", "that affect karma",
					p = AddLockerChest(new EqApplyChest(
						APPLY_KARMA, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("str_max", "that affect maximum strength (str_max)",
					p = AddLockerChest(new EqApplyChest(
						APPLY_STR_MAX, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("dex_max", "that affect maximum dexterity (dex_max)",
					p = AddLockerChest(new EqApplyChest(
						APPLY_DEX_MAX, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("int_max", "that affect maximum intelligence (int_max)",
					p = AddLockerChest(new EqApplyChest(
						APPLY_INT_MAX, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("wis_max", "that affect maximum wisdom (wis_max)",
					p = AddLockerChest(new EqApplyChest(
						APPLY_WIS_MAX, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("con_max", "that affect maximum constitution (con_max)",
					p = AddLockerChest(new EqApplyChest(
						APPLY_CON_MAX, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("agi_max", "that affect maximum agility (agi_max)",
					p = AddLockerChest(new EqApplyChest(
						APPLY_AGI_MAX, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("pow_max", "that affect maximum power (pow_max)",
					p = AddLockerChest(new EqApplyChest(
						APPLY_POW_MAX, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("cha_max", "that affect maximum charisma (cha_max)",
					p = AddLockerChest(new EqApplyChest(
						APPLY_CHA_MAX, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("luck_max", "that affect maximum luck (luck_max)",
					p = AddLockerChest(new EqApplyChest(
						APPLY_LUCK_MAX, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("karma_max", "that affect maximum karma (karma_max)",
					p = AddLockerChest(new EqApplyChest(
						APPLY_KARMA_MAX, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("ac", "armor class",
					p = AddLockerChest(new EqApplyChest(APPLY_AC, chestKeyword,
									    chestDesc)));
			IF_ISLOCKERTYPE("mana_reg", "that affect mana regeneration",
					p = AddLockerChest(new EqApplyChest(
						APPLY_MANA_REG, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("move_reg", "that affect movement regeneration",
					p = AddLockerChest(new EqApplyChest(
						APPLY_MOVE_REG, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("hit_reg", "that affect hitpoint regeneration",
					p = AddLockerChest(new EqApplyChest(
						APPLY_HIT_REG, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("spell_pulse",
					"that affect spell_pulse (negative is better)",
					p = AddLockerChest(new EqApplyChest(
						APPLY_SPELL_PULSE, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("combat_pulse",
					"that affect combat_pulse (negative is better)",
					p = AddLockerChest(new EqApplyChest(
						APPLY_COMBAT_PULSE, chestKeyword, chestDesc)));

			// Mine related.
			IF_ISLOCKERTYPE(
				"mine", "that are ore from a mine",
				p = AddLockerChest(new OreChest(NULL, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("mine_adamantium",
					"that are adamantium ore from a mine (mine_adamantium)",
					p = AddLockerChest(new OreChest("adamantium", chestKeyword,
									chestDesc)));
			IF_ISLOCKERTYPE("mine_mithril",
					"that are mithril ore from a mine (mine_mithril)",
					p = AddLockerChest(
						new OreChest("mithril", chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("mine_platinum",
					"that are platinum ore from a mine (mine_platinum)",
					p = AddLockerChest(
						new OreChest("platinum", chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE(
				"mine_gold", "that are gold ore from a mine (mine_gold)",
				p = AddLockerChest(new OreChest("gold", chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("mine_silver",
					"that are silver ore from a mine (mine_silver)",
					p = AddLockerChest(
						new OreChest("silver", chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("mine_copper",
					"that are copper ore from a mine (mine_copper)",
					p = AddLockerChest(
						new OreChest("copper", chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE(
				"mine_tin", "that are iron ore from a mine (mine_tin)",
				p = AddLockerChest(new OreChest("tin", chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE(
				"mine_iron", "that are iron ore from a mine (mine_iron)",
				p = AddLockerChest(new OreChest("iron", chestKeyword, chestDesc)));

			IF_ISLOCKERTYPE("invis", "that provide you with invisibility",
					p = AddLockerChest(new EqAffectChest(
						AFF_INVISIBLE, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("farsee", "that provide you with farsee",
					p = AddLockerChest(new EqAffectChest(
						AFF_FARSEE, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("det_invis", "that provide you with detect invisibile",
					p = AddLockerChest(new EqAffectChest(
						AFF_DETECT_INVISIBLE, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("haste", "that provide you with haste",
					p = AddLockerChest(new EqAffectChest(
						AFF_HASTE, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("sense_life", "that provide you with sense life",
					p = AddLockerChest(new EqAffectChest(
						AFF_SENSE_LIFE, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("minor_globe",
					"that provide you with minor globe of invulnerability",
					p = AddLockerChest(new EqAffectChest(
						AFF_MINOR_GLOBE, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("stone_skin", "that provide you with stone skin",
					p = AddLockerChest(new EqAffectChest(
						AFF_STONE_SKIN, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("waterbreath", "that provide you with waterbreath",
					p = AddLockerChest(new EqAffectChest(
						AFF_WATERBREATH, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("prot_evil", "that provide you with protection from evil",
					p = AddLockerChest(new EqAffectChest(
						AFF_PROTECT_EVIL, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("slow_poison", "that provide you with slow poison",
					p = AddLockerChest(new EqAffectChest(
						AFF_SLOW_POISON, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("prot_good", "that provide you with protection from good",
					p = AddLockerChest(new EqAffectChest(
						AFF_PROTECT_GOOD, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("sneak", "that provide you with sneak",
					p = AddLockerChest(new EqAffectChest(
						AFF_SNEAK, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("barkskin", "that provide you with barkskin",
					p = AddLockerChest(new EqAffectChest(
						AFF_BARKSKIN, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("infravision", "that provide you with infravision",
					p = AddLockerChest(new EqAffectChest(
						AFF_INFRAVISION, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("levitate", "that provide you with levitation",
					p = AddLockerChest(new EqAffectChest(
						AFF_LEVITATE, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("fly", "that provide you with fly",
					p = AddLockerChest(new EqAffectChest(
						AFF_FLY, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("aware", "that provide you with awareness",
					p = AddLockerChest(new EqAffectChest(
						AFF_AWARE, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("prot_fire", "that provide you with protection from fire",
					p = AddLockerChest(new EqAffectChest(
						AFF_PROT_FIRE, 1, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("biofeedback", "that provide you with biofeedback",
					p = AddLockerChest(new EqAffectChest(
						AFF_BIOFEEDBACK, 1, chestKeyword, chestDesc)));

			IF_ISLOCKERTYPE("fireshield", "that provide you with fireshield",
					p = AddLockerChest(new EqAffectChest(
						AFF2_FIRESHIELD, 2, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("ultravision", "that provide you with ultravision",
					p = AddLockerChest(new EqAffectChest(
						AFF2_ULTRAVISION, 2, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("det_evil", "that provide you with detect evil",
					p = AddLockerChest(new EqAffectChest(
						AFF2_DETECT_EVIL, 2, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("det_good", "that provide you with detect good",
					p = AddLockerChest(new EqAffectChest(
						AFF2_DETECT_GOOD, 2, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("det_magic", "that provide you with detect magic",
					p = AddLockerChest(new EqAffectChest(
						AFF2_DETECT_MAGIC, 2, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("prot_cold", "that provide you with protection from cold",
					p = AddLockerChest(new EqAffectChest(
						AFF2_PROT_COLD, 2, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("prot_light",
					"that provide you with protection from lightning",
					p = AddLockerChest(new EqAffectChest(
						AFF2_PROT_LIGHTNING, 2, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("globe", "that provide you with globe of invulnerability",
					p = AddLockerChest(new EqAffectChest(
						AFF2_GLOBE, 2, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("prot_gas", "that provide you with protection from gas",
					p = AddLockerChest(new EqAffectChest(
						AFF2_PROT_GAS, 2, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("prot_acid", "that provide you with protection from acid",
					p = AddLockerChest(new EqAffectChest(
						AFF2_PROT_ACID, 2, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("soulshield", "that provide you with soulshield",
					p = AddLockerChest(new EqAffectChest(
						AFF2_SOULSHIELD, 2, chestKeyword, chestDesc)));

			IF_ISLOCKERTYPE("ecto_form", "that provide you with ectoplasmic form",
					p = AddLockerChest(new EqAffectChest(AFF3_ECTOPLASMIC_FORM,
									     3, chestKeyword,
									     chestDesc)));
			IF_ISLOCKERTYPE("prot_animal",
					"that provide you with protection from animals",
					p = AddLockerChest(new EqAffectChest(
						AFF3_PROT_ANIMAL, 3, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("spirit_ward", "that provide you with spirit ward",
					p = AddLockerChest(new EqAffectChest(
						AFF3_SPIRIT_WARD, 3, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("gsw", "that provide you with greater spirit ward",
					p = AddLockerChest(new EqAffectChest(
						AFF3_GR_SPIRIT_WARD, 3, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("inert_barrier", "that provide you with inertial barrier",
					p = AddLockerChest(new EqAffectChest(AFF3_INERTIAL_BARRIER,
									     3, chestKeyword,
									     chestDesc)));
			IF_ISLOCKERTYPE("light_shield", "that provide you with lightning shield",
					p = AddLockerChest(new EqAffectChest(
						AFF3_LIGHTNINGSHIELD, 3, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("coldshield", "that provide you with coldshield",
					p = AddLockerChest(new EqAffectChest(
						AFF3_COLDSHIELD, 3, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("blur", "that provide you with blur",
					p = AddLockerChest(new EqAffectChest(
						AFF3_BLUR, 3, chestKeyword, chestDesc)));

			IF_ISLOCKERTYPE("nofear", "that make you fearless",
					p = AddLockerChest(new EqAffectChest(
						AFF4_NOFEAR, 4, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("regeneration", "that provide you with regeneration",
					p = AddLockerChest(new EqAffectChest(
						AFF4_REGENERATION, 4, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("hawkvision", "that provide you with hawkvision",
					p = AddLockerChest(new EqAffectChest(
						AFF4_HAWKVISION, 4, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("sense_holy", "that provide you with sense holyness",
					p = AddLockerChest(new EqAffectChest(
						AFF4_SENSE_HOLINESS, 4, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("prot_living",
					"that provide you with protection from living",
					p = AddLockerChest(new EqAffectChest(
						AFF4_PROT_LIVING, 4, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("det_illusion", "that provide you with detect illusion",
					p = AddLockerChest(new EqAffectChest(
						AFF4_DETECT_ILLUSION, 4, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("neg_shield", "that provide you with negative shield",
					p = AddLockerChest(new EqAffectChest(
						AFF4_NEG_SHIELD, 4, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("wildmagic", "that provide you with wildmagic",
					p = AddLockerChest(new EqAffectChest(
						AFF4_WILDMAGIC, 4, chestKeyword, chestDesc)));

			IF_ISLOCKERTYPE("prot_undead",
					"that provide you with protection from undead",
					p = AddLockerChest(new EqAffectChest(
						AFF5_PROT_UNDEAD, 5, chestKeyword, chestDesc)));
			// New locker sorts added by Gellz 29/04/15
			IF_ISLOCKERTYPE("vamp", "that provide you with vampiric touch",
					p = AddLockerChest(new EqAffectChest(
						AFF2_VAMPIRIC_TOUCH, 2, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("toiw", "that provide you with tower of iron will",
					p = AddLockerChest(new EqAffectChest(
						AFF3_TOWER_IRON_WILL, 3, chestKeyword, chestDesc)));
			IF_ISLOCKERTYPE("dark", "that provide you with globe of darkness",
					p = AddLockerChest(new EqAffectChest(AFF4_GLOBE_OF_DARKNESS,
									     4, chestKeyword,
									     chestDesc)));
			IF_ISLOCKERTYPE(
				"pwt", "that provide you with pass without trace",
				p = AddLockerChest(new EqAffectChest(AFF3_PASS_WITHOUT_TRACE, 3,
								     chestKeyword, chestDesc)));

			IF_ISLOCKERTYPE("dazzle", "that make you a dazzler",
					p = AddLockerChest(new EqAffectChest(
						AFF4_DAZZLER, 4, chestKeyword, chestDesc)));

			// New locker sorts added by Gellz 29/04/15
			// ignore 'unsorted' (or none), but give error if not found, not in
			// help mode, and nothing added
			if (!p && !bFound && str_cmp("unsorted", GBuf1) &&
			    helpMode !=
				    LOCKER_HELP_SHORT) // != LOCKER_HELP_ALL_SHORT && helpMode != LOCKER_HELP_ALL_LONG )
			{
				checked_snprintf(GBuf2 + strlen(GBuf2),
						 MAX_STRING_LENGTH - strlen(GBuf2),
						 "Invalid sort option: %s \n", GBuf1);
			}
			args = one_argument(args, GBuf1);
		} while ('\0' != GBuf1[0]);
	}

	if (bMakeAttachable)
		AddLockerChest(new EqSlotChest(ITEM_ATTACH_BELT, "attach", "attached to belt"));
	if (bMakeHoldable)
		AddLockerChest(new EqSlotChest(ITEM_HOLD, "hold", "that you can hold"));

	if (helpMode == LOCKER_HELP_NONE && ('\0' != GBuf2[0]))
	{
		// error messages...
		send_to_char(GBuf2, ch);
	}

	// For non-custom, create the chest P_objs, and place them in the room...
	if (helpMode == LOCKER_HELP_NONE)
	{
		if (bIsCustomChest)
		{
			if (NULL != m_pChestList)
			{
				// The combochest gets the chest list we have now...
				ComboChest *pCombo = new ComboChest(m_pChestList);

				// Which is then reset to nothing
				m_pChestList = NULL;
				// Insert the created combo
				AddLockerChest(pCombo);
			}
		}
		// unsorted chest is ALWAYS present, and always the last chest
		AddLockerChest(new UnsortedChest());

		LockerChest *p = m_pChestList;

		while (p)
		{
			P_obj obj = p->CreateChestObject();

			obj_to_room(obj, m_realRoom);
			p = p->m_pNextInChain;
		}
	}
	else
	{
		// If there's a short list, replace the last ", " with ".\n"
		if (('\0' != GBuf2[0]) &&
		    (helpMode == LOCKER_HELP_SHORT || helpMode == LOCKER_HELP_ALL_SHORT))
		{
			snprintf(GBuf2 + strlen(GBuf2) - 2, MAX_STRING_LENGTH - (strlen(GBuf2) - 2),
				 ".\n");
		}
		send_to_char(GBuf2, ch);
	}

	return bRet;
}

void LockerChest::BeautifyDesc(const char *srcDesc, char *destDesc)
{
	int len = strlen(m_chestKeyword);
	const char *p1 = srcDesc;
	char *p2 = destDesc;

	do
	{
		if (!strn_cmp(p1, m_chestKeyword, len))
		{
			*p2++ = '&';
			*p2++ = '+';
			*p2++ = 'C';
			for (int i = 0; i < len; i++)
				*p2++ = *p1++;
			*p2++ = '&';
			*p2++ = '+';
			*p2++ = 'y';
		}
		else
			*p2++ = *p1++;
	} while (*p1);
	*p2 = '\0';
}

void LockerChest::FillExtraDescBuf(char *GBuf1)
{
	snprintf(GBuf1, MAX_STRING_LENGTH, "&+yThis chest contains your items %s&n.",
		 this->m_chestDescText);
}

P_obj LockerChest::CreateChestObject(void)
{
	if (!m_pChestObject)
	{
		m_pChestObject = read_object(m_chestVnum, VIRTUAL);
		if (m_pChestObject)
		{
			// set sane values (or insane ones)
			m_pChestObject->wear_flags = 0;
			m_pChestObject->cost = 0;
			m_pChestObject->weight = 0;
			m_pChestObject->condition = 100;
			m_pChestObject->value[0] = -1;
			m_pChestObject->value[1] = m_pChestObject->value[2] =
				m_pChestObject->value[3] = 0;
			m_pChestObject->type = ITEM_CONTAINER;
			// string it
			m_pChestObject->str_mask |= (STRUNG_KEYS | STRUNG_DESC1);
			char GBuf1[MAX_STRING_LENGTH];

			snprintf(GBuf1, sizeof(GBuf1), "chest %s", this->m_chestKeyword);
			m_pChestObject->name = str_dup(GBuf1);
			snprintf(GBuf1, sizeof(GBuf1), "&+yAn ornate chest bearing items %s&+y.&n",
				 this->m_chestDescText);
			char GBuf2[MAX_STRING_LENGTH];

			BeautifyDesc(GBuf1, GBuf2);
			m_pChestObject->description = str_dup(GBuf2);
			// make the extra keywords for the obj
			// "An ornate chest bearing your items *desc*." obj_data
			CREATE(m_pChestObject->ex_description, extra_descr_data, 1,
			       MEM_TAG_EXDESCD);

			m_pChestObject->ex_description->keyword = str_dup(m_pChestObject->name);
			FillExtraDescBuf(GBuf1);
			BeautifyDesc(GBuf1, GBuf2);
			m_pChestObject->ex_description->description = str_dup(GBuf2);
			m_pChestObject->ex_description->next = NULL;
		}
	}
	return m_pChestObject;
}

LockerChest::~LockerChest(void)
{
	int room;
	P_obj content, next;

	if (m_pChestObject)
	{
		// Drop the contents - default to limbo just in case.
		if (OBJ_ROOM(m_pChestObject))
		{
			room = m_pChestObject->loc.room;
			room = (room < 0 || room > top_of_world) ? RROOM_LIMBO : room;
		}
		// This should never happen, but just in case.
		else
		{
			room = RROOM_LIMBO;
		}
		next = m_pChestObject->contains;
		while ((content = next) != NULL)
		{
			next = content->next_content;
			obj_from_obj(content);
			obj_to_room(content, room);
		}
		obj_from_room(m_pChestObject);
		extract_obj(m_pChestObject, TRUE); // Not an arti, but 'in game.'
	}
}

ComboChest::~ComboChest(void)
{
	LockerChest *p;

	while (m_LockerChests)
	{
		p = m_LockerChests;
		m_LockerChests = p->m_pNextInChain;
		delete p;
	}
}

void ComboChest::FillExtraDescBuf(char *GBuf1)
{
	char GBuf2[MAX_STRING_LENGTH];

	strlcpy(GBuf1, "&+yThis &+Ccustom&+y chest bears your items ", MAX_STRING_LENGTH);
	LockerChest *p = m_LockerChests;

	while (p)
	{
		p->BeautifyDesc(p->m_chestDescText, GBuf2);
		strlcat(GBuf1, GBuf2, MAX_STRING_LENGTH);
		p = p->m_pNextInChain;
		if (p)
		{
			if (!p->m_pNextInChain)
				strlcat(GBuf1, " and ", MAX_STRING_LENGTH);
			else
				strlcat(GBuf1, ", ", MAX_STRING_LENGTH);
		}
	}
	strlcat(GBuf1, "&n.", MAX_STRING_LENGTH);
}

bool ComboChest::ItemFits(P_obj obj)
{
	LockerChest *p = m_LockerChests;

	while (p)
	{
		if (!p->ItemFits(obj))
			return false;
		p = p->m_pNextInChain;
	}
	return true;
}

PrivateChest::PrivateChest(int chest_id, const char *name, const char *password_hash)
	: LockerChest(name, "in your private chest")
	, m_chestId(chest_id)
	, m_passwordHash(password_hash ? password_hash : "")
{
	strlcpy(m_chestName, name, sizeof(m_chestName));

	m_pChestObject = read_object(m_chestVnum, VIRTUAL);
	if (m_pChestObject)
	{
		m_pChestObject->wear_flags = 0;
		m_pChestObject->cost = 0;
		m_pChestObject->weight = 0;
		m_pChestObject->condition = 100;
		m_pChestObject->value[0] = chest_id;
		m_pChestObject->value[1] = m_pChestObject->value[2] = m_pChestObject->value[3] = 0;
		m_pChestObject->type = ITEM_CONTAINER;
		m_pChestObject->str_mask |= (STRUNG_KEYS | STRUNG_DESC1);

		char buf[MAX_STRING_LENGTH];
		snprintf(buf, sizeof(buf), "chest %s private", name);
		m_pChestObject->name = str_dup(buf);

		snprintf(buf, sizeof(buf), "&+cA private chest labeled '&+W%s&+c'%s.&n", name,
			 m_passwordHash.empty() ? "" : " &+Y(locked)&n");
		m_pChestObject->description = str_dup(buf);
	}
}

bool EqApplyChest::ItemFits(P_obj obj)
{
	for (int i = 0; i < MAX_OBJ_AFFECT; i++)
	{
		if ((obj->affected[i].location == m_applyType) && (obj->affected[i].modifier != 0))
			return true;
	}
	return false;
}

bool EqAffectChest::ItemFits(P_obj obj)
{
	// Removed buggy switch.
	if (m_bitVector == 1 && IS_SET(obj->bitvector, m_bit))
	{
		return true;
	}
	else if (m_bitVector == 2 && IS_SET(obj->bitvector2, m_bit))
	{
		return true;
	}
	else if (m_bitVector == 3 && IS_SET(obj->bitvector3, m_bit))
	{
		return true;
	}
	else if (m_bitVector == 4 && IS_SET(obj->bitvector4, m_bit))
	{
		return true;
	}
	else if (m_bitVector == 5 && IS_SET(obj->bitvector5, m_bit))
	{
		return true;
	}
	else
	{
		return false;
	}
	return false;
}

/* storage locker room proc */
int storage_locker(int room, P_char ch, int cmd, char *arg);

/* create a new locker room for locker 'locker' which 'ch' will go to */
static int create_new_locker(P_char ch, P_char locker, const sql_rows &rows);

/* free memory associated with creating a new locker */
static void free_locker(int roomNum);

/* A flat-file locker's public chest: the items to restore, those no other owner holds. */
struct flat_locker_chest
{
	item_owner_identity owner;
	uint64_t owner_revision = 0;
	std::vector<player_item_snapshot> items;
	std::vector<player_load_item_identity> identities;
};

/* Load a locker character from its entry rows and optionally enforce entry authorization;
 * a flat-file locker's public chest comes as flat. */
static P_char load_locker_char(P_char ch, char *esc_locker_name, int bValidateAccess, bool busy,
			       const sql_rows &rows, const flat_locker_chest *flat);
static P_char create_locker_char(P_char chOwner, P_char newCh, char *esc_locker_name);
static int save_locker_char(P_char chInLocker, int bTerminal);

static bool check_for_artisInRoom(P_char ch, int rroom);
static int lockerName_is_inuse(char *lockerName);

static int locker_grantcmd(P_char ch, char *arg);
static int locker_equipcmd(P_char ch, char *arg);
static int locker_chestcmd(P_char ch, char *arg);
static int locker_opencmd(P_char ch, char *arg);
static int locker_closecmd(P_char ch, char *arg);
static int locker_logcmd(P_char ch, char *arg);

/* cmds for access lists, each read and written on the persistence writer... */
static void locker_access_transferAccess(P_char locker, P_char ch);
static void locker_access_show(P_char ch, const char *locker_name);
static void locker_access_add(P_char ch, P_char locker, const char *name);
static void locker_access_remove(P_char ch, P_char locker, const char *name);

/* Checks both locker entrances make, again when the locker's rows arrive. */
static bool locker_ready_to_enter(P_char ch);
/* The rest of an entrance, once ch is at the door of the loaded locker. */
using locker_entered = std::function<void(P_char ch, P_char chLocker, int locker_room)>;
static void locker_enter(P_char ch, const char *locker_name, int bValidate, locker_entered entered);
static void storage_locker_entered(P_char ch, P_char chLocker, int locker_room,
				   int is_guild_locker);
static void guild_locker_entered(P_char ch, P_char chLocker, int locker_room);

int storage_locker_room_hook(int room, P_char ch, int cmd, char *arg);

void display_no_mem(P_char ch)
{
	if (IS_PUNDEAD(ch) || GET_CLASS(ch, CLASS_WARLOCK) || IS_UNDEADRACE(ch) ||
	    is_wearing_necroplasm(ch))
	{
		send_to_char("You can not manage your link with your &+Lnegative powers&N!\n", ch);
	}
	else if (USES_COMMUNE(ch))
	{
		send_to_char("&+yYou don't seem to see any nature in this closet.\n\r", ch);
	}
	else if (USES_DEFOREST(ch))
	{
		send_to_char("&+yYou don't seem to see any &+gnature&+y in this closet.\n\r", ch);
	}
	else if (USES_TUPOR(ch))
	{
		send_to_char(
			"You seem unable to relax enough to commune with the storm spirits.\r\n",
			ch);
	}
	else if (book_class(ch))
	{
		send_to_char("It's too quiet to read here.\n", ch);
	}
	else if (GET_CLASS(ch, CLASS_SHAMAN))
	{
		send_to_char("You seem unable to manage your trance.\n", ch);
	}
	else
	{
		send_to_char("Your prayers don't seem to be heard here.\n", ch);
	}
}

/* obj proc - put on bank counter objects instead of in bank rooms */
int storage_locker_obj_hook(P_obj obj, P_char ch, int cmd, char *argument)
{
	return storage_locker_room_hook(obj->loc.room, ch, cmd, argument);
}

/* room proc put in banks, etc to allow a person to enter a locker */
int storage_locker_room_hook(int /*room*/, P_char ch, int cmd, char *arg)
{
	char enterWhat[MAX_INPUT_LENGTH];
	char enterWho[MAX_INPUT_LENGTH];
	int is_guild_locker = 0;

	char lockerName[500];
	int bValidate = 0;

	if (cmd != CMD_ENTER)
		return FALSE;

	if (ch == NULL)
		return (FALSE);

	// not a god and not in a town?  then there's no locker here
	else if (!CHAR_IN_TOWN(ch) &&
		 (!IS_TRUSTED(ch) && (GET_RACE(ch) != RACE_LICH) && !IS_RACEWAR_NEUTRAL(ch)))
	{
		return FALSE;
	}

	if (IS_NPC(ch) || IS_MORPH(ch))
		return (FALSE);

	argument_interpreter(arg, enterWhat, enterWho);

	if (str_cmp(enterWhat, "locker"))
		return FALSE;

	if (IS_TRUSTED(ch) && GET_LEVEL(ch) < OVERLORD)
		return FALSE;

	if (!locker_ready_to_enter(ch))
		return TRUE;

	if (IS_NOTWELCOME(ch))
	{
		send_to_char("You are NOT welcome here!\r\n", ch);
		return TRUE;
	}

	// zone = &zone_table[world[ch->in_room].zone];
	// if (zone->status > ZONE_NORMAL && (GET_LEVEL(ch) > 25) &&
	// (zone_table[world[ch->in_room].zone].number != WINTERHAVEN))
	// {
	// send_to_char("The safety commission says to you, '&+RThe town is under attack!!&n'\n", ch);
	// send_to_char(" .. '&+WWe must fortify our defenses and keep the invaders out of the locker!'\n", ch);
	// return TRUE;
	// }

	// check for guild locker
	if (!str_cmp(enterWho, "guild"))
	{ /* guild lockers are named:  guild.x.locker where 'x' is the assoc number */
		if (!GET_ASSOC(ch) || !IS_MEMBER(GET_A_BITS(ch)) ||
		    (IS_PC(ch) && !GT_PAROLE(GET_A_BITS(ch))))
		{
			send_to_char("Try becoming part of a guild first!\r\n", ch);
			return TRUE;
		}

		const unsigned long required_prestige = static_cast<unsigned long>(
			MAX(0, get_property("prestige.locker.required", 0)));
		if (GET_ASSOC(ch)->get_prestige() < required_prestige)
		{
			send_to_char(
				"Your association is not yet prestigious enough to have a locker!\r\n",
				ch);
			return TRUE;
		}
		snprintf(enterWho, MAX_INPUT_LENGTH, "guild.%d", GET_ASSOC(ch)->get_id());
		is_guild_locker = 1;
	}
	else if ('\0' == enterWho[0])
	{
		const char *acct = get_account_name_safe(ch);
		if (!acct || !strcmp(acct, "Unknown"))
		{
			send_to_char("You need an account to use the locker system.\r\n", ch);
			return TRUE;
		}
		char acct_lower[MAX_INPUT_LENGTH];
		int i;
		for (i = 0; acct[i] && i < MAX_INPUT_LENGTH - 1; i++)
			acct_lower[i] = tolower(acct[i]);
		acct_lower[i] = '\0';
		checked_snprintf(enterWho, MAX_INPUT_LENGTH, "account.%s.%d", acct_lower,
				 GET_RACEWAR(ch));
	}
	else
	{
		bValidate = 1;
	}

	checked_snprintf(lockerName, 500, "%s.locker", enterWho);

	locker_enter(ch, lockerName, bValidate,
		     [is_guild_locker](P_char entrant, P_char chLocker, int locker_room)
		     { storage_locker_entered(entrant, chLocker, locker_room, is_guild_locker); });
	return TRUE;
}

/* The rest of a bank locker entrance, once the locker is loaded. */
static void storage_locker_entered(P_char ch, P_char chLocker, int locker_room, int is_guild_locker)
{
#if defined(CTF_MUD) && (CTF_MUD == 1)
	if (ctf_carrying_flag(ch) == CTF_PRIMARY)
	{
		send_to_char("You can't carry that with you.\r\n", ch);
		drop_ctf_flag(ch);
	}
#endif

	send_to_char(
		"A member of the &+YStorage Locker Safety Commission&n escorts you to the locker.\r\n",
		ch);
	act("A member of the &+YStorage Locker Safety Commission&n escorts $n to a private room.",
	    FALSE, ch, 0, ch, TO_ROOM);

	send_to_char(
		"&+WYour items will be safely stored here. Use '&+Cequip sort <stat>&+W' to sort "
		"equipment into a second chest by stat. A deferred save will complete "
		"shortly after you depart.&n\r\n",
		ch);

	// PFileToLocker

	StorageLocker *pLocker = GetChestList(locker_room);
	if (pLocker)
		pLocker->PFileToLocker();
	// MONEY HACK

	char_from_room(ch);

	char_to_room(ch, locker_room, 0);

	int temp = pLocker ? (1 + (3 * pLocker->m_itemCount)) : 1;

	if (pLocker && pLocker->m_itemCount >= 5001)
	{
		send_to_char(
			"\r\n&+RYou have a ton of &+WSTUFF&+R, as in more than 5000 items - so there's a surcharge!\r\n",
			ch);
		temp += (pLocker->m_itemCount - 5000) * 2000;
	}

	if (is_guild_locker && pLocker)
	{
		temp = 1 + (1 * pLocker->m_itemCount);
	}

	char money_string[MAX_INPUT_LENGTH];
	snprintf(money_string, MAX_INPUT_LENGTH,
		 "\r\nThe escort says 'You have &+W%d items&n, this cost you %s'&n\r\n",
		 pLocker ? pLocker->m_itemCount : 0, coin_stringv(temp));
	send_to_char(money_string, ch);

	if (GET_MONEY(ch) < temp)
	{
		if (SUB_BALANCE(ch, temp, 0) != 0)
		{
			send_to_char(
				"..but you don't have the money or the bank could not complete the payment, GET OUT!\r\n\r\n",
				ch);
			const int exit_room = locker_exit_room(ch, ch->in_room);
			char_from_room(ch);
			if (ch->in_room == NOWHERE)
				char_to_room(ch, exit_room, 0);
			return;
		}
	}
	else
	{
		SUB_MONEY(ch, temp, 0);
	}
	// End Money hack

	// Stop deforest/commune/etc.
	if (IS_AFFECTED2(ch, AFF2_MEMORIZING) || get_scheduled(ch, event_memorize))
	{
		REMOVE_BIT(ch->specials.affected_by2, AFF2_MEMORIZING);
		disarm_char_nevents(ch, event_memorize);
		send_to_char("\n\r", ch);
		display_no_mem(ch);
		CharWait(ch, WAIT_SEC * 3);
	}

	bool is_owner = esc_locker_name_matches_player(GET_NAME(chLocker), ch);

	// warn them that they can't idle in the locker...
	if (!is_owner)
	{
		logit(LOG_WIZ, "LOCKER: (%s) entered (%s's) locker.", GET_NAME(ch),
		      GET_NAME(chLocker));
		send_to_char(
			"&+RWARNING:&n This isn't your own locker.  Therefore, you'll be ejected if\r\n"
			"you are idle for more then 2 minutes.\r\n",
			ch);
	}
}

/* room proc put in guildhalls, etc to allow a person to enter their guild locker */
int guild_locker_room_hook(int /*room*/, P_char ch, int cmd, char *arg)
{
	char enterWhat[MAX_INPUT_LENGTH];
	char enterWho[MAX_INPUT_LENGTH];

	char lockerName[500];
	int bValidate = 0;

	if (cmd != CMD_ENTER)
		return FALSE;

	if (ch == NULL)
		return (FALSE);

	if (IS_NPC(ch) || IS_MORPH(ch))
		return (FALSE);

	argument_interpreter(arg, enterWhat, enterWho);

	if (str_cmp(enterWhat, "locker"))
		return FALSE;

	if (IS_TRUSTED(ch) && GET_LEVEL(ch) < OVERLORD)
		return FALSE;

	if (!locker_ready_to_enter(ch))
		return TRUE;

	/* guild lockers are named:  guild.x.locker where 'x' is the assoc number */
	if (!GET_ASSOC(ch) || !IS_MEMBER(GET_A_BITS(ch)) ||
	    (IS_PC(ch) && !GT_PAROLE(GET_A_BITS(ch))))
	{
		send_to_char("Try becoming part of a guild first!\r\n", ch);
		return TRUE;
	}

	snprintf(enterWho, MAX_INPUT_LENGTH, "guild.%d", GET_ASSOC(ch)->get_id());

	checked_snprintf(lockerName, 500, "%s.locker", enterWho);

	locker_enter(ch, lockerName, bValidate, guild_locker_entered);
	return TRUE;
}

/* The rest of a guildhall locker entrance, once the locker is loaded. */
static void guild_locker_entered(P_char ch, P_char chLocker, int locker_room)
{
#if defined(CTF_MUD) && (CTF_MUD == 1)
	if (ctf_carrying_flag(ch) == CTF_PRIMARY)
	{
		send_to_char("You can't carry that with you.\r\n", ch);
		drop_ctf_flag(ch);
	}
#endif

	send_to_char(
		"A member of the &+YStorage Locker Safety Commission&n escorts you to the locker\r\n",
		ch);
	act("A member of the &+YStorage Locker Safety Commission&n escorts $n to a private room.",
	    FALSE, ch, 0, ch, TO_ROOM);

	// PFileToLocker

	StorageLocker *pLocker = GetChestList(locker_room);
	if (pLocker)
		pLocker->PFileToLocker();
	// MONEY HACK

	char_from_room(ch);
	char_to_room(ch, locker_room, 0);

	bool is_guild_owner = esc_locker_name_matches_player(GET_NAME(chLocker), ch);

	// warn them that they can't idle in the locker...
	if (!is_guild_owner)
	{
		logit(LOG_WIZ, "LOCKER: (%s) entered (%s's) locker.", GET_NAME(ch),
		      GET_NAME(chLocker));
		send_to_char(
			"&+RWARNING:&n This isn't your own locker.  Therefore, you'll be ejected if\r\n"
			"you are idle for more then 2 minutes.\r\n",
			ch);
	}
}

int storage_locker(int room, P_char ch, int cmd, char *arg)
{
	int cost;
	int troom;

	if (cmd == CMD_SET_PERIODIC)
		return FALSE;

	if (!ch)
		return FALSE;

	troom = locker_exit_room(ch, room);
	P_char tmp_char;
	P_obj tmp_object;
	char name[MAX_INPUT_LENGTH];

	if ((cmd == CMD_SHAPECHANGE) || (cmd == CMD_DISGUISE) || (cmd == CMD_SWITCH) ||
	    (cmd == CMD_AT) || (cmd == CMD_CAMP) || (cmd == CMD_QUIT) || cmd == CMD_USE ||
	    cmd == CMD_SUMMON || cmd == CMD_INNATE || cmd == CMD_BANDAGE || cmd == CMD_QUEST)
	{
		send_to_char("You can't do that in here!  Leave first.\r\n", ch);
		return TRUE;
	}

	if (cmd == CMD_ASSIMILATE || cmd == CMD_COMMUNE || cmd == CMD_DEFOREST ||
	    cmd == CMD_TUPOR || cmd == CMD_FOCUS || cmd == CMD_PRAY || cmd == CMD_MEMORIZE)
	{
		display_no_mem(ch);
		return TRUE;
	}

	if ((cmd == CMD_DOORBASH) || (cmd == CMD_DOORKICK))
	{
		send_to_char("Instead, just open the door and walk out, okay?\r\n", ch);
		return TRUE;
	}

	one_argument(arg, name);

	// check legend lore

	if (cmd == CMD_STAT && !IS_TRUSTED(ch))
	{
		if (!strcasecmp(name, "receipt"))
		{
			locker_identify_receipt(ch);
			return TRUE;
		}
		if (!*name)
		{
			send_to_char(
				"The member of the &+YStorage Locker Safety Commission&n says 'Hmm, what item should i tell you more about?'\r\n",
				ch);
			return TRUE;
		}

		generic_find(name, FIND_OBJ_INV, ch, &tmp_char, &tmp_object);

		// 1000 = 1 plat, 100 = 1 gold
		cost = get_property("locker.stat.cost", 100);

		// check legend lore
		if (tmp_object)
		{
			locker_identify(ch, tmp_object, cost);
			return TRUE;
		}
		else
		{
			send_to_char(
				"The member of the &+YStorage Locker Safety Commission&n says 'Hmm, what item should i tell you more about?'\r\n",
				ch);
			return TRUE;
		}
	}
	StorageLocker *pLocker = locker_current(ch);

	if (!pLocker)
		return FALSE;

	if (cmd == CMD_FROMROOM)
	{ /* they are leaving the locker - say bye-bye! */
		if (!locker_handle_leave(ch, pLocker, room, troom))
			return ROOM_PROC_LEAVE_VETO;
	}
	if (cmd == (-80))
	{
		/* save hook - someone in the room is being saved. adjust things so they don't
		   really get saved in the locker room */
		/* this return value will ensure that the pfile is saved where the locker_hook is, and NOT
		   in the actual locker room */
		return locker_handle_save_hook(ch, troom);
	}

	if (cmd == (-81))
	{
		/* another save hook... this one is called AFTER the player is saved.  If it happens that
		   the character being saved is the proper occupant, save the locker character too */
		locker_handle_postsave(ch, pLocker, room);
	}
	if (cmd == CMD_GRANT)
	{
		return locker_grantcmd(ch, arg);
	}
	if (cmd == CMD_EQUIPMENT)
	{
		return locker_equipcmd(ch, arg);
	}
	if (cmd == CMD_OPEN)
	{
		return locker_opencmd(ch, arg);
	}
	if (cmd == CMD_CLOSE)
	{
		return locker_closecmd(ch, arg);
	}
	return FALSE;
}

void StorageLocker::event_resortLocker(P_char chLocker, P_char ch, P_obj /*obj*/, void *data)
{
	/* always will be attached to the 'unsorted' locker...  when called, all the lockers
	   will already be in the room.  ch will be the player, and chLocker is the locker..
	   if 'data' is null, this was called from the event mgr, meaning a save or initial
	   entry.  Otherwise, its being called directly - from an eq sort command */
	StorageLocker *pLocker = locker_current_or_error(ch, "Error: no locker found.\r\n");
	if (!pLocker)
	{
		return;
	}

	int nOldCount = pLocker->m_itemCount;
	bool explicit_sort = (data != NULL);
	struct timespec sort_started;
	struct timespec after_locker_to_pfile;
	struct timespec after_pfile_to_locker;
	if (explicit_sort)
		clock_gettime(CLOCK_MONOTONIC, &sort_started);

	// usually, everything will already be on pfile, but just make sure
	if (!pLocker->LockerToPFile())
	{
		send_to_char("&+RLocker save failed; please try again or contact staff.\r\n", ch);
		return;
	}
	if (explicit_sort)
		clock_gettime(CLOCK_MONOTONIC, &after_locker_to_pfile);

	// move everything from the pfile to the locker - this also sorts it
	pLocker->PFileToLocker();
	if (explicit_sort)
	{
		clock_gettime(CLOCK_MONOTONIC, &after_pfile_to_locker);
		logit(LOG_DEBUG,
		      "locker equip sort timing: user=%s locker=%s items_before=%d items_after=%d locker_to_pfile_ms=%ld pfile_to_locker_ms=%ld total_ms=%ld",
		      ch ? GET_NAME(ch) : "<null>", chLocker ? GET_NAME(chLocker) : "<null>",
		      nOldCount, pLocker->m_itemCount,
		      locker_elapsed_ms(&sort_started, &after_locker_to_pfile),
		      locker_elapsed_ms(&after_locker_to_pfile, &after_pfile_to_locker),
		      locker_elapsed_ms(&sort_started, &after_pfile_to_locker));
	}

	if (NULL != data)
	{
		/* eq sort cmd... */
		if (world[ch->in_room].contents && world[ch->in_room].contents->next_content)
		{
			send_to_char(
				"&+LA small &+ggremlin&+L appears out of no where, quickly arranging your belongings "
				"before disappearing into thin &+Cair&n.\r\n",
				ch);
		}
		else
		{
			send_to_char(
				"&+LA &+gLARGE gremlin&+L with hulking muscles storms through the room, gathers all of your "
				"belongings and places them back into the &+Cunsorted&+y items chest&n.\r\n",
				ch);
		}
	}
	else
	{
		/* due to the locker being saved (most likely from dropping something ) */
		/* to prevent spammage, however, only display the message if something was added to the locker */
		if (nOldCount < pLocker->m_itemCount)
		{
			/* Player may still be in the locker or may have already left. */
			if (ch && ch->in_room != NOWHERE && IS_ROOM(ch->in_room, ROOM_LOCKER))
				send_to_char(
					"&+LA small &+ggremlin&+L appears out of nowhere, and ensures everything is sorted...&n\r\n",
					ch);
			else if (ch && ch->in_room != NOWHERE)
				send_to_char(
					"&+LYou hear a faint &+gclinking&+L and &+gclattering&+L from the direction of the locker, as a small &+ggremlin&+L finishes sorting your belongings.&n\r\n",
					ch);
		}
	}
}

/* The async locker writer refused the terminal save when the player left (its slots were
 * full): ask it again a little later. The locker character keeps every item in memory until
 * the writer takes the save, then the writer's completion extracts it. */
static void event_deferredTerminalSave(P_char chLocker, P_char /*ch*/, P_obj /*obj*/,
				       void * /*data*/)
{
	if (chLocker && !locker_async_mark_dirty(chLocker, NULL, 1, "deferred-terminal"))
		add_event(event_deferredTerminalSave, WAIT_SEC, chLocker, NULL, NULL, 0, NULL, 0);
}

static int locker_equipcmd(P_char ch, char *arg)
{
	P_char chLocker = NULL;
	char arg1[MAX_INPUT_LENGTH];

	StorageLocker *pLocker = locker_current_or_error(ch, "Error: no locker found.\r\n");

	if (!pLocker)
	{
		return TRUE;
	}

	if (!locker_require_owner(pLocker, ch, "Sort your own locker!.\r\n"))
	{
		return TRUE;
	}
	chLocker = locker_char_or_error(
		pLocker, ch, "Error: unable to locate chLocker.  Please report ASAP\r\n");
	if (!chLocker)
	{
		return TRUE;
	}
	arg = one_argument(arg, arg1);

	if (!str_cmp(arg1, "chest"))
	{
		return locker_chestcmd(ch, arg);
	}
	if (!str_cmp(arg1, "log"))
	{
		return locker_logcmd(ch, arg);
	}
	if (str_cmp(arg1, "sort"))
	{
		return FALSE;
	}

	if (pLocker->MakeChests(ch, arg))
	{
		/* event_resortLocker owns the room-to-locker transition.  Do not
		 * serialize here as well: that would walk the entire locker twice
		 * and can repeat synchronous private-chest SQL before rebuilding
		 * the visible chest contents. */
		StorageLocker::event_resortLocker(chLocker, ch, NULL, (void *)-1);
		/* resort event will move everything back into the room */
	}

	return TRUE;
}

static int locker_grantcmd(P_char ch, char *arg)
{
	P_char chLocker = NULL;
	char arg1[MAX_INPUT_LENGTH];
	char arg2[MAX_INPUT_LENGTH];

	StorageLocker *pLocker = locker_current_or_error(ch, "Error: no locker found.\r\n");

	if (!pLocker)
	{
		return TRUE;
	}
	bool bPlayerIsGod = ((GET_LEVEL(ch) >= OVERLORD) || god_check(ch->player.name));

	chLocker = locker_char_or_error(
		pLocker, ch, "Error: unable to locate chLocker.  Please report ASAP\r\n");
	if (!chLocker)
	{
		return TRUE;
	}

	strcpy(arg1, GET_NAME(chLocker));
	bool is_owner = esc_locker_name_matches_player(arg1, ch);
	bool is_guild_member = locker_is_guild_member(pLocker, ch);
	bool is_guild_locker = (strncmp(GET_NAME(chLocker), "guild.", 6) == 0);
	if (!is_owner && !is_guild_member && !bPlayerIsGod)
	{
		send_to_char("Only the locker owner can manage access.\r\n", ch);
		return TRUE;
	}

	/* Guild locker access is managed through guild membership - you're
	 * either in the guild or you're not.  The grant command's add/remove/
	 * list/transfer subcommands are personal-locker features and don't
	 * apply here. */
	if (is_guild_locker)
	{
		send_to_char("Guild locker access is managed through guild membership. "
			     "Join or leave the guild to change locker access.\r\n",
			     ch);
		return TRUE;
	}

	if (!bPlayerIsGod)
		GET_RACEWAR(chLocker) = GET_RACEWAR(ch);
	argument_interpreter(arg, arg1, arg2);
	if (*arg1 == '\0')
		snprintf(arg1, MAX_INPUT_LENGTH, "?");

	if (is_abbrev(arg1, "list"))
	{
		locker_access_show(ch, GET_NAME(chLocker));
		return TRUE;
	}
	else if (is_abbrev(arg1, "add"))
	{ /* max of 10 people in the list */
		if ('\0' == arg2[0])
			send_to_char("Okay, you want to add someone.  WHO!?\r\n", ch);
		else
			locker_access_add(ch, chLocker, arg2);
		return TRUE;
	}
	else if (is_abbrev(arg1, "remove"))
	{
		if ('\0' == arg2[0])
			send_to_char("Okay, you want to remove someone.  WHO!?\r\n", ch);
		else
			locker_access_remove(ch, chLocker, arg2);
		return TRUE;
	}
	else if (is_abbrev(arg1, "transfer"))
	{
		locker_access_transferAccess(chLocker, ch);
		return TRUE;
	}
	else
	{
		if (str_cmp(arg1, "?") && !is_abbrev(arg1, "help"))
		{
			send_to_char_f(ch, "'%s' is not a valid locker command.\n", arg1);
		}
		send_to_char("Locker Grant Commands\r\n", ch);
		send_to_char(
			"----------------------------------------------------------------------------------\n",
			ch);
		send_to_char("grant list            shows who has access to your locker.\n", ch);
		send_to_char(
			"grant add <name>      adds <name> to those who can access your locker.\n",
			ch);
		send_to_char(
			"                      <name> can be a character name or account name.\n",
			ch);
		send_to_char(
			"grant remove <name>   removes <name> from those who can access your locker.\n",
			ch);
		send_to_char(
			"grant transfer        transfers the old list of those with access to the new list.\n",
			ch);
		send_to_char("grant [? | help]      displays this help.\n\n", ch);
		return TRUE;
	}
	return FALSE;
}

/* On the writer: whether `name` holds a grant to the locker, directly or through the
 * account of a character of that name on the locker's side. Both arrive escaped. */
static unsigned int locker_granted(MYSQL *connection, const std::string &owner,
				   const std::string &name, int racewar, bool *granted)
{
	sql_rows found;
	unsigned int error_code =
		sql_select(connection,
			   "SELECT 1 FROM locker_access WHERE owner='" + owner +
				   "' AND LOWER(visitor)=LOWER('" + name + "') LIMIT 1",
			   &found);
	if (!error_code && found.empty())
		error_code = sql_select(
			connection,
			sql_format(
				"SELECT 1 FROM locker_access la "
				"JOIN account_characters ac ON LOWER(la.visitor) = LOWER(ac.account_name) "
				"WHERE la.owner = '%s' AND LOWER(ac.char_name) = LOWER('%s') AND ac.racewar = %d AND ac.deleted_at IS NULL LIMIT 1",
				owner.c_str(), name.c_str(), racewar),
			&found);
	*granted = !found.empty();
	return error_code;
}

static sql_row locker_outcome(const char *outcome)
{
	sql_row row;
	row.fields.emplace_back(outcome);
	return row;
}

static void locker_access_show(P_char ch, const char *locker_name)
{
	if (!sql_read_for(ch,
			  "select visitor from locker_access where owner = '" +
				  escape_str(locker_name) + "'",
			  [](P_char viewer, const sql_rows &rows)
			  {
				  if (rows.empty())
				  {
					  send_to_char(
						  "No one has access to your locker but you.\n",
						  viewer);
					  return;
				  }
				  std::string list = "Locker Access: ";
				  for (size_t i = 0; i < rows.size(); i++)
					  list += std::string(i ? ", " : "") +
						  (rows[i][0] ? rows[i][0] : "");
				  send_to_char((list + ".\n").c_str(), viewer);
			  }))
		send_to_char("Error with database.\n", ch);
}

/* After a grant changes: save the locker and show the list again. */
static void locker_access_changed(P_char ch, const std::string &locker_name)
{
	if (locker_current(ch))
		storage_locker(ch->in_room, ch, (-81), NULL); // saves the locker
	locker_access_show(ch, locker_name.c_str());
}

/* Grant `name` access: at most ten grants, to a character on the locker's side (read
 * from its row) or an account with a character on that side. */
static void locker_access_add(P_char ch, P_char locker, const char *name)
{
	const std::string owner = escape_str(GET_NAME(locker));
	const std::string visitor = escape_str(name);
	const int racewar = GET_RACEWAR(locker);
	const int pid = sql_get_player_pid(name);
	if (!sql_read_work_for(
		    ch,
		    [owner, visitor, racewar, pid](MYSQL *connection,
						   sql_rows *rows) -> unsigned int
		    {
			    sql_rows found;
			    if (const unsigned int error_code = sql_select(
					connection,
					"SELECT COUNT(*) FROM locker_access WHERE owner='" + owner +
						"'",
					&found))
				    return error_code;
			    if (found.empty() || !found[0][0] || atoi(found[0][0]) >= 10)
			    {
				    rows->push_back(locker_outcome("full"));
				    return 0;
			    }
			    bool granted = false;
			    if (const unsigned int error_code = locker_granted(
					connection, owner, visitor, racewar, &granted))
				    return error_code;
			    if (granted)
			    {
				    rows->push_back(locker_outcome("granted"));
				    return 0;
			    }
			    found.clear();
			    const std::string side =
				    pid > 0 ?
					    sql_format(
						    "SELECT racewar FROM player_data WHERE pid=%d",
						    pid) :
					    sql_format(
						    "SELECT racewar FROM account_characters "
						    "WHERE LOWER(account_name) = LOWER('%s') AND deleted_at IS NULL AND racewar = %d LIMIT 1",
						    visitor.c_str(), racewar);
			    if (const unsigned int error_code =
					sql_select(connection, side, &found))
				    return error_code;
			    if (found.empty() || !found[0][0])
			    {
				    rows->push_back(locker_outcome("unknown"));
				    return 0;
			    }
			    if (atoi(found[0][0]) != racewar)
			    {
				    rows->push_back(locker_outcome("side"));
				    return 0;
			    }
			    rows->push_back(locker_outcome("added"));
			    return sql_execute(
				    connection,
				    "INSERT INTO locker_access (owner, visitor) VALUES ('" + owner +
					    "', '" + visitor + "')");
		    },
		    [shown = std::string(name), locker_name = std::string(GET_NAME(locker))](
			    P_char viewer, const sql_rows &rows)
		    {
			    const char *outcome = rows.empty() ? "" : rows[0][0];
			    if (!strcmp(outcome, "full"))
				    send_to_char(
					    "Too many people would have access!  Remove someone first.\r\n",
					    viewer);
			    else if (!strcmp(outcome, "granted"))
				    send_to_char("That person already has access!\r\n", viewer);
			    else if (!strcmp(outcome, "side"))
				    send_to_char_f(viewer,
						   "'%s' is not on your side of the racewar.\r\n",
						   shown.c_str());
			    else if (!strcmp(outcome, "unknown"))
				    send_to_char_f(viewer, "Unknown character or account: %s\r\n",
						   shown.c_str());
			    else
			    {
				    send_to_char_f(viewer, "'%s' given access to your locker.\n",
						   shown.c_str());
				    locker_access_changed(viewer, locker_name);
			    }
		    }))
		send_to_char("Failed to add access (database error).\r\n", ch);
}

static void locker_access_remove(P_char ch, P_char locker, const char *name)
{
	const std::string owner = escape_str(GET_NAME(locker));
	const std::string visitor = escape_str(name);
	const int racewar = GET_RACEWAR(locker);
	if (!sql_read_work_for(
		    ch,
		    [owner, visitor, racewar](MYSQL *connection, sql_rows *rows) -> unsigned int
		    {
			    bool granted = false;
			    if (const unsigned int error_code = locker_granted(
					connection, owner, visitor, racewar, &granted))
				    return error_code;
			    rows->push_back(locker_outcome(granted ? "removed" : "missing"));
			    return granted ? sql_execute(connection,
							 "DELETE FROM locker_access WHERE owner='" +
								 owner + "' AND visitor='" +
								 visitor + "'") :
					     0;
		    },
		    [shown = std::string(name), locker_name = std::string(GET_NAME(locker))](
			    P_char viewer, const sql_rows &rows)
		    {
			    if (rows.empty() || strcmp(rows[0][0], "removed"))
			    {
				    send_to_char(
					    "You can only remove someone who already has access.  Duh!\r\n",
					    viewer);
				    return;
			    }
			    send_to_char_f(viewer, "'%s' lost access to your locker.\n",
					   shown.c_str());
			    locker_access_changed(viewer, locker_name);
		    }))
		send_to_char("Failed to remove access (database error).\r\n", ch);
}

static bool locker_ready_to_enter(P_char ch)
{
	if (IS_IMMOBILE(ch) || IS_STUNNED(ch) || GET_STAT(ch) == STAT_SLEEPING)
	{
		send_to_char("You're not in much of a condition for that!\r\n", ch);
		return false;
	}
	if (affected_by_spell(ch, TAG_PVPDELAY))
	{
		send_to_char(
			"There is too much adrenaline pumping through your body right now.\r\n",
			ch);
		return false;
	}
	if (IS_RIDING(ch))
	{
		send_to_char(
			"If you really want your mount in your locker, you'll have to kill it first.\r\n",
			ch);
		return false;
	}
	if (get_linking_char(ch, LNK_RIDING))
	{
		send_to_char("Perhaps your rider should dismount first?\r\n", ch);
		return false;
	}
	return true;
}

/* Lockers with an entry read in flight, in lower case. Each counts as in use until its
 * rows arrive, so no second copy of it is loaded meanwhile, and its rows are never
 * older than a save of it. */
static std::set<std::string> locker_entries;

static std::string locker_entry_key(const char *locker_name)
{
	std::string key = locker_name;
	for (char &c : key)
		c = LOWER(c);
	return key;
}

/* What an entry reads, escaped on the game thread. */
struct locker_entry
{
	std::string locker, visitor;
	int visitor_pid, visitor_racewar;
	bool check_access; // entering someone else's locker
	bool read_contents; // false while the locker is in use: only the access verdict
	bool create; // an own account or guild locker is created if it is missing
	int owner_assoc_id, racewar, race; // for a created locker's row
};

/* On the writer, behind every save queued before it: the rows an entry needs, tagged in
 * their first column. "access" is the visitor's verdict (when asked), "locker" the
 * locker (id, racewar, race, public chest), "chest" each private chest (id, name,
 * password hash), and "item", "affect" and "extra" the contents of every chest (see
 * sql_locker_items_from_rows()). A missing account or guild locker gets its row and
 * public chest, as its first save would create them. */
static unsigned int locker_entry_read(MYSQL *connection, const locker_entry &entry, sql_rows *rows)
{
	const std::string by_name = "SELECT 'locker', id, racewar, race FROM lockers "
				    "WHERE locker_name='" +
				    entry.locker + "'";
	sql_rows found;
	unsigned int error_code = sql_select(connection, by_name, &found);
	if (!error_code && found.empty() && entry.create && entry.read_contents)
	{
		error_code = sql_execute(
			connection,
			sql_format(
				"INSERT INTO lockers (locker_name, owner_pid, owner_assoc_id, racewar, race) "
				"VALUES ('%s', NULL, %s, %d, %d)",
				entry.locker.c_str(),
				entry.owner_assoc_id > 0 ?
					std::to_string(entry.owner_assoc_id).c_str() :
					"NULL",
				entry.racewar, entry.race));
		if (!error_code)
			error_code = sql_select(connection, by_name, &found);
	}
	if (error_code)
		return error_code;

	if (entry.check_access)
	{
		bool granted = false;
		if (!found.empty())
		{
			sql_rows owner;
			error_code = sql_select(
				connection,
				sql_format(
					"SELECT 1 FROM lockers l JOIN account_characters ac ON ac.pid=l.owner_pid "
					"WHERE l.locker_name='%s' AND l.owner_pid=%d AND l.owner_assoc_id IS NULL "
					"AND l.racewar=%d AND ac.racewar=l.racewar AND ac.blocked=0 "
					"AND ac.deleted_at IS NULL LIMIT 1",
					entry.locker.c_str(), entry.visitor_pid,
					entry.visitor_racewar),
				&owner);
			granted = !owner.empty();
			if (!error_code && !granted)
				error_code = locker_granted(connection, entry.locker, entry.visitor,
							    atoi(found[0][2]), &granted);
			if (error_code)
				return error_code;
		}
		rows->push_back(locker_outcome("access"));
		rows->back().fields.emplace_back(granted ? "1" : "0");
	}
	if (found.empty() || !entry.read_contents)
		return 0;

	const std::string id = found[0][1];
	const std::string public_chest = "SELECT id FROM private_chests WHERE locker_id=" + id +
					 " AND is_public=1 ORDER BY id LIMIT 1";
	sql_rows chest;
	error_code = sql_select(connection, public_chest, &chest);
	if (!error_code && chest.empty())
	{
		error_code = sql_execute(connection,
					 "INSERT INTO private_chests (locker_id, chest_name, "
					 "is_public) VALUES (" +
						 id + ", 'public', 1)");
		if (!error_code)
			error_code = sql_select(connection, public_chest, &chest);
	}
	if (error_code || chest.empty())
		return error_code ? error_code : EIO;
	found[0].fields.push_back(chest[0].fields[0]);
	rows->push_back(found[0]);

	const std::string of_locker = " WHERE li.locker_id=" + id;
	if ((error_code =
		     sql_select(connection,
				"SELECT 'chest', id, chest_name, password_hash FROM private_chests "
				"WHERE locker_id=" +
					id + " AND is_public=0 ORDER BY id",
				rows)) ||
	    (error_code = sql_select(
		     connection,
		     "SELECT 'item', li.id, li.vnum, li.weight, li.cost, li.timer, li.extra_flags, "
		     "li.wear_flags, li.item_type, li.value0, li.value1, li.value2, li.value3, "
		     "li.value4, li.value5, li.value6, li.value7, li.name, li.short_descr, "
		     "li.description, li.action_descr, li.obj_uid, li.item_condition, li.bitvector1, "
		     "li.bitvector2, li.bitvector3, li.bitvector4, li.bitvector5, li.item_material, "
		     "li.chest_id, li.container_id, " SQL_ITEM_OWNER_COLUMNS
		     " FROM locker_items li LEFT JOIN item_current_owner current_item "
		     "ON current_item.item_uid=li.obj_uid " SQL_ITEM_OWNER_REVISION_JOIN +
			     of_locker + " ORDER BY li.id",
		     rows)) ||
	    (error_code = sql_select(
		     connection,
		     "SELECT 'affect', a.item_id, a.location, a.modifier "
		     "FROM locker_item_affects a JOIN locker_items li ON li.id=a.item_id" +
			     of_locker + " ORDER BY a.id",
		     rows)))
		return error_code;
	return sql_select(connection,
			  "SELECT 'extra', e.item_id, e.keyword, e.description "
			  "FROM locker_item_extra_descr e JOIN locker_items li ON li.id=e.item_id" +
				  of_locker + " ORDER BY e.id",
			  rows);
}

/* The first row the entry read tagged `tag`, or NULL. */
static const sql_row *locker_row(const sql_rows &rows, const char *tag)
{
	for (const sql_row &row : rows)
		if (row[0] && !strcmp(row[0], tag))
			return &row;
	return NULL;
}

/* Flat-file: the stored locker named name as an entry read gives it (no rows when there is
 * none), with its public chest. Private chests are MariaDB's. */
static bool flat_locker_read(const std::string &name, sql_rows *rows, flat_locker_chest *chest)
{
	const char *root = persistence_mode_flatfile_root();
	if (!root)
		return false;
	flatfile_locker_record locker;
	std::string error;
	const auto found = flatfile_locker_find(root, name, &locker, &error);
	if (found == flatfile_locker_result::not_found)
		return true;
	const auto stored = std::find_if(locker.chests.begin(), locker.chests.end(),
					 [](const auto &entry) { return entry.is_public; });
	if (found == flatfile_locker_result::ok && stored != locker.chests.end())
	{
		chest->owner = { item_owner_type::locker, locker.locker_id, stored->chest_id };
		if (flatfile_world_load_item_ownership(root, chest->owner, stored->items,
						       &chest->items, &chest->owner_revision,
						       &chest->identities, &error) ==
		    flatfile_corpse_ownership_result::ok)
		{
			sql_row row = locker_outcome("locker");
			for (const uint64_t field : { static_cast<uint64_t>(locker.locker_id),
						      static_cast<uint64_t>(locker.racewar),
						      static_cast<uint64_t>(locker.race),
						      static_cast<uint64_t>(stored->chest_id) })
				row.fields.push_back(std::to_string(field));
			rows->push_back(std::move(row));
			return true;
		}
	}
	logit(LOG_FILE, "Flat locker %s could not be read: %s", name.c_str(),
	      error.empty() ? "no public chest" : error.c_str());
	return false;
}

/* The locker's rows have arrived: enter it if ch is still at the door and may. */
static void locker_arrive(P_char ch, const std::string &name, int bValidate, bool busy, int room,
			  const sql_rows &rows, const locker_entered &entered,
			  const flat_locker_chest *flat = nullptr)
{
	if (ch->in_room != room)
	{
		send_to_char("You have moved away from the locker.\r\n", ch);
		return;
	}
	if (!locker_ready_to_enter(ch))
		return;

	char locker_name[500];
	strlcpy(locker_name, name.c_str(), sizeof(locker_name));
	P_char chLocker = load_locker_char(ch, locker_name, bValidate, busy, rows, flat);
	if (!chLocker)
		return;

	const int locker_room = create_new_locker(ch, chLocker, rows);
	if (!locker_room)
	{
		send_to_char("There are no free rooms available right now.  Please try later.\r\n",
			     ch);
		return;
	}
	entered(ch, chLocker, locker_room);
}

static void locker_enter(P_char ch, const char *locker_name, int bValidate, locker_entered entered)
{
	// A locker in use, or with an entry read in flight, is not loaded again.
	const bool busy = lockerName_is_inuse(const_cast<char *>(locker_name)) > 0;
	const std::string name = locker_name;
	const int room = ch->in_room;
	// Flat-file reads the stored locker here.
	if (!DB)
	{
		sql_rows rows;
		flat_locker_chest chest;
		if (!flat_locker_read(name, &rows, &chest))
		{
			send_to_char(
				"The locker could not be opened right now.  Please try later.\r\n",
				ch);
			return;
		}
		locker_arrive(ch, name, bValidate, busy, room, rows, entered, &chest);
		return;
	}
	const bool god = GET_LEVEL(ch) >= OVERLORD || god_check(ch->player.name);
	const locker_entry entry = { escape_str(locker_name),
				     escape_str(GET_NAME(ch)),
				     GET_PID(ch),
				     GET_RACEWAR(ch),
				     bValidate && !god,
				     !busy,
				     !bValidate,
				     strncmp(locker_name, "guild.", 6) ? 0 : atoi(locker_name + 6),
				     GET_RACEWAR(ch),
				     GET_RACE(ch) };
	const std::string key = locker_entry_key(locker_name);
	if (!busy)
		locker_entries.insert(key);
	const uint64_t runtime_id = ch->runtime_id;
	if (!sql_read_work(
		    [entry](MYSQL *connection, sql_rows *rows)
		    { return locker_entry_read(connection, entry, rows); },
		    [name, bValidate, busy, room, key, runtime_id, entered](bool ok,
									    const sql_rows &rows)
		    {
			    if (!busy)
				    locker_entries.erase(key);
			    P_char live = find_character_by_runtime_id(runtime_id);
			    if (!live)
				    return;
			    if (!ok)
				    send_to_char(
					    "The locker could not be opened right now.  Please try later.\r\n",
					    live);
			    else
				    locker_arrive(live, name, bValidate, busy, room, rows, entered);
		    }))
	{
		if (!busy)
			locker_entries.erase(key);
		send_to_char("The locker could not be opened right now.  Please try later.\r\n",
			     ch);
	}
}

/* The private chests an entry read, each put in the room with its items. */
static void create_private_chest_objects(StorageLocker *pLocker, const sql_rows &rows)
{
	int locker_id = pLocker->GetLockerId();
	int realRoom = pLocker->GetRealRoom();

	if (locker_id <= 0)
		return;

	for (const sql_row &row : rows)
	{
		if (!row[0] || strcmp(row[0], "chest") || !row[1])
			continue;
		int chest_id = atoi(row[1]);
		PrivateChest *pChest = new PrivateChest(chest_id, row[2] ? row[2] : "", row[3]);
		pLocker->AddPrivateChest(pChest);

		P_obj chest_obj = pChest->GetChestObj();
		if (chest_obj)
		{
			obj_to_room(chest_obj, realRoom);
			sql_locker_items_from_rows(rows, locker_id, chest_id, chest_obj);
		}
	}
}

static int create_new_locker(P_char ch, P_char locker, const sql_rows &rows)
{
	P_obj tmp_object = NULL, next_obj = NULL;
	int roomNum = -1;
	int realNum = -1;
	int dir;

	/* find a room to use... */
	roomNum = LOCKERS_START + 1;
	while (roomNum < (LOCKERS_START + LOCKERS_MAX) &&
	       world[realNum = real_room0(roomNum)].funct == storage_locker)
	{
		roomNum++;
	}

	if (roomNum >= (LOCKERS_START + LOCKERS_MAX))
	{
		wizlog(AVATAR, "All locker rooms in use or locker rooms not loaded!");
		return 0;
	}

	if (roomNum < (LOCKERS_START + LOCKERS_MAX))
	{
		// clear any leftover items from previous locker session
		for (tmp_object = world[realNum].contents; tmp_object; tmp_object = next_obj)
		{
			next_obj = tmp_object->next_content;
			extract_obj(tmp_object);
		}

		char roomNameBuf[500];

		/* check for a guild locker... */
		if (!strn_cmp("guild.", GET_NAME(locker), 6))
		{ /* its a guild locker... room name is based on assoc name */
			FILE *f = NULL;
			int assoc_num = 0;
			char Gbuf1[MAX_STR_NORMAL];

			assoc_num = atoi(GET_NAME(locker) + 6);
			snprintf(Gbuf1, MAX_STR_NORMAL, "%sasc.%u", ASC_DIR, assoc_num);
			f = fopen(Gbuf1, "r");
			if (f)
			{
				REQUIRED_FGETS(Gbuf1, MAX_STR_NORMAL, f);
				fclose(f);
			}
			else
			{
				strcpy(Gbuf1, "&+RUNKNOWN ASSOC&n");
			}
			snprintf(roomNameBuf, 500, "The Storage Locker for %s&n", Gbuf1);
		}
		else if (!strn_cmp("account.", GET_NAME(locker), 8))
		{ /* account locker - format: account.name.racewar.locker */
			char acct_name[MAX_INPUT_LENGTH];
			char *src = GET_NAME(locker) + 8;
			char *dot = strchr(src, '.');
			if (dot)
			{
				int len = dot - src;
				memcpy(acct_name, src, len);
				acct_name[len] = '\0';
			}
			else
				strcpy(acct_name, src);
			checked_snprintf(roomNameBuf, 500, "The Storage Locker for %s", acct_name);
		}
		else
		{ /* normal player locker */
			snprintf(roomNameBuf, 500, "The Storage Locker for %s", GET_NAME(locker));
			if (strrchr(roomNameBuf, '.'))
				*(strrchr(roomNameBuf, '.')) = '\0';
		}
		/* found a room to use!  set the room name, flags, etc */
		world[realNum].sector_type = LOCKERS_SECT_TYPE;
		// commenting this out for now
		// room names/description pointers can be shared, so we effectively have to leak
		// this memory because we don't know if it is being used somewhere else or not
		// if(world[realNum].name)
		//    str_free(world[realNum].name);
		world[realNum].name = str_dup(roomNameBuf);
		world[realNum].funct = storage_locker;
		world[realNum].room_flags = LOCKERS_ROOMFLAGS;

		if (world[realNum].description)
			str_free(world[realNum].description);
		world[realNum].description = str_dup(
			"   You are in a private storage locker. Items dropped here will be saved.\r\n"
			"\r\n"
			"&+WCommands:&n\r\n"
			"  eq sort <type>              - sort items\r\n"
			"  eq chest list               - list your chests\r\n"
			"  eq chest create <name> [pw] - create private chest (500p)\r\n"
			"  eq chest delete <name>      - delete empty chest\r\n"
			"  eq chest password <name> <pw|none>\r\n"
			"  eq log                      - view activity log\r\n"
			"  open <chest> [password]     - open a chest\r\n"
			"  close                       - close current chest\r\n");

		strcpy(roomNameBuf, LOCKERS_DOORSIGN);
		strcat(roomNameBuf, GET_NAME(ch));
		/* exit 0 will always be the way out... */
		if (!world[realNum].dir_option[0])
			CREATE(world[realNum].dir_option[0], room_direction_data, 1,
			       MEM_TAG_DIRDATA);

		world[realNum].dir_option[0]->to_room = ch->in_room;
		world[realNum].dir_option[0]->exit_info = EX_ISDOOR | EX_CLOSED;
		// world[realNum].dir_option[0]->general_description = NULL;
		// fixed issue in free_world() when trying to free a locker room's keyword
		if (world[realNum].dir_option[0]->keyword)
			str_free(world[realNum].dir_option[0]->keyword);
		world[realNum].dir_option[0]->keyword = str_dup("door");
		if (world[realNum].dir_option[0]->general_description)
			str_free(world[realNum].dir_option[0]->general_description);
		world[realNum].dir_option[0]->general_description = str_dup(roomNameBuf);
		world[realNum].dir_option[0]->key = -1;

		/* setup an extra description for the room which tells me the real locker pfile name */
		StorageLocker *pLocker = new StorageLocker(realNum, locker, ch);

		if (const sql_row *row = locker_row(rows, "locker"))
		{
			pLocker->SetLockerId(atoi((*row)[1]));
			pLocker->SetPublicChestId(atoi((*row)[4]));
		}

		pLocker->MakeChests(ch, writable_arg("none"));
		create_private_chest_objects(pLocker, rows);

		for (dir = 1; dir < NUM_EXITS; dir++)
		{
			if (world[realNum].dir_option[dir])
				world[realNum].dir_option[dir]->to_room = -1;
		}
	}
	else
	{
		/* failed to find a valid room to use as a locker */
		realNum = 0;
	}
	return realNum;
}

/* Release the transient room and chest state allocated for a loaded locker. */
static void free_locker(int roomNum)
{
	/* perform cleanup - basically just frees a couple pointers and marks the room as
	   available for reuse */

	if (-1 != roomNum)
	{
		str_free(world[roomNum].name);
		world[roomNum].name = NULL;
		world[roomNum].funct = NULL;
		if ((world[roomNum].dir_option[0]) &&
		    (world[roomNum].dir_option[0]->general_description))
		{
			str_free(world[roomNum].dir_option[0]->general_description);
			world[roomNum].dir_option[0]->general_description = NULL;
		}

		StorageLocker *p = GetChestList(roomNum);

		if (p)
			delete p;
	}
}

/* Load a locker character from the rows its entry read, while preserving occupancy
 * privacy and access rules. `busy` says the locker was in use when they were read. */
static P_char load_locker_char(P_char ch, char *esc_locker_name, int bValidateAccess, bool busy,
			       const sql_rows &rows, const flat_locker_chest *flat)
{
	P_char vict = NULL;

	if (!ch)
	{
		wizlog(56, "load_locker_char() in storage_lockers.c without ch : locker %s!",
		       esc_locker_name);
		logit(LOG_WIZ, "load_locker_char() in storage_lockers.c without ch : locker %s!",
		      esc_locker_name);
		sql_log(ch, PLAYERLOG,
			"load_locker_char() in storage_lockers.c without ch : locker %s!",
			esc_locker_name);
		logit(LOG_EXIT, "load_locker_char() called in storage_lockers.c without ch.");
		return NULL;
	}

	bool bPlayerIsGod = (GET_LEVEL(ch) >= OVERLORD || god_check(ch->player.name));
	const sql_row *access = locker_row(rows, "access");
	const bool has_access = access && (*access)[1] && !strcmp((*access)[1], "1");
	const sql_row *locker = locker_row(rows, "locker");

	// check if locker is currently in use
	if (busy || lockerName_is_inuse(esc_locker_name) > 0)
	{
		// Check if this is a pending deferred save rather than an
		// active user, and give a more appropriate message.
		bool deferred_save_pending = false;
		for (P_char chk = character_list; chk; chk = chk->next)
		{
			if (chk && GET_NAME(chk) && !str_cmp(esc_locker_name, GET_NAME(chk)) &&
			    get_scheduled(chk, event_deferredTerminalSave))
			{
				deferred_save_pending = true;
				break;
			}
		}

		if (deferred_save_pending)
		{
			send_to_char(
				"&+YSlow your roll.&n  The locker is still finishing its save from your last visit. "
				"This is exactly why you kept having issues before - let it finish and try again in a moment.\r\n",
				ch);
		}
		else
		{
			// An active occupant is inside.  If the requesting player
			// doesn't have access, don't reveal that the locker is in
			// use at all - just deny access.

			// Find the locker char in memory to check access.
			P_char active_locker_char = NULL;
			StorageLocker *pOcc = NULL;
			for (P_char chk = character_list; chk; chk = chk->next)
			{
				if (chk && GET_NAME(chk) &&
				    !str_cmp(esc_locker_name, GET_NAME(chk)) &&
				    chk->in_room != NOWHERE && IS_ROOM(chk->in_room, ROOM_LOCKER))
				{
					pOcc = GetChestList(chk->in_room);
					if (pOcc && pOcc->GetLockerChar() == chk)
					{
						active_locker_char = chk;
						break;
					}
				}
			}

			if (active_locker_char)
			{
				if (bValidateAccess && !bPlayerIsGod && !has_access)
				{
					// No access - don't reveal anything about the
					// locker's state or its occupant.
					send_to_char("You don't have access to that locker!\r\n",
						     ch);
					return NULL;
				}

				P_char occupant = pOcc->GetLockerUser();

				// Player has access (or is staff / entering own locker).
				if (occupant && occupant != ch)
				{
					send_to_char_f(
						ch,
						"%s is currently using that locker.  Please try later.\r\n",
						GET_NAME(occupant));

					// Notify the active occupant that someone is knocking.
					send_to_char_f(
						occupant,
						"&+YA member of the &+YStorage Locker Safety Commission&n leans in and whispers, "
						"'%s is trying to get in here. You might want to wrap things up.'&n\r\n",
						GET_NAME(ch));
				}
				else
				{
					send_to_char(
						"Someone is currently using that locker.  Please try later.\r\n",
						ch);
				}
			}
			else
			{
				send_to_char(
					"Someone is currently using that locker.  Please try later.\r\n",
					ch);
			}
		}
		return NULL;
	}

	if (locker)
	{
		// validate access
		if (bValidateAccess && !bPlayerIsGod && !has_access)
		{
			send_to_char("You don't have access to that locker!\r\n", ch);
			return NULL;
		}

		// check racewar side
		if (bValidateAccess)
		{
			if (!bPlayerIsGod && GET_RACEWAR(ch) != atoi((*locker)[2]))
			{
				send_to_char(
					"Well, THIS is interesting... You have access to a locker on the other racewar\n"
					"side.  A special log is being generated which will be followed up on to\n"
					"determine if this was a mistake, or an attempt at cheating.\n",
					ch);
				wizlog(56,
				       "&+RPOSSIBLE CHEATING:&n %s is trying to access opposite racewar side locker %s",
				       GET_NAME(ch), esc_locker_name);
				logit(LOG_WIZ,
				      "POSSIBLE CHEATING: %s is trying to access opposite racewar side locker %s",
				      GET_NAME(ch), esc_locker_name);
				sql_log(ch, PLAYERLOG,
					"&+RPOSSIBLE CHEATING:&n trying to access opposite racewar side locker %s",
					esc_locker_name);
				return NULL;
			}
		}

		// the locker character holds the public chest's items
		std::vector<P_obj> flat_items;
		if (flat && !flat->items.empty() &&
		    !player_load_item_graph_materialize_detached(flat->items, flat->identities,
								 flat->owner, flat->owner_revision,
								 false, true, &flat_items, nullptr))
		{
			send_to_char(
				"The locker could not be opened right now.  Please try later.\r\n",
				ch);
			return NULL;
		}
		vict = (P_char)mm_get(dead_mob_pool);
		if (!vict)
			return NULL;
		clear_char(vict);
		ensure_pconly_pool();
		vict->only.pc = (struct pc_only_data *)mm_get(dead_pconly_pool);
		memset(vict->only.pc, 0, sizeof(struct pc_only_data));
		vict->only.pc->aggressive = -1;
		vict->desc = NULL;
		vict->player.name = str_dup(esc_locker_name);
		// just in case their racewar side happened to change mysteriously..
		GET_RACEWAR(vict) = bValidateAccess ? atoi((*locker)[2]) : GET_RACEWAR(ch);
		GET_RACE(vict) = atoi((*locker)[3]);
		if (flat)
			for (auto item = flat_items.rbegin(); item != flat_items.rend(); ++item)
			{
				(*item)->next_content = vict->carrying;
				vict->carrying = *item;
			}
		else
			vict->carrying = sql_locker_items_from_rows(rows, atoi((*locker)[1]),
								    atoi((*locker)[4]), NULL);
		for (P_obj obj = vict->carrying; obj; obj = obj->next_content)
		{
			obj->loc_p = LOC_CARRIED;
			obj->loc.carrying = vict;
		}
	}
	else
	{
		// locker doesn't exist - need to create new
		if (bValidateAccess)
		{
			send_to_char("You don't have access to that locker!\r\n", ch);
			return NULL;
		}

		// allocate new locker char
		vict = (P_char)mm_get(dead_mob_pool);
		if (!vict)
			return NULL;
		clear_char(vict);
		ensure_pconly_pool();
		vict->only.pc = (struct pc_only_data *)mm_get(dead_pconly_pool);
		vict->only.pc->aggressive = -1;
		vict->only.pc->zone_trophy = NULL;
		vict->desc = NULL;

		create_locker_char(ch, vict, esc_locker_name);
	}

	// insert in list
	vict->next = character_list;
	character_list = vict;

	// saving info for teleport return command
	vict->specials.was_in_room = vict->in_room;

	char_to_room(vict, real_room0(LOCKERS_START), -2);

	return vict;
}

static P_char create_locker_char(P_char chOwner, P_char ch, char *esc_locker_name)
{
	/* create a new pfile with 'esc_locker_name' name */

	ch->player.name = str_dup(esc_locker_name);
	GET_RACEWAR(ch) = GET_RACEWAR(chOwner);
	GET_RACE(ch) = GET_RACE(chOwner);
	//  init_char(ch);
	strcpy(ch->only.pc->pwd, chOwner->only.pc->pwd);
	// Stored by the async locker writer once it holds something or its user leaves.
	return ch;
}

static int save_locker_char(P_char ch, int bTerminal)
{
	StorageLocker *pLocker = locker_current_or_error(ch, "Error: which locker are you in?\r\n");

	if (!pLocker)
	{
		logit(LOG_OBJ, "Locker save failed: no locker context for %s", GET_NAME(ch));
		logit(LOG_FILE, "Locker save failed: no locker context for %s", GET_NAME(ch));
		return 0;
	}
	if (item_movement_transaction_player_busy(ch))
	{
		logit(LOG_DEBUG,
		      "Locker save deferred: ownership movement pending user=%s locker_id=%d",
		      GET_NAME(ch), pLocker->GetLockerId());
		return 1;
	}

	P_char chLocker = pLocker->GetLockerChar();
	if (!chLocker)
	{
		logit(LOG_OBJ, "Locker save failed: no locker character loaded for %s",
		      GET_NAME(ch));
		logit(LOG_FILE, "Locker save failed: no locker character loaded for %s",
		      GET_NAME(ch));
		return 0;
	}

	if (persistence_trace_enabled())
		logit(LOG_DEBUG,
		      "Locker save start: phase=%s user=%s locker_char=%s locker_id=%d room=%d(%s) item_count=%d carried=%d was_in_room=%d txn=%s",
		      bTerminal ? "terminal" : "async", GET_NAME(ch), GET_NAME(chLocker),
		      pLocker->GetLockerId(), pLocker->GetRealRoom(),
		      locker_room_name(pLocker->GetRealRoom()), pLocker->m_itemCount,
		      locker_count_carried_objects(chLocker),
		      (ch->specials.was_in_room != NOWHERE) ? ch->specials.was_in_room : -1,
		      sql_in_transaction() ? "existing" : "new");

	/* Move room/chest contents onto locker char (LockerToPFile queues each
	 * private chest on the persistence writer). Then mark async dirty and
	 * return; the writer saves the public inventory from its snapshot. */
	if (!pLocker->LockerToPFile())
	{
		locker_log_save_failure(pLocker, ch, chLocker, "locker-to-pfile",
					"LockerToPFile failed before async mark");
		pLocker->PFileToLocker();
		return 0;
	}

	if (bTerminal)
	{
		/* Terminal mid-function path is rare (almost all leave goes through
		 * locker_handle_leave). Keep fail-closed: mark terminal async. */
		if (!locker_async_mark_dirty(chLocker, ch, 1, "save_locker_char-terminal"))
		{
			locker_log_save_failure(pLocker, ch, chLocker, "terminal-async-refused",
						"the async locker writer refused the save");
			pLocker->PFileToLocker();
			return 0;
		}
		return 1;
	}

	/* Non-terminal: coalesce on dirty slot; one snapshot per pulse globally. */
	if (!locker_async_mark_dirty(chLocker, ch, 0, "save_locker_char-nonterminal"))
	{
		locker_log_save_failure(pLocker, ch, chLocker, "async-refused",
					"the async locker writer refused the save");
		pLocker->PFileToLocker();
		return 0;
	}
	return 1;
}

bool StorageLocker::LockerToPFile(void)
{
	bool ok = true;

	// first, save private chest items directly to db with their chest_id
	int private_chest_count = 0;
	for (LockerChest *p = m_pChestList; p; p = p->m_pNextInChain)
	{
		if (p->IsPrivateChest())
		{
			++private_chest_count;
			P_obj chest_obj = p->GetChestObj();
			if (!chest_obj)
			{
				logit(LOG_DEBUG,
				      "LockerToPFile: missing chest object for private chest %d",
				      p->GetChestId());
				ok = false;
				continue;
			}
			int chest_contents = 0;
			for (P_obj cur = chest_obj->contains; cur; cur = cur->next_content)
				++chest_contents;
			if (persistence_trace_enabled())
				logit(LOG_DEBUG,
				      "LockerToPFile: saving private chest locker_id=%d chest_id=%d chest_vnum=%d chest_uid=%lu contains=%d room=%d",
				      m_lockerId, p->GetChestId(),
				      (chest_obj->R_num >= 0) ?
					      obj_index[chest_obj->R_num].virtual_number :
					      -1,
				      chest_obj->obj_uid, chest_contents, m_realRoom);
			if (!sql_save_private_chest_items(m_lockerId, p->GetChestId(), chest_obj))
			{
				logit(LOG_DEBUG,
				      "LockerToPFile: failed to save private chest locker_id=%d chest_id=%d chest_vnum=%d chest_uid=%lu contains=%d",
				      m_lockerId, p->GetChestId(),
				      (chest_obj->R_num >= 0) ?
					      obj_index[chest_obj->R_num].virtual_number :
					      -1,
				      chest_obj->obj_uid, chest_contents);
				ok = false;
			}
		}
	}
	if (persistence_trace_enabled())
		logit(LOG_DEBUG,
		      "LockerToPFile: private chest scan complete locker_id=%d room=%d private_chests=%d ok=%d",
		      m_lockerId, m_realRoom, private_chest_count, ok ? 1 : 0);

	if (!ok)
	{
		logit(LOG_DEBUG,
		      "LockerToPFile: aborting before non-private chest moves locker_id=%d room=%d",
		      m_lockerId, m_realRoom);
		return false;
	}

	// now handle non-private chests - move items to locker char
	for (P_obj tmp_object : locker_snapshot_room_contents(m_realRoom))
	{
		if (!tmp_object || tmp_object->type == ITEM_CORPSE)
			continue;
		LockerChest *chest = FindChestForObject(tmp_object);
		if (chest)
		{
			if (chest->IsPrivateChest())
				continue;

			if (persistence_trace_enabled())
			{
				int inner_count = 0;
				for (P_obj cur = tmp_object->contains; cur; cur = cur->next_content)
					++inner_count;
				logit(LOG_DEBUG,
				      "LockerToPFile: moving public chest contents locker_id=%d chest_id=%d chest_vnum=%d chest_uid=%lu contains=%d",
				      m_lockerId, chest->GetChestId(),
				      (tmp_object->R_num >= 0) ?
					      obj_index[tmp_object->R_num].virtual_number :
					      -1,
				      tmp_object->obj_uid, inner_count);
			}

			// not a private chest, dump contents to locker char
			for (P_obj innerObj = tmp_object->contains; tmp_object->contains;
			     innerObj = tmp_object->contains)
			{
				obj_from_obj(innerObj);
				obj_to_char(innerObj, m_chLocker);
			}
		}
		else
		{
			if (persistence_trace_enabled())
				logit(LOG_DEBUG,
				      "LockerToPFile: moving loose room object locker_id=%d room=%d vnum=%d uid=%lu contains=%s",
				      m_lockerId, m_realRoom,
				      (tmp_object->R_num >= 0) ?
					      obj_index[tmp_object->R_num].virtual_number :
					      -1,
				      tmp_object->obj_uid, tmp_object->contains ? "yes" : "no");
			obj_from_room(tmp_object);
			obj_to_char(tmp_object, m_chLocker);
		}
	}
	return ok;
}

void StorageLocker::PFileToLocker(void)
{
	/* drop everything chLocker is holding into rroom - sorting into chests if they're present */
	int nCount = 0;

	for (P_obj tmp_object : locker_snapshot_char_carrying(m_chLocker))
	{
		++nCount;
		if (persistence_trace_enabled())
			logit(LOG_DEBUG,
			      "PFileToLocker: moving carried object locker_id=%d room=%d vnum=%d uid=%lu type=%d contains=%s",
			      m_lockerId, m_realRoom,
			      (tmp_object->R_num >= 0) ?
				      obj_index[tmp_object->R_num].virtual_number :
				      -1,
			      tmp_object->obj_uid, tmp_object->type,
			      tmp_object->contains ? "yes" : "no");
		obj_from_char(tmp_object);
		if ((tmp_object->type == ITEM_MONEY) || !PutInProperChest(tmp_object))
		{
			// Items that don't fit any chest (including money and rejected
			// containers) go on the locker room floor so the player can see
			// and interact with them.  They will be picked up on the next
			// LockerToPFile() or PFileToLocker() cycle.
			obj_to_room(tmp_object, m_realRoom);
		}
	}
	m_itemCount = nCount;

	if (m_bIValue)
		SortIValues();
}

static bool check_for_artisInRoom(P_char ch, int rroom)
{
	P_obj tmp_object, next_obj;
	bool found = false;

	for (tmp_object = world[rroom].contents; tmp_object; tmp_object = next_obj)
	{
		next_obj = tmp_object->next_content;

		if (IS_SET(tmp_object->extra_flags, ITEM_ARTIFACT))
		{
			/* okay, they can't store that here... tell them so, and stick it back
			   in their inventory */
			obj_from_room(tmp_object);
			obj_to_char(tmp_object, ch);
			act("&+LThe overpowering will of $p &+Ldenies $n&+L's attempt to release it.",
			    TRUE, ch, tmp_object, 0, TO_ROOM);
			act("&+LThe overpowering will of $p &+Ldefies you as it flies back into your hands.",
			    TRUE, ch, tmp_object, 0, TO_CHAR);
			wizlog(56, "Artifact %s (%d) returns to %s's hands in room %d.",
			       tmp_object->short_description,
			       obj_index[tmp_object->R_num].virtual_number, J_NAME(ch),
			       world[ch->in_room].number);
			logit(LOG_OBJ, "Artifact %s (%d) returns to %s's hands in room %d.",
			      tmp_object->short_description,
			      obj_index[tmp_object->R_num].virtual_number, J_NAME(ch),
			      world[ch->in_room].number);
			found = true;
		}
	}
	return found;
}

static int lockerName_is_inuse(char *lockerName)
{
	P_char chLocker = NULL;
	// An entry whose rows are still being read counts as a user.
	int nCnt = locker_entries.count(locker_entry_key(lockerName));

	for (chLocker = character_list; chLocker; chLocker = chLocker->next)
	{
		if (chLocker && GET_NAME(chLocker) && !str_cmp(lockerName, GET_NAME(chLocker)))
		{
			/* Count any matching character, whether or not an active
			 * StorageLocker wrapper still exists.  A locker char with a
			 * pending deferred terminal save has no StorageLocker (the
			 * room was freed) but is still alive in memory holding items.
			 * It must be counted as "in use" to prevent the player from
			 * re-entering the same locker and loading a duplicate before
			 * the save event fires. */
			StorageLocker *pLocker = NULL;

			if (chLocker->in_room != NOWHERE && IS_ROOM(chLocker->in_room, ROOM_LOCKER))
				pLocker = GetChestList(chLocker->in_room);

			if (pLocker && pLocker->GetLockerChar() == chLocker)
			{
				nCnt++;
			}
			else if (get_scheduled(chLocker, event_deferredTerminalSave))
			{
				/* Legacy deferred save pending - locker char is still active. */
				nCnt++;
				logit(LOG_DEBUG,
				      "lockerName_is_inuse: counting locker char %s with pending deferred save (room=%d)",
				      GET_NAME(chLocker), chLocker->in_room);
			}
			else if (locker_async_name_busy(GET_NAME(chLocker)))
			{
				/* Async pump has this locker dirty or in-flight. */
				nCnt++;
				logit(LOG_DEBUG,
				      "lockerName_is_inuse: counting locker %s with async save pending",
				      GET_NAME(chLocker));
			}
			else
			{
				logit(LOG_DEBUG,
				      "lockerName_is_inuse: ignoring stale locker char %s room=%d desc=%p locker=%p",
				      GET_NAME(chLocker), chLocker->in_room, (void *)chLocker->desc,
				      (void *)pLocker);
			}
		}
	}
	return nCnt;
}

/*
 * Whether `char_name`'s personal locker ("<name>.locker") is open or has a
 * save in flight.  A rename must wait for it, because the rename moves the
 * locker's rows to the new name, and the open locker would still save under
 * the old one.
 */
bool personal_locker_in_use(const char *char_name)
{
	char locker_name[MAX_STRING_LENGTH];

	snprintf(locker_name, sizeof(locker_name), "%s.locker", char_name);
	return lockerName_is_inuse(locker_name) > 0 || locker_async_name_busy(locker_name);
}

void StorageLocker::SortIValues(void)
{
	P_obj object, rest, pObjList;
	LockerChest *pChests = m_pChestList;
	int value;

	if (m_bIValue)
	{
		while (pChests)
		{
			rest = pChests->m_pChestObject->contains;
			pChests->m_pChestObject->contains = NULL;

			// While there is more to sort..
			while (rest)
			{
				// Remove one object from the list
				object = rest;
				rest = rest->next_content;
				object->next_content = NULL;
				value = itemvalue(object);

				// Put into right spot in chest.
				// If value is smallest, insert to head of list.
				if (!pChests->m_pChestObject->contains ||
				    value <= itemvalue(pChests->m_pChestObject->contains))
				{
					object->next_content = pChests->m_pChestObject->contains;
					pChests->m_pChestObject->contains = object;
				}
				else
				{
					// Walk through the list to find the correct spot.
					pObjList = pChests->m_pChestObject->contains;
					while (pObjList->next_content &&
					       value > itemvalue(pObjList->next_content))
						pObjList = pObjList->next_content;

					// Insert the object into the list.
					object->next_content = pObjList->next_content;
					pObjList->next_content = object;
				}
			}
			pChests = pChests->m_pNextInChain;
		}
	}
	else
		logit(LOG_DEBUG, "SortIValues called when m_bIValue is not set!");
	m_bIValue = false;
}

std::string remove_all_locker_access_statement(const char *name)
{
	return "DELETE FROM locker_access WHERE visitor='" + escape_str(name) + "'";
}

static void locker_access_transferAccess(P_char chLocker, P_char ch)
{
	// Set list of names that have access to locker.
	std::vector<std::string> names;
	char ch_name[MAX_INPUT_LENGTH];
	for (char *pIndex = chLocker->player.description; pIndex && *pIndex;)
	{
		pIndex = one_argument(pIndex, ch_name);
		if (*ch_name)
			names.emplace_back(ch_name);
	}
	if (names.empty())
	{
		send_to_char("No old accesses found.\n", ch);
		return;
	}

	const std::string owner = escape_str(GET_NAME(chLocker));
	const int racewar = GET_RACEWAR(chLocker);
	std::vector<std::string> visitors;
	for (const std::string &name : names)
		visitors.push_back(escape_str(name.c_str()));
	if (!sql_read_work_for(
		    ch,
		    [owner, racewar, visitors](MYSQL *connection, sql_rows *rows) -> unsigned int
		    {
			    for (const std::string &visitor : visitors)
			    {
				    bool granted = false;
				    unsigned int error_code = locker_granted(
					    connection, owner, visitor, racewar, &granted);
				    if (!error_code && !granted)
					    error_code = sql_execute(
						    connection,
						    "INSERT INTO locker_access (owner, visitor) VALUES ('" +
							    owner + "', '" + visitor + "')");
				    if (error_code)
					    return error_code;
				    rows->push_back(locker_outcome(granted ? "has" : "given"));
			    }
			    return 0;
		    },
		    [names](P_char viewer, const sql_rows &rows)
		    {
			    for (size_t i = 0; i < rows.size() && i < names.size(); i++)
				    if (strcmp(rows[i][0], "has"))
					    send_to_char_f(viewer,
							   "'%s' given access to your locker.\n",
							   names[i].c_str());
				    else
					    send_to_char_f(
						    viewer,
						    "'%s' already has access to your locker.\n",
						    names[i].c_str());
		    }))
		send_to_char("No old accesses found.\n", ch);
}

// ============================================================================
// private chest commands
// ============================================================================

/* The id of the chest `name` names in the locker: a private chest, or "public". */
static int locker_chest_id(StorageLocker *pLocker, const char *name)
{
	if (!str_cmp(name, "public"))
		return pLocker->GetPublicChestId();
	PrivateChest *chest = pLocker->FindPrivateChest(name);
	return chest ? chest->GetChestId() : 0;
}

/* Private chests live in memory while their locker is open: each change is made there
 * at once and queued on the persistence writer. A new chest's id comes from its row,
 * created on the writer. */
static int locker_chestcmd(P_char ch, char *arg)
{
	if (!ch || !ch->desc)
		return FALSE;
	StorageLocker *pLocker = locker_current_or_error(ch, "Error: no locker found.\r\n");
	if (!pLocker)
	{
		return TRUE;
	}

	if (!locker_require_owner(pLocker, ch, "Only the locker owner can manage chests.\r\n"))
	{
		return TRUE;
	}

	int locker_id = pLocker->GetLockerId();
	if (locker_id <= 0)
	{
		send_to_char("Locker not properly initialized.\r\n", ch);
		return TRUE;
	}

	char arg1[MAX_INPUT_LENGTH], arg2[MAX_INPUT_LENGTH], arg3[MAX_INPUT_LENGTH];
	arg = one_argument(arg, arg1);
	arg = one_argument(arg, arg2);
	strcpy(arg3, arg);

	if (is_abbrev(arg1, "list") || !arg1[0])
	{
		std::vector<PrivateChest *> chests = pLocker->GetPrivateChests();
		std::sort(chests.begin(), chests.end(), [](PrivateChest *left, PrivateChest *right)
			  { return strcasecmp(left->GetName(), right->GetName()) < 0; });
		send_to_char("&+WYour chests:&n\r\n", ch);
		send_to_char("  public &+G(public)&n\r\n", ch);
		for (PrivateChest *chest : chests)
			send_to_char_f(ch, "  %s%s\r\n", chest->GetName(),
				       chest->GetPasswordHash().empty() ? "" : " &+Y(password)&n");
		send_to_char_f(ch, "\r\nPrivate chests: %zu/5\r\n", chests.size());
		return TRUE;
	}

	if (is_abbrev(arg1, "create"))
	{
		if (!arg2[0])
		{
			send_to_char("Usage: eq chest create <name> [password]\r\n", ch);
			return TRUE;
		}
		if (strlen(arg3) > BCRYPT_PASSWORD_MAX_BYTES)
		{
			send_to_char("Chest passwords must be at most 72 bytes.\r\n", ch);
			return TRUE;
		}

		auto finish = [locker_id, name = std::string(arg2)](P_desc completed_desc, int,
								    const char *hash)
		{
			P_char actor = completed_desc->character;
			StorageLocker *locker = locker_current(actor);
			if (!locker || locker->GetLockerId() != locker_id ||
			    !locker_require_owner(locker, actor,
						  "Only the locker owner can manage chests.\r\n"))
				return;
			if (hash && !is_bcrypt_hash(hash))
			{
				send_to_char("Failed to hash chest password.\r\n", actor);
				return;
			}
			const std::string stored_hash = hash ? hash : "";
			const std::string escaped_name = escape_str(name.c_str());
			const std::string escaped_hash = hash ? "'" + escape_str(hash) + "'" :
								std::string("NULL");
			// The row is created on the writer, which counts the chests there.
			if (!sql_read_work_for(
				    actor,
				    [locker_id, escaped_name, escaped_hash](
					    MYSQL *connection, sql_rows *rows) -> unsigned int
				    {
					    sql_rows count;
					    if (const unsigned int error_code = sql_select(
							connection,
							sql_format(
								"SELECT COUNT(*) FROM private_chests "
								"WHERE locker_id=%d AND is_public=0",
								locker_id),
							&count))
						    return error_code;
					    if (count.empty() || !count[0][0] ||
						atoi(count[0][0]) >= 5)
					    {
						    rows->push_back(locker_outcome("full"));
						    return 0;
					    }
					    const unsigned int error_code = sql_execute(
						    connection,
						    sql_format(
							    "INSERT INTO private_chests (locker_id, chest_name, password_hash, is_public) "
							    "VALUES (%d, '%s', %s, 0)",
							    locker_id, escaped_name.c_str(),
							    escaped_hash.c_str()));
					    if (error_code == ER_DUP_ENTRY)
					    {
						    rows->push_back(locker_outcome("taken"));
						    return 0;
					    }
					    rows->push_back(locker_outcome("created"));
					    rows->back().fields.emplace_back(
						    std::to_string(mysql_insert_id(connection)));
					    return error_code;
				    },
				    [locker_id, name, stored_hash](P_char payer,
								   const sql_rows &rows)
				    {
					    const char *outcome = rows.empty() ? "" : rows[0][0];
					    if (!strcmp(outcome, "full"))
					    {
						    send_to_char(
							    "You already have the maximum of 5 private chests.\r\n",
							    payer);
						    return;
					    }
					    if (strcmp(outcome, "created") || !rows[0][1])
					    {
						    send_to_char(
							    "Failed to create chest. Name may already be in use.\r\n",
							    payer);
						    return;
					    }
					    const int chest_id = atoi(rows[0][1]);
					    int chest_cost = 500000;
					    if (GET_MONEY(payer) < chest_cost)
					    {
						    if (SUB_BALANCE(payer, chest_cost, 0) != 0)
						    {
							    sql_queue(
								    "DELETE FROM private_chests WHERE id=%d AND is_public=0",
								    chest_id);
							    send_to_char(
								    "The bank could not complete the chest payment.\r\n",
								    payer);
							    return;
						    }
					    }
					    else
						    SUB_MONEY(payer, chest_cost, 0);
					    // The chest is in the room at once while the open_locker is open.
					    StorageLocker *open_locker = locker_current(payer);
					    if (open_locker &&
						open_locker->GetLockerId() == locker_id &&
						!open_locker->FindPrivateChest(name.c_str()))
					    {
						    PrivateChest *chest = new PrivateChest(
							    chest_id, name.c_str(),
							    stored_hash.empty() ?
								    NULL :
								    stored_hash.c_str());
						    open_locker->AddPrivateChest(chest);
						    if (chest->GetChestObj())
							    obj_to_room(chest->GetChestObj(),
									open_locker->GetRealRoom());
					    }
					    send_to_char_f(
						    payer,
						    "Private chest '%s' created for 500 platinum.%s\r\n",
						    name.c_str(),
						    stored_hash.empty() ? "" : " Password set.");
				    }))
				send_to_char(
					"Failed to create chest. Name may already be in use.\r\n",
					actor);
		};
		if (!arg3[0])
			finish(ch->desc, 1, nullptr);
		else if (!password_async_start(
				 ch->desc, password_work_submit(arg3, nullptr, nullptr, 0, 0),
				 nullptr,
				 [finish](P_desc completed_desc, int valid, const char *hash)
				 {
					 if (!hash)
					 {
						 send_to_char("Failed to hash chest password.\r\n",
							      completed_desc->character);
						 return;
					 }
					 finish(completed_desc, valid, hash);
				 }))
			send_to_char("Password service is busy; try again later.\r\n", ch);
		return TRUE;
	}

	if (is_abbrev(arg1, "delete"))
	{
		if (!arg2[0])
		{
			send_to_char("Usage: eq chest delete <name>\r\n", ch);
			return TRUE;
		}

		PrivateChest *chest = pLocker->FindPrivateChest(arg2);
		if (!chest)
		{
			send_to_char("Chest not found.\r\n", ch);
			return TRUE;
		}

		if (!chest->GetChestObj() || chest->GetChestObj()->contains)
		{
			send_to_char("Cannot delete a non-empty or unavailable private chest.\r\n",
				     ch);
			return TRUE;
		}

		// Memory holds the chest empty, so its stored rows go with it.
		const int chest_id = chest->GetChestId();
		sql_queue_statements(
			{ sql_format("DELETE FROM locker_items WHERE locker_id=%d AND chest_id=%d",
				     locker_id, chest_id),
			  sql_format("DELETE FROM private_chests WHERE id=%d AND is_public=0",
				     chest_id) });
		pLocker->RemovePrivateChest(chest);
		send_to_char_f(ch, "Chest '%s' deleted.\r\n", arg2);
		return TRUE;
	}

	if (is_abbrev(arg1, "password"))
	{
		if (!arg2[0])
		{
			send_to_char("Usage: eq chest password <chest> <newpassword>\r\n", ch);
			send_to_char(
				"       eq chest password <chest> none  (to remove password)\r\n",
				ch);
			return TRUE;
		}

		PrivateChest *chest = pLocker->FindPrivateChest(arg2);
		if (!chest)
		{
			send_to_char("Chest not found.\r\n", ch);
			return TRUE;
		}
		const int chest_id = chest->GetChestId();

		if (!arg3[0] || !strcasecmp(arg3, "none"))
		{
			chest->SetPasswordHash(NULL);
			sql_queue(
				"UPDATE private_chests SET password_hash=NULL WHERE id=%d AND is_public=0",
				chest_id);
			send_to_char_f(ch, "Password removed from chest '%s'.\r\n", arg2);
		}
		else
		{
			if (strlen(arg3) > BCRYPT_PASSWORD_MAX_BYTES)
			{
				send_to_char("Chest passwords must be at most 72 bytes.\r\n", ch);
				return TRUE;
			}
			if (!password_async_start(
				    ch->desc, password_work_submit(arg3, nullptr, nullptr, 0, 0),
				    nullptr,
				    [locker_id, chest_id, name = std::string(arg2)](
					    P_desc completed_desc, int, const char *hash)
				    {
					    P_char actor = completed_desc->character;
					    StorageLocker *locker = locker_current(actor);
					    if (!locker || locker->GetLockerId() != locker_id ||
						locker_chest_id(locker, name.c_str()) != chest_id ||
						!locker_require_owner(
							locker, actor,
							"Only the locker owner can manage chests.\r\n"))
						    return;
					    if (!hash || !is_bcrypt_hash(hash))
					    {
						    send_to_char(
							    "Failed to set chest password.\r\n",
							    actor);
						    return;
					    }
					    locker->FindPrivateChest(name.c_str())
						    ->SetPasswordHash(hash);
					    sql_queue(
						    "UPDATE private_chests SET password_hash='%s' WHERE id=%d AND is_public=0",
						    escape_str(hash).c_str(), chest_id);
					    send_to_char_f(actor,
							   "Password set for chest '%s'.\r\n",
							   name.c_str());
				    }))
				send_to_char("Password service is busy; try again later.\r\n", ch);
		}
		return TRUE;
	}

	send_to_char("Usage: eq chest list\r\n", ch);
	send_to_char("       eq chest create <name> [password]\r\n", ch);
	send_to_char("       eq chest delete <name>\r\n", ch);
	send_to_char("       eq chest password <name> <newpassword|none>\r\n", ch);
	return TRUE;
}

static int locker_opencmd(P_char ch, char *arg)
{
	if (!ch || !ch->desc)
		return FALSE;
	StorageLocker *pLocker = locker_current(ch);
	if (!pLocker)
		return FALSE;

	int locker_id = pLocker->GetLockerId();
	if (locker_id <= 0)
		return FALSE;

	char arg1[MAX_INPUT_LENGTH], arg2[MAX_INPUT_LENGTH];
	arg = one_argument(arg, arg1);
	strcpy(arg2, arg);

	if (!arg1[0])
		return FALSE;

	int chest_id = locker_chest_id(pLocker, arg1);
	if (chest_id <= 0)
		return FALSE;

	P_char locker_char = pLocker->GetLockerChar();
	bool is_owner = locker_char && esc_locker_name_matches_player(GET_NAME(locker_char), ch);
	auto finish = [locker_id, chest_id, name = std::string(arg1)](P_desc completed_desc,
								      int valid, const char *)
	{
		P_char actor = completed_desc->character;
		StorageLocker *locker = locker_current(actor);
		if (!locker || locker->GetLockerId() != locker_id ||
		    locker_chest_id(locker, name.c_str()) != chest_id)
			return;
		if (!valid)
		{
			send_to_char("Wrong password.\r\n", actor);
			sql_log_chest_activity(locker_id, chest_id, GET_NAME(actor),
					       CHEST_ACTION_FAIL, NULL);
			return;
		}
		locker->SetCurrentChestId(chest_id);
		send_to_char_f(actor, "You open the '%s' chest.\r\n", name.c_str());
		sql_log_chest_activity(locker_id, chest_id, GET_NAME(actor), CHEST_ACTION_OPEN,
				       NULL);
	};
	if (is_owner)
	{
		finish(ch->desc, 1, nullptr);
		return TRUE;
	}
	if (strlen(arg2) > BCRYPT_PASSWORD_MAX_BYTES)
	{
		finish(ch->desc, 0, nullptr);
		return TRUE;
	}
	PrivateChest *chest = pLocker->FindPrivateChest(arg1);
	const std::string hash = chest ? chest->GetPasswordHash() : std::string();
	if (hash.empty() || !arg2[0])
	{
		finish(ch->desc, hash.empty() && !arg2[0], nullptr);
		return TRUE;
	}
	bool submitted = password_async_start(
		ch->desc, password_work_submit(arg2, hash.c_str(), nullptr, 1, 1), hash.c_str(),
		[finish, name = std::string(arg1), hash](P_desc completed_desc, int valid,
							 const char *upgrade)
		{
			// A racing password change fails closed; a rehash replaces the
			// password it checked, never a newer one.
			StorageLocker *locker = locker_current(completed_desc->character);
			PrivateChest *current = locker ? locker->FindPrivateChest(name.c_str()) :
							 NULL;
			const bool same = current && current->GetPasswordHash() == hash &&
					  (!upgrade || is_bcrypt_hash(upgrade));
			if (valid && same && upgrade)
			{
				current->SetPasswordHash(upgrade);
				sql_queue(
					"UPDATE private_chests SET password_hash='%s' WHERE id=%d AND password_hash='%s'",
					escape_str(upgrade).c_str(), current->GetChestId(),
					escape_str(hash.c_str()).c_str());
			}
			finish(completed_desc, valid && same, nullptr);
		});
	if (!submitted)
		send_to_char("Password service is busy; try again later.\r\n", ch);
	return TRUE;
}

static int locker_closecmd(P_char ch, char * /*arg*/)
{
	StorageLocker *pLocker = locker_current(ch);
	if (!pLocker)
		return FALSE;

	if (pLocker->GetCurrentChestId() == 0)
		return FALSE;

	int locker_id = pLocker->GetLockerId();
	int chest_id = pLocker->GetCurrentChestId();

	sql_log_chest_activity(locker_id, chest_id, GET_NAME(ch), CHEST_ACTION_CLOSE, NULL);
	pLocker->SetCurrentChestId(0);
	send_to_char("You close the chest.\r\n", ch);
	return TRUE;
}

static int locker_logcmd(P_char ch, char * /*arg*/)
{
	StorageLocker *pLocker = locker_current(ch);
	if (!pLocker)
	{
		return TRUE;
	}

	if (!locker_require_owner(pLocker, ch, "Only the locker owner can view the log.\r\n"))
	{
		return TRUE;
	}

	int locker_id = pLocker->GetLockerId();
	if (locker_id <= 0)
	{
		send_to_char("Locker not properly initialized.\r\n", ch);
		return TRUE;
	}

	// Read on the writer, behind the entries queued before it.
	if (!sql_read_for(
		    ch,
		    sql_format(
			    "SELECT l.logged_at, l.char_name, l.action_type, c.chest_name, l.item_short "
			    "FROM private_chest_log l "
			    "LEFT JOIN private_chests c ON l.chest_id = c.id "
			    "WHERE l.locker_id=%d "
			    "ORDER BY l.logged_at DESC LIMIT 50",
			    locker_id),
		    [](P_char viewer, const sql_rows &rows)
		    {
			    send_to_char("&+WRecent locker activity:&n\r\n", viewer);
			    for (const sql_row &row : rows)
				    send_to_char_f(viewer, "%s - %s %s %s%s%s\r\n",
						   row[0] ? row[0] : "?", row[1] ? row[1] : "?",
						   row[2] ? row[2] : "?", row[3] ? row[3] : "",
						   row[4] ? ": " : "", row[4] ? row[4] : "");
		    }))
		send_to_char("Error reading log.\r\n", ch);
	return TRUE;
}
