#include "combat/frag_cap.h"
#include <algorithm>
#include <array>
#include <limits>
#include <openssl/crypto.h>
#include <openssl/sha.h>

namespace
{
constexpr std::array<uint8_t, 8> magic = { 'D', 'U', 'R', 'C', 'A', 'P', '0', '2' };
constexpr int64_t maximum_duration = 3650 * 24 * FRAG_CAP_HOUR;
bool valid_time(int64_t value)
{
	return value > 0 && value <= INT64_MAX - maximum_duration;
}
bool valid_policy(const frag_cap_policy &policy)
{
	return policy.round_duration > 0 && policy.round_duration <= maximum_duration;
}
bool circle(int level)
{
	return (level - 1) % 5 == 0;
}
void start_round(frag_cap_state &state, int64_t at, const frag_cap_policy &policy)
{
	state.round_start = at;
	state.earned = {};
	state.deadline = state.level == FRAG_CAP_MAXIMUM_LEVEL ? 0 : at + policy.round_duration;
}
bool settle(frag_cap_state &state, int64_t now, const frag_cap_policy &policy)
{
	while (state.level < FRAG_CAP_MAXIMUM_LEVEL && now >= state.deadline)
	{
		const int64_t at = state.deadline;
		if (!valid_time(at))
			return false;
		++state.level;
		if (circle(state.level))
			state.advantage = frag_cap_side::none;
		else if (state.earned[0] > state.earned[1])
			state.advantage = frag_cap_side::good;
		else if (state.earned[1] > state.earned[0])
			state.advantage = frag_cap_side::evil;
		// A tie retains the existing advantage: both old caps rise by one.
		start_round(state, at, policy);
	}
	return true;
}
bool finish(frag_cap_state *state, frag_cap_state next)
{
	if (next == *state)
		return true;
	if (next.revision == UINT64_MAX)
		return false;
	++next.revision;
	if (!frag_cap_state_valid(next))
		return false;
	*state = next;
	return true;
}
template <typename T> void append(std::vector<uint8_t> &bytes, T value)
{
	for (size_t index = 0; index < sizeof(T); ++index)
		bytes.push_back(static_cast<uint8_t>(static_cast<uint64_t>(value) >> (index * 8)));
}

template <typename T> bool read(const std::vector<uint8_t> &bytes, size_t &offset, T &value)
{
	if (offset > bytes.size() || sizeof(T) > bytes.size() - offset)
		return false;
	uint64_t decoded = 0;
	for (size_t index = 0; index < sizeof(T); ++index)
		decoded |= static_cast<uint64_t>(bytes[offset++]) << (index * 8);
	value = static_cast<T>(decoded);
	return true;
}
}

bool frag_cap_state_valid(const frag_cap_state &state)
{
	if (!state.revision || state.level < FRAG_CAP_INITIAL_LEVEL ||
	    state.level > FRAG_CAP_MAXIMUM_LEVEL || state.advantage > frag_cap_side::evil ||
	    !valid_time(state.credit_cutoff) || !valid_time(state.round_start) ||
	    state.round_start < state.credit_cutoff ||
	    (circle(state.level) && state.advantage != frag_cap_side::none))
		return false;
	if (state.level == FRAG_CAP_MAXIMUM_LEVEL)
		return !state.deadline && state.earned == std::array<uint64_t, 2>{};
	return valid_time(state.deadline) && state.deadline > state.round_start &&
	       state.deadline - state.round_start <= maximum_duration;
}
int frag_cap_for_side(const frag_cap_state &state, frag_cap_side side)
{
	return state.level - (state.advantage != frag_cap_side::none && state.advantage != side);
}
int64_t frag_cap_due_at(const frag_cap_state &state)
{
	return state.deadline;
}

