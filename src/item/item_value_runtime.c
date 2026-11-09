// Engine context and compatibility entry point for item valuation.
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/item_value.h"

extern P_index obj_index;
extern const struct stat_data stat_factor[];
int get_mincircle(int spell);
int get_ival_from_proc(obj_proc_type proc);

static double item_value_racial_credit(P_obj obj, int i)
{
	double workingvalue = 0;
	double mod = obj->affected[i].modifier;
	// Racial attributes #'s - Do we still have these?
	if ((obj->affected[i].location == APPLY_AGI_RACE) ||
	    (obj->affected[i].location == APPLY_STR_RACE) ||
	    (obj->affected[i].location == APPLY_CON_RACE) ||
	    (obj->affected[i].location == APPLY_INT_RACE) ||
	    (obj->affected[i].location == APPLY_WIS_RACE) ||
	    (obj->affected[i].location == APPLY_CHA_RACE) ||
	    (obj->affected[i].location == APPLY_DEX_RACE))
	{
		if (mod < 1 || mod > LAST_RACE)
		{
			debug("itemvalue: obj '%s' %d has APPLY_..._RACE %d and bad modifier %g.",
			      obj->short_description, OBJ_VNUM(obj), obj->affected[i].location,
			      mod);
			workingvalue += 100;
		}
		else
		{
			switch (obj->affected[i].location)
			{
			// We're looking for the stat vs 100. 75->0pts, 100->50pts, 150->150pts, 200->250pts
			case APPLY_AGI_RACE:
				workingvalue += 2 * stat_factor[(int)mod].Agi - 150;
				break;
			case APPLY_STR_RACE:
				workingvalue += 2 * stat_factor[(int)mod].Str - 150;
				break;
			case APPLY_CON_RACE:
				workingvalue += 2 * stat_factor[(int)mod].Con - 150;
				break;
			case APPLY_INT_RACE:
				workingvalue += 2 * stat_factor[(int)mod].Int - 150;
				break;
			case APPLY_WIS_RACE:
				workingvalue += 2 * stat_factor[(int)mod].Wis - 150;
				break;
			case APPLY_CHA_RACE:
				workingvalue += 2 * stat_factor[(int)mod].Cha - 150;
				break;
			case APPLY_DEX_RACE:
				workingvalue += 2 * stat_factor[(int)mod].Dex - 150;
				break;
			// Should never be the case but..
			default:
				debug("itemvalue: obj '%s' %d has 'bad' APPLY_..._RACE %d, modifier %g.",
				      obj->short_description, OBJ_VNUM(obj),
				      obj->affected[i].location, mod);
				workingvalue += 100;
				break;
			}
		}
	}

	return workingvalue;
}

int itemvalue(P_obj obj, item_value_breakdown *breakdown)
{
	if (!obj)
	{
		if (breakdown)
			*breakdown = {};
		return 0;
	}
	item_value_input input;
	input.type = obj->type;
	input.wear_flags = obj->wear_flags;
	input.extra_flags = obj->extra_flags;
	input.extra2_flags = obj->extra2_flags;
	input.bitvector = obj->bitvector;
	input.bitvector2 = obj->bitvector2;
	input.bitvector3 = obj->bitvector3;
	input.bitvector4 = obj->bitvector4;
	input.bitvector5 = obj->bitvector5;
	for (int i = 0; i < NUMB_OBJ_VALS; ++i)
		input.value[i] = obj->value[i];
	item_value_context context;
	for (int i = 0; i < MAX_OBJ_AFFECT; ++i)
	{
		input.affected[i] = { obj->affected[i].location, obj->affected[i].modifier };
		context.racial_credits[i] = item_value_racial_credit(obj, i);
	}
	if (item_value_has_packed_proc(input))
	{
		context.spell_circles[0] = get_mincircle(obj->value[5] % 1000);
		context.spell_circles[1] = get_mincircle(obj->value[5] % 1000000 / 1000);
		context.spell_circles[2] = get_mincircle(obj->value[5] % 1000000000 / 1000000);
	}
	if (obj_index[obj->R_num].func.obj)
		context.native_proc_credit = get_ival_from_proc(obj_index[obj->R_num].func.obj);
	item_value_breakdown detail;
	const int score = evaluate_item_value(input, context, &detail);
	if (detail.utility_override && !detail.floored && detail.unrounded != 1)
		debug("Always load obj '%s' %d has stats giving ival %.3lf.", OBJ_SHORT(obj),
		      OBJ_VNUM(obj), detail.unrounded);
	if (breakdown)
		*breakdown = detail;
	return score;
}

int itemvalue(P_obj obj)
{
	return itemvalue(obj, nullptr);
}
