#include "item/item_command_policy.h"

#include "core/utils.h"
#include "classes/necromancy.h"
#include "item/item_ownership_runtime.h"
#include "item/storage_lockers.h"

extern P_room world;

bool item_command_uses_durable_ownership(P_obj /*object*/)
{
	// Memory is the authority: every command moves the object in memory, and the
	// next save of each owner records where it went.
	return false;
}

bool item_command_object_is_takeable(P_char actor, P_obj object)
{
	return actor && object &&
	       (CAN_WEAR(object, ITEM_TAKE) || ((GET_LEVEL(actor) >= 60) && !IS_NPC(actor)));
}

bool item_command_container_is_valid(P_obj container)
{
	return container && ((GET_ITEM_TYPE(container) == ITEM_CONTAINER) ||
			     (GET_ITEM_TYPE(container) == ITEM_STORAGE) ||
			     (GET_ITEM_TYPE(container) == ITEM_QUIVER) ||
			     (GET_ITEM_TYPE(container) == ITEM_CORPSE));
}

bool item_command_resolve_put_destination(P_char actor, P_obj container,
					  item_put_destination *destination)
{
	if (!actor || !container || !destination || !container->obj_uid ||
	    !item_command_container_is_valid(container))
		return false;

	*destination = {};
	if (locker_owner_for_container(actor, container, &destination->owner))
	{
		destination->target_container = NULL;
		destination->reason = item_transfer_reason::locker_deposit;
		destination->reason_id = static_cast<int64_t>(destination->owner.context_id);
		return true;
	}

	item_ownership_runtime_entry runtime = {};
	if (!item_ownership_runtime_lookup(container->obj_uid, &runtime) ||
	    runtime.state != item_custody_state::active ||
	    !item_owner_identity_valid(runtime.owner) || runtime.owner.type == item_owner_type::pet)
		return false;

	destination->target_container = container;
	destination->owner = runtime.owner;
	destination->reason = item_transfer_reason::player_put;
	destination->reason_id = static_cast<int64_t>(container->obj_uid);
	return true;
}

bool item_command_resolve_drop_destination(P_char actor, item_owner_identity *destination,
					   item_transfer_reason *reason, int64_t *reason_id)
{
	if (!actor || !destination || !reason || !reason_id || actor->in_room == NOWHERE)
		return false;

	*destination = { item_owner_type::room, static_cast<uint64_t>(world[actor->in_room].number),
			 0 };
	*reason = item_transfer_reason::player_drop;
	*reason_id = world[actor->in_room].number;
	if (locker_owner_for_room(actor, destination))
	{
		*reason = item_transfer_reason::locker_deposit;
		*reason_id = 0;
	}
	return true;
}
