#ifndef DURIS_ITEM_VALUE_H
#define DURIS_ITEM_VALUE_H

#include "core/config.h"
#include "core/defines.h"

inline constexpr const char *ITEM_VALUE_FORMULA_REVISION = "ival-v8-proc-semantics";

// Numeric inputs only: no object identity, links, callbacks, or mutable state.
struct item_value_apply
{
	int location = 0;
	int modifier = 0;
};

struct item_value_input
{
	int type = 0;
	unsigned int wear_flags = 0, extra_flags = 0, extra2_flags = 0;
	unsigned long bitvector = 0, bitvector2 = 0, bitvector3 = 0, bitvector4 = 0;
	unsigned long long bitvector5 = 0;
	int value[NUMB_OBJ_VALS]{};
	item_value_apply affected[MAX_OBJ_AFFECT]{};
};

// Resolved by the caller, not by the numeric evaluator. Zero means no credit;
// callers with incomplete context must identify their output as an estimate.
enum class item_value_proc_policy
{
	none,
	priced,
	utility,
	unclassified
};
const char *item_value_proc_policy_name(item_value_proc_policy policy);

struct item_value_context
{
	int spell_circles[3]{};
	int native_proc_credit = 0;
	double racial_credits[MAX_OBJ_AFFECT]{};
	item_value_proc_policy native_proc_policy = item_value_proc_policy::none;
	unsigned int callable_packed_spells = 7;
	bool packed_proc_disabled = false;
};

struct item_value_breakdown
{
	double base = 0;
	double multiplier = 1;
	double unrounded = 0;
	bool floored = false;
	bool utility_override = false;
	int score = 0;
	bool invalid = false;
	item_value_proc_policy native_proc_policy = item_value_proc_policy::none;
	const char *native_proc_name = nullptr;
	double packed_credit = 0;
	unsigned int packed_cast_mask = 0;
	bool native_melee_suppressed = false;
	bool native_price_suppressed = false;
	bool context_complete = true;
	double flags_base = 0, applies_base = 0, type_base = 0, native_base = 0;
	double after_wear = 1, after_flags = 1, after_applies = 1, after_type = 1;
	unsigned long long unpriced_affects[5]{};
	unsigned int unpriced_apply_slots = 0;
	bool unpriced_type = false, unpriced_dynamic_effects = false;
};

// The power-field part of convertObj(), shared with read-only template views.
// Both obj_data and item_value_input expose these fields; no lifecycle is involved.
template <typename Object> void normalize_item_value_fields(Object &object)
{
	if (object.extra_flags & ITEM_IGNORE)
		return;
	object.bitvector &= ~(AFF_SLEEP | AFF_FEAR | AFF_CHARM);
	if (object.type == ITEM_WEAPON)
	{
		if (object.value[1] < 1)
			object.value[1] = 1;
		if (object.value[2] < 1)
			object.value[2] = 1;
	}
}

bool item_value_has_packed_proc(const item_value_input &input);
// Dispatch selects a prefix by nonzero slot count; monk gloves also require density.
unsigned int item_value_packed_cast_mask(const item_value_input &input,
					 unsigned int callable_spells);
// Historical material decomposition, scaled upward. Outputs change only on success.
bool item_value_material_quantities(int score, double scale, int &high, int &low);
// Positive scores are usable. Zero means unavailable, including invalid arithmetic.
int evaluate_item_value(const item_value_input &input, const item_value_context &context,
			item_value_breakdown *breakdown = nullptr);

// Runtime adapter; the existing one-argument itemvalue() API remains compatible.
struct obj_data;
int itemvalue(obj_data *obj, item_value_breakdown *breakdown);
struct object_template;
int itemvalue(const object_template &prototype, item_value_breakdown *breakdown = nullptr);

#endif
