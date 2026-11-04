#include "item/item_removal_audit.h"

#include "core/prototypes.h"
#include "core/utils.h"
#include "persistence/persistence_log.h"
#include "world/db.h"

#include <cstdio>

extern const int top_of_world;

item_removal_location capture_item_removal(P_obj object)
{
	item_removal_location location;
	location.uid = object->obj_uid;
	location.vnum = OBJ_VNUM(object);
	location.placement = "detached";

	P_obj root = object;
	if (OBJ_INSIDE(object))
	{
		location.placement = "container";
		location.container_uid = object->loc.inside->obj_uid;
		while (OBJ_INSIDE(root))
			root = root->loc.inside;
	}
	P_char holder = nullptr;
	if (OBJ_WORN(root))
	{
		if (root == object)
			location.placement = "worn";
		// Scrapping can encounter stale wearer links and repair them later.
		if (char_in_list(root->loc.wearing))
		{
			holder = root->loc.wearing;
			for (int slot = 0; slot < MAX_WEAR; ++slot)
				if (holder->equipment[slot] == root)
				{
					location.wear_slot = slot;
					break;
				}
		}
	}
	else if (OBJ_CARRIED(root))
	{
		if (root == object)
			location.placement = "inventory";
		holder = root->loc.carrying;
	}
	else if (root == object && OBJ_ROOM(root))
		location.placement = "room";

	int room = NOWHERE;
	if (holder)
	{
		room = holder->in_room;
		if (IS_NPC(holder))
		{
			location.holder_mob_vnum = GET_VNUM(holder);
			location.holder_runtime_id = holder->runtime_id;
		}
		else
			location.holder_pid = GET_PID(holder);
	}
	else if (OBJ_ROOM(root))
		room = root->loc.room;
	if (room >= 0 && room <= top_of_world)
		location.room = world[room].number;
	return location;
}

void audit_item_removal(const char *cause, const item_removal_location &source,
			const item_removal_location &destination, int damage_type)
{
	if (!source.uid)
		return;
	char record[768];
	snprintf(record, sizeof(record),
		 "domain=item_removal cause=%s uid=%lu vnum=%d room=%d "
		 "source=%s source_container_uid=%lu source_slot=%d holder_pid=%d "
		 "holder_mob_vnum=%d holder_runtime_id=%llu "
		 "destination=%s destination_room=%d destination_pid=%d destination_mob_vnum=%d "
		 "destination_runtime_id=%llu result_uid=%lu result_vnum=%d damage_type=%d",
		 cause, source.uid, source.vnum, source.room, source.placement,
		 source.container_uid, source.wear_slot, source.holder_pid, source.holder_mob_vnum,
		 static_cast<unsigned long long>(source.holder_runtime_id), destination.placement,
		 destination.room, destination.holder_pid, destination.holder_mob_vnum,
		 static_cast<unsigned long long>(destination.holder_runtime_id), destination.uid,
		 destination.vnum, damage_type);
	persistence_log_submit(record);
}
