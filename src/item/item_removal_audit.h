#ifndef ITEM_REMOVAL_AUDIT_H
#define ITEM_REMOVAL_AUDIT_H

#include "core/structs.h"

struct item_removal_location
{
	unsigned long uid = 0;
	int vnum = -1;
	int room = -1;
	const char *placement = "removed";
	unsigned long container_uid = 0;
	int wear_slot = -1;
	int holder_pid = 0;
	int holder_mob_vnum = -1;
	uint64_t holder_runtime_id = 0;
};

// Capture identity and placement while the object and its holder are still live.
item_removal_location capture_item_removal(P_obj object);
void audit_item_removal(const char *cause, const item_removal_location &source,
			const item_removal_location &destination = {}, int damage_type = 0);

#endif
