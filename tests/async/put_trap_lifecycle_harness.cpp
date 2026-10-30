#include "core/prototypes.h"
#include "core/utils.h"
#include "item/storage_lockers.h"
#include "net/comm.h"
#include "magic/spells.h"
#include "player/player_snapshot.h"
#include "item/item_movement_transaction.h"
#include "classes/necromancy.h"
#include "sql/sql.h"
#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <cstring>
#include <string>
#include <vector>
#define USE_SPACE 0
room_data rooms[2] = {};
P_room world = rooms;
index_data indexes[1] = {};
P_index obj_index = indexes;
P_obj object_list;
P_char character_list;
static P_char actor;
static P_obj container, item, sibling;
static int calls, mode, transfers, publications, saves;

P_char find_character_by_runtime_id(uint64_t id)
{
	return character_list && character_list->runtime_id == id ? character_list : nullptr;
}
P_obj find_live_object(P_obj expected, uint64_t uid)
{
	for (P_obj obj = object_list; obj; obj = obj->next)
		if (obj == expected && obj->obj_uid == uid)
			return obj;
	return nullptr;
}
P_obj find_live_item_uid(uint64_t uid)
{
	for (P_obj obj = object_list; obj; obj = obj->next)
		if (obj->obj_uid == uid)
			return obj;
	return nullptr;
}
void extract_obj(P_obj object, int)
{
	for (auto **link = &object_list; *link; link = &(*link)->next)
		if (*link == object)
		{
			*link = object->next;
			break;
		}
	delete object;
}
bool checkgetput(P_char ch, P_obj object)
{
	if (!(object->trap_eff & 2) || !object->trap_charge || IS_TRUSTED(ch))
		return false;
	++calls;
	--object->trap_charge;
	if (mode == 1)
	{
		delete actor->only.pc;
		delete actor;
		actor = character_list = nullptr;
	}
	if (mode == 2)
	{
		ch->in_room = 1;
	}
	if (mode == 3)
	{
		ch->specials.affected_by2 |= AFF2_MINOR_PARALYSIS;
	}
	if (mode == 4)
	{
		extract_obj(object, FALSE);
		item = nullptr;
	}
	if (mode == 5)
	{
		extract_obj(container, FALSE);
		container = nullptr;
	}
	if (mode == 6)
	{
		extract_obj(sibling, FALSE);
		sibling = nullptr;
	}
	return true;
}
bool affected_by_spell(P_char, int)
{
	return false;
}
void send_to_char(const char *, P_char ch)
{
	assert(ch == actor && actor);
	++publications;
}
void act(const char *, int, P_char ch, P_obj, void *, int)
{
	assert(ch == actor && actor);
	++publications;
}
bool ac_can_see_obj(P_char, P_obj, int)
{
	return true;
}
bool isname(const char *, const char *)
{
	return true;
}
bool item_movement_transaction_player_busy(P_char)
{
	return false;
}
bool item_command_container_is_valid(P_obj object)
{
	return object->type == ITEM_CONTAINER || object->type == ITEM_STORAGE ||
	       object->type == ITEM_CORPSE || object->type == ITEM_QUIVER;
}
int char_light(P_char ch)
{
	assert(ch == actor && actor);
	return 0;
}
int room_light(int, int)
{
	return 0;
}
void mark_player_dirty_components(int, player_component_mask_t) {}
int container_total_weight(P_obj object)
{
	return object->weight;
}
void writeSavedItem(P_obj object)
{
	assert(find_live_object(object, object->obj_uid));
	++saves;
}
void writeCorpse(P_obj object)
{
	assert(find_live_object(object, object->obj_uid));
	++saves;
}
void obj_from_char(P_obj object)
{
	for (auto **link = &actor->carrying; *link; link = &(*link)->next_content)
		if (*link == object)
		{
			*link = object->next_content;
			break;
		}
	object->loc_p = LOC_NOWHERE;
}
void obj_from_room(P_obj)
{
	std::abort();
}
void obj_to_obj(P_obj object, P_obj destination)
{
	++transfers;
	object->loc_p = LOC_INSIDE;
	object->loc.inside = destination;
	object->next_content = destination->contains;
	destination->contains = object;
}
void do_get_reject_text(P_char ch, const char *text)
{
	send_to_char(text, ch);
}
char *FirstWord(char *)
{
	static char word[] = "object";
	return word;
}
int checked_snprintf_at(const char *, int, char *buffer, size_t size, const char *format, ...)
{
	va_list args;
	va_start(args, format);
	int result = vsnprintf(buffer, size, format, args);
	va_end(args);
	return result;
}

