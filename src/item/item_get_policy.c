#include "item/item_get_policy.h"

#include "core/prototypes.h"
#include "core/utils.h"
#include "classes/necromancy.h"
#include "item/storage_lockers.h"

extern P_room world;
extern const int top_of_world;
extern int top_of_objt;

namespace
{
constexpr const char *MALFORMED_CONTAINER_MESSAGE = "That container has a malformed item.\r\n";

bool actor_room_is_valid(P_char actor)
{
	return actor && actor->in_room > NOWHERE && actor->in_room <= top_of_world;
}

bool live_placement_outer(P_char actor, P_obj object, P_obj container, P_obj *outer_out)
{
	if (!actor || !object || !outer_out || !actor_room_is_valid(actor))
		return false;

	P_obj outer = container ? container : object;
	if (container && (!OBJ_INSIDE(object) || object->loc.inside != container))
		return false;

	int safety = top_of_objt + 1;
	while (outer && OBJ_INSIDE(outer) && outer->loc.inside)
	{
		if (safety-- <= 0)
		{
			send_to_char(MALFORMED_CONTAINER_MESSAGE, actor);
			return false;
		}
		outer = outer->loc.inside;
	}
	if (!outer)
		return false;
	*outer_out = outer;
	return true;
}

bool live_placement_owner(P_char actor, P_obj object, P_obj container, item_owner_identity *owner)
{
	if (!owner)
		return false;
	*owner = {};
	P_obj outer = NULL;
	if (!live_placement_outer(actor, object, container, &outer))
		return false;

	if (outer->type == ITEM_CORPSE && IS_SET(outer->value[CORPSE_FLAGS], PC_CORPSE) &&
	    outer->value[CORPSE_PID] > 0 && outer->value[CORPSE_SAVEID] > 0)
	{
		*owner = item_owner_identity{
			item_owner_type::corpse,
			item_corpse_owner_id(static_cast<uint32_t>(outer->value[CORPSE_PID]),
					     static_cast<uint32_t>(outer->value[CORPSE_SAVEID])),
			0
		};
		return item_owner_identity_valid(*owner);
	}

	if (OBJ_ROOM(outer) && outer->loc.room == actor->in_room)
	{
		*owner = { item_owner_type::room,
			   static_cast<uint64_t>(world[actor->in_room].number), 0 };
		return item_owner_identity_valid(*owner);
	}

	if (OBJ_CARRIED_BY(outer, actor) || OBJ_WORN_BY(outer, actor))
	{
		*owner = { item_owner_type::player, static_cast<uint64_t>(GET_PID(actor)), 0 };
		return item_owner_identity_valid(*owner);
	}

	/* NPC custody and objects in nowhere have no durable source authority. */
	return false;
}

} // namespace

bool item_get_source_owner(P_char actor, P_obj object, P_obj container, item_owner_identity *source)
{
	if (!actor || !object || !source)
		return false;
	// Memory is the authority: the source is wherever the object lies now.
	P_obj outer = NULL;
	if (!live_placement_owner(actor, object, container, source) ||
	    !live_placement_outer(actor, object, container, &outer))
		return false;
	if (source->type == item_owner_type::room && outer != object)
		locker_owner_for_container(actor, outer, source);
	else if (source->type == item_owner_type::room)
		locker_owner_for_room(actor, source);
	return true;
}
