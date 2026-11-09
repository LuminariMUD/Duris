#ifndef DURIS_ITEM_VALUE_H
#define DURIS_ITEM_VALUE_H

#include "core/config.h"
#include "core/defines.h"

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
struct item_value_context
{
	int spell_circles[3]{};
	int native_proc_credit = 0;
	double racial_credits[MAX_OBJ_AFFECT]{};
};

struct item_value_breakdown
{
	double base = 0;
	double multiplier = 1;
	double unrounded = 0;
	bool floored = false;
	bool utility_override = false;
	int score = 0;
};

bool item_value_has_packed_proc(const item_value_input &input);
int evaluate_item_value(const item_value_input &input, const item_value_context &context,
			item_value_breakdown *breakdown = nullptr);

// Runtime adapter; the existing one-argument itemvalue() API remains compatible.
struct obj_data;
int itemvalue(obj_data *obj, item_value_breakdown *breakdown);

#endif
