// Engine context and compatibility entry point for item valuation.
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/item_value.h"
#include "item/item_value_procs.h"
#include "item/objmisc.h"
#include "item/native_artifact_actions.h"
#include "world/object_template.h"
#include "core/proc-libs.h"
#include "mob/studioproclib.h"
#include "world/specs.prototypes.h"

extern P_index obj_index;
extern const struct stat_data stat_factor[];
extern int top_of_objt;
extern Skill skills[];
int get_mincircle(int spell);

template <typename Object> static item_value_input item_value_fields(const Object &object)
{
	item_value_input input;
	input.type = object.type;
	input.wear_flags = object.wear_flags;
	input.extra_flags = object.extra_flags;
	input.extra2_flags = object.extra2_flags;
	input.bitvector = object.bitvector;
	input.bitvector2 = object.bitvector2;
	input.bitvector3 = object.bitvector3;
	input.bitvector4 = object.bitvector4;
	input.bitvector5 = object.bitvector5;
	for (int i = 0; i < NUMB_OBJ_VALS; ++i)
		input.value[i] = object.value[i];
	for (int i = 0; i < MAX_OBJ_AFFECT; ++i)
		input.affected[i] = { object.affected[i].location, object.affected[i].modifier };
	return input;
}

static double item_value_racial_credit(const item_value_apply &apply, const char *name, int vnum)
{
	double workingvalue = 0;
	double mod = apply.modifier;
	// Racial attributes #'s - Do we still have these?
	if ((apply.location == APPLY_AGI_RACE) || (apply.location == APPLY_STR_RACE) ||
	    (apply.location == APPLY_CON_RACE) || (apply.location == APPLY_INT_RACE) ||
	    (apply.location == APPLY_WIS_RACE) || (apply.location == APPLY_CHA_RACE) ||
	    (apply.location == APPLY_DEX_RACE))
	{
		if (mod < 1 || mod > LAST_RACE)
		{
			debug("itemvalue: obj '%s' %d has APPLY_..._RACE %d and bad modifier %g.",
			      name, vnum, apply.location, mod);
			workingvalue += 100;
		}
		else
		{
			switch (apply.location)
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
				      name, vnum, apply.location, mod);
				workingvalue += 100;
				break;
			}
		}
	}

	return workingvalue;
}

static int item_value_with_context(const item_value_input &input, int rnum, const char *name,
				   obj_proc_type proc, item_value_breakdown *breakdown)
{
	item_value_context context;
	const int vnum = obj_index[rnum].virtual_number;
	for (int i = 0; i < MAX_OBJ_AFFECT; ++i)
		context.racial_credits[i] = item_value_racial_credit(input.affected[i], name, vnum);
	if (item_value_has_packed_proc(input))
	{
		context.callable_packed_spells = 0;
		for (int packed = input.value[5] % 1000000000, i = 0; i < 3; ++i, packed /= 1000)
		{
			const int spell = packed % 1000;
			if (spell > 0 && spell < MAX_SKILLS && skills[spell].spell_pointer)
			{
				context.callable_packed_spells |= 1u << i;
				context.spell_circles[i] = get_mincircle(spell);
			}
		}
		context.packed_proc_disabled = (vnum == 21 || vnum == 22) &&
					       native_artifact_configured_owner(vnum);
	}
	const auto native_proc = item_value_proc(proc);
	context.native_proc_credit = native_proc.credit;
	context.native_proc_policy = native_proc.policy;
	const bool proc_glove = (input.type == ITEM_ARMOR || input.type == ITEM_WORN) &&
				(input.wear_flags & ITEM_WEAR_HANDS) &&
				(input.extra2_flags & ITEM2_MONK_PROC);
	const bool invalid_glove =
		proc_glove && input.value[5] &&
		(!item_value_has_packed_proc(input) ||
		 !item_value_packed_cast_mask(input, context.callable_packed_spells));
	const bool native_melee_suppressed =
		proc && ((item_value_has_packed_proc(input) && !context.packed_proc_disabled) ||
			 invalid_glove);
	const bool native_price_suppressed = native_melee_suppressed && native_proc.melee_only &&
					     !IS_BACKSTABBER(&input);
	if (native_price_suppressed)
		context.native_proc_credit = 0;
	item_value_breakdown detail;
	const int score = evaluate_item_value(input, context, &detail);
	detail.native_proc_name = native_proc.name;
	detail.native_melee_suppressed = native_melee_suppressed;
	detail.native_price_suppressed = native_price_suppressed;
	// Existing native prices aggregate melee, periodic and invoke behavior. Retain
	// that legacy price and expose unresolved decomposition instead of inventing weights.
	detail.context_complete = detail.context_complete &&
				  native_proc.policy != item_value_proc_policy::unclassified &&
				  (!native_melee_suppressed || native_price_suppressed);
	if (detail.utility_override && !detail.floored && detail.unrounded != 1)
		debug("Always load obj '%s' %d has stats giving ival %.3lf.", name, vnum,
		      detail.unrounded);
	if (breakdown)
		*breakdown = detail;
	return score;
}

int itemvalue(P_obj obj, item_value_breakdown *breakdown)
{
	if (!obj || !obj_index || obj->R_num < 0 || obj->R_num > top_of_objt)
	{
		if (breakdown)
		{
			*breakdown = {};
			breakdown->invalid = true;
		}
		return 0;
	}
	obj_proc_type proc = obj_index[obj->R_num].func.obj;
	if (proc == proclib_obj_cmd_bridge && !(obj->extra_flags & ITEM_PROCLIB))
		proc = proclib_chain_incumbent(obj->R_num);
	const int score = item_value_with_context(item_value_fields(*obj), obj->R_num,
						  obj->short_description, proc, breakdown);
	if (breakdown && obj->affects)
	{
		breakdown->unpriced_dynamic_effects = true;
		breakdown->context_complete = false;
	}
	return score;
}

int itemvalue(P_obj obj)
{
	return itemvalue(obj, nullptr);
}

int itemvalue(const object_template &prototype, item_value_breakdown *breakdown)
{
	const int rnum = prototype.R_num;
	if (!obj_index || rnum < 0 || rnum > top_of_objt)
	{
		if (breakdown)
		{
			*breakdown = {};
			breakdown->invalid = true;
		}
		return 0;
	}
	auto input = item_value_fields(prototype);
	normalize_item_value_fields(input);
	obj_proc_type proc = obj_index[rnum].func.obj;
	if (proc == proclib_obj_cmd_bridge)
		proc = proclib_chain_incumbent(rnum);
	if (!proc && prototype.type == ITEM_SWITCH)
		proc = item_switch;
	for (const auto &description : prototype.descriptions)
		if (!strn_cmp(description.keyword.c_str(), "_proclib_", 9) &&
		    valid_object_proclib(description.keyword.c_str() + 9,
					 description.description.c_str()))
		{
			// The constructor installs this bridge for a successfully decoded
			// library. Match its legacy credit without attaching or invoking it.
			proc = proclib_obj_cmd_bridge;
			break;
		}
	return item_value_with_context(input, rnum, prototype.short_description.c_str(), proc,
				       breakdown);
}
