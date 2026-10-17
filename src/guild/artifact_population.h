#ifndef DURIS_ARTIFACT_POPULATION_H
#define DURIS_ARTIFACT_POPULATION_H

#include "guild/artifact_identity.h"
#include "guild/artifact_population_repository.h"

struct artifact_population_template
{
	int32_t vnum = 0;
	uint64_t extra_flags = 0;
};

struct artifact_population_identity
{
	int32_t vnum = 0;
	uint64_t canonical_item_uid = 0;
	artifact_identity_state state = artifact_identity_state::unresolved;
};

enum class artifact_population_reason : uint8_t
{
	complete,
	incomplete,
	unqualified_payload,
	conflicting_identities,
	retired_payload,
};

struct artifact_population_decision
{
	artifact_population_identity identity;
	artifact_population_reason reason = artifact_population_reason::incomplete;
	// Same-UID hydration must match one of these exact source projections, not
	// just the UID. Indices refer to the input vector; no physical object exists.
	std::vector<size_t> canonical_payloads;
};

// Pure boot/audit classifier. Inputs include ordinary ancestors and the complete
// prototype catalog. complete is the caller's combined-source qualification,
// never inferred from a successful page/decoder or an empty input. The caller
// must reconcile the selected warm handoff's captured authority with durable
// custody before calling. Failed input/allocation preserves *decisions.
unsigned int
artifact_population_classify(const std::vector<artifact_payload_projection> &items,
			     const std::vector<artifact_population_template> &prototypes,
			     const std::vector<artifact_population_identity> &previous,
			     bool complete, std::vector<artifact_population_decision> *decisions);

// Boot only. Publishes into the existing artifact rows, preserving legacy
// tracking, timers and souls. Persistence uses their existing dirty captures.
// This does not itself collect sources or enable creation/materialization.
bool artifacts_stage_population(const std::vector<artifact_payload_projection> &items,
				const std::vector<artifact_population_template> &prototypes,
				bool complete);

#endif
