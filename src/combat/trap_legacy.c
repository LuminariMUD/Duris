#include "combat/trap_legacy.h"
#include "core/structs.h"
#include "core/utils.h"

void normalize_legacy_trap(P_obj object, int vnum)
{
	// Only the original authored mask/type/level identifies a legacy definition.
	// Charges can differ legitimately after use or disarming.
	static const struct
	{
		int vnum, mask, type, level, final_mask, final_level;
		bool finite;
	} repairs[] = {
		{ 32820, 1536, 11, 50, 512, 50, true },
		{ 32831, 516, 11, 50, 0, 0, false },
		{ 32835, 32, 11, 56, 65, 56, true },
		{ 32846, 5, 11, 56, 509, 56, true },
		{ 32870, 1536, 11, 50, 512, 50, true },
		{ 41361, 3140, 10, 100, 2069, 100, true },
		{ 41926, 2304, 9, 100, 2305, 100, false },
		{ 43503, 256, 16, 50, 257, 50, false },
		{ 43506, 64, 12, 50, 17, 50, false },
		{ 43511, 5, 15, 75, 509, 75, false },
		{ 44160, 64, 13, 90, 17, 90, false },
		{ 44465, 1057, 16, 80, 1089, 80, false },
		{ 55022, 2, 13, 50, 0, 0, false },
		{ 57567, 1, 15, 100, 0, 0, false },
		{ 58404, 509, 12, 0, 509, 25, false },
		{ 59047, 6, 15, 200, 6, 100, false },
		{ 59239, 260, 16, 100, 261, 100, false },
		{ 59258, 8, 15, 60, 9, 60, false },
		{ 77721, 2180, 16, 60, 0, 0, false },
		{ 91025, 2308, 9, 60, 2309, 60, false },
		{ 130002, 9, 9, 60, 2057, 60, false },
		{ 131215, 509, 16, 99, 0, 0, false },
		{ 131226, 509, 16, 99, 0, 0, false },
	};
	for (const auto &repair : repairs)
	{
		if (vnum != repair.vnum || object->trap_eff != repair.mask ||
		    object->trap_dam != repair.type || object->trap_level != repair.level)
			continue;
		object->trap_eff = repair.final_mask;
		object->trap_level = repair.final_level;
		if (!repair.final_mask)
			object->trap_dam = object->trap_charge = 0;
		else if (repair.finite && (object->trap_charge == -1 || object->trap_charge > 1))
			object->trap_charge = 1;
		return;
	}

	// These containers were not closeable at all. Preserve their saved open state;
	// CLOSED is a fresh-prototype choice, never a restoration default.
	if (object->type == ITEM_CONTAINER && object->value[1] == 0 &&
	    ((vnum == 142251 && object->trap_eff == 1536 && object->trap_dam == 12 &&
	      object->trap_level == 60) ||
	     (vnum == 142438 && object->trap_eff == 512 && object->trap_dam == 9 &&
	      object->trap_level == 60)))
		object->value[1] = CONT_CLOSEABLE;
}
