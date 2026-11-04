#ifndef ITEM_INSTANCE_FIELDS_H
#define ITEM_INSTANCE_FIELDS_H

#include "magic/spells.h"
#include "player/player_snapshot.h"

inline uint32_t sql_item_permanent_extra2(const player_item_snapshot &item)
{
	uint32_t temporary = 0;
	uint32_t base = item.extra2_flags;
	for (const auto &affect : item.dynamic_affects)
		if (affect.type == TAG_ALTERED_EXTRA2)
			base = static_cast<uint32_t>(affect.extra2);
		else
			temporary |= static_cast<uint32_t>(affect.extra2);
	// SQL restores the permanent flags without restoring the temporary affects.
	// Keep live changes outside the overlay and the original values under it.
	return (item.extra2_flags & ~temporary) | (base & temporary);
}

#endif
