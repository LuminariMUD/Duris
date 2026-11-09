#ifndef DURIS_ITEM_VALUE_PROCS_H
#define DURIS_ITEM_VALUE_PROCS_H

#include "core/structs.h"
#include "item/item_value.h"
#include <span>

struct item_value_proc_entry
{
	obj_proc_type callback;
	const char *name;
	int credit;
	item_value_proc_policy policy;
};

std::span<const item_value_proc_entry> item_value_proc_entries();
item_value_proc_entry item_value_proc(obj_proc_type proc);

#endif
