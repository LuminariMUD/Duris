#ifndef DURIS_ARTIFACT_POPULATION_REPOSITORY_H
#define DURIS_ARTIFACT_POPULATION_REPOSITORY_H

#include "item/item_ownership_runtime.h"

#include <cstdint>
#include <string>
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
	auction,
	collector,
	delivery,
	embedded,
	auction_legacy,
	auction_pickup,
	redis_generation,
	redis_floor,
	copyover_ground,
	copyover_reconstruction,
};

enum class artifact_payload_role : uint8_t
{
	stored,
	delivery,
	history,
	reconstruction,
};

// Raw payload provenance is retained even when its UID/owner is missing or its
// custody disagrees. A custody row alone is not a physical payload projection.
// Roles describe the source, not the final existence decision: claimed/history
// blobs must still be correlated with current payloads and custody. Flat row IDs
// are local to (domain, owner_reference, owner_context, source_operation).
struct artifact_payload_projection
{
	artifact_payload_domain domain;
	artifact_payload_role role = artifact_payload_role::stored;
	critical_operation_id source_operation = {};
	uint64_t delivery_ordinal = 0; // capture order within the retained delivery catalog
	uint64_t row_id = 0;
	uint64_t item_uid = 0;
	uint64_t parent_row_id = 0;
	uint64_t parent_item_uid = 0;
	uint64_t payload_root_item_uid = 0; // 0 when the source has not qualified the root
	int64_t owner_reference = 0;
	uint64_t owner_context = 0;
	int32_t vnum = 0;
	uint64_t extra_flags = 0;
	bool extra_flags_present = false;
	uint64_t quantity = 0;
	bool parent_missing = false;
	bool parent_owner_disagrees = false;
	item_owner_identity payload_owner = {};
	bool source_quarantined = false;
	bool custody_required = false;
	bool custody_examined = false; // unqueried is distinct from a confirmed missing row
	bool custody_found = false;
	// Revision zero is valid; a missing authority row remains distinct.
	bool custody_owner_revision_found = false;
	item_ownership_runtime_entry custody = {};
};

// Boot/offline inspection only: no writers may mutate the selected stores while
// these catalog/file readers run. Includes retained auction/collector and
// delivery payloads. Recovery evidence is separate. Output is atomic.
// Ordinary store reads can complete committed authority journals; offline audit
// callers must use a retained store copy if the original must remain untouched.
// Additional recovery rows receive independent custody in the same source cut.
// Flat custody revisions come from the same ownership catalog; no runtime custody is published.
unsigned int artifact_population_read_flat_payloads(
	const std::string &root, std::vector<artifact_payload_projection> *items,
	std::string *error, const std::vector<artifact_payload_projection> *additional = nullptr);

struct redis_world_boot_snapshot;
struct artifact_recovery_mob_projection
{
	int32_t vnum = 0;
	int32_t instance_id = 0;
	int32_t room_vnum = 0;
	int32_t birthplace = 0;
	int32_t shopkeeper_shop_id = -1;
};
struct artifact_recovery_population
{
	std::vector<artifact_payload_projection> items;
	std::vector<artifact_recovery_mob_projection> mobs;
	bool restore_conflict = false;
};
// Read a pinned Redis source cut, without templates, materialization or custody
// lookup. Retain all valid raw graphs, including overlapping projections. Fully
// repeated floor trees are history, matching recovery; partial overlap is retained
// and quarantined, never silently discarded. NPCs require reset/identity mapping.
// Success is source decoding, not complete recovery/population qualification.
// Failure preserves output. Encoded record/aggregate limits apply.
unsigned int artifact_population_read_recovery(const redis_world_boot_snapshot &snapshot,
					       artifact_recovery_population *population);

struct copyover_boot_snapshot;
// Ground trees carry physical UIDs and captured live custody. Historical NPC
// vnums are reconstruction requests with no trustworthy item identity, not
// physical candidates or proof of absence. Admission must qualify them separately.
unsigned int artifact_population_read_copyover(const copyover_boot_snapshot &snapshot,
					       artifact_recovery_population *population);

#ifndef __NO_MYSQL__
#include <mysql/mysql.h>

constexpr size_t ARTIFACT_POPULATION_SQL_PAGE_SIZE = 256;

struct artifact_population_sql_page
{
	std::vector<artifact_payload_projection> rows;
	size_t source_rows = 0; // includes metadata-only collector rows
	uint64_t next_row_id = 0;
	bool complete = false;
};

// Read inside the caller's consistent boot/audit snapshot. Success publishes one
// page atomically; complete applies to this table only, not the whole population.
// Failure leaves *page unchanged and returns a MySQL error or EINVAL/ENOMEM.
unsigned int artifact_population_read_sql_page(MYSQL *connection, artifact_payload_domain domain,
					       uint64_t after_row_id,
					       artifact_population_sql_page *page);
// Blob pages use auction (packed auction_id/slot cursor), auction_legacy,
// auction_pickup, collector and embedded domains. History is retained as history.
unsigned int artifact_population_read_sql_blob_page(MYSQL *connection,
						    artifact_payload_domain domain,
						    uint64_t after_row_id,
						    artifact_population_sql_page *page);

// Dedicated idle autocommit connection only. Owns a read-only repeatable-read
// transaction across every numeric/blob page; commits before publishing output.
// Additional recovery rows receive independent custody inside this transaction.
// This is complete SQL source evidence, not complete recovery/population proof.
unsigned int artifact_population_read_sql_payloads(
	MYSQL *connection, std::vector<artifact_payload_projection> *items,
	const std::vector<artifact_payload_projection> *additional = nullptr);
#endif

#endif
