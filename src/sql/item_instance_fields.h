#ifndef ITEM_INSTANCE_FIELDS_H
#define ITEM_INSTANCE_FIELDS_H

#include "core/structs.h"
#include "magic/spells.h"
#include "player/player_snapshot.h"

struct sql_extra2_projection
{
	uint32_t base;
	uint32_t temporary = 0;

	void include(int type, uint32_t flags)
	{
		if (type == TAG_ALTERED_EXTRA2)
			base = flags;
		else
			temporary |= flags;
	}

	uint32_t permanent(uint32_t live) const
	{
		// SQL restores permanent flags without restoring temporary affects.
		return (live & ~temporary) | (base & temporary);
	}
};

inline uint32_t sql_item_permanent_extra2(const player_item_snapshot &item)
{
	sql_extra2_projection flags{ item.extra2_flags };
	for (const auto &affect : item.dynamic_affects)
		flags.include(affect.type, static_cast<uint32_t>(affect.extra2));
	return flags.permanent(item.extra2_flags);
}

inline uint32_t sql_item_permanent_extra2(const obj_data &item)
{
	sql_extra2_projection flags{ item.extra2_flags };
	for (const obj_affect *affect = item.affects; affect; affect = affect->next)
		flags.include(affect->type, static_cast<uint32_t>(affect->extra2));
	return flags.permanent(item.extra2_flags);
}

#endif
