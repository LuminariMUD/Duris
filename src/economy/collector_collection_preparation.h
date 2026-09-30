#ifndef DURIS_COLLECTOR_COLLECTION_PREPARATION_H
#define DURIS_COLLECTOR_COLLECTION_PREPARATION_H

#include "economy/collector_command.h"

#include <cstdint>
#include <memory>

struct obj_data;
typedef struct obj_data *P_obj;

enum class collector_collection_prepare_outcome : uint8_t
{
	prepared,
	invalid_request,
	not_due,
	missing_item,
	claimed,
	destroyed,
	excluded,
	stale_custody,
	invalid_topology,
	limit_exceeded,
	allocation_failure,
};

bool collector_collection_item_eligible(P_obj object);

// Captures the live selected object as an empty singleton while fencing the
// complete ownership root that currently surrounds it. The returned payload is
// heap-owned because a maximum-size collector command is intentionally large.
collector_collection_prepare_outcome
collector_collection_prepare(const collector::record &entry, uint64_t observed_at,
			     std::unique_ptr<collector_command_payload> *payload);

// The submit checks the same live topology, then detaches the selected item: its
// contents move up to where it was, and it leaves the world until the collection
// commits (the transaction extracts it) or is refused (it goes back).
bool collector_collection_live_matches(const collector_command_payload &payload, P_obj *selected);
bool collector_collection_detach_live(P_obj selected);

#endif
