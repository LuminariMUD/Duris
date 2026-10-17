#ifndef DURIS_ARTIFACT_POPULATION_BOOT_H
#define DURIS_ARTIFACT_POPULATION_BOOT_H

#include "guild/artifact_population_repository.h"

struct artifact_population_boot_snapshot
{
	bool complete = false;
	std::string unavailable_sources; // controlled source names, no payload/account data
	std::vector<artifact_payload_projection> items;
	std::vector<uint64_t> retained_uids; // sorted, unique physical/pending payloads
};

// Once before the boot reap and before any world population. The immutable input
// buffer is not an item authority. A failed source leaves completeness false;
// valid other components remain evidence, never a successful aggregate prefix.
const artifact_population_boot_snapshot &artifact_population_prepare_boot(bool native_copyover);
const artifact_population_boot_snapshot &artifact_population_boot_evidence();
void artifact_population_boot_clear();

#endif