bool frag_cap_adopt(frag_cap_state *state, int legacy_level, int64_t legacy_deadline, int64_t now,
		    const frag_cap_policy &policy)
{
	if (!state || !valid_time(now) || !valid_policy(policy) || legacy_level < 1 ||
	    legacy_level > FRAG_CAP_MAXIMUM_LEVEL || legacy_deadline < 0 ||
	    (legacy_deadline && !valid_time(legacy_deadline)))
		return false;
	frag_cap_state next;
	next.level = std::max(FRAG_CAP_INITIAL_LEVEL, legacy_level);
	next.credit_cutoff = now;
	start_round(next, now, policy);
	if (legacy_level >= FRAG_CAP_INITIAL_LEVEL && next.level < FRAG_CAP_MAXIMUM_LEVEL &&
	    legacy_deadline)
	{
		if (legacy_deadline <= now)
		{
			++next.level;
			start_round(next, now, policy);
		}
		else
			next.deadline = std::min(next.deadline, legacy_deadline);
	}
	if (!frag_cap_state_valid(next))
		return false;
	*state = next;
	return true;
}
bool frag_cap_settle(frag_cap_state *state, int64_t now, const frag_cap_policy &policy)
{
	if (!state || !frag_cap_state_valid(*state) || !valid_time(now) ||
	    now < state->round_start || !valid_policy(policy))
		return false;
	auto next = *state;
	return settle(next, now, policy) && finish(state, next);
}
bool frag_cap_apply(frag_cap_state *state, int64_t admitted_at, int64_t now,
		    const frag_cap_award *awards, size_t count, const frag_cap_policy &policy)
{
	if (!state || !frag_cap_state_valid(*state) || !valid_time(now) ||
	    now < state->round_start || !valid_policy(policy) || (count && !awards))
		return false;
	auto next = *state;
	if (!settle(next, now, policy))
		return false;
	if (next.level < FRAG_CAP_MAXIMUM_LEVEL && admitted_at >= next.credit_cutoff &&
	    admitted_at >= next.round_start && admitted_at <= now)
		for (size_t index = 0; index < count; ++index)
		{
			const auto &award = awards[index];
			if (award.points <= 0 || award.side == frag_cap_side::none)
				continue;
			if (award.side > frag_cap_side::evil)
				return false;
			auto &total = next.earned[award.side == frag_cap_side::good ? 0 : 1];
			if (static_cast<uint64_t>(award.points) > UINT64_MAX - total)
				return false;
			total += static_cast<uint64_t>(award.points);
		}
	return finish(state, next);
}
bool frag_cap_state_encode(const frag_cap_state &state, std::vector<uint8_t> *bytes)
{
	if (!bytes || !frag_cap_state_valid(state))
		return false;
	std::vector<uint8_t> encoded(magic.begin(), magic.end());
	append(encoded, UINT32_C(2));
	append(encoded, state.revision);
	append(encoded, state.level);
	append(encoded, static_cast<uint8_t>(state.advantage));
	append(encoded, state.credit_cutoff);
	append(encoded, state.round_start);
	append(encoded, state.deadline);
	for (auto score : state.earned)
		append(encoded, score);
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest;
	SHA256(encoded.data(), encoded.size(), digest.data());
	encoded.insert(encoded.end(), digest.begin(), digest.end());
	*bytes = std::move(encoded);
	return true;
}
bool frag_cap_state_decode(const std::vector<uint8_t> &bytes, frag_cap_state *state)
{
	if (!state || bytes.size() != FRAG_CAP_MAX_BYTES ||
	    !std::equal(magic.begin(), magic.end(), bytes.begin()))
		return false;
	const size_t size = bytes.size() - SHA256_DIGEST_LENGTH;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest;
	SHA256(bytes.data(), size, digest.data());
	if (CRYPTO_memcmp(digest.data(), bytes.data() + size, digest.size()))
		return false;
	size_t offset = magic.size();
	uint32_t version = 0;
	uint8_t side = 0;
	frag_cap_state decoded;
	if (!read(bytes, offset, version) || version != 2 ||
	    !read(bytes, offset, decoded.revision) || !read(bytes, offset, decoded.level) ||
	    !read(bytes, offset, side) || !read(bytes, offset, decoded.credit_cutoff) ||
	    !read(bytes, offset, decoded.round_start) || !read(bytes, offset, decoded.deadline))
		return false;
	decoded.advantage = static_cast<frag_cap_side>(side);
	for (auto &score : decoded.earned)
		if (!read(bytes, offset, score))
			return false;
	if (offset != size || !frag_cap_state_valid(decoded))
		return false;
	*state = decoded;
	return true;
}
