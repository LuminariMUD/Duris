#ifndef DURIS_ARTIFACT_POPULATION_REPOSITORY_H
#define DURIS_ARTIFACT_POPULATION_REPOSITORY_H

#include "item/item_ownership_runtime.h"

#include <cstdint>
#include <vector>

enum class artifact_payload_domain : uint8_t
{
	player,
	pet,
	locker,
	account_locker,
	corpse,
	room,
	shopkeeper,
	siege,
};

// Raw payload provenance is retained even when its UID/owner is missing or its
// custody disagrees. A custody row alone is not a physical payload projection.
struct artifact_payload_projection
{
	artifact_payload_domain domain;
	uint64_t row_id = 0;
	uint64_t item_uid = 0;
	uint64_t parent_row_id = 0;
	uint64_t parent_item_uid = 0;
	int64_t owner_reference = 0;
	uint64_t owner_context = 0;
	int32_t vnum = 0;
	uint64_t extra_flags = 0;
	bool extra_flags_present = false;
	uint64_t quantity = 0;
	bool parent_missing = false;
	bool parent_owner_disagrees = false;
	item_owner_identity payload_owner = {};
	bool custody_found = false;
	// Revision zero is valid; a missing authority row remains distinct.
	bool custody_owner_revision_found = false;
	item_ownership_runtime_entry custody = {};
};

#ifndef __NO_MYSQL__
#include <mysql/mysql.h>

constexpr size_t ARTIFACT_POPULATION_SQL_PAGE_SIZE = 256;

struct artifact_population_sql_page
{
	std::vector<artifact_payload_projection> rows;
	uint64_t next_row_id = 0;
	bool complete = false;
};

// Read inside the caller's consistent boot/audit snapshot. Success publishes one
// page atomically; complete applies to this table only, not the whole population.
// Failure leaves *page unchanged and returns a MySQL error or EINVAL/ENOMEM.
unsigned int artifact_population_read_sql_page(MYSQL *connection, artifact_payload_domain domain,
					       uint64_t after_row_id,
					       artifact_population_sql_page *page);
#endif

#endif
