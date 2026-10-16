#ifndef ARTIFACT_IDENTITY_H
#define ARTIFACT_IDENTITY_H

#include <cstdint>
#include <cstddef>

constexpr size_t ARTIFACT_IDENTITY_MAX_RECORDS = 1048576;

// Stored in artifact_domain_state and the flat-file artifact catalog. Never renumber.
enum class artifact_identity_state : uint8_t
{
	unresolved = 0,
	present = 1,
	retired = 2,
	absent = 3,
};

constexpr bool artifact_identity_valid(uint64_t uid, artifact_identity_state state)
{
	return state <= artifact_identity_state::absent &&
	       ((state == artifact_identity_state::present ||
		 state == artifact_identity_state::retired) == (uid != 0));
}

#endif
