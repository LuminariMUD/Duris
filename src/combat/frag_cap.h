#ifndef DURIS_FRAG_CAP_H
#define DURIS_FRAG_CAP_H

#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

constexpr int FRAG_CAP_INITIAL_LEVEL = 31;
constexpr int FRAG_CAP_MAXIMUM_LEVEL = 56;
constexpr int64_t FRAG_CAP_HOUR = INT64_C(3600000000);
constexpr size_t FRAG_CAP_MAX_BYTES = 97;

enum class frag_cap_side : uint8_t
{
	none,
	good,
	evil
};
struct frag_cap_policy
{
	int64_t round_duration = 72 * FRAG_CAP_HOUR;
};

// Unix microseconds, matching critical_command.accepted_at_usec. The current
// deadline is authoritative; changed settings apply only to the next round.
struct frag_cap_state
{
	uint64_t revision = 1;
	int32_t level = FRAG_CAP_INITIAL_LEVEL;
	frag_cap_side advantage = frag_cap_side::none;
	int64_t credit_cutoff = 0;
	int64_t round_start = 0;
	int64_t deadline = 0;
	std::array<uint64_t, 2> earned = {};
	bool operator==(const frag_cap_state &) const = default;
};
struct frag_cap_award
{
	frag_cap_side side;
	int64_t points;
};

bool frag_cap_state_valid(const frag_cap_state &state);
int frag_cap_for_side(const frag_cap_state &state, frag_cap_side side);
int64_t frag_cap_due_at(const frag_cap_state &state);
// One-time adoption preserves the highest old effective cap, with equal caps
// and zero scores. An expired legacy deadline grants exactly one tied result.
bool frag_cap_adopt(frag_cap_state *state, int legacy_level, int64_t legacy_deadline, int64_t now,
		    const frag_cap_policy &policy = {});
// Atomic preparations: false preserves the input. Persist before publication.
bool frag_cap_settle(frag_cap_state *state, int64_t now, const frag_cap_policy &policy = {});
// The parent combat receipt supplies deduplication. Pass the whole event once,
// after its receipt check, inside the same durable transaction.
bool frag_cap_apply(frag_cap_state *state, int64_t admitted_at, int64_t now,
		    const frag_cap_award *awards, size_t count, const frag_cap_policy &policy = {});
bool frag_cap_state_encode(const frag_cap_state &state, std::vector<uint8_t> *bytes);
bool frag_cap_state_decode(const std::vector<uint8_t> &bytes, frag_cap_state *state);
#endif