// PUT_FUNCTIONS

static P_obj object(int type, uint64_t uid)
{
	auto *obj = new obj_data{};
	obj->type = type;
	obj->obj_uid = uid;
	obj->weight = 1;
	obj->name = const_cast<char *>("item");
	obj->short_description = const_cast<char *>("an item");
	obj->next = object_list;
	object_list = obj;
	return obj;
}
static void clear()
{
	while (object_list)
		extract_obj(object_list, FALSE);
	if (actor)
	{
		delete actor->only.pc;
		delete actor;
	}
	actor = character_list = nullptr;
}
static void reset(uint64_t uid = 1, int type = ITEM_CONTAINER)
{
	clear();
	actor = new char_data{};
	actor->only.pc = new pc_only_data{};
	actor->only.pc->pid = 42;
	actor->runtime_id = 1;
	actor->specials.position = POS_STANDING | STAT_NORMAL;
	actor->in_room = 0;
	actor->player.level = 1;
	character_list = actor;
	container = object(type, uid);
	container->value[0] = 100;
	container->weight = 0;
	container->loc_p = LOC_ROOM;
	container->loc.room = 0;
	item = object(ITEM_OTHER, uid + 1);
	item->trap_eff = 2;
	item->trap_dam = 13;
	item->trap_charge = 2;
	item->loc_p = LOC_CARRIED;
	item->loc.carrying = actor;
	actor->carrying = item;
	sibling = object(ITEM_OTHER, uid + 2);
	sibling->loc_p = LOC_CARRIED;
	sibling->loc.carrying = actor;
	item->next_content = sibling;
	calls = mode = transfers = publications = saves = 0;
}
int main()
{
	for (int target_type : { ITEM_CONTAINER, ITEM_QUIVER })
	{
		for (int failure = 0; failure < 4; ++failure)
		{
			reset(1, target_type);
			item->type = ITEM_MISSILE;
			if (failure == 0)
				container->value[1] = CONT_CLOSED;
			if (failure == 1)
				container->value[0] = 0;
			if (failure == 2)
				item->extra_flags = ITEM_NODROP;
			if (failure == 3)
				item->extra_flags = ITEM_ARTIFACT;
			bool trap_rejected = true;
			assert(!put(actor, item, container, FALSE, &trap_rejected) && !calls &&
			       item->trap_charge == 2 && !transfers);
			assert(!trap_rejected);
		}
		for (int callback = 0; callback <= 6; ++callback)
		{
			reset(1, target_type);
			item->type = ITEM_MISSILE;
			mode = callback;
			bool trap_rejected = false;
			assert(!put(actor, item, container, TRUE, &trap_rejected));
			assert(trap_rejected);
			assert(calls == 1 && !transfers && !publications);
		}
	}
	for (uint64_t uid : { 0, 1 })
		for (int callback = 0; callback <= 6; ++callback)
		{
			reset(uid);
			mode = callback;
			start_bulk_put(actor, container, nullptr, false);
			assert(calls == 1 && !transfers && !publications && !saves);
		}
	reset(1, ITEM_STORAGE);
	auto *first = object(ITEM_OTHER, 4);
	first->loc_p = LOC_CARRIED;
	first->loc.carrying = actor;
	first->next_content = item;
	actor->carrying = first;
	mode = 1;
	start_bulk_put(actor, container, nullptr, false);
	assert(calls == 1 && transfers == 1 && saves == 1 && !publications);
	reset();
	item->trap_dam = 8;
	assert(put(actor, item, container, TRUE) && transfers == 1 && !calls);
	reset();
	item->trap_charge = 0;
	assert(put(actor, item, container, TRUE) && transfers == 1 && !calls);
	reset();
	container->trap_dam = 13;
	container->trap_eff = 2;
	container->trap_charge = 2;
	item->trap_charge = 0;
	assert(put(actor, item, container, TRUE) && !calls && container->trap_charge == 2);
	clear();
}
