#ifndef DURIS_COLLECTOR_CUSTODY_BOUNDARY_H
#define DURIS_COLLECTOR_CUSTODY_BOUNDARY_H

#include "economy/collector_policy.h"
#include "item/item_transfer_command.h"

#include <cstdint>
#include <limits>

// Classify a committed transfer of a collector candidate: destroying it, or a player or a
// shopkeeper on either side, ends its candidacy; anything else (a repair within a room)
// leaves it. The command's full item list makes cancelling a container's contents
// transitive without a history scan.
inline collector::reason
collector_item_transfer_boundary_reason(const item_transfer_payload &payload)
{
	if (payload.to_owner.type == item_owner_type::destruction ||
	    payload.reason == item_transfer_reason::destruction)
		return collector::reason::destroyed;
	if (payload.from_owner.type == item_owner_type::player ||
	    payload.to_owner.type == item_owner_type::player ||
	    payload.from_owner.type == item_owner_type::shopkeeper ||
	    payload.to_owner.type == item_owner_type::shopkeeper)
		return collector::reason::claimed;
	return collector::reason::none;
}

inline uint32_t collector_item_transfer_actor_pid(const item_transfer_payload &payload)
{
	const uint64_t actor =
		payload.to_owner.type == item_owner_type::player   ? payload.to_owner.id :
		payload.from_owner.type == item_owner_type::player ? payload.from_owner.id :
								     0;
	return actor <= std::numeric_limits<uint32_t>::max() ? static_cast<uint32_t>(actor) : 0;
}

struct collector_custody_boundary_item
{
	uint64_t item_uid = 0;
	uint64_t post_item_revision = 0;
};

#endif
