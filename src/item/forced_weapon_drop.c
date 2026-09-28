#include "item/forced_weapon_drop.h"

#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "persistence/persistence_checkpoint.h"
#include "redis/redis_floor_runtime.h"

extern P_room world;
extern const int top_of_world;

namespace
{
int equipped_slot(P_char actor, P_obj weapon)
{
	if (!actor || !weapon)
		return MAX_WEAR;
	for (int slot = 0; slot < MAX_WEAR; ++slot)
		if (actor->equipment[slot] == weapon)
			return slot;
	return MAX_WEAR;
}

bool valid_room(int room)
{
	return room >= 0 && room <= top_of_world;
}

void announce_recovery(P_char actor, P_obj weapon, int room, forced_weapon_drop_cause cause)
{
	if (!actor || !weapon || cause != forced_weapon_drop_cause::combat_fumble)
		return;
	act("&-L&+YYou lose control of your&n $q&-L&+Y, but recover it before it hits "
	    "the ground!&n\r\n",
	    FALSE, actor, weapon, 0, TO_CHAR);
	if (actor->in_room == room)
		act("$n stumbles with $s attack, but recovers $s weapon!", TRUE, actor, 0, 0,
		    TO_ROOM);
}

void announce_drop(P_char actor, P_obj weapon, int room, forced_weapon_drop_cause cause)
{
	if (!actor || !weapon || cause != forced_weapon_drop_cause::combat_fumble)
		return;
	if (actor->in_room == room)
	{
		act("&-L&+YYou swing at your foe _really_ badly, sending your&n "
		    "$q&-L&+Y flying!&n\r\n",
		    FALSE, actor, weapon, 0, TO_CHAR);
		act("$n stumbles with $s attack, sending $s weapon flying!", TRUE, actor, 0, 0,
		    TO_ROOM);
		return;
	}
	act("&-L&+YThe&n $q&-L&+Y you fumbled lands where you lost it.&n\r\n", FALSE, actor, weapon,
	    0, TO_CHAR);
	act("$p clatters to the ground after being sent flying!", TRUE, 0, weapon, 0, TO_ROOM);
}

} // namespace

forced_weapon_drop_result forced_weapon_drop(P_char actor, P_obj weapon,
					     forced_weapon_drop_cause cause)
{
	const int room = actor ? actor->in_room : NOWHERE;
	const int slot = equipped_slot(actor, weapon);
	if (!actor || !weapon || slot == MAX_WEAR || !valid_room(room))
	{
		announce_recovery(actor, weapon, room, cause);
		return forced_weapon_drop_result::rejected;
	}
	P_obj removed = unequip_char(actor, slot);
	if (removed != weapon)
	{
		announce_recovery(actor, weapon, room, cause);
		return forced_weapon_drop_result::rejected;
	}
	obj_to_room(weapon, room);
	if (IS_PC(actor))
	{
		if (weapon->obj_uid && OBJ_ROOM(weapon))
			redis_log_floor_drop(weapon, world[weapon->loc.room].number);
		mark_player_dirty_components(GET_PID(actor), PLAYER_COMPONENT_STATUS |
								     PLAYER_COMPONENT_EQUIPMENT |
								     PLAYER_COMPONENT_INVENTORY);
	}
	char_light(actor);
	room_light(room, REAL);
	announce_drop(actor, weapon, room, cause);
	return forced_weapon_drop_result::dropped;
}
