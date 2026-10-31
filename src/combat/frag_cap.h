#ifndef DURIS_FRAG_CAP_H
#define DURIS_FRAG_CAP_H

#include <cstddef>
#include <cstdint>
#include <map>
#include <vector>

constexpr int FRAG_CAP_INITIAL_LEVEL = 31;
constexpr int FRAG_CAP_MAXIMUM_LEVEL = 56;
constexpr int64_t FRAG_CAP_HOUR = INT64_C(3600000000);
// One entry per contributing character, never a truncated or evicted balance.
constexpr size_t FRAG_CAP_MAX_CONTRIBUTORS = 65536;
constexpr size_t FRAG_CAP_MAX_BYTES = 102 + 6 * FRAG_CAP_MAX_CONTRIBUTORS;

struct frag_cap_policy
{
	int64_t earliest_after = 48 * FRAG_CAP_HOUR;
	int64_t automatic_after = 72 * FRAG_CAP_HOUR;
	uint16_t target_points = 20;
};

// All timestamps are Unix microseconds, matching critical_command.accepted_at_usec.
// Only the active round's policy is saved; changed settings affect later rounds.
struct frag_cap_state
{
	uint64_t revision = 1;
	int32_t level = FRAG_CAP_INITIAL_LEVEL;
	int64_t credit_cutoff = 0;
	int64_t round_start = 0;
	int64_t earliest_at = 0;
	int64_t automatic_at = 0;
	int64_t qualified_at = 0;
	uint16_t target_points = 20;
	std::map<uint32_t, uint16_t> earned;
	bool operator==(const frag_cap_state &) const = default;
};

struct frag_cap_award
{
	uint32_t pid;
	int64_t points;
};

bool frag_cap_state_valid(const frag_cap_state &state);
int64_t frag_cap_due_at(const frag_cap_state &state);
// Adopt the highest legacy effective normal cap and its next unlock. Zero means
// no valid legacy deadline. An expired deadline opens exactly one level at cutover.
bool frag_cap_adopt(frag_cap_state *state, int legacy_level, int64_t legacy_deadline, int64_t now,
		    const frag_cap_policy &policy = {});
// These are atomic in-memory preparations: false leaves the input unchanged.
// The repository must persist the resulting snapshot before publishing it.
bool frag_cap_settle(frag_cap_state *state, int64_t now, const frag_cap_policy &policy = {});
// The parent combat receipt supplies deduplication. Pass the entire ordinary PvP
// event once, after its receipt check, inside the same durable transaction.
bool frag_cap_apply(frag_cap_state *state, int64_t admitted_at, int64_t now,
		    const frag_cap_award *awards, size_t count, const frag_cap_policy &policy = {});
bool frag_cap_state_encode(const frag_cap_state &state, std::vector<uint8_t> *bytes);
bool frag_cap_state_decode(const std::vector<uint8_t> &bytes, frag_cap_state *state);

#endif
