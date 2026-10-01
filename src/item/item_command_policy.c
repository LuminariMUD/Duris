#include "item/item_command_policy.h"

#include "core/utils.h"

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
