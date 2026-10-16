#ifndef ARTIFACT_IDENTITY_H
#define ARTIFACT_IDENTITY_H

#include <cstdint>

// Stored in artifact_domain_state and the flat-file artifact catalog. Never renumber.
enum class artifact_identity_state : uint8_t
{
	unresolved = 0,
	present = 1,
	retired = 2,
	absent = 3,
};

#endif
