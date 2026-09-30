#ifndef FORCED_WEAPON_DROP_H
#define FORCED_WEAPON_DROP_H

#include "core/structs.h"

#include <cstdint>

enum class forced_weapon_drop_cause : uint8_t
{
	combat_fumble,
	critical_disarm,
};

enum class forced_weapon_drop_result : uint8_t
{
	rejected,
	dropped,
};

// Knock an equipped weapon out of the actor's grasp onto the floor.
forced_weapon_drop_result forced_weapon_drop(P_char actor, P_obj weapon,
					     forced_weapon_drop_cause cause);

#endif
