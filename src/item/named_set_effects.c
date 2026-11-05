#include "item/named_set_effects.h"

#include "core/prototypes.h"
#include "core/utils.h"
#include "item/named_set_origin.h"
#include "item/named_sets.h"
#include "world/vnum.obj.h"

extern P_index obj_index;

static int supporting_zone(P_char ch, int spell)
{
	for (size_t i = 0; i < named_set_count; ++i)
		for (const auto &tier : named_sets[i].proc_spells)
		{
			if (!tier[0] || tier[1] != spell)
				continue;
			int count = 0;
			bool armor_driver = false;
			for (int slot = 0; slot < MAX_WEAR; ++slot)
			{
				P_obj object = ch->equipment[slot];
				if (!object || object->R_num < 0)
					continue;
				const int vnum = obj_index[object->R_num].virtual_number;
				if ((vnum != VOBJ_RANDOM_ARMOR && vnum != VOBJ_RANDOM_WEAPON) ||
				    named_set_origin(object).zone != named_sets[i].zone)
					continue;
				armor_driver = armor_driver || vnum == VOBJ_RANDOM_ARMOR;
				if (slot != WEAR_ATTACH_BELT_2 && slot != WEAR_ATTACH_BELT_3)
					++count;
			}
			if (armor_driver && count >= tier[0])
				return named_sets[i].zone;
		}
	return 0;
}

bool reconcile_named_set_spell(P_char ch, int spell)
{
	const int support = supporting_zone(ch, spell);
	bool removed = false;
	for (affected_type *affect = ch->affected, *next; affect; affect = next)
	{
		next = affect->next;
		if (!(affect->flags & AFFTYPE_SET_AFFECT) || affect->set_spell != spell ||
		    affect->set_owner != ch->runtime_id)
			continue;
		if (support)
			affect->set_zone = support;
		else
		{
			wear_off_message(ch, affect);
			affect_remove(ch, affect);
			removed = true;
		}
	}
	return removed;
}
